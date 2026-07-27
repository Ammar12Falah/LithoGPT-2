# Item K: exploratory-run label for the first ATCE ablation pass (2026-07-26)

Per the brief: "DO NOT STOP THE RUNNING JOB. Let the in-flight ablation finish and
report its numbers. Declared now, before those numbers are read: this run is
EXPLORATORY pipeline validation, not the manuscript run. It is not sealed and
nothing from it is reported in the paper."

**This declaration was made before the run's numbers were read or interpreted**,
consistent with the pre-registration discipline used throughout this project.

## What this run was

`scripts/atce/atce_ablation.py`, executed to completion (full scale: N_STEPS=3000,
N_REALIZATIONS=5, N_BOOTSTRAP=1000, MAX_GEN_LEN=1000) at commit time of items A-I.
Outputs: `reports/basinshift/atce_ablation/atce_ablation_summary_2026-07-26.json` +
`atce_ablation_raw_results_2026-07-26.json` (+ sha256 sidecars).

## Why it is exploratory, not sealed

Three defects were found in it by the subsequent brief (items L, M, N, S, O, P),
discovered only after this run had already been launched and while it continued
running unmodified per item K's instruction:

1. **Item S**: the tokenizer/scaler were freshly refit on FORCE data
   (`StandardScaler().fit(train_feats)` / `MiniBatchKMeans(...).fit(...)`), not
   loaded from v1's authentic `kmeans_pure.joblib`/`scaler_pure.joblib` artifacts,
   even though those artifacts load cleanly. This makes the caveat on this run's
   Arm A "reimplemented from spec" in the fullest sense (tokenizer included), not
   the narrower "v1's authentic tokenizer, transformer retrained from spec."
2. **Item O**: Arm B (renamed B-linear in the corrected run) was the only
   depth-conditioning mechanism tested; no B2 richer-featurization arm existed to
   check whether the rank-1 linear mechanism itself was the limiting factor.
3. **Item P**: the generation cap (MAX_GEN_LEN=1000 samples = 152 m) covered as
   little as 7.7% of a held-out well's post-prime depth range on the longest test
   wells (30/6-5: 13047 remaining samples, only 1000 generated). Every
   depth-conditioned arm was therefore scored inside a narrow, arbitrarily-placed
   band where a depth-dependent effect had little room to appear.

None of these defects invalidates the pipeline mechanics (data loading, blind_force
assertion, training loop, batched generation, bootstrap CIs, sha256/output
writing) -- those were exercised correctly and are unchanged in the corrected
script. They invalidate this run's **numbers** as the reported result.

## Disposition

- This run's outputs are retained and committed as-is, unmodified, for lineage --
  they are the artifact item K's numbers refer to.
- **Not sealed. Not reported in the paper.**
- The corrected run (`scripts/atce/atce_ablation_v2.py`, items S+O+P applied) is
  the manuscript-candidate result; see `reports/basinshift/atce_ablation_v2/`.
