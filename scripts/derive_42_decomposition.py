"""Decompose the 42 log-bearing-but-never-processed NLOG boreholes (card evidence, R5).

OUTSIDE the hashed set: this script and its inputs are not in the 24-file qc_code_sha256
set nor the manifest pin payload, so nothing here moves qc_code_sha256 or the FINAL
manifest d5b35a00; the freeze is untouched. Read-only.

The 42 = (boreholes with >=1 log document) INTERSECT (borehole_index) MINUS (processed).
Bucket each of the 42 from committed artifacts, summing to 42 exactly:
  A. failure-blocked : borehole appears in reports/nlog_failures.csv (attempted; parse/
     timeout failure with a recorded per-file reason).
  B. remainder       : NOT in nlog_failures. Sub-split by whether any of the borehole's
     log-document URLs appears in the fetch manifest (data/raw/nlog/_manifest.json):
       B1 fetched-but-no-record : doc was fetched yet produced neither QC record nor
          failure row (a silent drop / queue-timing gap).
       B2 never-fetched         : no doc URL in the fetch manifest (resolve-stage
          straggler: log-bearing in the index but never queued for fetch).
"""
import json
from pathlib import Path
import pandas as pd

R = Path("/workspace/LithoGPT-2")
bh   = pd.read_csv(R/"data/raw/nlog/borehole_index.csv"); bh["well_id"] = bh["well_id"].astype(str)
li   = pd.read_csv(R/"data/raw/nlog/log_index.csv.gz");   li["well_id"] = li["well_id"].astype(str)
qc   = pd.read_csv(R/"reports/nlog_qc_records.csv");      qc["well_id"] = qc["well_id"].astype(str)
fail = pd.read_csv(R/"reports/nlog_failures.csv");        fail["bh"]    = fail["well_id"].astype(str).str.split("__").str[0]
man  = json.loads((R/"data/raw/nlog/_manifest.json").read_text())
man_keys = set(man.keys()) if isinstance(man, dict) else set()

bh_ids = set(bh["well_id"]); log_bh = set(li["well_id"])
proc   = set(qc["well_id"].str.split("__").str[0]); fbh = set(fail["bh"])

s42 = (bh_ids & log_bh) - proc
blocked   = s42 & fbh          # A
remainder = s42 - fbh          # B

li["fetched"] = li["download_url"].astype(str).isin(man_keys)
fetched_bh = set(li[li["fetched"]]["well_id"])
B1 = remainder & fetched_bh    # fetched-but-no-record
B2 = remainder - fetched_bh    # never-fetched

lines = []
def out(s): lines.append(s); print(s)

out("=== 42 log-bearing-never-processed NLOG boreholes: decomposition (R5) ===")
out(f"42 set size = {len(s42)}")
out(f"A. failure-blocked (in nlog_failures)      = {len(blocked)}")
out(f"B. remainder (not in nlog_failures)        = {len(remainder)}")
out(f"   B1 fetched-but-no-record               = {len(B1)}")
out(f"   B2 never-fetched (no doc in manifest)   = {len(B2)}")
out(f"SUM CHECK  A + B = {len(blocked)+len(remainder)}  (must == 42)")
out(f"           A + B1 + B2 = {len(blocked)+len(B1)+len(B2)}")
out("")
out(f"cross-check: failure-boreholes not processed (the 15) = {len(fbh - proc)}; "
    f"all in the 42 = {len((fbh-proc) & s42)}")
out(f"'5 permanent retry failures' = G1-era note (docs/milestone_G1_nlog.md: 13 of 5,009); "
    f"NO distinct committed 5-borehole artifact today. Per-file reasons are in nlog_failures.csv.")
out("")
out("A) failure-blocked per-FILE reasons (a borehole can hold several failure rows):")
for r, n in fail[fail["bh"].isin(blocked)]["error"].str.slice(0, 55).value_counts().items():
    out(f"    {n:3d}  {r}")
lt = li[li["well_id"].isin(remainder)]
out("")
out(f"B) remainder log-doc file_types: {lt['file_type'].value_counts().to_dict()}")
out(f"   remainder boreholes with >=1 LAS/DLIS doc = "
    f"{lt[lt['file_type'].isin(['LAS','DLIS'])]['well_id'].nunique()} of {len(remainder)}")

assert len(blocked) + len(remainder) == 42, "HALT: buckets do not sum to 42"
assert len(blocked) + len(B1) + len(B2) == 42, "HALT: A+B1+B2 != 42"
out("")
out("STOP-CONDITION PASS: buckets sum to 42 exactly.")

SUM = R/"reports/card_derivations/nlog_42_decomposition.txt"
SUM.parent.mkdir(parents=True, exist_ok=True)
SUM.write_text("\n".join(lines) + "\n")
