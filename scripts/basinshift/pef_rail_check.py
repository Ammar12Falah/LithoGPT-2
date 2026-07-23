#!/usr/bin/env python3
"""PEF rail/sentinel check (report addendum, advisor-directed). Read-only over TRAIN parquets.
Per basin: fraction of PEF samples exactly at 20.0 (pile-up at a clip/sentinel = R4-type rail),
fraction above the typical 1.5-6 band, plus band/tail fractions. A hard max merely touched differs
from a pile-up at a rail, and the latter changes how PEF's relative-degradation bar reads."""
import json
import numpy as np
import eval_harness as EH

OUT = EH.ROOT / "reports/basinshift/fsq_diag"


def main():
    res = {}
    for basin, key in [("KGS", "kgs_train"), ("NLOG_Netherlands", "nlog_train"), ("FORCE_Norway", "force_train")]:
        vals = []
        for (src, safe, wid) in EH.POOLS[key]:
            df = EH.load_well(src, safe, wid)
            v = df["PEF"].to_numpy(); v = v[np.isfinite(v)]
            if len(v):
                vals.append(v)
        if not vals:
            res[basin] = dict(n_samples=0)
            continue
        a = np.concatenate(vals)
        n = len(a)
        res[basin] = dict(
            n_samples=int(n), n_wells=len(vals),
            min=float(a.min()), median=float(np.median(a)), mean=float(a.mean()),
            max=float(a.max()), std=float(a.std()),
            frac_eq_20p0=float(np.mean(np.abs(a - 20.0) < 1e-3)),
            frac_ge_19p99=float(np.mean(a >= 19.99)),
            frac_in_1p5_6=float(np.mean((a >= 1.5) & (a <= 6.0))),
            frac_above_6=float(np.mean(a > 6.0)),
            frac_below_1p5=float(np.mean(a < 1.5)),
            frac_negative=float(np.mean(a < 0)),
            frac_gt10=float(np.mean(a > 10.0)),
            n_wells_with_any_eq20=int(sum(1 for w in vals if np.any(np.abs(w - 20.0) < 1e-3))),
        )
        r = res[basin]
        print(f"[{basin}] n={n} median={r['median']:.3f} max={r['max']:.3f} "
              f"eq20.0={r['frac_eq_20p0']*100:.3f}% >6={r['frac_above_6']*100:.2f}% "
              f"in[1.5,6]={r['frac_in_1p5_6']*100:.2f}% wells_with_eq20={r['n_wells_with_any_eq20']}", flush=True)
    (OUT / "pef_rail_check.json").write_text(json.dumps(res, indent=2))
    print("PEF_RAIL_DONE", flush=True)


if __name__ == "__main__":
    main()
