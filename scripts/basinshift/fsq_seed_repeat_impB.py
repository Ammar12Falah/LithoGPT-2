#!/usr/bin/env python3
"""Top-up run: D2 item 5, imputer-seed axis only (Sweep B), reusing fsq_seed_repeat.py's
functions. The first invocation completed the tokenizer-seed axis (3/3, cached on disk) but its
guard halted before Sweep B using a blended average that conflated cheap imputer-fit cost with
expensive tokenizer-training cost -- a false-positive halt, not an actual budget breach (imputer
refits are ~170s each vs ~3500-3800s per tokenizer retrain). This script rebuilds the canonical
tokenizer once (deterministic -- same seed, should reproduce PEF_deg=13.37% as a consistency
check against tokA_seed20260715.json) and then runs the imputer-seed sweep, which is the
genuinely cheap part. Own fresh $5/4h gate; reports real elapsed/cost.
"""
import json, time
from pathlib import Path
import sys
sys.path.insert(0, "scripts/basinshift")
import fsq_seed_repeat as SR

t0 = time.time()
SR.log(f"=== D2 item 5 TOP-UP (imputer-seed axis only) START seeds={SR.IMPUTER_SEEDS} ===")

banks, stats = SR.build_banks()
SR.log("banks built (topup)")

imp_raw_by_seed = {}
t1 = time.time()
imp_raw_by_seed[SR.CANONICAL_IMP_SEED] = SR.fit_imputer_and_raw(SR.CANONICAL_IMP_SEED)
SR.log(f"[imputer canonical seed={SR.CANONICAL_IMP_SEED}] fit in {time.time()-t1:.1f}s (topup)")

t1 = time.time()
toks = SR.train_toks_seeded(banks, stats, SR.CANONICAL_TOK_SEED)
canonical_recon = SR.reconstruct_gdev(toks)
del toks
SR.log(f"[canonical tokenizer rebuild seed={SR.CANONICAL_TOK_SEED}] done in {time.time()-t1:.1f}s (topup)")

# sanity check against the cached tokA result
cached = json.loads((SR.RES / f"tokA_seed{SR.CANONICAL_TOK_SEED}.json").read_text())
check = SR.score_literal(canonical_recon, imp_raw_by_seed[SR.CANONICAL_IMP_SEED])
pef_now = check["PEF"]["literal_deg"]
pef_cached = cached["PEF"]["literal_deg"]
SR.log(f"[sanity check] PEF literal_deg rebuild={pef_now*100:.2f}% cached={pef_cached*100:.2f}% "
       f"diff={(pef_now-pef_cached)*100:+.3f}pp")

impB_results = {}
for imp_seed in SR.IMPUTER_SEEDS:
    rf = SR.RES / f"impB_seed{imp_seed}.json"
    if rf.exists():
        impB_results[imp_seed] = json.loads(rf.read_text())
        SR.log(f"SKIP impB seed={imp_seed} (result exists)")
        continue
    t1 = time.time()
    if imp_seed in imp_raw_by_seed:
        iar = imp_raw_by_seed[imp_seed]
    else:
        iar = SR.fit_imputer_and_raw(imp_seed)
        imp_raw_by_seed[imp_seed] = iar
    res = SR.score_literal(canonical_recon, iar)
    dt = time.time() - t1
    impB_results[imp_seed] = res
    (SR.RES / f"impB_seed{imp_seed}.json").write_text(json.dumps(res, indent=2))
    pef_deg = res["PEF"]["literal_deg"]
    pef_str = f"{pef_deg*100:.2f}%" if pef_deg is not None else "degenerate"
    SR.log(f"[impB seed={imp_seed}] done in {dt:.1f}s  PEF_deg={pef_str}")

imp_seeds_done = sorted(impB_results.keys())
imputer_axis_summary = SR.summarize_axis(impB_results, imp_seeds_done)

topup_total_s = time.time() - t0
topup_cost = round(topup_total_s / 3600 * SR.A40_RATE, 2)
SR.log(f"=== TOP-UP DONE imp_seeds={len(imp_seeds_done)}/{len(SR.IMPUTER_SEEDS)} "
       f"wall={topup_total_s:.0f}s (~${topup_cost}) ===")
SR.log("TOPUP_COMPLETE")

# merge into the combined summary
prior = json.loads((SR.DIAG / "seed_repeat_summary.json").read_text())
prior["imputer_seed_axis"] = dict(seeds_planned=SR.IMPUTER_SEEDS, seeds_done=imp_seeds_done,
                                   per_curve=imputer_axis_summary)
prior["sanity_check_canonical_pef_rebuild_vs_cached"] = dict(
    rebuild=pef_now, cached=pef_cached, diff=pef_now - pef_cached)
prior["topup_wall_s"] = round(topup_total_s, 1)
prior["topup_cost_usd"] = topup_cost
prior["total_wall_s_combined"] = round(prior["total_wall_s"] + topup_total_s, 1)
prior["est_cost_usd_combined"] = round(prior["est_cost_usd"] + topup_cost, 2)
(SR.DIAG / "seed_repeat_summary.json").write_text(json.dumps(prior, indent=2))
print("MERGED_SUMMARY_WRITTEN")
