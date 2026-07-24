#!/usr/bin/env python3
"""D2 item 5 (R5 ruling): seed-repeat noise-floor measurement, cb15360_p16, GLOBAL_DEV LITERAL
arm only (the strict-floor metric; matches Phase B/D1 global_dev_literal exactly). CPU only.

Pre-registered scope (docs/decisions/6p3_gate_ruling_e1029b20.md, Part D.2/D.3):
  - Tokenizer seed and imputer seed varied SEPARATELY (not collapsed) since they are independent
    constants in independent modules (fsq_tokenizer.SEED drives torch.manual_seed + patch-order
    rng; eval_harness.SEED drives XGBoost random_state + train-cap subsample rng).
  - Sweep A (tokenizer-seed): imputer held at canonical seed (retrained ONCE, raw-only, so it does
    not depend on the tokenizer at all); tokenizer retrained per seed (the expensive step).
  - Sweep B (imputer-seed): tokenizer held at canonical seed, REUSING Sweep A's canonical
    reconstruction (no duplicate tokenizer retrain); imputer retrained per seed (cheap, no
    tokenizer touch).
  - Minimum 3 seeds per axis; imputer axis extended to 5 since it is nearly free once one
    tokenizer reconstruction exists. Report mean and full per-curve spread per axis, NOT combined
    (collapsing the two axes into one sample would waste the run per the advisor's ruling).

Money gate identical to fsq_diag.py: <=$5 AND <=4h, A40 $0.44/hr, guard at 92% of 4h, completed
work written incrementally. Frozen splits untouched; blind_force never loaded; GLOBAL_DEV only
(kgs_dev + nlog_dev) -- no cross-basin, no matched arm, no test/open-10 holdouts.
"""
import json, time
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
import eval_harness as EH
import fsq_tokenizer as FT
import r8_acceptance as R8

OUT = EH.ROOT / "reports/basinshift"
DIAG = OUT / "fsq_diag"; DIAG.mkdir(exist_ok=True)
RES = DIAG / "seed_repeat_results"; RES.mkdir(exist_ok=True)

EPOCHS = 30
PATCH = 16
LEVELS = (8, 8, 8, 6, 5)
CFG_NAME = "cb15360_p16"
A40_RATE = 0.44
MAX_WALL_S = 4 * 3600
GUARD_S = int(MAX_WALL_S * 0.92)
HEADLINE = ["DTC", "RHOB", "NPHI"]

CANONICAL_TOK_SEED = FT.SEED   # 20260715 (same value fsq_diag.py used for cb15360_p16)
CANONICAL_IMP_SEED = EH.SEED   # 20260715

TOKENIZER_SEEDS = [CANONICAL_TOK_SEED, 20260815, 20260915]                          # min 3
IMPUTER_SEEDS   = [CANONICAL_IMP_SEED, 20260716, 20260717, 20260718, 20260719]       # 5, cheap

_LINES = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); _LINES.append(s)
    (DIAG / "seed_repeat_log.txt").write_text("\n".join(_LINES) + "\n")

GDEV_WELLS = EH.wells_of("kgs", "dev") + EH.wells_of("nlog", "dev")
GTRAIN_WELLS = [w for k in ["kgs_train", "nlog_train", "force_train"] for w in EH.POOLS[k]]

T0 = time.time()
_DONE_S = []
def guard_check(label):
    if _DONE_S:
        avg = sum(_DONE_S) / len(_DONE_S)
        elapsed = time.time() - T0
        proj = elapsed + avg
        log(f"[projection] elapsed={elapsed:.0f}s last_avg={avg:.0f}s proj_after_next={proj:.0f}s guard={GUARD_S}s")
        if proj > GUARD_S:
            log(f"STOP_GATE: projected {proj:.0f}s would exceed money gate; halting before {label}")
            return False
    return True


def build_banks():
    banks, stats = {}, {}
    for c in EH.CANON:
        arrs = R8.curve_arrays_train(c)
        m, s = FT.compute_stats(arrs)
        stats[c] = (m, s)
        banks[c] = FT.build_patch_bank(arrs, m, s, patch=PATCH, cap=None)
    return banks, stats


def grid_pool(wells, target):
    grid = []
    for (src, safe, wid) in wells:
        df = EH.load_well(src, safe, wid)
        y = df[target].to_numpy()
        valid = np.where(~np.isnan(y))[0]
        if len(valid) < EH.MIN_TARGET_SAMPLES:
            continue
        grid.append((wid, valid, EH.inverse_transform(target, y[valid]), src, safe))
    return grid

GDEV_GRID = {c: grid_pool(GDEV_WELLS, c) for c in EH.CANON}


def score3(grid5, preds, target):
    grid3 = [(w, v, y) for (w, v, y, s, sf) in grid5]
    return EH.score(grid3, preds, target)


def train_toks_seeded(banks, stats, tok_seed):
    toks = {}
    for c in EH.CANON:
        model = FT.train_tokenizer(banks[c], LEVELS, epochs=EPOCHS, patch=PATCH, seed=tok_seed, log=None)
        toks[c] = (model, stats[c][0], stats[c][1])
    return toks


