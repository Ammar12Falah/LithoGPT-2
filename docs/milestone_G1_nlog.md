# Milestone Report: G1 Diversity Condition (NLOG Ingestion, Task A)

Gate: G1 corpus-diversity condition (NLOG European wells)
Date: 9 July 2026
Repo HEAD at report: af769bb (main, pushed)
Prepared by: execution agent. Gate closure is recorded by Ammar after advisor review; this report is not a self-certification.

## Shipped
- NLOG Phase B crawl complete. 4,996 of ~5,009 log-bearing boreholes processed. Artifact: reports/nlog_qc_records.csv (af769bb).
- Full-run QC dashboard: reports/qc_nlog/ (coverage, depth histogram, washout, index.html).
- Crawl fixes committed and tested during the run: fallback cap to top-5 candidates per borehole (0e9471f); --reprocess-ids-file added to run_qc_nlog.py to unblock fallback re-QC (c7fc220). Test suite: 63 passing.
- Off-pod evidence tarball built, hashed, and verified. Contents: nlog_qc_records.csv, qc_nlog dashboard, nlog_coverage.csv, nlog_unmapped_mnemonics.csv, nlog_failures.csv, borehole_index.csv, log_index.csv, LICENSE_MATRIX.md, and a sha256 manifest. Tarball sha256: 037dc72abc357052a89c338936e848a3789abd8e08a3cfedc20ac295352f7019. Downloaded off-pod and hash-verified on the owner's machine (match confirmed).

## Metrics (each backed by reports/nlog_qc_records.csv at af769bb)
- QC-passing European (NLOG) wells: 1,812.
- Boreholes processed: 4,996. Overall pass rate: 36.3 percent.
- Pass rate held near 44 percent through the first ~3,660 boreholes, then fell across the tail as the crawl reached old, sparse, zero-canonical-curve wells that cannot meet the 3-curve / 100 m floor. The mid-run projection (2,112 to 2,273, 95 percent interval) assumed a uniform rate and overshot for this reason. 1,812 is the true count, reported over the point estimate per the interval-discipline instruction.
- Combined corpus: ~1,812 NLOG + 6,336 KGS + 98 FORCE = ~8,246 QC-passing wells across two continents.

## Gate criteria check
- G1 floor, 5,000+ QC-passing wells across two continents: MET. ~8,246 wells, North America and Europe.
- Diversity condition, at least 1,500 QC-passing European wells or a written rescope: MET. 1,812 European wells, 312 over the bar (~20 percent headroom). No rescope required.
- Evidence tarball off-pod with recorded hash (advisor closure requirement): MET. sha256 above, verified off-pod.
- Status: diversity condition MET; closure requirement satisfied; awaiting the recorded GATE APPROVED note.

## Deviations from handoff
- Two in-flight code fixes (fallback cap, reprocess flag), both tested and committed, neither touching the banned list or the frozen manifest. Justified as pipeline bug/efficiency fixes within existing scope.
- Infrastructure only: the work pod's network volume was 10 GB (not the assumed 15 GB) and was expanded to 50 GB mid-task to hold accumulating parquets. Region remained EU-SE-1. No data or scope impact.

## Blockers and escalations
- 13 unprocessed boreholes (4,996 of 5,009). Plan: retry once, then record as permanent failures with per-borehole reasons, so the dataset card reads "all but 13, disposition recorded" rather than an approximate total.
- NLOG index denominator has drifted across reports (6,609 access-report / ~6,572 elsewhere / ~5,009 log-bearing). Expected for a rolling-release catalog. The dataset card must pin the index snapshot date, the committed index file, and released-total plus log-bearing counts from that snapshot, so every percentage has a fixed base.

## Spend
- Approximate actual cost of the NLOG work: ~15 USD. This covers the ~19-hour crawl on an A40-class pod plus debugging pods, stranded CPU pods, and idle A40 time during the pod-mount recovery.
- Budget context: planning cap 150 A40-hours (~66 USD), absolute ceiling 300 hours. Pod balance confirmed at 375 USD. Spend is not a constraint on remaining work.
- Note: this was a CPU-and-network-bound job that ran on a GPU pod. Future CPU-only jobs run on CPU pods, and pods are stopped when idle, to keep the A40 budget reserved for training.

## Decisions recorded this period
- Benchmark name: BasinShift, confirmed. Public web collision check passed (no existing benchmark, dataset, or model of that name; no collision with WellLogBench). Pending a final direct Hugging Face Hub and GitHub name search before publication. Note: the name follows the common "[domain]Shift" ML-benchmark convention (RainShift, TableShift, DivShift, ContextShift), which makes it legible but not linguistically distinctive.
- Architecture / transfer-track ruling captured separately in the benchmark doc and decisions log (from-scratch method confirmed; TS-FM baseline moved to post-freeze with a pre-registered dev-only tripwire; blind wells reserved for final scoring only).

## Pending inputs from owner (Section 12.3 status)
- User-agent contact email: RESOLVED (owner's address in the fetcher user-agent since the conditions patch). Struck.
- RunPod balance vs cap: CONFIRMED, 375 USD against a ~66 USD planning cap.
- Milestone evidence tarball downloaded off-pod: DONE, hash-verified.
- Still open: direct Hugging Face and GitHub search confirming no existing open-weights well-log pretrained model (closes the POSITIONING hedge); final HF Hub / GitHub name search for BasinShift.

## Next period plan (advisor-sequenced)
1. Alias triage, round two. Timebox two working days plus one re-QC pass. Scope only mnemonics appearing in at least 50 boreholes, value-checked and unambiguous. Target two populations: failures flippable to passing, and passing wells that would gain a benchmark target curve (DTC, RHOB, NPHI first). Report two numbers: wells added, and per-target-curve coverage delta on the existing corpus. Freeze regardless of result.
2. Commit the decision-capture text (transfer-track ruling) to the benchmark doc and decisions log.
3. Retry and dispose of the 13 unprocessed boreholes; pin the index denominator in the dataset card.
4. Corpus freeze (G2 Task C): manifest hashed, norm stats recomputed on the frozen train split, dataset card with the KGS alias-jump explanation, the NLOG snapshot pinning, and a pass-rate-by-vintage chart explaining the 44-to-36 falloff.
- No tokenizer or benchmark work begins before the freeze manifest hash exists.
