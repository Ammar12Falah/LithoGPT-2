# KGS harmonize + QC runner status note

Shipped (code, tested; awaiting the real KGS download to produce real numbers):
- Shared batch engine `src/lithogpt2/pipeline/batch.py`: one harmonize + six-step
  QC code path for every source. Memory-safe (streams; does not retain wells by
  default, so tens of thousands of KGS wells process without holding the corpus
  in RAM), and per-well failures are caught and recorded so one bad LAS never
  aborts a bulk run. Includes processed-parquet writing, per-source report
  writing, an adaptive dashboard (per-well heatmap for small N, per-curve mean
  coverage for large N), and merged_pass_count.
- `src/lithogpt2/ingest/las_dir.py`: tolerant LAS-directory reader
  (iter_las_wells) that turns KGS LAS files into RawWell via read_las, recording
  unreadable files as failures.
- `scripts/run_qc_kgs.py`: KGS harmonize + QC pass -> data/processed/kgs/*.parquet,
  reports/kgs_qc_records.csv, kgs_coverage.csv, kgs_unmapped_mnemonics.csv,
  kgs_failures.csv, and reports/qc_kgs/ dashboard.
- `scripts/combine_qc.py`: combined Gate G1 evidence across sources (FORCE =
  Norway, KGS = Kansas), printing total QC-passing across continents and writing
  reports/qc_combined/ with a per-source pass figure. G1 logic: >= 5,000
  QC-passing across 2+ continents.

Validated end to end on synthetic LAS (not committed, since they are not real
data): 3 synthetic KGS wells harmonized and QC-passed through run_qc_kgs.py with
washout flagging working, and combine_qc.py reported FORCE 98 (Norway) + KGS 3
(Kansas) = 101 QC-passing across 2 continents, G1 correctly "not yet met". The
synthetic-derived reports were removed; only the real FORCE artifacts remain.

Tests: 41 passing (added LAS-dir read of two wells, bulk failure recording,
max-wells cap, run_batch end to end with parquet, and merged_pass_count). Ruff
clean.

Next (on the pod, after the KGS download):
  python -m lithogpt2.ingest.kgs          # index + G1 subset + unpack
  python scripts/run_qc_kgs.py            # harmonize + QC the KGS LAS
  python scripts/combine_qc.py            # combined FORCE + KGS G1 count
This produces the real cross-continent QC-passing count for the advisor to check
before G1. KGS mnemonics will surface many unmapped entries in
reports/kgs_unmapped_mnemonics.csv for weekly alias triage (extend from observed
data, never guessed).

Spend cumulative: 0 A40-hours, 0 USD.
