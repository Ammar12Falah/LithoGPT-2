#!/usr/bin/env python3
"""Plumbing smoke for fsq_diag: shrink pools + 1 epoch + 1 tiny config, run main() end-to-end in a
temp dir. Validates the global/cross-basin/symmetry/summary paths without the full-run cost."""
from pathlib import Path
import eval_harness as EH
import fsq_diag as D

# shrink pools (plumbing only)
EH.POOLS["kgs_train"] = EH.POOLS["kgs_train"][:10]
EH.POOLS["nlog_train"] = EH.POOLS["nlog_train"][:10]
EH.POOLS["force_train"] = EH.POOLS["force_train"][:4]
_orig = EH.wells_of
EH.wells_of = lambda src, split: _orig(src, split)[:8]

D.EPOCHS = 1
D.CONFIGS = [("smoke_p32", (8, 6, 5), 32), ("smoke_p16", (8, 6, 5), 16)]
D.DIAG = Path("/tmp/diag_smoke"); D.DIAG.mkdir(exist_ok=True)
D.RES = D.DIAG / "results"; D.RES.mkdir(exist_ok=True)

D.main()
print("SMOKE_OK")
