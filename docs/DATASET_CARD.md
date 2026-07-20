# LithoGPT-2 Corpus — Dataset Card
**Frozen against manifest `d5b35a00`** (`corpus_manifest.json`, sha256
`d5b35a00ffa49aab7f7e634013c238aa1fc989a17e3ad1c5a5d83f7606e3a8a9`).
Split-generation commit `d4113797`; QC-code pin `qc_code_sha256 = e12d4b64`;
seed `20260715`. Every figure is derived from a committed artifact on `origin/main` at or
below evidence HEAD `9c6b9fc`. Where a figure cannot be recovered from committed artifacts,
the card says so explicitly rather than estimating.
This card is a contract. It states what the corpus contains, how it was selected and
split, what was cleaned, and — with equal care — what is *not* recoverable and why.
---
## 1. What this is
An open, physics-informed corpus of public well logs for cross-basin generalization
benchmarking (BasinShift) and for training LithoGPT-2. Three public sources across two
continents:
- **FORCE 2020** (Norway, North Sea) — DOI 10.5281/zenodo.4351156, licence NOLD 2.0.
- **NLOG** (Netherlands) — public borehole releases.
- **KGS** (Kansas Geological Survey, USA) — public well logs on the PLSS grid.
QC-passing: **at least 3 canonical curves covering at least 100 m** (`min_curves = 3`,
`min_interval_m = 100`).
---
## 2. Corpus counts (frozen)
| Source | Ingested / Processed | QC-passing | Pass rate |
|---|---|---|---|
| KGS | 9,307 ingested | 6,336 | 68.1% |
| NLOG | 5,004 processed | 2,355 | 47.1% |
| FORCE 2020 | 98 | 98 | 100% |
| **Combined passing** | | **8,789** | |
Manifest `row_count` is **8,809 = 8,789 + 20**, the 20 being the FORCE open (10) and blind
(10) wells the manifest carries in full while the passing count folds FORCE in as its 98
train wells (sample vs census; stated wherever the two differ).
**Count growth from G1.** At the G1 milestone the KGS-only counts were **8,084 ingested /
5,546 passing** (`reports/status_g1.md`); the combined KGS+FORCE G1 total was 8,182 / 5,644.
KGS subsequently rose to the frozen **9,307 / 6,336** through additional well recovery and
the audited alias admissions. *The committed artifacts record the before/after counts but
do not document a specific recovery mechanism; no mechanism is asserted here beyond what is
committed.*
*Source: `reports/{kgs,nlog,force2020}_qc_records.csv`, `corpus_manifest.json`,
`reports/status_g1.md`.*
---
## 3. Splits (frozen, spatial-only)
Splits are **spatial blocks only** — random well-level splits are banned (spatial
autocorrelation leaks). KGS blocks on the PLSS township–range grid; NLOG blocks
geographically from index lon/lat; FORCE stays exactly official, never re-cut. Wells with
unresolvable coordinates go to **train**, never a holdout.
| Source | Train | Dev | Holdout | Open | Blind |
|---|---|---|---|---|---|
| KGS | 5,734 | 339 | 263 (test_kgs) | | |
| NLOG | 1,757 | 257 | 341 (test_nlog) | | |
| FORCE 2020 | 98 | | | 10 | 10 |
| **Total** | | | | | **8,809** |
**Holdout sizing.** `test_kgs` = 263 (4.15% of KGS passing); `test_nlog` = 341 (14.48% of
NLOG passing). Both exceed the ~250 cap and ~10% target. Reviewed and signed (D3): block
integrity over soft size targets; 263 / 341 ample for per-curve error estimation. A
deliberate, recorded choice, not drift.
**Selection is a floor (R3).** The corpus was built **select-primary with fallback**: for
each well the primary log file is selected, with fallback to alternates. Recovered coverage
is therefore a **floor** — a newly aliased curve sitting only in an unfetched secondary file
can be missed. Select-all is documented future work.
**Reproducibility.** `build_splits.py` @ `d4113797` (seed `20260715`) regenerates
`split_assignment.csv` byte-identical — the project's second end-to-end reproducibility
result, paired with FORCE. Leakage assertions pass: physical-well atomicity, coordinate
atomicity, FORCE blind-10 isolation, no duplicate rows, zero cross-source collisions.
*Source: `corpus_manifest.json`, `build_splits.py` @ `d4113797`.*
---
## 4. KGS same-well reconciliation
The 6,336 KGS passing **logs** come from **5,751 distinct physical wells** — three
partitions, never meant to be equal:
- **Physical:** 6,336 logs = 5,751 physical wells + **585** same-well extra logs.
- **Content:** 346 exact-duplicate (`dedup_hash`) groups, 741 members, so **redundant
  copies = 741 - 346 = 395**; **9** groups span >1 physical well.
