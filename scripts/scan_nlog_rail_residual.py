"""NLOG rail-rule COMPLETENESS scan (survivors in the frozen processed set).

*** THIS IS NOT THE HISTORICAL RAIL-IMPACT COUNT. *** How many wells were rail-nulled at
harmonize time is UNRECOVERABLE without reopening the frozen corpus: the processed parquets
store rail-nulled samples as NaN (indistinguishable from any other null) and the raw NLOG
wells are gone (data/raw/nlog/wells/ is empty). This scan instead re-applies the
_null_rail_pileup criteria to the FROZEN processed values to measure how many discrete
rail pileups SURVIVED the rule (a completeness check). Expected near zero.

OUTSIDE the hashed set: this script and its inputs are not in the 24-file qc_code_sha256
set nor the manifest pin payload, so nothing here moves qc_code_sha256 or the FINAL
manifest d5b35a00; the freeze is untouched. Read-only scan; no ingestion, no re-harmonize.

Criteria (identical to harmonize.py::_null_rail_pileup): a value is on a rail if it is
within 1e-6 of a valid_range bound; a pileup counts if it holds >=25 real samples AND
>=5% of finite real samples. Resistivity curves are log10 in the parquet, so bounds are
log10-transformed to match.
"""
import sys, json, time, traceback
sys.path.insert(0, "/workspace/LithoGPT-2/src")
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from lithogpt2.config import HarmonizationConfig

ROOT = Path("/workspace/LithoGPT-2")
PROC = ROOT/"data/processed/nlog"
OUT_LOG = Path("/tmp/rail_scan"); OUT_LOG.mkdir(parents=True, exist_ok=True)
LOG = OUT_LOG/"run.log"
SUMMARY = ROOT/"reports/card_derivations/nlog_rail_residual.txt"
SUMMARY.parent.mkdir(parents=True, exist_ok=True)

RAIL_EPS, RAIL_MIN_FRAC, RAIL_MIN_COUNT = 1e-6, 0.05, 25

def log(m):
    with open(LOG, "a") as f: f.write(f"[{time.strftime('%H:%M:%S')}] {m}\n")

open(LOG, "w").close()
try:
    cfg = HarmonizationConfig.load()
    CANON = list(cfg.canonical_curves)
    STEP = float(cfg.grid_step_m)
    MINC = int(cfg.min_curves)
    MINI = float(cfg.min_interval_m)
    bounds = {}
    for c in CANON:
        sp = cfg.curve(c); lo, hi = sp.valid_range
        if sp.transform == "log10":
            lo = np.log10(lo) if lo > 0 else None
            hi = np.log10(hi) if hi > 0 else None
        bounds[c] = (lo, hi)
    log(f"canon={CANON} step={STEP} min_curves={MINC} min_interval_m={MINI}")

    qc = pd.read_csv(ROOT/"reports/nlog_qc_records.csv")
    qc["well_id"] = qc["well_id"].astype(str)
    passmap = dict(zip(qc["well_id"], qc["min_interval_pass"].astype(bool)))
    ncm_map = dict(zip(qc["well_id"], qc["n_curves_meeting"]))

    files = sorted(PROC.glob("*.parquet"))
    log(f"nlog processed parquets: {len(files)}")
    affected = []
    for i, p in enumerate(files, 1):
        t = pq.read_table(p)
        names = set(t.column_names)
        hits = []
        for c in CANON:
            if c not in names or f"{c}_mask" not in names:
                continue
            v = np.asarray(t.column(c).to_numpy(zero_copy_only=False), dtype="float64")
            mk = np.asarray(t.column(f"{c}_mask").to_numpy(zero_copy_only=False), dtype=bool)
            real = v[mk & np.isfinite(v)]
            n = real.size
            if n == 0:
                continue
            lo, hi = bounds[c]
            for name, bound in (("lo", lo), ("hi", hi)):
                if bound is None:
                    continue
                cnt = int((np.abs(real - bound) <= RAIL_EPS).sum())
                if cnt >= RAIL_MIN_COUNT and (cnt / n) >= RAIL_MIN_FRAC:
                    hits.append(f"{c}@{name}:{cnt}/{n}")
        if hits:
            w = p.stem
            affected.append({"well": w, "curves": hits,
                             "passing": bool(passmap.get(w, False)),
                             "n_curves_meeting": int(ncm_map.get(w, -1))})
        if i % 1000 == 0:
            log(f"  {i}/{len(files)} scanned, residual so far {len(affected)}")

    N = len(affected)
    K = sum(1 for a in affected if a["passing"] and a["n_curves_meeting"] == MINC)
    log(f"SCAN DONE: scanned={len(files)} N_residual={N} K_floor_adjacent={K}")

    lines = []
    lines.append("NLOG rail-rule COMPLETENESS scan -- residual pileups surviving in the frozen processed set.")
    lines.append("*** NOT the historical rail-impact count (unrecoverable without reopening the frozen corpus:")
    lines.append("    processed parquets store rail-nulls as NaN; raw NLOG wells are gone). ***")
    lines.append("OUTSIDE the hashed set: nothing here moves qc_code_sha256 or the FINAL manifest d5b35a00.")
    lines.append("")
    lines.append(f"wells scanned                 = {len(files)}")
    lines.append(f"N wells with residual pileup  = {N}")
    lines.append(f"K of N near coverage floor    = {K}")
    lines.append(f"floor margin                  = curve-count slack 0 (passing AND n_curves_meeting == min_curves={MINC})")
    lines.append(f"criteria                      = within {RAIL_EPS} of a valid_range bound, >={RAIL_MIN_COUNT} samples AND >={int(RAIL_MIN_FRAC*100)}% of finite real")
    if N:
        lines.append("")
        lines.append("affected wells:")
        for a in affected:
            lines.append(f"  {a['well']}  passing={a['passing']}  n_curves_meeting={a['n_curves_meeting']}  {a['curves']}")
    SUMMARY.write_text("\n".join(lines) + "\n")
    log("STATUS: DONE")
    print("\n".join(lines))
except Exception:
    with open(LOG, "a") as f:
        f.write(traceback.format_exc())
    log("STATUS: FAILED")
    raise
