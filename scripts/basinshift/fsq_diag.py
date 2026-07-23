#!/usr/bin/env python3
"""6.3 advisor-directed diagnostic round (GATE NOT APPROVED). CPU only.

Pre-registered in docs/decisions/6p3_gate_ruling_e1029b20.md (committed BEFORE this compute).

Two metrics, per curve, degradation = (arm_RMSE - raw_reference_RMSE) / raw_reference_RMSE, physical:
  LITERAL  : imputer trained on RAW src_train; scored on eval with FEATURE curves reconstructed.
  MATCHED  : imputer RETRAINED on RECONSTRUCTED src_train (features recon, target raw); scored on
             eval with FEATURE curves reconstructed. Both vs the same raw_reference_RMSE.
raw_reference: imputer trained on RAW src_train, scored on RAW eval features (shared denominator).

Cross-basin transfer directions (holdouts reserved, blind_force never loaded; FORCE has no dev):
  KGS_to_NLOG : src_train = kgs_train (Kansas), eval = nlog_dev (Norway)  [decisive honesty test]
  NLOG_to_KGS : src_train = nlog_train (Norway), eval = kgs_dev (Kansas)  [symmetry]

Configs: cb4375 [7,5,5,5,5] patch 32; cb15360 [8,8,8,6,5] patch 32; cb15360 [8,8,8,6,5] patch 16.
One global tokenizer per config (trained on all TRAIN pools, 30 epochs), same as Phase B; only the
IMPUTER is basin-specific for the transfer test. Symmetry guard reported on DTC/RHOB/NPHI. Also:
PEF baseline + per-basin distribution (Step 3). REPORTS facts; does NOT rule, seal, or carve out.
"""
import json, time, sys
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
import eval_harness as EH
import fsq_tokenizer as FT
import r8_acceptance as R8

OUT = EH.ROOT / "reports/basinshift"
DIAG = OUT / "fsq_diag"; DIAG.mkdir(exist_ok=True)
RES = DIAG / "results"; RES.mkdir(exist_ok=True)

EPOCHS = 30
HEADLINE = ["DTC", "RHOB", "NPHI"]
A40_RATE = 0.44
MAX_WALL_S = 4 * 3600
GUARD_S = int(MAX_WALL_S * 0.92)

# Global-dev LITERAL arm (Phase B setup: global imputer, global dev) = the strict floor that
# defines outcome-tree branch 1 and cross-checks Phase B at patch 32.
GLOBAL_TRAIN_KEYS = ["kgs_train", "nlog_train", "force_train"]

DIRECTIONS = [  # (name, src_train POOLS-key, (eval_source, "dev"))
    ("KGS_to_NLOG", "kgs_train", ("nlog", "dev")),
    ("NLOG_to_KGS", "nlog_train", ("kgs", "dev")),
]
CONFIGS = [  # (name, levels, patch)  grouped by patch (p32 first so banks are reused)
    ("cb4375_p32",  (7, 5, 5, 5, 5), 32),
    ("cb15360_p32", (8, 8, 8, 6, 5), 32),
    ("cb15360_p16", (8, 8, 8, 6, 5), 16),
]

_LINES = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); _LINES.append(s)
    (DIAG / "diag_log.txt").write_text("\n".join(_LINES) + "\n")


def compute_stats_all():
    stats = {}
    for c in EH.CANON:
        arrs = R8.curve_arrays_train(c)
        stats[c] = FT.compute_stats(arrs)
    return stats


def build_banks(patch):
    banks = {}
    for c in EH.CANON:
        arrs = R8.curve_arrays_train(c)
        m, s = FT.compute_stats(arrs)
        banks[c] = FT.build_patch_bank(arrs, m, s, patch=patch, cap=None)
    return banks


def train_toks(banks, stats, levels, patch):
    toks = {}
    for c in EH.CANON:
        model = FT.train_tokenizer(banks[c], levels, epochs=EPOCHS, patch=patch, log=None)
        toks[c] = (model, stats[c][0], stats[c][1])
    return toks


def reconstruct_pool(wells, toks, patch):
    recon = {}
    for (src, safe, wid) in wells:
        df = EH.load_well(src, safe, wid)
        rc = {}
        for c, (model, mean, std) in toks.items():
            rc[c] = FT.reconstruct_curve(df[c].to_numpy(), model, mean, std, patch=patch)
        recon[(src, safe)] = rc
    return recon


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