- **All-source:** `dup_group_members_total = 749 = 741 (KGS) + 8 (NLOG) + 0 (FORCE)`.
So 585 (logs minus wells) and 395 (content redundancy) measure different things by
construction. Of the 9 cross-well-identical groups, **0 straddle a train/holdout boundary**
(verified by recompute of the pre-hash forensics logic over committed CSVs; the forensics
output was not itself committed as a report, so this is a fresh recompute, not a stored
artifact).
*Source: `reports/kgs_qc_records.csv`, `kgs_coord_crosswalk.csv`, `split_assignment.csv`.*
---
## 5. KGS vintage distribution (frozen)
Decade histogram of the 6,336 passing KGS wells:
| Decade | Wells |
|---|---|
| 1970s | 1 |
| 1980s | 8 |
| 1990s | 14 |
| 2000s | 1,513 |
| 2010s | 4,262 |
| 2020s | 506 |
| **Covered** | **6,304** |
| No vintage | 32 |
| **Total** | **6,336** |
Covered 6,304 + no-vintage 32 = 6,336 exactly. Pre-2000 tail (23) is sparse - bin or
annotate in any chart. The 32 no-vintage = 2 no-coordinate + 30 with a KID but blank
`vintage_year`.
*Source: `kgs_vintage_crosswalk.csv` join `kgs_coord_crosswalk.csv` join passing KGS.*
---
## 6. NLOG borehole disposition (frozen)
The NLOG index releases **6,609 boreholes** (on/offshore **4,457 / 2,152**):
```
6,609 released
  = 5,004 processed          (one QC record per borehole)
  + 1,605 never-processed
        = 1,563 with no log document at all
        +    42 log-bearing but never processed
```
Within 5,004 processed: **2,355 passing + 2,649 floor-fail**.
**The 42 decompose as 15 + 27:**
- **15 failure-blocked** - in `nlog_failures.csv`. File-level reasons across these (52
  rows): could-not-convert 21, no-readable-log 15, timeout 7, no-depth-index 4, reshape 3,
  LAS-header 1, too-short 1.
- **27 fetched-but-silently-dropped** - a real record-keeping gap, stated plainly. All 27
  have LAS/DLIS documents in the log index **and completed downloads in the fetch manifest**
  - verified at byte level: 123 document URLs across the 27, every one carrying a positive
  `bytes` count **and** a `sha256` (e.g. 5.78 MB / 16.3 MB downloads with recorded hashes).
  Yet they produced **neither a QC record nor a failure row**. The never-fetched bucket is
  therefore **0** (not inferred - the manifest shows the bytes and hashes). Why the QC batch
  dropped these 27 without recording anything is **not attributable from committed
  artifacts**, and the run logs contain no such record (section 8).
15 + 27 = 42, no residual.
**On the "5 permanent retry failures."** An earlier framing referenced 5 permanent retry
failures. There is **no committed artifact** for such a set; it traces only to a superseded
G1-era note (`docs/milestone_G1_nlog.md`, 13 unprocessed of 5,009 - a different snapshot).
It cannot be mapped into the frozen 15, and the card does not carry it as a bucket. The 15
are solid and all sit within the 42; the "5" is a superseded number with no frozen source.
*Provenance:* endpoints (6,609; 5,004) and on/offshore are from committed
`borehole_index.csv`. The 1,563 / 42 split and the 5,046 log-bearing subtotal derive from
`log_index.csv`, committed as evidence (gzip, sha256 `d2f256de...`) so these figures trace to
a frozen artifact. Index resolved **2026-07-07** (file mtime); content horizon
**2026-05-31** (latest `public_as_of`). No embedded snapshot-date field; both dates stated
with provenance, no more claimed.
*Source: `borehole_index.csv`, `log_index.csv.gz`, `nlog_failures.csv`, `_manifest.json`,
`scripts/derive_nlog_disposition.py`, `scripts/derive_42_decomposition.py`.*
---
## 7. Failure-to-borehole bridge (frozen)
The 363 file-level NLOG failures span **174 distinct boreholes**. Of those 174:
**159 recovered** into the 5,004 processed set via alternate files; **15 never-processed**
(the 15 of section 6). **Recovered fraction 91.4%.** The per-borehole fallback design - retry
via alternate files rather than failing the borehole on one bad file - converted the large
majority of file-level failures into processed boreholes, a designed-in robustness result
the frozen artifacts support directly.
*Source: `nlog_failures.csv`, `scripts/derive_failure_bridge.py`.*
---
## 8. Cleaning: sentinels and the rail rule
**KGS sentinel clean (fully quantified).** Run as a separate, instrumented pass over
existing parquets, so impact is counted per well:
- Resistivity ceiling 100,000 ohm-m on RDEP/RMED/RSHA.
- **GR floor (0.0 gAPI): 4,248 wells / 8,852 samples ~ 2.08 samples/well** - the
  edge-padding signature (roughly two samples per affected well), not interval fill.
