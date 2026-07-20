"""Re-derive the NLOG borehole disposition from COMMITTED artifacts (card evidence).

OUTSIDE the hashed set: this script, log_index.csv.gz, borehole_index.csv, and
nlog_qc_records.csv are not in the 24-file qc_code_sha256 set nor the manifest pin
payload, so nothing here moves qc_code_sha256 or the FINAL manifest d5b35a00.

Sources (all committed):
  data/raw/nlog/borehole_index.csv   (6609 boreholes)
  data/raw/nlog/log_index.csv.gz     (log documents; distinct boreholes = log-bearing)
  reports/nlog_qc_records.csv        (processed boreholes)
"""
import hashlib
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
BH = ROOT/"data/raw/nlog/borehole_index.csv"
LI = ROOT/"data/raw/nlog/log_index.csv.gz"
QC = ROOT/"reports/nlog_qc_records.csv"

bh = pd.read_csv(BH); bh["well_id"] = bh["well_id"].astype(str)
li = pd.read_csv(LI); li["well_id"] = li["well_id"].astype(str)   # pandas auto-gunzips .gz
qc = pd.read_csv(QC); qc["well_id"] = qc["well_id"].astype(str)

bh_ids   = set(bh["well_id"])
log_bh   = set(li["well_id"])
proc_set = set(qc["well_id"].str.split("__").str[0])

n_bore          = len(bh_ids)                       # 6609
n_proc          = len(proc_set & bh_ids)            # processed boreholes present in index
never_proc      = len(bh_ids - proc_set)            # 6609 - processed
log_bearing     = len(bh_ids & log_bh)              # boreholes with >=1 log doc
no_log          = len(bh_ids - log_bh)              # no log document
log_unproc      = len((bh_ids & log_bh) - proc_set) # has log, never processed
onoff           = bh["on_offshore"].value_counts().to_dict()
on, off         = int(onoff.get("ON", 0)), int(onoff.get("OFF", 0))
proc_not_in_idx = len(proc_set - bh_ids)

print("=== NLOG disposition (from committed artifacts) ===")
print(f"borehole_index boreholes      = {n_bore}")
print(f"processed boreholes (in index)= {n_proc}   (processed not in index = {proc_not_in_idx})")
print(f"never-processed               = {never_proc}")
print(f"  no-log-document             = {no_log}")
print(f"  log-bearing but unprocessed = {log_unproc}")
print(f"log-bearing subtotal          = {log_bearing}")
print(f"on/offshore                   = ON {on} / OFF {off} (sum {on+off})")

# STOP-CONDITIONS (Plan): halt on any contradiction of a frozen fact
assert no_log + log_unproc == never_proc, f"HALT: {no_log}+{log_unproc} != never_proc {never_proc}"
assert never_proc == 1605, f"HALT: never_proc {never_proc} != 1605 (contradicts 6609-5004)"
assert on + off == n_bore, f"HALT: on+off {on+off} != {n_bore}"
print("STOP-CONDITIONS PASS: no_log + log_unproc == never_proc == 1605 ; on+off == 6609")

sha = hashlib.sha256(LI.read_bytes()).hexdigest()
print(f"log_index.csv.gz sha256 = {sha}")