def reconstruct_gdev(toks):
    recon = {}
    for (src, safe, wid) in GDEV_WELLS:
        df = EH.load_well(src, safe, wid)
        rc = {}
        for c, (model, mean, std) in toks.items():
            rc[c] = FT.reconstruct_curve(df[c].to_numpy(), model, mean, std, patch=PATCH)
        recon[(src, safe)] = rc
    return recon


def predict_grid_recon(target, imputer, recon_map):
    feats = EH.feats_for(target)
    g5 = GDEV_GRID[target]
    preds = {}
    for (wid, valid, _y, src, safe) in g5:
        df = EH.load_well(src, safe, wid)
        rc = recon_map[(src, safe)]
        cols = [(df[f].to_numpy() if f == "depth_m" else rc[f]) for f in feats]
        X = np.column_stack(cols)[valid]
        preds[wid] = EH.inverse_transform(target, imputer.predict(X))
    return preds


def predict_grid_raw(target, imputer):
    feats = EH.feats_for(target)
    g5 = GDEV_GRID[target]
    preds = {}
    for (wid, valid, _y, src, safe) in g5:
        df = EH.load_well(src, safe, wid)
        X = df[feats].to_numpy()[valid]
        preds[wid] = EH.inverse_transform(target, imputer.predict(X))
    return preds


def fit_imputer_and_raw(imp_seed):
    """Train one raw global imputer per curve (kgs+nlog+force train), score raw_rmse on
    GLOBAL_DEV. Config-independent (no tokenizer involved) -- cacheable per imp_seed."""
    out = {}
    for c in EH.CANON:
        g5 = GDEV_GRID[c]
        feats = EH.feats_for(c)
        Xs, ys = [], []
        for (src, safe, wid) in GTRAIN_WELLS:
            df = EH.load_well(src, safe, wid)
            y = df[c].to_numpy(); v = ~np.isnan(y)
            if v.sum() == 0:
                continue
            Xs.append(df[feats].to_numpy()[v]); ys.append(y[v])
        if not Xs or not g5:
            out[c] = dict(model=None, raw_rmse=None)
            continue
        X = np.vstack(Xs); y = np.concatenate(ys)
        if len(y) > EH.TRAIN_CAP:
            rng = np.random.default_rng(imp_seed)
            idx = rng.choice(len(y), EH.TRAIN_CAP, replace=False); X, y = X[idx], y[idx]
        xgb_params = dict(EH.XGB); xgb_params["random_state"] = imp_seed
        m = XGBRegressor(**xgb_params); m.fit(X, y)
        preds = predict_grid_raw(c, m)
        rr = score3(g5, preds, c)["pooled_rmse"]
        out[c] = dict(model=m, raw_rmse=rr)
    return out


def score_literal(recon_map, imp_and_raw):
    result = {}
    for c in EH.CANON:
        entry = imp_and_raw[c]
        if entry["model"] is None or entry["raw_rmse"] is None:
            result[c] = dict(raw_rmse=None, literal_rmse=None, literal_deg=None, degenerate=True)
            continue
        preds = predict_grid_recon(c, entry["model"], recon_map)
        lit = score3(GDEV_GRID[c], preds, c)["pooled_rmse"]
        rr = entry["raw_rmse"]
        result[c] = dict(raw_rmse=rr, literal_rmse=lit, literal_deg=(lit - rr) / rr, degenerate=False)
    return result


def summarize_axis(per_seed_results, seeds):
    """per_seed_results: {seed: {curve: {..., literal_deg}}}. Returns per-curve mean/spread."""
    out = {}
    for c in EH.CANON:
        degs = [per_seed_results[s][c]["literal_deg"] for s in seeds
                 if per_seed_results[s][c]["literal_deg"] is not None]
        if not degs:
            out[c] = None
            continue
        out[c] = dict(seeds=seeds, values=degs, mean=float(np.mean(degs)),
                       min=float(np.min(degs)), max=float(np.max(degs)),
                       spread=float(np.max(degs) - np.min(degs)), n=len(degs))
    return out


