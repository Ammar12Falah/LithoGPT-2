#!/usr/bin/env python3
"""CPU smoke for the FSQ tokenizer R8 path (roadmap 6.3, Phase A).

Proves plumbing, NOT good numbers: trains one small FSQ config on CPU (all canonical curves,
tiny patch cap + few epochs), reconstructs the dev split, and pushes >=1 curve's degradation
all the way through the committed XGBoost machinery. Tokenizes every curve (needed as imputer
features) but scores a 2-target subset to keep XGBoost fits cheap. Writes fsq_smoke.json.

Also emits a throughput probe (patches, wall time) used to size the full-sweep cost estimate.
"""
import json, time
from pathlib import Path
import numpy as np
import r8_acceptance as R8
import eval_harness as EH

OUT = EH.ROOT / "reports/basinshift"

LEVELS = (8, 6, 5)          # codebook 240 ~ 2^8, a small config for the smoke
EPOCHS = 3
CAP = 30_000                # patches per curve (subsample) for a fast CPU pass
SCORE = ["DTC", "NPHI"]     # >=1 curve degradation; both are committed targets


def main():
    lines = []
    def log(*a):
        s = " ".join(str(x) for x in a)
        print(s, flush=True)
        lines.append(s)

    t0 = time.time()
    res = R8.run(levels=LEVELS, curves=EH.CANON, score_curves=SCORE,
                 epochs=EPOCHS, cap=CAP, log=log)
    res["wall_s_total"] = round(time.time() - t0, 1)
    res["env"] = {}
    for mod in ["numpy", "pandas", "pyarrow", "xgboost", "sklearn", "torch"]:
        try:
            m = __import__(mod)
            res["env"][mod] = m.__version__
        except Exception as e:
            res["env"][mod] = f"ERR {e}"

    (OUT / "fsq_smoke.json").write_text(json.dumps(res, indent=2))
    (OUT / "fsq_smoke_log.txt").write_text("\n".join(lines) + "\n")
    log(f"SMOKE_DONE wall={res['wall_s_total']}s "
        f"median_deg={res['median_degradation']} max_deg={res['max_degradation']}")


if __name__ == "__main__":
    main()