def build_train_pool(wells, target, recon_map=None, cap=EH.TRAIN_CAP, seed=EH.SEED):
    feats = EH.feats_for(target)
    Xs, ys = [], []
    for (src, safe, wid) in wells:
        df = EH.load_well(src, safe, wid)
        y = df[target].to_numpy(); v = ~np.isnan(y)
        if v.sum() == 0:
            continue
        if recon_map is None:
            X = df[feats].to_numpy()[v]
        else:
            rc = recon_map[(src, safe)]
            cols = [(df[f].to_numpy() if f == "depth_m" else rc[f]) for f in feats]
            X = np.column_stack(cols)[v]
        Xs.append(X); ys.append(y[v])
    if not Xs:
        return None, None                      # no training rows for this target in this pool
    X = np.vstack(Xs); y = np.concatenate(ys)
    if len(y) > cap:
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(y), cap, replace=False); X, y = X[idx], y[idx]
    return X, y


def predict_grid(target, imputer, grid5, recon_map=None):
    feats = EH.feats_for(target)
    preds = {}
    for (wid, valid, _y, src, safe) in grid5:
        df = EH.load_well(src, safe, wid)
        if recon_map is None:
            X = df[feats].to_numpy()[valid]
        else:
            rc = recon_map[(src, safe)]
            cols = [(df[f].to_numpy() if f == "depth_m" else rc[f]) for f in feats]
            X = np.column_stack(cols)[valid]
        preds[wid] = EH.inverse_transform(target, imputer.predict(X))
    return preds


def score3(grid5, preds, target):
    grid3 = [(w, v, y) for (w, v, y, s, sf) in grid5]
    return EH.score(grid3, preds, target)


def pef_per_basin():
    out = {}
    for basin, key in [("KGS", "kgs_train"), ("NLOG", "nlog_train"), ("FORCE", "force_train")]:
        vals = []
        for (src, safe, wid) in EH.POOLS[key]:
            df = EH.load_well(src, safe, wid)
            v = df["PEF"].to_numpy(); v = v[np.isfinite(v)]
            if len(v):
                vals.append(v)
        if vals:
            a = np.concatenate(vals)
            out[basin] = dict(n_samples=int(len(a)), n_wells=len(vals),
                              min=float(a.min()), p01=float(np.percentile(a, 1)),
                              median=float(np.median(a)), mean=float(a.mean()),
                              p99=float(np.percentile(a, 99)), max=float(a.max()),
                              std=float(a.std()),
                              frac_in_1p5_6=float(np.mean((a >= 1.5) & (a <= 6.0))),
                              frac_negative=float(np.mean(a < 0)),
                              frac_gt10=float(np.mean(a > 10)))
        else:
            out[basin] = dict(n_samples=0, n_wells=0)
    return out


def precompute_global(stats):
    """Global-dev LITERAL arm (Phase B setup): one global imputer per curve (raw, trained on
    kgs+nlog+force), its raw global-dev RMSE (should ~reproduce Phase B within 1M-subsample noise),
    and the global-dev grid. Config-independent."""
    gtrain = [w for k in GLOBAL_TRAIN_KEYS for w in EH.POOLS[k]]
    gdev = EH.wells_of("kgs", "dev") + EH.wells_of("nlog", "dev")
    g_imp, g_raw = {}, {}
    for C in EH.CANON:
        g5 = grid_pool(gdev, C)
        if not g5:
            g_imp[C] = None
            g_raw[C] = dict(raw_rmse=None, n_samples=0, n_wells=0, degenerate=True,
                            cause="empty global-dev grid", grid5=[])
            log(f"  [glob {C}] DEGENERATE empty global-dev grid")
            continue
        Xtr, ytr = build_train_pool(gtrain, C, recon_map=None)
        if Xtr is None:
            g_imp[C] = None
            g_raw[C] = dict(raw_rmse=None, n_samples=len(g5) and sum(len(v) for _, v, _, _, _ in g5),
                            n_wells=len(g5), degenerate=True,
                            cause="no training rows for target in global train", grid5=g5)
            log(f"  [glob {C}] DEGENERATE no training rows")
            continue
        m = XGBRegressor(**EH.XGB); m.fit(Xtr, ytr)
        preds = predict_grid(C, m, g5, recon_map=None)
        sc = score3(g5, preds, C)
        rr = sc["pooled_rmse"]
        degen = (rr is None) or (not np.isfinite(rr)) or (rr < 1e-6)
        g_imp[C] = m
        g_raw[C] = dict(raw_rmse=rr, n_samples=sc["n_samples"], n_wells=sc["n_wells"],
                        degenerate=bool(degen), cause=("raw near-zero/non-finite" if degen else None),
                        grid5=g5)
        log(f"  [glob {C}] global-dev raw_RMSE={rr:.6g} n={sc['n_samples']} wells={sc['n_wells']}"
            + ("  DEGENERATE" if degen else ""))
    return g_imp, g_raw