def main():
    log(f"=== D2 item 5 seed-repeat START cfg={CFG_NAME} patch={PATCH} levels={LEVELS} "
        f"tok_seeds={TOKENIZER_SEEDS} imp_seeds={IMPUTER_SEEDS} ===")
    banks, stats = build_banks()
    log("banks built")

    # ---- canonical imputer/raw, computed once, reused by BOTH sweeps ----
    t0 = time.time()
    imp_raw_by_seed = {}
    imp_raw_by_seed[CANONICAL_IMP_SEED] = fit_imputer_and_raw(CANONICAL_IMP_SEED)
    dt = time.time() - t0
    _DONE_S.append(dt)
    log(f"[imputer canonical seed={CANONICAL_IMP_SEED}] fit in {dt:.1f}s")

    # ---- Sweep A: tokenizer-seed axis, imputer held at canonical ----
    tokA_results = {}
    recon_by_tokseed = {}
    for tok_seed in TOKENIZER_SEEDS:
        rf = RES / f"tokA_seed{tok_seed}.json"
        if rf.exists():
            tokA_results[tok_seed] = json.loads(rf.read_text())
            log(f"SKIP tokA seed={tok_seed} (result exists)")
            continue
        if not guard_check(f"tokA seed={tok_seed}"):
            break
        t0 = time.time()
        toks = train_toks_seeded(banks, stats, tok_seed)
        recon = reconstruct_gdev(toks)
        if tok_seed == CANONICAL_TOK_SEED:
            recon_by_tokseed[tok_seed] = recon   # kept for Sweep B reuse
        res = score_literal(recon, imp_raw_by_seed[CANONICAL_IMP_SEED])
        dt = time.time() - t0
        _DONE_S.append(dt)
        tokA_results[tok_seed] = res
        (RES / f"tokA_seed{tok_seed}.json").write_text(json.dumps(res, indent=2))
        pef_deg = res["PEF"]["literal_deg"]
        pef_str = f"{pef_deg*100:.2f}%" if pef_deg is not None else "degenerate"
        log(f"[tokA seed={tok_seed}] done in {dt:.1f}s  PEF_deg={pef_str}")
        del toks
        if tok_seed != CANONICAL_TOK_SEED:
            del recon

    # ---- Sweep B: imputer-seed axis, tokenizer held at canonical (reuse recon) ----
    impB_results = {}
    canonical_recon = recon_by_tokseed.get(CANONICAL_TOK_SEED)
    if canonical_recon is None:
        # canonical tokA result already existed on disk from a prior partial run; need the
        # reconstruction to score new imputer seeds, so rebuild it once (cheap relative to a
        # fresh tokenizer retrain avoided -- this IS a tokenizer retrain, but only if resuming).
        log("[sweepB] canonical reconstruction not in memory (resumed run) -- rebuilding once")
        if guard_check("rebuild canonical recon for sweepB"):
            t0 = time.time()
            toks = train_toks_seeded(banks, stats, CANONICAL_TOK_SEED)
            canonical_recon = reconstruct_gdev(toks)
            dt = time.time() - t0
            _DONE_S.append(dt)
            log(f"[sweepB canonical recon rebuild] done in {dt:.1f}s")
            del toks

    if canonical_recon is not None:
        for imp_seed in IMPUTER_SEEDS:
            rf = RES / f"impB_seed{imp_seed}.json"
            if rf.exists():
                impB_results[imp_seed] = json.loads(rf.read_text())
                log(f"SKIP impB seed={imp_seed} (result exists)")
                continue
            if not guard_check(f"impB seed={imp_seed}"):
                break
            t0 = time.time()
            if imp_seed in imp_raw_by_seed:
                iar = imp_raw_by_seed[imp_seed]
            else:
                iar = fit_imputer_and_raw(imp_seed)
                imp_raw_by_seed[imp_seed] = iar
            res = score_literal(canonical_recon, iar)
            dt = time.time() - t0
            _DONE_S.append(dt)
            impB_results[imp_seed] = res
            (RES / f"impB_seed{imp_seed}.json").write_text(json.dumps(res, indent=2))
            log(f"[impB seed={imp_seed}] done in {dt:.1f}s")

    # ---- summaries ----
    tok_seeds_done = sorted(tokA_results.keys())
    imp_seeds_done = sorted(impB_results.keys())
    summary = dict(
        config=CFG_NAME, patch=PATCH, levels=list(LEVELS), epochs=EPOCHS,
        canonical_tok_seed=CANONICAL_TOK_SEED, canonical_imp_seed=CANONICAL_IMP_SEED,
        tokenizer_seed_axis=dict(seeds_planned=TOKENIZER_SEEDS, seeds_done=tok_seeds_done,
                                  per_curve=summarize_axis(tokA_results, tok_seeds_done)),
        imputer_seed_axis=dict(seeds_planned=IMPUTER_SEEDS, seeds_done=imp_seeds_done,
                                per_curve=summarize_axis(impB_results, imp_seeds_done)),
        headline_curves=HEADLINE,
        total_wall_s=round(time.time() - T0, 1),
        est_cost_usd=round((time.time() - T0) / 3600 * A40_RATE, 2),
        money_gate="UNDER" if (time.time() - T0) <= MAX_WALL_S else "OVER",
        note="D2 item 5 facts only. Advisor rules the N/threshold consequence per D.2/D.3; nothing sealed.",
    )
    (DIAG / "seed_repeat_summary.json").write_text(json.dumps(summary, indent=2))
    log(f"=== SEED_REPEAT DONE tok_seeds={len(tok_seeds_done)}/{len(TOKENIZER_SEEDS)} "
        f"imp_seeds={len(imp_seeds_done)}/{len(IMPUTER_SEEDS)} wall={summary['total_wall_s']:.0f}s "
        f"(~${summary['est_cost_usd']}) gate={summary['money_gate']} ===")
    log("SEED_REPEAT_COMPLETE")


if __name__ == "__main__":
    main()
