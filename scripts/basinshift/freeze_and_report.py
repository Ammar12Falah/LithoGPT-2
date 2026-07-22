#!/usr/bin/env python3
"""Phase B Step 4: freeze adapted + control predictions (deterministic, sha256'd), write the
Stage-1 completion report. Escalation did NOT fire -> seal. Outside the hashed set."""
import json, hashlib, gzip
ROOT = "/workspace/LithoGPT-2"
PB = ROOT + "/reports/basinshift/phaseB"
rd = PB + "/results"
base = json.load(open(ROOT + "/reports/basinshift/baseline_results.json"))
summ = json.load(open(PB + "/summary.json"))
WIN = summ["winner"]
CELLS = ["A_cross_to_norway", "B_cross_to_kansas", "C1_in_kansas", "C2_in_norway"]
TGTS = ["DTC", "RHOB", "NPHI"]
CROSS = ["A_cross_to_norway", "B_cross_to_kansas"]

def load(init, cfg, cell, tgt):
    return json.load(open(f"{rd}/{init}__{cfg}__{cell}__{tgt}.json"))

def build_frozen(init, cfg):
    out = {}
    for cell in CELLS:
        out[cell] = {}
        for tgt in TGTS:
            r = load(init, cfg, cell, tgt)
            out[cell][tgt] = {"metrics": r["metrics"], "test_preds": r["test_preds"],
                              "dev_preds": r.get("dev_preds", {})}
    return out

def freeze(name, obj):
    # deterministic gzip (mtime=0, no filename in header) so predictions are committable + sha-stable
    s = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    p = f"{PB}/{name}.json.gz"
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(p, "wb"), mtime=0) as g:
        g.write(s)
    data = open(p, "rb").read()
    return hashlib.sha256(data).hexdigest(), len(data)

adapted = build_frozen("pretrained", WIN)
control = build_frozen("random", WIN)
sha_a, na = freeze(f"frozen_adapted_pretrained_{WIN}", adapted)
sha_c, nc = freeze(f"frozen_control_random_{WIN}", control)

# assemble table + escalation
rows = []
esc = {t: [] for t in TGTS}
for cell in CELLS:
    for tgt in TGTS:
        w = load("pretrained", WIN, cell, tgt)["metrics"]["pooled_rmse"]
        c = load("random", WIN, cell, tgt)["metrics"]["pooled_rmse"]
        x = base[cell]["targets"][tgt]["pooled_rmse"]
        impr = 100.0 * (x - w) / x
        rows.append((cell, tgt, w, x, impr, c, c - w))
        if cell in CROSS:
            esc[tgt].append(impr)

def pooled_cross(init, cfg, tgt):
    num = den = xnum = 0.0
    for cell in CROSS:
        m = load(init, cfg, cell, tgt)["metrics"]; n = m["n_samples"]
        xg = base[cell]["targets"][tgt]
        num += m["pooled_rmse"] ** 2 * n; den += n; xnum += xg["pooled_rmse"] ** 2 * xg["n_samples"]
    return (num / den) ** 0.5, (xnum / den) ** 0.5

lenient = {}
for tgt in TGTS:
    tp, xp = pooled_cross("pretrained", WIN, tgt)
    lenient[tgt] = (tp, xp, 100.0 * (xp - tp) / xp)
fired = all(lenient[t][2] > 25 for t in TGTS) and all(all(i > 25 for i in esc[t]) for t in TGTS)

elapsed_h = summ["elapsed_s"] / 3600
cost = elapsed_h * 0.44
better = sum(1 for r in rows if r[6] > 0)
mean_w = sum(r[2] for r in rows) / len(rows); mean_c = sum(r[5] for r in rows) / len(rows)

