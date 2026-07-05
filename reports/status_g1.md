# Gate G1 milestone report

## Gate and date
Gate G1 (target end of week 2). Date: 2026-07-05. Repo commit: `e21b2da`.
Overall: MET.

## Shipped
- FORCE 2020 (Norway, North Sea): 98 wells harmonized and QC'd, records at `reports/force2020_qc_records.csv`.
- KGS (Kansas, USA): 8084 wells harmonized and QC'd, records at `reports/kgs_qc_records.csv`.
- Combined G1 dashboard: `reports/qc_combined/index.html` (from scripts/combine_qc.py).
- Repo state at commit `e21b2da`.

## Metrics
- FORCE 2020 (Norway, North Sea): wells=98, QC-passing (min-interval)=98, unreadable=0, unmapped rows=6. Backing: `reports/force2020_qc_records.csv`.
- KGS (Kansas, USA): wells=8084, QC-passing (min-interval)=5546, unreadable=50, unmapped rows=1929. Backing: `reports/kgs_qc_records.csv`.
- TOTAL: wells=8182, QC-passing=5644, continents=2 (Europe, North America). Backing: the per-source CSVs above and `scripts/combine_qc.py` stdout.

## Gate criteria check
- PASS: 5,000+ QC-passing wells (8,000 stretch). Actual QC-passing = 5644. Evidence: per-source records CSVs.
- PASS: two or more continents. Actual = 2 (Europe, North America). Evidence: source map.
- PASS: license matrix complete. Committed at `docs/LICENSE_MATRIX.md` (FORCE redistributable; NLOG and KGS raw-redistribution unclear; release posture is pipeline plus weights plus attribution, no raw mirror, which is safe for all three).

## Deviations from the handoff
None recorded for weeks 1 to 2. CONFIRM before advisor review.

## Blockers and escalations
- NLOG LAS file-list API still pending (two URLs to capture, docs/NLOG_ACCESS.md). NLOG is NOT on the G1 critical path.

## Spend
No paid compute or GPU hours recorded to date. Weeks 1 to 2 ran on CPU pods and the free FORCE and GitHub paths. Cap: 150 hours. CONFIRM before advisor review.

## Pending inputs needed from Ammar
- NLOG per-borehole LAS file-list API: the two request URLs (file-list JSON and file-download), captured per docs/NLOG_ACCESS.md. NOT on the G1 critical path.
- Direct Hugging Face hub and GitHub search confirming no existing open-weights well-log pretrained model (closes the POSITIONING.md hedge).
- G2 tokenizer bar sign-off (proposed default: 5 percent relative degradation).
- Benchmark name decision (week 3, collision-checked vs WellLogBench).

## Next period plan
G2 (weeks 3 to 4): dedup finalization across sources; carbonate gate built and
validated on FORCE lithofacies labels; Athy trend fits per basin group; tokenizer
level sweep against the numeric bar; dataset card with real counts; test manifest
frozen and hashed; benchmark name collision-checked and decided. Model size set by
the HANDOFF Section 7.2 rule at G2.