- **RDEP 3777 ohm-m fill: ~254 wells / 79,446 samples**, bit-identical float64
  `3.5771469848275252` across 219+ wells; residual 0.
*Sample-vs-census note:* early working memos cited small per-sample figures (e.g. 27, 16)
that are **sample-level** counts on inspected wells; the figures above are **census-level**
well/sample totals over the full KGS set. The large apparent jump between them is the two
definitions, not a discrepancy. A general isolated-spike detector was rejected on the CALI
evidence.
**NLOG rail rule (impact NOT recoverable - stated honestly).** `_null_rail_pileup` ran
**inline at harmonize time** and discards its nulled-count: it sets rail samples to `NaN`
indistinguishably from any other null, and the raw NLOG well data has since been deleted.
Recovering the historical per-well impact would require re-fetching and re-harmonizing the
full NLOG set - **declined** under the corpus-frozen rules. A grep over all crawl/QC logs
for any rail/null counter returns **0 matches**: the count is **confirmed absent from run
logs**, not merely inferred.
What the frozen data *can* answer is a **completeness check** (explicitly not the impact
count): a read-only scan of all 5,004 NLOG processed wells for residual rail pileups meeting
the exact rule criteria (within 1e-6 of a `valid_range` bound, >=25 samples and >=5% of finite
samples; resistivity bounds log10-transformed) returns **N = 0 survivors, K = 0
floor-adjacent**. No rail pileups survive - the rule fired to completion.
**The asymmetry is deliberate to state:** KGS sentinel impact is fully quantified (separate
instrumented pass); NLOG rail impact is unquantified (ran inline, uncounted). Trust the KGS
impact figures as exact; read the NLOG rail treatment as verified-complete-but-uncounted.
Future ingestion (v2.1+) makes mutation counters mandatory so this asymmetry is not
repeated.
*Source: `reports/kgs_sentinel_clean_report.md`, `scripts/scan_nlog_rail_residual.py`,
`scripts/derive_42_decomposition.py` (log grep).*
---
## 9. Curve harmonization (frozen)
**Alias map (final; window closed).** RGR, ECGR -> GR; SON -> DTC; RCAL, CAL1, CAL2 -> CALI;
SN -> RSHA; LN -> RMED (log10 overlap 0.667, 0.652). NEUT rejected (uncalibrated API-unit
neutron counts - wrong-scale trap). LATL deferred (436 NLOG wells). Alias YAML sha256
`e888ac7`, double-pinned.
**SN/LN admission asymmetry (future work).** SN and LN were admitted and applied to **NLOG
at ingestion**; the **KGS parquets predate the admission**, so any SN/LN content in KGS raw
is **unrecovered and unknowable without re-download**. Stated as future work (section 13),
not silently uniform across sources.
**Alias gain.** Aliasing lifted NLOG passing **1,812 -> 2,355 = +543 wells**. Because both
the pre-alias and final QC snapshots are **post-sentinel**, this +543 **isolates the alias
effect** by construction - it contains no sentinel component and is not decomposed as if it
did. (No committed NLOG sentinel-impact artifact exists to quantify an NLOG sentinel loss
separately; see section 8 asymmetry.)
*Source: `reports/_pre_alias/nlog_qc_records.csv` vs `reports/nlog_qc_records.csv`.*
---
## 10. NLOG pass-rate trajectory (frozen; no vintage axis)
The NLOG pass rate fell during the crawl and recovered with aliasing: **~44%** through the
first ~3,660 boreholes (crawl order), **36.3% pre-alias** at 4,996 processed, **47.1%
post-alias** (frozen). The early falloff is the crawl reaching older, low-canonical-curve
wells; the recovery is the +543 alias lift.
**No vintage/spud-year axis exists in any committed NLOG artifact** - `nlog_qc_records.csv`
has none, `borehole_index.csv` carries only `public_as_of` (catalog-release horizon, not log
vintage), `log_index.csv` has depths and file metadata but no date. So the trajectory is
documented against **crawl order**, not vintage, and a pass-rate-by-vintage chart **cannot
be built from frozen artifacts**. This omission is stated rather than implied.
*Source: `docs/milestone_G1_nlog.md`, `docs/G2_progress_report.md`.*
---
## 11. Runtime and reproducibility provenance
- **Reproduction-verified (`==`):** `pandas==2.2.3`, `numpy==1.26.3`, verified by
  clean-environment regeneration of the manifest (minimal venv of the pair + transitive
  deps regenerated it byte-identical).
