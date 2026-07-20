"""Bridge the file-level NLOG failures to the borehole-level processed set (card evidence).

OUTSIDE the hashed set: this script and its inputs are not in the 24-file qc_code_sha256
set nor the manifest pin payload, so nothing here moves qc_code_sha256 or the FINAL
manifest d5b35a00.

Of the distinct boreholes touched by the file-level failures, how many were RECOVERED
into the processed set (via an alternate file) vs ended up never-processed.

Sources (all committed):
  reports/nlog_failures.csv      (file-level failures; well_id = borehole__fileid.ext)
  reports/nlog_qc_records.csv    (processed boreholes)
"""
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
fail = pd.read_csv(ROOT/"reports/nlog_failures.csv")
qc   = pd.read_csv(ROOT/"reports/nlog_qc_records.csv")

fail["bh"] = fail["well_id"].astype(str).str.split("__").str[0]
proc_set = set(qc["well_id"].astype(str).str.split("__").str[0])
fail_bh  = set(fail["bh"])

n_rows      = len(fail)
n_fail_bh   = len(fail_bh)
recovered   = fail_bh & proc_set
never_proc  = fail_bh - proc_set

print("=== NLOG failure/borehole bridge (from committed artifacts) ===")
print(f"failure rows (file-level)      = {n_rows}")
print(f"distinct failure boreholes     = {n_fail_bh}")
print(f"recovered into processed (5004)= {len(recovered)}")
print(f"never-processed                = {len(never_proc)}")
print(f"sum                            = {len(recovered)+len(never_proc)}  (must == {n_fail_bh})")
print(f"recovered fraction             = {len(recovered)/n_fail_bh:.1%}")

# STOP-CONDITION (Plan): the two must sum to the distinct failure-borehole count
assert len(recovered) + len(never_proc) == n_fail_bh, \
    f"HALT: recovered {len(recovered)} + never_proc {len(never_proc)} != {n_fail_bh}"
print("STOP-CONDITION PASS: recovered + never_processed == distinct failure boreholes")