def precompute_raw(stats):
    """Per (direction, curve): raw imputer, raw_cross grid + RMSE (config-independent)."""
    raw_imp, raw_cross = {}, {}
    for (dname, src_key, tgt_spec) in DIRECTIONS:
        src_wells = EH.POOLS[src_key]
        tgt_wells = EH.wells_of(*tgt_spec)
        for C in EH.CANON:
            g5 = grid_pool(tgt_wells, C)
            if not g5:
                raw_cross[(dname, C)] = dict(raw_rmse=None, n_samples=0, n_wells=0,
                                             degenerate=True, cause="empty cross-basin eval grid", grid5=[])
                raw_imp[(dname, C)] = None
                log(f"  [raw {dname}/{C}] DEGENERATE empty eval grid")
                continue
            Xtr, ytr = build_train_pool(src_wells, C, recon_map=None)
            if Xtr is None:
                raw_cross[(dname, C)] = dict(raw_rmse=None, n_samples=0, n_wells=len(g5),
                                             degenerate=True,
                                             cause="no training rows for target in source-basin train",
                                             grid5=g5)
                raw_imp[(dname, C)] = None
                log(f"  [raw {dname}/{C}] DEGENERATE no source-basin training rows")
                continue
            m = XGBRegressor(**EH.XGB); m.fit(Xtr, ytr)
            preds = predict_grid(C, m, g5, recon_map=None)
            sc = score3(g5, preds, C)
            rr = sc["pooled_rmse"]
            degen = (rr is None) or (not np.isfinite(rr)) or (rr < 1e-6)
            raw_imp[(dname, C)] = m
            raw_cross[(dname, C)] = dict(raw_rmse=rr, n_samples=sc["n_samples"], n_wells=sc["n_wells"],
                                         degenerate=bool(degen),
                                         cause=("raw_ref near-zero/non-finite" if degen else None), grid5=g5)
            log(f"  [raw {dname}/{C}] raw_ref_RMSE={rr:.6g} n={sc['n_samples']} wells={sc['n_wells']}"
                + ("  DEGENERATE" if degen else ""))
    return raw_imp, raw_cross


