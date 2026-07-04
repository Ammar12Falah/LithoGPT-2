# LithoGPT-2 Agent Handoff: Current State and Continuation

Prepared 4 July 2026. Purpose: hand this build to a new execution agent with
zero context loss. This document is the state-and-next-steps layer. The frozen
design authority is `docs/HANDOFF.md` (the original blueprint), and where this
document is silent, that handoff governs. Owner: Ammar Falah (GitHub
Ammar12Falah, HF Ammar12Falah, email amarfalah1212@gmail.com, single m).

Read order for a new agent: this file, then `docs/HANDOFF.md` (rules and scope),
then `docs/POSITIONING.md` (claim wording rules), then the per-source access
maps (`docs/KGS_ACCESS.md`, `docs/NLOG_ACCESS.md`, `docs/LICENSE_MATRIX.md`).

## 1. One-paragraph project recap

LithoGPT-2 is an open, physics-gated well-log foundation model plus a QC suite
and a cross-basin benchmark, built on public data (FORCE 2020, NLOG, KGS). It
serves Ammar's O-1A/EB-1A visa evidence and is a pre-startup asset; the durable
assets are the pipeline, QC suite, and benchmark, not the model. The scientific
target is to close a diagnosed porosity/compaction-trend bias from LithoGPT v1
with an explicit, gated physics prior, trained on a multi-basin public corpus.

## 2. Current state (verified facts, not claims)

Repo: 8 commits, 41 tests passing, ruff clean, CI configured (ruff + pytest on
push). The container that produced this cannot reach the data-source domains
(Zenodo, gdngeoservices, kgs.ku.edu) over its shell; those runs happen on
Ammar's pod. All web verification below was done live via the fetch tools.

Done and verified:
- Repository scaffold, config loader, LAS reader, harmonization spine, six-step
  QC suite, and a shared batch engine. All unit-tested.
- FORCE 2020: counts verified against the real files (see section 5). Harmonized
  and QC-passed on all 98 training wells with a real dashboard.
- NLOG: borehole index fully solved and runnable (GeoServer WFS), verified
  against live data. One hop (per-borehole LAS file-list API) is pending, not
  guessed.
- KGS: ingester built against verified endpoints (index + per-year LAS
  archives). QC path built. Neither has been run on real KGS data yet (needs the
  pod download); the QC path was validated on synthetic LAS only.

Canonical curves: GR, RHOB, NPHI, DTC, PEF, SP, CALI, RDEP, RMED, RSHA, DTS.
Auxiliary QC-only curve: BS (bit size, for the washout gate).

## 3. Environment and how to run everything

Runs on any pod with open internet (RunPod Jupyter, CPU is fine; no GPU is
needed until model training in a later phase). Ammar's constraint: browser-based
Jupyter only, no SSH. Office network (Forcepoint) blocks the data domains, so all
ingestion runs on the pod, not his laptop. GitHub push from the pod uses an
HTTPS token, not SSH.

Setup and tests:
```
pip install -e ".[dev]"          # 1 to 3 min; if requires-python complains,
                                 #   use: pip install -r requirements.txt
ruff check src tests scripts     # < 1 s
python -m pytest -q              # ~1 to 6 s, expect 41 passed
```
If the editable install did not run, prefix module commands with `PYTHONPATH=src`.

FORCE (verify counts, then harmonize + QC all 98 training wells):
```
python -m lithogpt2.ingest.force2020 --dry-run    # 5 to 15 s
python -m lithogpt2.ingest.force2020              # 2 to 6 min, downloads ~100 to 300 MB
python scripts/harmonize_force_demo.py --max-wells 12   # smoke, ~1 min
python scripts/run_qc_force.py                    # full 98-well QC pass, ~2 to 4 min
```

KGS (the G1 volume anchor; run these next, see section 8):
```
python -m lithogpt2.ingest.kgs --dry-run          # instant, shows the plan
python -m lithogpt2.ingest.kgs                    # G1 subset ~9,324 LAS, several GB,
                                                  #   download-bound, tens of minutes
python scripts/run_qc_kgs.py                      # harmonize + QC the KGS LAS
python scripts/combine_qc.py                      # combined FORCE + KGS G1 count
```

NLOG (index is runnable now; LAS pull is blocked on two URLs, section 7):
```
python -m lithogpt2.ingest.nlog build-index       # writes the borehole index CSV
```

## 4. Repository map

- `src/lithogpt2/config.py` typed loader for the YAML. Exposes canonical curves,
  aliases, unit conversions, range gates, transforms, QC params (incl.
  washout.require_bitsize), prior-gate thresholds, and the auxiliary-curve path
  (aux_curve, resolve_aux_alias).
