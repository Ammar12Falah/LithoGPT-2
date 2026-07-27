# Item W: the v2 run is also diagnostic, not sealed (2026-07-26)

Declared before its numbers were read, same rule as item K, for two stated
reasons:

1. **B-linear vs B2 was confounded (item V).** v2's Arm B2 changed both the
   depth reference frame (per-well dnorm -> would need absolute depth for the
   Athy/sin/cos terms to be meaningful) and the featurization richness at the
   same time as Arm B-linear. A difference between B-linear and B2 in that run
   cannot be attributed to either variable alone.
2. **v1's tokenizer was unvalidated (item U).** v2 used v1's authentic
   `kmeans_pure.joblib`/`scaler_pure.joblib` directly (item S's decision), before
   item U's validation gate existed. That gate later found v1's tokenizer
   reconstructs this project's actual data materially worse than a fresh refit,
   particularly on NPHI (3x worse RMSE) -- the primary metric every arm in v2
   was scored on.

## Disposition

v2's outputs (`reports/basinshift/atce_ablation_v2/`) are retained and committed
as-is, unmodified, for lineage -- they are the artifact items U and V's
findings refer to, and running them was what surfaced both defects. **Not
sealed. Not reported in the paper.**

The v3 run (`scripts/atce/atce_ablation_v3.py`, items U+V applied: fresh-refit
tokenizer, Arm B-abs added, B2's reference frame fixed to match B-abs) is the
manuscript-candidate result; see `reports/basinshift/atce_ablation_v3/`.