def run_config(cfg_name, levels, patch, banks, stats, raw_imp, raw_cross, g_imp, g_raw):
    t0 = time.time()
    toks = train_toks(banks, stats, levels, patch)
    log(f"  [{cfg_name}] tokenizers trained (patch {patch})")
    # reconstruct every pool used by any direction (all 4 pools distinct; kgs_dev+nlog_dev also
    # serve the global-dev literal arm)
    recon = {}
    for (dname, src_key, tgt_spec) in DIRECTIONS:
        recon.update(reconstruct_pool(EH.POOLS[src_key], toks, patch))
        recon.update(reconstruct_pool(EH.wells_of(*tgt_spec), toks, patch))
    log(f"  [{cfg_name}] reconstructed {len(recon)} wells")

    # ---- global-dev LITERAL (Phase B setup, strict floor; defines branch 1) ----
    global_literal = {}
    for C in EH.CANON:
        gr = g_raw[C]
        if gr["degenerate"] or g_imp[C] is None:
            global_literal[C] = dict(raw_rmse=gr["raw_rmse"], literal_rmse=None, literal_deg=None,
                                     n_samples=gr["n_samples"], n_wells=gr["n_wells"],
                                     degenerate=True, cause=gr["cause"])
            continue
        g5 = gr["grid5"]; rr = gr["raw_rmse"]
        preds = predict_grid(C, g_imp[C], g5, recon_map=recon)
        lit = score3(g5, preds, C)["pooled_rmse"]
        global_literal[C] = dict(raw_rmse=rr, literal_rmse=lit, literal_deg=(lit - rr) / rr,
                                 n_samples=gr["n_samples"], n_wells=gr["n_wells"],
                                 degenerate=False, cause=None)
        log(f"    [{cfg_name}/GLOBAL_DEV/{C}] raw={rr:.5g} literal={lit:.5g} "
            f"deg={(lit-rr)/rr*100:+.2f}%")
    gl_degs = [v["literal_deg"] for v in global_literal.values()
               if not v["degenerate"] and v["literal_deg"] is not None]
    global_literal_summary = dict(
        median=float(np.median(gl_degs)) if gl_degs else None,
        max=float(np.max(gl_degs)) if gl_degs else None, n=len(gl_degs),
        bar_median_le5=(bool(np.median(gl_degs) <= 0.05) if gl_degs else None),
        bar_max_le10=(bool(np.max(gl_degs) <= 0.10) if gl_degs else None),
        max_curve=(max(((c, v["literal_deg"]) for c, v in global_literal.items()
                        if not v["degenerate"] and v["literal_deg"] is not None),
                       key=lambda t: t[1])[0] if gl_degs else None))

    per_dir = {}
    for (dname, src_key, tgt_spec) in DIRECTIONS:
        src_wells = EH.POOLS[src_key]
        pc = {}
        for C in EH.CANON:
            rc = raw_cross[(dname, C)]
            if rc["degenerate"]:
                pc[C] = dict(raw_rmse=rc["raw_rmse"], literal_rmse=None, matched_rmse=None,
                             literal_deg=None, matched_deg=None, n_samples=rc["n_samples"],
                             n_wells=rc["n_wells"], degenerate=True, cause=rc["cause"])
                continue
            g5 = rc["grid5"]; rr = rc["raw_rmse"]
            lit_preds = predict_grid(C, raw_imp[(dname, C)], g5, recon_map=recon)
            lit = score3(g5, lit_preds, C)["pooled_rmse"]
            Xtr, ytr = build_train_pool(src_wells, C, recon_map=recon)
            if Xtr is None:
                mat = None; mat_deg = None
            else:
                mm = XGBRegressor(**EH.XGB); mm.fit(Xtr, ytr)
                mat_preds = predict_grid(C, mm, g5, recon_map=recon)
                mat = score3(g5, mat_preds, C)["pooled_rmse"]
                mat_deg = (mat - rr) / rr
            pc[C] = dict(raw_rmse=rr, literal_rmse=lit, matched_rmse=mat,
                         literal_deg=(lit - rr) / rr, matched_deg=mat_deg,
                         n_samples=rc["n_samples"], n_wells=rc["n_wells"], degenerate=False, cause=None)
            log(f"    [{cfg_name}/{dname}/{C}] raw={rr:.5g} lit={lit:.5g}({(lit-rr)/rr*100:+.2f}%) "
                f"mat={mat:.5g}({(mat-rr)/rr*100:+.2f}%)")
        per_dir[dname] = pc

    # per-direction bar + symmetry summaries
    dir_summ = {}
    for dname, pc in per_dir.items():
        for metric in ["literal_deg", "matched_deg"]:
            degs = [v[metric] for v in pc.values() if not v["degenerate"] and v[metric] is not None]
            key = metric.split("_")[0]
            dir_summ.setdefault(dname, {})[key] = dict(
                median=float(np.median(degs)) if degs else None,
                max=float(np.max(degs)) if degs else None,
                n=len(degs),
                bar_median_le5=(bool(np.median(degs) <= 0.05) if degs else None),
                bar_max_le10=(bool(np.max(degs) <= 0.10) if degs else None))
        # symmetry guard on headline three: matched worse than literal?
        sg = {}
        for C in HEADLINE:
            v = pc[C]
            if v["degenerate"] or v["matched_deg"] is None:
                sg[C] = dict(literal=v["literal_deg"], matched=v["matched_deg"], matched_worse=None)
            else:
                sg[C] = dict(literal=v["literal_deg"], matched=v["matched_deg"],
                             matched_worse=bool(v["matched_deg"] > v["literal_deg"]))
        dir_summ[dname]["symmetry_headline"] = sg
        dir_summ[dname]["symmetry_violated"] = any(
            (sg[C]["matched_worse"] is True) for C in HEADLINE)

    result = dict(name=cfg_name, levels=list(levels), codebook_size=int(np.prod(levels)),
                  patch=patch, epochs=EPOCHS,
                  global_dev_literal=global_literal, global_dev_literal_summary=global_literal_summary,
                  per_direction=per_dir, dir_summary=dir_summ,
                  elapsed_s=round(time.time() - t0, 1))
    (RES / f"{cfg_name}.json").write_text(json.dumps(result, indent=2))
    log(f"  [{cfg_name}] DONE elapsed={result['elapsed_s']}s")
    del recon
    return result