- **Declared ranges (not reproduction-verified):** `pyarrow`, `lasio`, `scipy`, `dlisio`,
  `pyyaml` - provably outside the manifest-path dependency closure (measured), and the
  versions that wrote the frozen parquets are unrecorded.
- **Parser-version variance.** Exact ingestion-time parser-library versions were not
  recorded; declared ranges at freeze are as committed; the **frozen parquets are ground
  truth**. Regeneration from raw is subject to parser-version variance. (Norm-stats
  reconfirmation came out byte-identical under fresh scipy/lasio/pyarrow, corroborating that
  frozen values derive from exact parquet float64 samples, not parser behavior.)
The committed manifest builder (`build_manifest.py` @ `212faed9`) regenerates FINAL from
committed code by construction.
*Source: `qc_pin_manifest.txt`, `docs/freeze_closure_env_2026-07-20.txt`,
`build_manifest.py` @ `212faed9`.*
---
## 12. Licensing and provenance
- **FORCE 2020:** NOLD 2.0, DOI 10.5281/zenodo.4351156. Redistribution per NOLD with DOI.
- **NLOG:** redistribution permitted with attribution per its published terms; default
  posture carries **no raw mirror** unless separately decided. Per-record `public_as_of`
  provenance is carried as a records column.
- **KGS:** raw-redistribution terms unclear, hence a **pipeline-plus-weights** posture - the
  pipeline (code) and trained weights are shared; **no KGS raw mirror**.
---
## 13. Known open items (stated, not hidden)
- **NLOG historical rail impact** - unrecoverable without reopening the frozen corpus;
  confirmed absent from run logs (section 8). Residual-completeness N=0 is the adjacent
  frozen fact.
- **The 27 silently-dropped boreholes** (section 6) - drop mechanism not attributable from
  committed artifacts.
- **NLOG sentinel-loss figure** - not derivable (both alias snapshots post-sentinel); no
  committed NLOG sentinel-impact artifact. Stated unquantified (sections 8, 9).
- **SN/LN in KGS** - admitted post-KGS-ingestion; KGS SN/LN content unrecovered without
  re-download (section 9).
- **Unmapped mnemonics** - committed sets: **NLOG 14,315 distinct** (18,690 mnemonic+unit
  rows, `reports/nlog_unmapped_mnemonics.csv`) and **KGS 1,667 distinct** (2,077 rows,
  `reports/kgs_unmapped_mnemonics.csv`; no separate flagged-ambiguous subset). *A project
  dossier separately cites 17,970 distinct NLOG unmapped mnemonics - an earlier snapshot;
  this card pins the current committed CSV figure (14,315) and notes the dossier snapshot
  rather than reconciling two snapshots silently.*
- **Resistivity-channel disambiguation** - SN / LN / LATL deferred to documented future work
  rather than force-mapped (`reports/alias_audit/`). *(This is the parked ambiguity; there is
  no conductivity-conversion item in committed artifacts.)*
- **NLOG snapshot date** - soft; only file mtime (2026-07-07) and latest `public_as_of`
  (2026-05-31).
- **Pass-rate-by-vintage chart** - cannot be built; no NLOG vintage axis in frozen artifacts
  (section 10).
These are the pressure valve: documented future work, not silent gaps.
---
## Evidence lineage
Manifest lineage: `f497206b -> 88255b43 (pin-set completion) -> d5b35a00 (runtime pin fold-in
+ dlisio declaration reconciliation)`, splits unchanged throughout, `row_count` 8,809 and
all nine split counts invariant.
Freeze chain on `origin/main`: `9168d83 -> 212faed9 -> 41e0e51`, extended by evidence and
remediation commits `2272118 -> 568c951 -> ca11341 -> a181af7 -> ced8dd7 -> 9c6b9fc`. All
evidence and remediation commits sit **outside** the hashed set; none move `qc_code_sha256`
or `d5b35a00`.
