#!/usr/bin/env python3
"""Phase 3: finalize the BasinShift section of docs/BENCHMARK.md with the FROZEN manifest hash.
Two asserted string replacements; aborts if either does not match exactly once."""
from pathlib import Path
p = Path("/workspace/LithoGPT-2/docs/BENCHMARK.md")
t = p.read_text(encoding="utf-8")
H = "e5f653077587f2fa80aa4bf1c236e45735798d1421329c735e7dbb620bcfbb71"

old1 = ("**This is\n"
        "the design/CP1 version; the immutable BasinShift test-manifest hash is added only after Plan\n"
        "clears CHECKPOINT 1 (Phase 2).**")
new1 = ("**Test manifest FROZEN: `reports/basinshift/basinshift_test_manifest.json`, sha256\n"
        f"`{H}` (commit `bd344e5`); CP2\n"
        "leakage suite ALL PASS (commit `1ba8bf7`).**")

old2 = ("`scripts/basinshift/basinshift_baseline.py`; `reports/basinshift/{run_log.txt,\n"
        "baseline_results.json, eval_composition.json, test_manifest_PROPOSED.json}`. The proposed\n"
        "manifest is **NOT hashed** (CP1 review); the immutable hash lands after Plan clears CP1.")
new2 = ("**Frozen manifest:** `reports/basinshift/basinshift_test_manifest.json` (sha256\n"
        f"`{H}`, `.sha256` alongside).\n"
        "**Standing opponent (committed):** `scripts/basinshift/basinshift_baseline.py` + outputs\n"
        "`reports/basinshift/{run_log.txt, baseline_results.json, eval_composition.json}`.\n"
        "**Builder / leakage:** `scripts/basinshift/{build_test_manifest.py, leakage_suite.py}` +\n"
        "`reports/basinshift/leakage_suite.txt` (CP2 ALL PASS). **Env:** `docs/basinshift_env_2026-07-20.txt`.\n"
        "The superseded `test_manifest_PROPOSED.json` is retained for provenance.")

assert t.count(old1) == 1, f"old1 count={t.count(old1)}"
assert t.count(old2) == 1, f"old2 count={t.count(old2)}"
t = t.replace(old1, new1).replace(old2, new2)
p.write_text(t, encoding="utf-8")
print("BENCHMARK_FINAL_OK")
