#!/usr/bin/env python3
"""6.3 Phase B FSQ tokenizer sweep (LOCKED pre-registration). CPU only, resumable, polled.

LOCKED (do not deviate):
  patch 32; grid by level vector, TRUE codebook = product(levels):
    [8,6,5]=240, [8,5,5,5]=1000, [7,5,5,5,5]=4375, [8,8,8,6,5]=15360
  plus <=2 pre-declared smaller floor-probe configs (declared here): [8,8]=64, [5,5,5]=125.
  Standardization: TRAIN-global per-curve z-score in the baseline's stored space, std floor 1e-6.
  Imputer: ONE global pool (kgs+nlog+force train), trained once on RAW train, reused; degradation
    = that imputer on raw-dev vs tokenized-reconstructed-dev, all scored through committed
    eval_harness (same XGBoost params/SEED/transforms as the committed baseline).
  Scope: all 11 canonical curves as imputation targets. Selection: smallest TRUE codebook among
    bar-meeting configs (median deg <=5% AND max single-curve deg <=10%); tie-break median, then
    max, then fewer dims; none pass -> escalate, bar unchanged. Provisional pending GATE APPROVED.

Efficiency: the 11 patch banks and 11 imputers (and raw_RMSE, the fixed denominator) are built
ONCE and reused across all configs. Per config only trains 11 tokenizers + reconstructs dev.

Does NOT self-certify R8. blind_force NEVER loaded. Holdouts reserved. Outside hashed set.
"""
import json, time, sys
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor
import eval_harness as EH
import fsq_tokenizer as FT
import r8_acceptance as R8

OUT = EH.ROOT / "reports/basinshift"
SWEEP = OUT / "fsq_phaseB"; SWEEP.mkdir(exist_ok=True)
RES = SWEEP / "results"; RES.mkdir(exist_ok=True)

EPOCHS = 30
TRAIN_POOLS = R8.TRAIN_POOLS                 # kgs_train + nlog_train + force_train
A40_RATE = 0.44                              # $/hr (Stage-1: $9.82 / 22.3 h)
MAX_WALL_S = 4 * 3600                         # money gate: <= 4 h (and 4h*$0.44=$1.76 < $5)
GUARD_S = int(MAX_WALL_S * 0.92)             # stop before starting a config that would cross it

# name -> level vector. Ordered small->large; floor probes first. True codebook = product.
GRID = [
    ("cb64",    (8, 8)),            # floor probe (pre-declared)
    ("cb125",   (5, 5, 5)),         # floor probe (pre-declared)
    ("cb240",   (8, 6, 5)),         # LOCKED
    ("cb1000",  (8, 5, 5, 5)),      # LOCKED
    ("cb4375",  (7, 5, 5, 5, 5)),   # LOCKED
    ("cb15360", (8, 8, 8, 6, 5)),   # LOCKED
]

_LINES = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); _LINES.append(s)
    (SWEEP / "sweep_log.txt").write_text("\n".join(_LINES) + "\n")


def build_banks():
    banks, stats = {}, {}
    for c in EH.CANON:
        arrs = R8.curve_arrays_train(c)
        m, s = FT.compute_stats(arrs)
        banks[c] = FT.build_patch_bank(arrs, m, s, cap=None)
        stats[c] = (m, s)
        log(f"[bank {c}] n={len(banks[c])} mean={m:.4g} std={s:.4g}")
    return banks, stats


def build_imputers_and_raw(lut):
    """Train 11 imputers once; raw_RMSE per target on dev = the fixed degradation denominator."""
    imp, raw = {}, {}
    for tgt in EH.CANON:
        grid = R8.dev_grid(tgt)
        if len(grid) == 0:
            imp[tgt] = None
            raw[tgt] = dict(raw_rmse=None, n_samples=0, n_wells=0, degenerate=True,
                            cause=f"no dev wells with >={EH.MIN_TARGET_SAMPLES} valid {tgt} samples")
            log(f"[imp {tgt}] DEGENERATE (empty dev grid)")
            continue
        Xtr, ytr = EH.build_train(TRAIN_POOLS, tgt)
        m = XGBRegressor(**EH.XGB); m.fit(Xtr, ytr)
        imp[tgt] = m
        g, p = R8.predict_dev(tgt, m, recon=None, lut=lut)
        sc = EH.score(g, p, tgt)
        rr = sc["pooled_rmse"]
        degen = (rr is None) or (not np.isfinite(rr)) or (rr < 1e-6)
        raw[tgt] = dict(raw_rmse=rr, n_samples=sc["n_samples"], n_wells=sc["n_wells"],
                        degenerate=bool(degen),
                        cause=("raw_RMSE near-zero / non-finite (unpredictable denominator)" if degen else None))
        log(f"[imp {tgt}] raw_RMSE={rr:.6g} n={sc['n_samples']} wells={sc['n_wells']}"
            + ("  DEGENERATE" if degen else ""))
    return imp, raw


