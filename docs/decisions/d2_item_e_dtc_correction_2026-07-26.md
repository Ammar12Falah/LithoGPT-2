# Item E: DTC margin record, corrected (2026-07-26)

## The error being corrected

`docs/decisions/d2_phase5_no_refit_needed_2026-07-25.md` reported DTC's SE margin by
pairing DTC=9.20% (D1's single canonical-seed draw at cb15360_p16) against the
imputer-seed axis's standard error (0.170, derived from N=5 imputer-seed draws whose
own mean is 9.30%, not 9.20%). Mixing a single draw from one context with a different
axis's sampling-distribution SE is not a coherent estimator pairing -- **that figure
(4.73 SE) is retracted.**

## Corrected record: both axes, each with its own estimator

| Axis | mean | std | N | SE = std/sqrt(N) | gap to 10% bar | margin |
|---|---|---|---|---|---|---|
| tokenizer-seed | 9.57% | 0.13% | 3 | 0.075 | 0.43pp | **5.7 SE** |
| imputer-seed | 9.30% | 0.38% | 5 | 0.170 | 0.70pp | **4.1 SE** |

Both figures are already-committed data from `reports/basinshift/fsq_diag/
seed_repeat_summary.json` (tokenizer_seed_axis / imputer_seed_axis, curve DTC) --
recomputed here with the correct pairing, not new measurements.

## Conclusion: unchanged

DTC clears the 10% bar on both axes, using each axis's own internally-consistent
mean+SE, with the tighter (imputer-seed) margin still a comfortable 4.1 SE -- well
above the 3-SE reinstatement threshold. **No N=5 reinstatement fires.** This was
already Phase 5's conclusion; only the unsound intermediate figure (9.20 paired with
the imputer-axis SE) is corrected, not the pass/fail outcome.