- `src/lithogpt2/io/las.py` `read_las` -> `RawWell` (lasio wrapper, tolerant,
  raw-mnemonic-keyed curves).
- `src/lithogpt2/pipeline/harmonize.py` `harmonize_well` (the Week 1 spine):
  alias resolve, null->missing, unit-convert before range-gate, gate-to-missing
  (never clip), log10 for resistivities, nearest-within-tolerance resample onto
  the 0.1524 m grid, per-curve masks, usability flag, and the aux-curve path
  (BS). Also `write_unmapped_csv` and `compute_norm_stats` (train-split-only
  contract).
- `src/lithogpt2/pipeline/qc.py` the six-step QC suite: null assertion, range
  fraction logging, washout flag (honors require_bitsize), Hampel spike filter
  (scipy median_filter, window 11, 4 sigma), minimum-interval pass, dedup hash.
  `run_well_qc` returns a `QCRecord`.
- `src/lithogpt2/pipeline/batch.py` shared engine: `run_batch` (memory-safe,
  streams, catches per-well failures), parquet writer, per-source report writer,
  adaptive `build_dashboard`, `merged_pass_count`.
- `src/lithogpt2/pipeline/trend.py` SKELETON, guarded. Weeks 3 to 4 (Athy fit +
  carbonate gate). Do not build yet.
- `src/lithogpt2/ingest/_http.py` `PoliteFetcher`: throttled (>= 2 s/host),
  resumable (manifest + sha256 skip), robots-aware (respect_robots togglable),
  checksummed, stdlib only.
- `src/lithogpt2/ingest/force2020.py` FORCE ingester (GitHub-raw CSVs, unzip
  train, verify 98/10, stop on mismatch) plus `iter_force_wells` (CSV ->
  RawWell) and an optional `--with-las` Zenodo path (robots disabled for the
  direct DOI download).
- `src/lithogpt2/ingest/nlog.py` NLOG ingester: `build_index` (runnable, from the
  GeoServer WFS), `resolve_las_urls` (stub, pending the file-list API),
  `ingest_from_index` (resumable LAS fetch once URLs exist).
- `src/lithogpt2/ingest/kgs.py` KGS ingester: `fetch_index`, `parse_index`
  (delimiter-sniffing), `fetch_archives` (per-year zips, resumable),
  `unpack_las`, `ingest`. `ARCHIVE_ZIPS` pins each year's size/count;
  `RECOMMENDED_G1_YEARS` = 2024 + 2014 + 2016 (~9,324 LAS).
- `src/lithogpt2/ingest/las_dir.py` `iter_las_wells` tolerant LAS-directory
  reader (for KGS and any LAS source).
- `scripts/` runners: `harmonize_force_demo.py`, `run_qc_force.py`,
  `run_qc_kgs.py`, `combine_qc.py`.
- `configs/mnemonic_aliases.yaml` the alias/QC/prior-gate config (advisor owns
  this file; BS was added there under auxiliary_curves with require_bitsize).
- `configs/force2020/` pinned scoring artifacts (penalty_matrix.npy sha256 in
  pinned.json), starter notebook, and `norm_stats.json` (PROVISIONAL).
- `docs/` HANDOFF (blueprint), POSITIONING, EXECUTION_PLAN_v2, FEASIBILITY,
  LICENSE_MATRIX, NLOG_ACCESS, KGS_ACCESS, and this file.
- `reports/` FORCE QC records, coverage, dashboard, unmapped log, and status
  notes (status_week1, status_wo01, status_kgs, status_kgs_qc). These FORCE
  artifacts are from real data. No KGS/NLOG result artifacts exist yet.

## 5. Data sources: verified endpoints and status

FORCE 2020 (Norway). VERIFIED and used. Public release is 118 wells total = 98
training + 10 open leaderboard test + 10 blind final test. Counts confirmed from
the real files: train.csv 98 wells / 1,170,511 rows, open test 10, blind 10.
Labelled competition CSVs come from the GitHub repo
(`bolgebrygg/Force-2020-Machine-Learning-competition`, path
`lithology_competition/data/`, raw.githubusercontent.com, no robots issue).
train.zip contains train.csv. A LAS-format mirror plus NPD spreadsheets is on
Zenodo DOI 10.5281/zenodo.4351156, but Zenodo robots.txt blocks automated file
fetch, so that path is opt-in (`--with-las`, robots disabled for the direct DOI
download). License: logs NLOD 2.0, labels CC-BY-4.0; attribution Bormann et al.
2020. REDISTRIBUTABLE.