def run_config(name, levels, banks, stats, imp, raw, lut):
    t0 = time.time()
    toks = {}
    for c in EH.CANON:
        model = FT.train_tokenizer(banks[c], levels, epochs=EPOCHS, log=None)
        # convergence probe: mean recon MSE (standardized space) on up to 50k bank patches
        import torch
        with torch.no_grad():
            probe = banks[c][:50000]
            mse = float(((model(torch.from_numpy(probe)) - torch.from_numpy(probe)) ** 2).mean()) if len(probe) else None
        toks[c] = (model, stats[c][0], stats[c][1])
        log(f"  [tok {name}/{c}] recon_mse_train={mse:.5f}" if mse is not None else f"  [tok {name}/{c}] empty")
    recon = R8.reconstruct_dev(toks, log=lambda *a: None)

    per_curve = {}
    for tgt in EH.CANON:
        r = raw[tgt]
        if r["degenerate"] or imp[tgt] is None:
            per_curve[tgt] = dict(raw_rmse=r["raw_rmse"], recon_rmse=None, degradation=None,
                                  n_samples=r["n_samples"], n_wells=r["n_wells"],
                                  degenerate=True, cause=r["cause"])
            continue
        g, p = R8.predict_dev(tgt, imp[tgt], recon=recon, lut=lut)
        sc = EH.score(g, p, tgt)
        deg = (sc["pooled_rmse"] - r["raw_rmse"]) / r["raw_rmse"]
        per_curve[tgt] = dict(raw_rmse=r["raw_rmse"], recon_rmse=sc["pooled_rmse"], degradation=deg,
                              n_samples=sc["n_samples"], n_wells=sc["n_wells"], degenerate=False, cause=None)
        log(f"  [deg {name}/{tgt}] raw={r['raw_rmse']:.6g} recon={sc['pooled_rmse']:.6g} deg={deg*100:+.2f}%")

    valid = [v["degradation"] for v in per_curve.values() if not v["degenerate"]]
    med = float(np.median(valid)) if valid else None
    mx = float(np.max(valid)) if valid else None
    s = dict(name=name, levels=list(levels), codebook_size=int(np.prod(levels)), patch=FT.PATCH,
             epochs=EPOCHS, per_curve=per_curve, n_curves_scored=len(valid),
             degenerate_curves=[c for c, v in per_curve.items() if v["degenerate"]],
             median_degradation=med, max_degradation=mx,
             bar_median_le_5pct=(bool(med <= 0.05) if med is not None else None),
             bar_max_le_10pct=(bool(mx <= 0.10) if mx is not None else None),
             elapsed_s=round(time.time() - t0, 1))
    return s


def select(summaries):
    """Provisional selection (pending GATE APPROVED): smallest true codebook meeting the bar;
    tie-break lower median, then lower max, then fewer FSQ dims."""
    passing = [s for s in summaries
               if s["bar_median_le_5pct"] and s["bar_max_le_10pct"]]
    if not passing:
        return None, "NO config meets the R8 bar -> ESCALATE to advisor (bar unchanged)"
    passing.sort(key=lambda s: (s["codebook_size"], s["median_degradation"],
                                s["max_degradation"], len(s["levels"])))
    p = passing[0]
    return p["name"], (f"smallest true codebook={p['codebook_size']} (levels {p['levels']}) "
                       f"median={p['median_degradation']*100:.2f}% max={p['max_degradation']*100:.2f}%")


def main():
    run_t0 = time.time()
    log(f"=== 6.3 Phase B FSQ sweep START epochs={EPOCHS} grid={[g[0] for g in GRID]} ===")
    lut = R8._wid_lookup()
    banks, stats = build_banks()
    imp, raw = build_imputers_and_raw(lut)
    (SWEEP / "raw_denominators.json").write_text(json.dumps(raw, indent=2))
    prep_s = time.time() - run_t0
    log(f"=== prep done in {prep_s:.0f}s (banks+imputers+raw) ===")

    done_times = []
    for i, (name, levels) in enumerate(GRID):
        rf = RES / f"{name}.json"
        if rf.exists():
            log(f"SKIP {name} (result exists)")
            continue
        remaining = len(GRID) - i
        if done_times:
            avg = sum(done_times) / len(done_times)
            proj = (time.time() - run_t0) + avg * remaining
            log(f"[projection] elapsed={time.time()-run_t0:.0f}s avg_cfg={avg:.0f}s "
                f"remaining={remaining} projected_total={proj:.0f}s (guard {GUARD_S}s)")
            if proj > GUARD_S:
                log(f"STOP_GATE: projected total {proj:.0f}s would exceed the money gate "
                    f"({MAX_WALL_S}s / $5). Halting before config {name}; completed configs are saved.")
                break
        s = run_config(name, levels, banks, stats, imp, raw, lut)
        rf.write_text(json.dumps(s, indent=2))
        done_times.append(s["elapsed_s"])
        log(f"CONFIG_DONE {name} cb={s['codebook_size']} median={s['median_degradation']} "
            f"max={s['max_degradation']} elapsed={s['elapsed_s']}s")

    # aggregate whatever completed
    summaries = []
    for name, _ in GRID:
        rf = RES / f"{name}.json"
        if rf.exists():
            summaries.append(json.loads(rf.read_text()))
    sel_name, sel_reason = select(summaries)
    total_s = time.time() - run_t0
    agg = dict(epochs=EPOCHS, configs=summaries, n_configs_done=len(summaries),
               provisional_selected=sel_name, selection_reason=sel_reason,
               total_wall_s=round(total_s, 1), est_cost_usd=round(total_s / 3600 * A40_RATE, 2),
               money_gate="UNDER" if total_s <= MAX_WALL_S else "OVER",
               note="Provisional pending GATE APPROVED. R8 pass/fail is the advisor's gate; not self-certified.")
    (SWEEP / "fsq_phaseB_summary.json").write_text(json.dumps(agg, indent=2))
    log(f"=== SWEEP DONE configs={len(summaries)}/{len(GRID)} provisional_select={sel_name} "
        f"wall={total_s:.0f}s (~${agg['est_cost_usd']}) gate={agg['money_gate']} ===")
    log("SWEEP_COMPLETE")


if __name__ == "__main__":
    main()
