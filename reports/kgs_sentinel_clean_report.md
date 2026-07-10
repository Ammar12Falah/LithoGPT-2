# KGS Sentinel-Clean Report

Date: 10 July 2026
Scope: Detection and nulling of processing-fill sentinel masses in the KGS processed
parquets (data/processed/kgs, 9,307 wells). Resistivity stored as log10(ohmm). Values
set to missing (NaN) with paired _mask set False; values never clipped.

## Outcome (verified)
Residual fill = 0 on every target; value/mask consistency verified both directions across
all 9,307 files. Physical channels intact (RHOB 2.55 in 5,807 wells, CALI 7.0 in 1,347,
NPHI 0.0 in 2,904).

## Confirmed fills nulled (true, ungated counts)
- RDEP ceiling (100000 ohmm, log10 5.0): 3,634 wells / 374,287 samples
- RMED ceiling: 1,217 wells / 113,752 samples
- RSHA ceiling: 44 wells / 1,934 samples
- GR floor (0.0 gAPI, bit-exact; one well -0.0): 4,248 wells / 8,852 samples
- RDEP = 3777 ohmm exact (log10 3.5771469848275252, nulled in earlier pass): ~254 wells /
  79,446 samples; residual 0 confirmed

## Method and rationale
Rail-welded masses (resistivity ceiling, GR floor) are censoring events, not measurements,
so nulling them destroys no information (rail rule, commit 60f7473; NLOG re-fetch inherits
it). RDEP 3777 is mid-range, not on a rail; confirmed fill by bit-exactness (identical
float64 3.5771469848275252 across 219+ wells; real rock cannot repeat bit-identically) and
nulled via an explicit reviewed value, RDEP only. A general isolated-spike detector was
evaluated and REJECTED: real CALI bit-size clustering scores as isolated as fill
(iso-ratio order 1e11 both), so isolation cannot separate fill from physics here.

## Flagged, not nulled (below confidence bar)
PEF 20.0 (1 well); RDEP 3.5507 ~3556 ohmm (3 wells, not bit-exact across a population);
singletons. Recorded as seen and deliberately retained.

## Audit trail (disclosed)
First clean pass applied a per-well frequency gate (>=5% and >=25 samples) correct for the
live rail rule but wrong for cleaning known fills (a fill is a fill at any frequency); it
suppressed nulling in ~4,600 files and its reported per-rule counts were the gated subset.
Corrected by ungated exact-value null. First pass also left _mask unset at nulled samples;
a mask-consistency repair set mask = isfinite(value) across all files (1,316 files, 993,094
cells). Two verifier cells were themselves defective during the work (a wrong-cwd false
green, caught before action; a single-file over-generalization) and were corrected; final
verify uses absolute paths and checks mask consistency both directions. All counts
reconcile across dry-run, clean, repair, verify.

## Consequence
Nulling fill lowers some wells' resistivity/GR coverage; a few may fall below the coverage
floor at the next QC count. Accepted: real numbers over inflated ones.

## Provenance
KGS processed parquets are derived (untracked); this report is the durable record.
Related commits: rail rule 60f7473, e2e tests f224347, pre-alias snapshot 206af98.
