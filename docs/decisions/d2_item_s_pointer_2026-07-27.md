# Item S: pointer to embedded content (2026-07-27)

Per the AA-series brief item AE: item S's content (tokenizer provenance per
run, and the resulting manuscript caveat) was never committed as a
standalone decision doc for the v3 (sealed-candidate) run specifically. It
is embedded in `scripts/atce/atce_ablation_v3.py`, the v3 summary JSON, and
fully superseded/resolved by the already-committed
`docs/decisions/d2_item_u_tokenizer_validation_2026-07-26.md`. This is a
pointer, not a rewrite.

## What S originally found (v1/v2, preserved, not erased)

Item S's original finding: the v1 and v2 runs called `StandardScaler().fit()`
and `MiniBatchKMeans().fit()` fresh on FORCE data and did NOT use v1's
artifacts, despite them loading cleanly. That description is accurate for
what those exploratory/diagnostic runs did and is not changed by this pointer.

## Where v3's provenance decision is embedded

- Script, lines 341, 355, 359:
  ```
  # item U (BLOCKING, reverses item S for this sealed run): v1's tokenizer/scaler
  tokenizer_provenance = "refit_on_force_80_train_wells (item U: reverts item S
  after v1 tokenizer failed validation gate)"
  ... "reverting item S's decision per the pre-registered validation-gate rule."
  ```
- Summary JSON `tokenizer_provenance` field (verbatim): `"refit_on_force_80_
  train_wells (item U: reverts item S after v1 tokenizer failed validation
  gate)"`.
- Full validation-gate numbers and ruling: `docs/decisions/
  d2_item_u_tokenizer_validation_2026-07-26.md` (already committed).

## Manuscript caveat

All six v3 arms, including Arm A, use a tokenizer/scaler freshly refit on
this ablation's own 80 train wells -- not v1's artifacts. Arm A's caveat is
the fuller "reimplemented from spec, tokenizer included," not the narrower
"v1's authentic tokenizer" framing item S's original finding described for
v2.

## Ruling

S's provenance decision for v3 is fully captured by item U's committed doc
plus the script/summary fields above. No separate v3-specific pre-
registration doc is needed.

