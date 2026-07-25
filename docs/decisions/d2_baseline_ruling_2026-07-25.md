# Baseline ruling (advisor, relayed by Plan, 2026-07-25)

Resolves the question surfaced in `docs/decisions/d2_phase1_rng_fix_and_frozen_baseline_2026-07-25.md`
Section 1: what `reports/basinshift/baseline_results.json` means now that the shared-rng defect
that produced it has been identified.

## Ruling

- `baseline_results.json` stays **frozen as a historical artifact**. It is not regenerated.
- It is documented as **order-dependent and not seed-reproducible**: its exact values depend on
  the specific sequence in which `basinshift_baseline.py` called `build_train` across its 12
  (RUN x TARGET) cells during its one original execution, not solely on the stated seed. Re-running
  that script today, even with identical code and seed, is not guaranteed to reproduce it, because
  the shared module-level rng's state at each call depends on how many prior calls preceded it.
- `scripts/basinshift/basinshift_baseline.py` gets the **same fix** already applied to
  `eval_harness.py` (module-level shared rng -> fresh per-call rng, seeded per call) so that any
  *future* regeneration of a baseline through this script is order-independent and reproducible.
  **The fix is applied. The script is not rerun.** `baseline_results.json` is untouched by this fix.
- **All work from here scores against the frozen artifact** `reports/basinshift/
  frozen_raw_baseline_2026-07-25.json` (sha256 `d3ecb97c05472f64f0b810f7d323473abd7ee2b470a222469eedb70a9c21fae4`),
  not against `baseline_results.json` or any ad hoc recomputation.

## Reasoning

1. **Paired comparisons cancel a shifted baseline.** Every scoring path in this project (Phase B,
   D1, Phase 1's re-score) computes degradation as `(arm_rmse - raw_rmse) / raw_rmse` against a
   SINGLE raw_rmse held fixed across the comparison being made. A denominator shift changes the
   absolute percentage reported but does not change which arm is better than which, as long as the
   same denominator is used for every arm in a given comparison -- which every committed sweep
   already does (Phase B fit its 11 imputers once and reused them across all 6 configs; D1 did the
   same within its own run). The defect was never a threat to any *relative* ranking already made;
   it was only ever a threat to the *absolute* percentage's precision and to cross-session
   comparability (Phase B's raw_rmse vs D1's, which are not directly comparable without accounting
   for the shift -- already handled in Phase 1's Step 3 decomposition).
2. **Phase B's correction changed no conclusion.** The Phase 1 re-score against the frozen
   baseline shifted every config's reported degradation by 1-3.5pp but left the ranking, the
   binding failure (PEF, at every config), and the DTC headline margin qualitatively unchanged
   (best case 16.01% for PEF, 9.79% for DTC -- both still failing their respective bars). Nothing
   sealed under the old numbers is invalidated by the shift.
3. **Stage 1 stays sealed until after ATCE.** The TS-FM Stage 1 frozen predictions
   (`frozen_adapted_pretrained_A.json.gz` / `frozen_control_random_A.json.gz`, sha256s already
   committed) are untouched by this ruling and are not reopened or rescored during the ATCE
   critical path. They remain sealed as-is; any implication of the rng defect for that sealed
   record is out of scope until after the ATCE deadline.

## What is NOT ruled here

Whether `baseline_results.json`'s specific numbers should ever be regenerated (e.g. for a future
gate that explicitly wants a clean, order-independent baseline) is left open for a future
decision; today's ruling only fixes what future regeneration would look like if it is ever
authorized, and freezes today's reference point at `d3ecb97c...` in the meantime.