NLOG (Netherlands). Index VERIFIED and runnable. Borehole index is NLOG's
official GeoServer WFS: base `https://www.gdngeoservices.nl/geoserver/nlog/ows`,
layer `nlog:gdw_ng_wll_all_utm`, `outputFormat=json`. Each borehole carries
BOREHOLE_CODE, BOREHOLE_NAME, UWI, NITG_NUMBER, ON_OFFSHORE_CODE, PUBLIC_AS_OF
(confidentiality release date), coords, and URL (mapviewer id). `build_index`
consumes this. Logs released after a five-year confidentiality period (cited:
https://www.nlog.nl/en/boreholes). Raw-redistribution UNCLEAR (no named open
license). PENDING: the per-borehole LAS file-list API (section 7).

KGS (Kansas). VERIFIED, ingester built, NOT yet run. The volume anchor: 21,780
digital LAS logs as of 31 Dec 2024. Metadata index:
`https://www.kgs.ku.edu/PRS/Ora_Archive/ks_las_files.zip`. Per-year LAS archives:
`https://www.kgs.ku.edu/PRS/Scans/Log_Summary/<name>.zip` (1999, 2001_2005,
2006_2011, 2012 ... 2025; sizes/counts pinned in `kgs.ARCHIVE_ZIPS`). LAS free
after a two-year confidentiality period for public service and research (cited:
https://www.kgs.ku.edu/Publications/Bulletins/LA/02_digital.html).
Raw-redistribution UNCLEAR / partly restricted (some KGS-hosted data is
IHS-licensed). Do not confuse the SURVEY (kgs.ku.edu) with the SOCIETY
(kgslibrary.com, a separate paid library).

Default release posture across all three: pipeline + weights + attribution, no
raw mirror. This is safe for all three even with the two UNCLEAR rows.

## 6. What has run on REAL data vs synthetic

Real: FORCE count verification, and the full harmonize + QC pass over all 98
FORCE training wells. From `reports/force2020_qc_records.csv`: 98/98 pass
minimum-interval; 59 wells washout-flagged; 29 wells no-bit-size (washout
skipped, never assuming a nominal size); Hampel modified fraction 3.3 to 4.6% per
curve; dedup 98 unique of 98. `norm_stats.json` is PROVISIONAL (98 FORCE-only
training wells, no test leakage; superseded at G2 by stats on the frozen
multi-basin training split).

Synthetic only (validated, then deleted so nothing synthetic ships as real): the
KGS QC runner and the combined counter. On synthetic LAS the combine reported
FORCE 98 (Norway) + KGS 3 (Kansas) = 101 QC-passing across 2 continents, G1
correctly "not yet met". The real KGS numbers do not exist yet.

## 7. Pending inputs (must be supplied; do not guess)

1. NLOG per-borehole LAS file-list API: given a mapviewer borehole id (from the
   WFS URL field), the JSON call that lists that borehole's files, and the
   file-download URL. Capture: open a released borehole in the map viewer, open
   its Logs tab, open DevTools Network (F12), click a LAS download, copy the two
   request URLs. Then fill in `nlog.resolve_las_urls` and the bulk pull runs.
   Recipe in `docs/NLOG_ACCESS.md`. NLOG is NOT on the G1 critical path.
2. Hugging Face hub / GitHub open-weights search to close the "no open-weights
   well-log model exists" hedge in POSITIONING.md. Needs Ammar's approval to run
   the HF hub tool, or he runs it.
3. G2 tokenizer acceptance bar sign-off (proposed 5% relative degradation).
   Needed before tokenizer training (a later phase).
4. Benchmark name decision (week 3, collision-check vs WellLogBench).

## 8. Immediate next steps (in order)

1. Run the KGS pull on the pod: `python -m lithogpt2.ingest.kgs` (G1 subset,
   several GB, tens of minutes, download-bound, resumable). Then
   `python scripts/run_qc_kgs.py` and `python scripts/combine_qc.py`. This
   produces the real cross-continent QC-passing count, which is the Gate G1
   evidence the advisor wants to review.
2. Triage the KGS unmapped mnemonics that appear in
   `reports/kgs_unmapped_mnemonics.csv`. KGS LAS will surface many. Extend
   `configs/mnemonic_aliases.yaml` from observed data only, never guessed, and
   only after Ammar/advisor triage (this is the documented weekly step).
3. When the two NLOG URLs arrive, fill `nlog.resolve_las_urls`, then
   `python -m lithogpt2.ingest.nlog build-index` and the resumable LAS fetch.
4. Gate G1 review (end of week 2 target): 5,000+ QC-passing wells across two
   continents. KGS alone clears the count. Produce the G1 milestone report in the
   fixed template (HANDOFF Section 11.3) and stop for advisor approval.

Unblocked build work available now if data runs are waiting: dedup hardening for
cross-source overlap (currently a near-noop within one source; needed when KGS
and NLOG overlap) and the dataset-card scaffold that G2 needs. Both are in scope
and do not pull weeks 3 to 4 work forward.

## 9. Decisions locked (do not relitigate)

- BS is an auxiliary QC-only curve (washout gate), never a modeling target, never
  in the canonical count or the min-usable check. Already in the config.
- trend.py (Athy fit + carbonate gate) stays parked for weeks 3 to 4. Do not
  build it now even though PEF coverage exists. It needs the full corpus and
  basin groups defined first.
- FORCE count wording is always 118 = 98 + 10 + 10. Never an unlabeled 108/118.
- norm_stats.json is provisional and FORCE-only until recomputed on the frozen
  multi-basin training split at G2 (training split only).
- The real G1 path is KGS (volume), not NLOG. Do not treat the NLOG LAS hop as a
  blocker.

## 10. Gate map (from HANDOFF Section 11)

- G1 (end week 2): 5,000+ QC-passing wells, two continents, license matrix
  complete. KGS is the anchor.
- G2 (weeks 3 to 4): tokenizer meets the numeric bar; model size decided by the
  Section 7.2 rule; test manifest frozen and hashed; carbonate gate validated
  against FORCE lithofacies labels; benchmark name decided.
- G3 (weeks 5 to 7): main model beats the small debug run on dev; imputation at
  least competitive with XGBoost in-basin and better cross-basin.
- Then evaluation, release candidate, paper draft, outreach kit (Ammar sends
  outreach; the agent never does).

## 11. Operating rules for the agent (condensed from HANDOFF Section 0)

1. Never fabricate. Every number is backed by a file path or command output.
   Report failures verbatim. Never write a results table before the runs exist.
2. Mark UNVERIFIED / ASSUMPTION. Never edit POSITIONING.md claims; flag
   contradictions.
3. Ship weekly: a repo push and a status note in the fixed format.
4. Respect the scope freeze (banned: diffusion/flow backbone, synthetic corpus
   inflation, LoRA-as-method, more than one benchmark, models above 100M params,
   sources beyond FORCE/NLOG/KGS).
5. Money/machines: state expected duration at the top before any job over 1 hour;
   jobs over 4 hours or 5 USD need Ammar's confirmation; track cumulative spend.
   Nothing so far has used GPU or spent money.
6. Never take public actions without sign-off (weights, demo, dataset card,
   outreach). Repo push is pre-approved. The agent never sends outreach.
7. Protect data: never delete raw, never touch a frozen manifest, norm stats on
   the training split only.
8. Do not guess endpoints or aliases. Flag and escalate. This is why the NLOG LAS
   URL and any un-triaged mnemonics stay pending rather than invented.

## 12. Ammar's standing output preferences (enforce in every deliverable)

- No em dashes anywhere.
- Markdown (.md) for reports/plans/analysis; never HTML or styled PDF unless it
  is a frontend component or explicitly requested.
- Dark mode for any UI (the dashboards are dark-mode HTML).
- State long-job durations prominently at the top.
- No placeholder brackets in documents; flag missing info in the chat message
  only.
- Never include salary, passport, employee numbers, or supervisor names in any
  document unless explicitly asked.
- Direct, high-signal communication.

## 13. Known gotchas

- The build container's shell reaches only GitHub/PyPI, not the data domains.
  Ingestion runs on the pod. web_fetch/web_search and the HF tools are separate.
- Git push from the pod uses an HTTPS token (fine-grained, Contents read/write),
  not SSH. If a push is rejected as non-fast-forward, the remote already has
  commits; reconcile with pull --rebase or force with intent.
- KGS memory: the batch engine streams and does not retain wells by default, so
  do not set keep_harmonized=True on the full KGS corpus.
- Hampel with a perfectly constant neighbourhood has MAD = 0 and cannot flag an
  isolated spike; this is a known Hampel property and does not occur on real logs
  (real KGS/FORCE curves have noise; FORCE modified 3 to 4%).
- Zenodo robots.txt blocks automated file fetch; the FORCE path deliberately uses
  the GitHub-raw CSVs instead.
- Do not commit synthetic-data-derived reports as if real (the KGS synthetic run
  artifacts were deleted for this reason).

## 14. Verification log (what was checked live, 4 July 2026)

- FORCE counts: downloaded train.zip and the test CSVs from GitHub raw, counted
  the WELL column (98 / 10 / 10).
- NLOG index: fetched the GeoServer WFS GetFeature GeoJSON; confirmed layer,
  format, and the per-borehole attribute schema on live data.
- KGS: read the Magellan Logs page and the PRS/Scans/Log_Summary archive listing;
  confirmed the index zip, the per-year archive base path (two hrefs explicit),
  the 21,780 count, and the two-year-confidentiality license page.
- NLOG five-year confidentiality: cited to nlog.nl/en/boreholes.
