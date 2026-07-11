# LithoGPT-2 G2 Progress Report: NLOG Re-Fetch Complete

Date: 11 July 2026
Scope: G2 alias-triage and sentinel-clean window. QC/corpus only. No case-adjacent work, no model work.

## 1. Headline
NLOG re-fetch + re-QC complete: 5,004 boreholes processed, 2,355 QC-passing. SN and LN alias
admissions delivered the prize: RSHA coverage nearly tripled, RMED more than tripled, QC-passing
count rose by 543, and the pass rate rose from 36.3 to 47.1 percent (count and rate up together).
Run finished, checkpointed off-pod, processes stopped. Remaining before freeze: failure taxonomy,
dataset-card paragraphs, CI-green-on-main, corpus freeze (stops for advisor approval).

## 2. Four-number coverage (before = reports/_pre_alias/, commit 206af98; after = final records)
- Wells processed: 4,996 -> 5,004 (+8)
- QC-passing wells: 1,812 -> 2,355 (+543)
- RSHA coverage: 11.4% -> 29.6% (+18.2 pt)  [fraction of PROCESSED wells]
- RMED coverage: 5.5% -> 17.2% (+11.7 pt)   [fraction of PROCESSED wells]
- RDEP +0.6 pt (correct: nothing aliased to deep); GR +1.2, RHOB +0.9, NPHI +0.7, DTC +1.5, CALI +1.6

## 3. The pass rate ROSE (corrected)
Pre-alias 1,812/4,996 = 36.3%. Post-alias 2,355/5,004 = 47.1%. +10.8 points, plus +543 wells.
Both runs used the SAME select-primary-plus-fallback policy, so the comparison is valid and there
is no selection-strictness effect and no regression. An earlier draft carried a false-regression
narrative on a miscomputed baseline; corrected here before it reached the card. True story: correct
aliasing of old tool names (SN, LN) raised count and rate together, using no new data.
- 384 hard failures with recorded reasons (reports/nlog_failures.csv); remainder are floor QC-fails.
- select all (every file per borehole) is documented future-work, not a re-opening of this window.

## 4. Sentinel-clean (completed earlier; recap)
KGS parquets cleaned of fills: resistivity ceiling (100000 ohmm), GR floor (0.0, edge padding),
bit-exact RDEP 3777 ohmm (219+ wells, bit-exactness forensic). Verified residual 0, value/mask
consistent across 9,307 files, physics intact. General isolated-spike detector rejected (CALI
bit-size clustering indistinguishable from fill by isolation). Detail: reports/kgs_sentinel_clean_report.md (e190bfa).

## 5. Committed and durable
Main: alias admission, per-well unmapped column, rail rule + e2e tests, pre-alias snapshot (206af98),
KGS report (e190bfa), advisor-item notes + verify rule (834e1a3). Checkpoints branch: final re-fetch
records (5,004 boreholes, 2,355 passing). Per-well unmapped column populated corpus-wide.
Europe now 2,355 vs the 1,500 bar; combined corpus ~8,789.

## 6. Remaining before the G2 gate
Failure taxonomy; coverage report deliverable; merge final records to main; dataset card;
all-but-5 boreholes; decision-capture; corpus freeze; G2 milestone report then STOP.

## 7. Freeze checklist (advisor, five items)
1. Rail-rule NLOG impact reported with coverage: wells with nulled rail masses, any dropped below
   floor, so +543 decomposes into alias gains vs sentinel losses.
2. All-but-13 is stale: retry recovered 8 -> disposition is all-but-5, per-borehole reasons for five.
3. Outcome taxonomy, fixed denominators, once: 5,004 processed / 2,355 passing / 384 hard fail /
   remainder floor-fail. Every coverage % labeled with denominator (coverage figures are of PROCESSED).
4. CI red on main NOT deferrable past freeze. Read actual CI error, then fix (hypothesis: pin
   numpy>=1.26.4,<2.0), then green. Final records must be on MAIN before the manifest hash.
5. Freeze order: splits in one op; manifest hash; norm stats on frozen train only; card; tarball
   + off-pod copy; both hashes before the word freeze.

## 8. Process honesty
Agent shipped a wrong baseline in an earlier draft and built a false-regression narrative for a drop
that never happened (true pre-alias rate 36.3%, rate rose to 47.1%). Intermediate self-correction
caught a count-vs-rate confusion but left the wrong baseline; advisor caught the residual at review;
corrected before reaching the card. A false regression is a reconciliation failure as much as a false
gain. KGS clean took several disclosed iterations (frequency-gate bug, mask-update bug, two defective
verifier cells), each caught before a destructive step.