def main():
    t0 = time.time()
    log(f"=== 6.3 diagnostic START configs={[c[0] for c in CONFIGS]} dirs={[d[0] for d in DIRECTIONS]} ===")
    stats = compute_stats_all()
    log("stats computed")

    pef = pef_per_basin()
    (DIAG / "pef_baseline_per_basin.json").write_text(json.dumps(pef, indent=2))
    log(f"PEF per-basin: " + " | ".join(
        f"{b}: median={pef[b].get('median')} range[{pef[b].get('min')},{pef[b].get('max')}] "
        f"in[1.5,6]={pef[b].get('frac_in_1p5_6')}" for b in ["KGS", "NLOG", "FORCE"]))

    g_imp, g_raw = precompute_global(stats)
    gdump = {c: {k: v for k, v in g_raw[c].items() if k != "grid5"} for c in EH.CANON}
    (DIAG / "raw_reference_global_dev.json").write_text(json.dumps(gdump, indent=2))

    raw_imp, raw_cross = precompute_raw(stats)
    # persist raw denominators (strip grids)
    rawdump = {f"{d}|{c}": {k: v for k, v in raw_cross[(d, c)].items() if k != "grid5"}
               for (d, _, _) in DIRECTIONS for c in EH.CANON}
    (DIAG / "raw_reference_cross_basin.json").write_text(json.dumps(rawdump, indent=2))
    log(f"=== precompute done in {time.time()-t0:.0f}s ===")

    done_times = []
    # process grouped by patch so banks are reused within a patch
    from itertools import groupby
    for patch, group in groupby(CONFIGS, key=lambda c: c[2]):
        group = list(group)
        banks = build_banks(patch)
        log(f"=== banks built for patch {patch} ===")
        for i, (cfg_name, levels, p) in enumerate(group):
            rf = RES / f"{cfg_name}.json"
            if rf.exists():
                log(f"SKIP {cfg_name} (result exists)")
                continue
            if done_times:
                avg = sum(done_times) / len(done_times)
                remaining = len(CONFIGS) - sum(1 for c in CONFIGS if (RES / f"{c[0]}.json").exists())
                proj = (time.time() - t0) + avg * remaining
                log(f"[projection] elapsed={time.time()-t0:.0f}s avg={avg:.0f}s proj={proj:.0f}s guard={GUARD_S}s")
                if proj > GUARD_S:
                    log(f"STOP_GATE: projected {proj:.0f}s would exceed money gate; halting before {cfg_name}")
                    banks = None
                    _finish(t0, done_times); return
            r = run_config(cfg_name, levels, p, banks, stats, raw_imp, raw_cross, g_imp, g_raw)
            done_times.append(r["elapsed_s"])
        banks = None
    _finish(t0, done_times)


def _finish(t0, done_times):
    results = []
    for name, _, _ in CONFIGS:
        rf = RES / f"{name}.json"
        if rf.exists():
            results.append(json.loads(rf.read_text()))
    total_s = time.time() - t0
    agg = dict(configs=results, n_configs_done=len(results),
               total_wall_s=round(total_s, 1), est_cost_usd=round(total_s / 3600 * A40_RATE, 2),
               money_gate="UNDER" if total_s <= MAX_WALL_S else "OVER",
               note="Diagnostic facts only. Advisor rules the branch/gate; nothing sealed or carved out.")
    (DIAG / "fsq_diag_summary.json").write_text(json.dumps(agg, indent=2))
    log(f"=== DIAG DONE configs={len(results)}/{len(CONFIGS)} wall={total_s:.0f}s (~${agg['est_cost_usd']}) "
        f"gate={agg['money_gate']} ===")
    log("DIAG_COMPLETE")


if __name__ == "__main__":
    main()
