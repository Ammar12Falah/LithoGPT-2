# WO-01 status note (BS + QC suite)

Shipped:
- BS integrated as an auxiliary QC-only curve via the config's auxiliary_curves
  path (config loader + harmonize.py). BS is harmonized (inches, range gate
  [3.0, 30.0], out-of-range to missing) and written to the processed parquet as
  an auxiliary column; it is excluded from the canonical curve count and the
  minimum-usable-interval check. Confirmed captured: BS is gone from
  reports/unmapped_mnemonics.csv; ROP, DRHO, MUDWEIGHT, RXO, RMIC, ROPA remain.
- qc.py built with all six steps in handoff order (null assertion, range-gate
  fraction logging, washout flag, Hampel spike filter, minimum interval, dedup),
  each with an explicit contract and per-well logging. Washout honors
  require_bitsize: no nominal bit size is ever assumed.
- Full FORCE QC pass over all 98 training wells (the 10 open-leaderboard and 10
  blind-final test wells were not read). Artifacts: reports/force2020_qc_records.csv
  (98 rows, 36 columns), dashboard in reports/qc_force2020/ (coverage_heatmap.png,
  depth_hist.png, washout_summary.png, index.html), processed parquet in
  data/processed/force2020/ (gitignored, regenerate with scripts/run_qc_force.py).

Numbers (all from reports/force2020_qc_records.csv):
- minimum-interval pass: 98/98.
- washout flagged with washed intervals (BS present): 59 wells.
- no bit size, washout skipped (no_bitsize=true): 29 wells.
- BS present but no washed intervals: 10 wells (59 + 29 + 10 = 98).
- Hampel mean modified fraction per curve: 0.033 to 0.046 (GR 0.033, DTS 0.046).
- dedup: 98 unique hashes of 98 (near-noop within FORCE, as expected).

Counts reconciled (advisor): FORCE public release is 118 wells total = 98
training + 10 open leaderboard test + 10 blind final test. Stated this way in
configs/force2020/pinned.json, docs/LICENSE_MATRIX.md, and README.md.

norm_stats.json: annotated provisional. Computed on 98 FORCE-only training wells
from train.zip only; the 20 test wells were not read (no leakage). Superseded at
Gate G2 by stats recomputed on the frozen multi-basin training split.

Tests: 30 passing (added qc.py tests: range-gate boundary, washout with and
without BS, Hampel on a spike, minimum-interval just above and below, dedup
identical/near-identical/different, and an end-to-end run_well_qc record). Ruff
clean.

NLOG five-year confidentiality period now cited (source:
https://www.nlog.nl/en/boreholes) in docs/NLOG_ACCESS.md and the license matrix,
rather than asserted.

Blocked: nothing for this work order. NLOG bulk LAS still awaits the two
DevTools URLs (Ammar capturing); not on the G1 critical path.

Spend cumulative: 0 A40-hours, 0 USD (CPU-only harmonization and QC).

Next (per advisor): KGS bulk ingestion is the volume anchor for Gate G1's
5,000-well target and is the next work order. NLOG slots in once the two URLs
arrive.

Out of scope for WO-01 and untouched: trend.py / Athy fit / carbonate gate
(weeks 3 to 4), any KGS or NLOG ingestion run, any split or manifest freeze, any
model / tokenizer / GPU work.
