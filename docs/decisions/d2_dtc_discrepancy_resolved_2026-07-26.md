# DTC apparent discrepancy: resolved, not a defect (2026-07-26)

Recorded verbatim per instruction, no investigation performed (none was
warranted): the apparent DTC discrepancy is resolved and is not a defect. 9.79%
is Phase B's best config at patch32, while 9.57% and 9.30% are the Step 4 seed
means at patch16. Different configs, not contradictory measurements, and no N=5
reinstatement question arises. D1 and Step 4 both ran through `fsq_diag.py`,
which always used the correct per-call generator, so the patch-16 numbers were
never affected by the `eval_harness.py` RNG defect (item Phase 1.1). Going
forward, every DTC figure carries its patch size and config label explicitly.
