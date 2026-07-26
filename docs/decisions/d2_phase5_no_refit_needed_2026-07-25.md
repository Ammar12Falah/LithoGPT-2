# Phase 5 -- no refit needed, condition A satisfied by construction (2026-07-25/26)

Precise spec (Plan): hold config/level-vector/patch/seed/standardization identical to
cb15360/patch16/GLOBAL_DEV, remove only PEF and DTS from the fitting pool, score the remaining
nine curves. Pre-registered escape hatch: if the tokenizer is already per-curve (independent
encoder/decoder, no shared latent space), PEF never competed for capacity with the nine, and no
refit is needed.

## Verification: the tokenizer is per-curve independent (code read, no training run)

- `r8_acceptance.curve_arrays_train(curve)` pulls `df[curve]` for exactly one named curve --
  no cross-curve mixing anywhere in its body.
- `fsq_diag.build_banks()` / `fsq_phaseB_sweep.build_banks()` both loop `for c in EH.CANON:
  banks[c] = FT.build_patch_bank(R8.curve_arrays_train(c), ...)` -- one bank per curve, built
  from only that curve's own data.
- `fsq_tokenizer.train_tokenizer(bank, levels, ...)` calls `torch.manual_seed(seed)` as its
  first line (full RNG reset) then constructs a **brand new** `FSQAutoEncoder(levels, patch,
  hidden)` every call -- fresh `self.enc`, `self.fsq`, `self.dec`, no class-level or shared
  parameters, and the FSQ quantizer itself has **no learned codebook embedding at all** (it is a
  fixed tanh-bound-and-round operation parameterized only by the `levels` integer vector, so
  there is no shared table of any kind to compete for).
- Consequence: whether PEF/DTS are included in a given sweep has **zero mechanical effect** on
  any other curve's tokenizer -- GR/RHOB/NPHI/DTC/SP/CALI/RDEP/RMED/RSHA's models in the
  already-committed `cb15360_p16` run were never trained on PEF or DTS data to begin with.

**Condition A is satisfied by construction. No refit is needed or run.** Per the pre-registered
instruction, this is reported and Phase 5 skips straight to Phase 6.

## The nine-curve check (arithmetic only, against the already-committed cb15360/patch16/GLOBAL_DEV
result -- the "old" and "refit" codebook are identical by construction, so both are the same
frozen artifact: `reports/basinshift/fsq_diag/results/cb15360_p16.json`, whose raw_rmse values
already match the Phase 1 frozen baseline exactly)

| Curve | degradation | gap to 10% | SE (tok-axis, n=3) | SE (imp-axis, n=5) | tightest margin |
|---|---|---|---|---|---|
| GR | 6.32% | 3.68pp | 0.162 | 0.067 | 22.75 SE |
| RHOB | 1.39% | 8.61pp | 0.098 | 0.103 | 83.75 SE |
| NPHI | -0.67% | 10.67pp | 0.110 | 0.277 | 38.49 SE |
| DTC | 9.20% | 0.80pp | 0.075 | 0.170 | **4.73 SE** |
| SP | -0.41% | 10.41pp | 0.023 | 0.058 | 179.08 SE |
| CALI | 0.81% | 9.19pp | 0.133 | 0.246 | 37.34 SE |
| RDEP | 2.58% | 7.42pp | 0.774 | 0.398 | 9.59 SE |
| RMED | 1.05% | 8.95pp | 0.017 | 0.720 | 12.43 SE |
| RSHA | 0.40% | 9.60pp | 0.006 | 0.027 | 357.86 SE |

Median = **1.05%** (RMED), gap to the 5% bar = 3.95pp, ~5.5 SE clear using RMED's own
imputer-seed spread as a conservative proxy for median positional uncertainty. Max = **9.20%**
(DTC), the tightest of the nine but still **4.73 SE** clear of the 10% bar using the more
conservative (imputer-seed axis) standard error.

## Branch decision

All nine ≤10%, median (1.05%) ≤5%, every curve ≥3 SE clear of its own bar (worst case DTC at
4.73 SE) -> **Branch 1: continue to Phase 6.**

## Freeze

No new codebook was fit, so there is nothing new to freeze distinct from what Phase 1 already
froze. The existing `cb15360_p16.json` result (raw_rmse identical to
`frozen_raw_baseline_2026-07-25.json`, sha256 `d3ecb97c05472f64f0b810f7d323473abd7ee2b470a222469eedb70a9c21fae4`)
is the frozen reference for both "old" and "refit" by construction -- reported side by side above
is the nine-curve slice of that single frozen result, not two separate artifacts.
