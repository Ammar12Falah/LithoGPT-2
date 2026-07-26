# Item G: carbonate gate limitation, pre-registered before any physics-prior result (2026-07-26)

Committed **before** item J's Arm B/D results exist, per instruction, so this
interpretation is fixed ahead of the numbers it will be read against.

**The measured gate performance** (Phase 7 / R9, `reports/basinshift/
r9_physics_prior_2026-07-26.json`): precision 10.6%, recall 58.6% against FORCE 2020
lithofacies ground truth.

**Pre-registered interpretation rule:**

- Both figures **attenuate**, not amplify, any true physics-prior effect. Low precision
  means non-carbonate intervals are sometimes wrongly excluded from prior-conditioning
  (diluting the treated population with intervals that would not have shown a
  compaction-trend bias to begin with); imperfect recall means some genuinely
  carbonate-confounded intervals remain in the treated population, working against the
  prior's benefit. Both failure modes push a measured effect size **toward zero**,
  never away from it.
- **A positive result in item J's Arm B/D is therefore conservative**: if a benefit is
  detected despite this attenuation, the true benefit under a perfect gate is at least
  as large, plausibly larger.
- **A null result is confounded and cannot be read as evidence against the physics
  prior.** A null could mean the prior genuinely has no effect, or it could mean the
  gate's imperfect precision/recall masked a real effect. This experiment cannot
  distinguish those two explanations, and must not claim to.

This rule is fixed now, before Arm B or Arm D produce any number, precisely so it
cannot be adjusted after seeing whether the result is favorable.
