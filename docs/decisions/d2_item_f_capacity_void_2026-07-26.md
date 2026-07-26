# Item F: per-curve independence finding committed; capacity pre-registration VOID (2026-07-26)

## Marked VOID, with lineage

**Plan's capacity pre-registration** (the reasoning, standing in prior D2 sessions'
context, that excluding PEF from a codebook fit might free shared model capacity for
the other nine curves -- the premise behind Phase 5's original "refit the output
codebook on the nine emitted curves" instruction) and **the shared-capacity reasoning
behind the P2 branch** are both marked **VOID**, superseded by Phase 5's actual finding
(`docs/decisions/d2_phase5_no_refit_needed_2026-07-25.md`, committed 2026-07-25):
the tokenizer is per-curve independent by construction. Neither text is deleted; this
is a lineage marker, not an edit of the original pre-registration.

## For BENCHMARK.md

Each of the 11 canonical curves trains its own independent `FSQAutoEncoder` (own
encoder, own decoder, own patch bank) with no shared weights and no shared codebook
table -- the FSQ quantizer itself has no learned embedding at all, only a fixed
rounding operation parameterized by the level vector. Consequently **PEF had a fully
dedicated encoder and decoder at every tested level vector (cb64 through cb15360,
patch32 and patch16) and still exceeded the R8 bar at all of them** (best case 16.01%
at cb125/patch32, per the Phase 1 re-score; 13.84% at patch16/cb15360). **PEF's limit
is not a capacity artifact** -- there was never any capacity to share or free up.

**Recorded as the one remaining untested lever:** per-curve level allocation -- i.e.
giving PEF's own FSQAutoEncoder a *different* FSQ level vector (finer or differently
shaped than the shared vector every other curve uses) has never been tried. All sweeps
to date (Phase B, D1) applied one identical level vector across all 11 curves' separate
models simultaneously; whether a PEF-specific level allocation would help remains open
and untested.
