#!/usr/bin/env python3
"""Fold the CP1 ruling + n=9 Kansas-DTC label into docs/BENCHMARK.md (roadmap 6.1, Phase 2).
Two asserted string replacements; aborts if either does not match exactly once."""
from pathlib import Path
p = Path("/workspace/LithoGPT-2/docs/BENCHMARK.md")
t = p.read_text(encoding="utf-8")

old1 = "30.45 / 21.76 (floor 32.0) · **9w** | **12.61** / 6.84 · 9w |"
new1 = "30.45 / 21.76 · **n=9, low support, wide uncertainty** | **12.61** / 6.84 · **n=9, low support, wide uncertainty** |"

old2 = ("all 10 wells. Plan to\n"
        "rule: keep DTC→Kansas flagged-as-thin, or drop DTC from the Kansas direction.")
new2 = ("all 10 wells.\n\n"
        "**Ruling (CP1):** the Kansas-DTC cell is KEPT, flagged thin (**n=9, low well support, wide\n"
        "uncertainty**) — a true fact about the data, not hidden by deletion. Any Kansas-DTC score MUST\n"
        "report the well count (n=9) alongside RMSE, never RMSE alone.")

assert t.count(old1) == 1, f"old1 count={t.count(old1)}"
assert t.count(old2) == 1, f"old2 count={t.count(old2)}"
t = t.replace(old1, new1).replace(old2, new2)
p.write_text(t, encoding="utf-8")
print("BENCHMARK_EDIT_OK")