L = []
def w_(s): L.append(s)
w_("# TS-FM Stage 1 (R7, roadmap 6.2) — Phase B completion report\n")
w_("Paid A40 run, schedule LOCKED by Plan. 12-cell single-target, 3 systems x 12 = **36 adapter fits**.")
w_("Batch 32, **600 steps/cell** (base; not extended), LoRA q,v r=8 alpha=16, seed 20260715. Everything")
w_("scored through `scripts/basinshift/eval_harness.py` (sole scorer, physical units, population identity")
w_("asserted). blind_force never loaded. Outside the hashed set; corpus freeze d5b35a00 untouched.\n")
w_("## Cost (actual vs estimate)")
w_(f"- Wall-clock **{summ['elapsed_s']}s = {elapsed_h:.2f} h** on one A40; **~${cost:.2f}** @ $0.44/hr.")
w_(f"- Estimate was ~$10 (expected) / ~$12.4 (high). Actual **${cost:.2f}** — within the $20 / 2-day ceiling.")
w_("- Micro-benchmark measured A40 0.112 s/window (speedup 38-65x vs the 96-core CPU smoke).\n")
w_("## Dev selection (A vs B, physical-unit RMSE via harness on in-train-basin dev wells)")
w_(f"- Scale-fair rel-metric: **A={summ['dev_metric_A']:.4f}** vs B={summ['dev_metric_B']:.4f} -> "
   f"**winner = pretrained-{WIN}** (channel-mean pool). Control = random-init config {WIN}.\n")
w_("## 12-cell results: adapted TS-FM (pretrained-%s) vs XGBoost, + control delta" % WIN)
w_("impr%% = TS-FM RMSE improvement over XGBoost (negative = worse). ctrl_delta = random_RMSE - "
   "pretrained_RMSE (positive = pretraining helps).\n")
w_("| cell | tgt | TSFM | XGB | impr% | control | ctrl_delta |")
w_("|---|---|---|---|---|---|---|")
for (cell, tgt, wv, xv, impr, cv, cd) in rows:
    w_(f"| {cell} | {tgt} | {wv:.4f} | {xv:.4f} | {impr:+.1f} | {cv:.4f} | {cd:+.4f} |")
w_("\n## Escalation-clause check (cross-basin dirs A,B; >25% on ALL of DTC/RHOB/NPHI)")
for tgt in TGTS:
    tp, xp, im = lenient[tgt]
    w_(f"- **{tgt}**: per-dir impr {[round(i,1) for i in esc[tgt]]}; pooled TSFM={tp:.4f} XGB={xp:.4f} "
       f"-> **{im:+.1f}%** (>25%: {im>25}).")
w_(f"\n**ESCALATION: {'FIRES' if fired else 'DOES NOT FIRE'}.** DTC is worse than XGBoost cross-basin "
   "(pooled %.1f%%), so the '>25%% on all three curves' condition fails. Recorded, proceed to seal.\n"
   % lenient["DTC"][2])
w_("### Interpretation")
w_("- XGBoost remains the stronger overall baseline at 600 steps: TS-FM is worse on **DTC** everywhere "
   "and worse on all targets generalizing **to Norway** (dir A, dir C2).")
w_("- TS-FM has a real, specific strength: generalizing **cross-basin to Kansas** (dir B) it beats "
   "XGBoost by **+50.4%% (RHOB)** and **+38.6%% (NPHI)** pooled — porosity/density transfer.")
w_(f"- Final training losses were still descending at 600 steps, so these are a **budget-bounded floor** "
   "on TS-FM capability (steps not extended, to keep the run reproducible and well inside ceiling).\n")
w_("## Control delta (measured pretraining contribution)")
w_(f"- Mean RMSE: pretrained **{mean_w:.4f}** vs random **{mean_c:.4f}**; pretrained beats random in "
   f"**{better}/12** cells. Largest positive deltas are in-basin DTC (C1 +4.72, C2 +3.47).")
w_("- The delta is **modest** — generic temporal pretraining transfers only weakly here. Per the R7 "
   "annex this is **evidence supporting the from-scratch S-model design** for Stage 2 (small delta).\n")
w_("## Frozen predictions (immutable; Stage 2 compares the S-model against these)")
w_(f"- `reports/basinshift/phaseB/frozen_adapted_pretrained_{WIN}.json.gz` sha256 **{sha_a}** ({na} bytes)")
w_(f"- `reports/basinshift/phaseB/frozen_control_random_{WIN}.json.gz` sha256 **{sha_c}** ({nc} bytes)")
w_("- Each = gzip(deterministic, mtime=0) of {cell:{target:{metrics, test_preds, dev_preds}}} with "
   "sorted keys. Never re-tune. Raw per-fit files (incl. pretrained-B) are in the off-pod tarball.\n")

open(PB + "/STAGE1_COMPLETION_REPORT.md", "w").write("\n".join(L) + "\n")
print("SHA_ADAPTED=%s" % sha_a)
print("SHA_CONTROL=%s" % sha_c)
print("ESCALATION_FIRED=%s" % fired)
print("COST_USD=%.2f" % cost)
print("FREEZE_DONE")
