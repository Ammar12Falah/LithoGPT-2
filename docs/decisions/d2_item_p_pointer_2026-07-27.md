# Item P: pointer to embedded content (2026-07-27)

Per the AA-series brief item AE: item P's content (generation cap in samples
and metres, window start policy, depth range spanned, real interval scored
against) was never committed as a standalone decision doc. It is embedded
directly in `scripts/atce/atce_ablation_v3.py`, its run log, and the v3
summary JSON. This is a pointer, not a rewrite.

## Where in the script

- Line 72: cap raised "so it never binds for this well pool."
- Lines 337-338: measured depth-grid spacing (median dz across 98 wells) and
  the resulting CONTEXT-tokens-to-metres conversion.
- Line 504: `MAX_GEN_LEN` samples logged at generation time.
- Lines 578, 580: total depth range spanned across all wells/realizations/
  arms, and coverage percentage (min/median/max across all well x arm pairs).

## Where in the run log

`reports/basinshift/atce_ablation_v3/run_log.txt`:
```
item P: generation cap MAX_GEN_LEN=20000 samples (3040.0 m at measured spacing);
window start is FIXED (not randomized per realization) at
prime_n=max(CONTEXT, PRIME_FRAC*well_len), identical across realizations of a
given well/arm; the real interval scored against is
feats_real[prime_n:prime_n+gen_len], i.e. matched exactly to the generated
window, not an independently chosen reference span.
item P: total depth range spanned across all wells/realizations/arms:
min=1295.63 m, max=3897.35 m
item P: coverage_pct_of_remaining (min/median/max across all well x arm
pairs): 100.0% / 100.0% / 100.0%
```

## Where in the summary JSON

`atce_ablation_v3_summary_2026-07-26.json` -> `generation_cap`:
`max_gen_len_samples: 20000`, `max_gen_len_metres: 3040.0`,
`coverage_pct_min/median/max: 100.0`, `window_start_policy` and
`real_interval_matching` as quoted above, `total_depth_range_m: [1295.63,
3897.35]`. Also `context_tokens_to_metres: {512 tokens, 77.824 m}` and
`measured_depth_spacing_m: 0.152`.

## Ruling

P's content is fully captured in the script, run log, and summary JSON. No
separate pre-registration doc is needed.

