#!/usr/bin/env python3
"""Compact digest of the 6.3 diagnostic results for the report. Reads JSON only (fast)."""
import json
from pathlib import Path
import eval_harness as EH

D = EH.ROOT / "reports/basinshift/fsq_diag"
RES = D / "results"
CANON = EH.CANON
CFGS = ["cb4375_p32", "cb15360_p32", "cb15360_p16"]

PHASEB = {"DTC": {"raw": 14.100294683511459, "lit_deg": 0.09992728415687144},
          "PEF": {"raw": 1.46538, "lit_deg": 0.20090392105310736}}


def pct(x):
    return "None" if x is None else f"{x*100:+.2f}%"


for cfg in CFGS:
    r = json.loads((RES / f"{cfg}.json").read_text())
    print(f"\n######## {cfg}  levels={r['levels']} cb={r['codebook_size']} patch={r['patch']} elapsed={r['elapsed_s']}s")
    gl = r["global_dev_literal"]; gs = r["global_dev_literal_summary"]
    print("-- GLOBAL-DEV LITERAL (Phase B setup) --")
    for c in CANON:
        v = gl[c]
        print(f"   {c:5s} raw={v['raw_rmse']} lit_deg={pct(v['literal_deg'])} n={v['n_samples']} wells={v['n_wells']} degen={v['degenerate']}")
    print(f"   >> median={pct(gs['median'])} max={pct(gs['max'])} max_curve={gs['max_curve']} "
          f"bar_med<=5={gs['bar_median_le5']} bar_max<=10={gs['bar_max_le10']}")
    for dname, pc in r["per_direction"].items():
        ds = r["dir_summary"][dname]
        print(f"-- CROSS-BASIN {dname} --")
        for c in CANON:
            v = pc[c]
            print(f"   {c:5s} raw={v['raw_rmse']} lit={pct(v['literal_deg'])} mat={pct(v['matched_deg'])} "
                  f"n={v['n_samples']} wells={v['n_wells']} degen={v['degenerate']}")
        print(f"   >> LIT  median={pct(ds['literal']['median'])} max={pct(ds['literal']['max'])} "
              f"bar_med={ds['literal']['bar_median_le5']} bar_max={ds['literal']['bar_max_le10']}")
        print(f"   >> MAT  median={pct(ds['matched']['median'])} max={pct(ds['matched']['max'])} "
              f"bar_med={ds['matched']['bar_median_le5']} bar_max={ds['matched']['bar_max_le10']}")
        sg = ds["symmetry_headline"]
        for c in ["DTC", "RHOB", "NPHI"]:
            print(f"   >> SYM {c}: lit={pct(sg[c]['literal'])} mat={pct(sg[c]['matched'])} matched_worse={sg[c]['matched_worse']}")
        print(f"   >> SYMMETRY_VIOLATED={ds['symmetry_violated']}")

print("\n######## STABILITY PROBE cb15360_p32 vs Phase B (global-dev) ########")
r = json.loads((RES / "cb15360_p32.json").read_text())["global_dev_literal"]
for c in ["DTC", "PEF"]:
    v = r[c]
    dr = v["raw_rmse"] - PHASEB[c]["raw"]
    print(f"   {c}: raw_now={v['raw_rmse']:.5f} raw_PhaseB={PHASEB[c]['raw']:.5f} d_raw={dr:+.5f} "
          f"| lit_deg_now={pct(v['literal_deg'])} lit_deg_PhaseB={pct(PHASEB[c]['lit_deg'])} "
          f"d_deg={(v['literal_deg']-PHASEB[c]['lit_deg'])*100:+.2f}pp")

print("\n######## PEF per-basin (rail) ########")
try:
    pr = json.loads((D / "pef_rail_check.json").read_text())
    for b, v in pr.items():
        if v.get("n_samples", 0):
            print(f"   {b}: n={v['n_samples']} median={v['median']:.3f} max={v['max']:.3f} "
                  f"eq20.0={v['frac_eq_20p0']*100:.3f}% >6={v['frac_above_6']*100:.2f}% "
                  f"in[1.5,6]={v['frac_in_1p5_6']*100:.2f}% neg={v['frac_negative']*100:.3f}% "
                  f"wells_eq20={v['n_wells_with_any_eq20']}")
except FileNotFoundError:
    print("   pef_rail_check.json not yet written")
print("DIGEST_DONE")
