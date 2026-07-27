# v3 status declaration (2026-07-27)

Per Plan's standing ruling 13 (LithoGPT-2 Planning Agent Handoff v1.6,
section 6): v3 is sealed only after two conditions are both met -- (1) item
U's tokenizer validation gate is confirmed passed, and (2) Plan has
cross-checked the summary numbers. Until both hold, v3's status is recorded
explicitly as neither "sealed" nor "exploratory."

## Status as of this entry

**v3 is the CANDIDATE manuscript run.** Not sealed. Not exploratory.

## Condition 1: item U's gate

Confirmed this session, independently, from three sources (not just the
handoff's prior claim):
- `scripts/atce/atce_ablation_v3.py` lines 341, 355, 359 -- the gate's
  revert-to-fresh-refit branch is coded and reasoned about explicitly.
- `run_log.txt` and the summary JSON's `tokenizer_provenance` field --
  confirm the fresh-refit tokenizer was the one actually used to train and
  evaluate all six arms, not v1's artifacts.
- `docs/decisions/d2_item_u_tokenizer_validation_2026-07-26.md` -- the full
  six-number comparison and the pre-registered rule it was measured against.

The gate ran, produced a clear decision (revert), and that decision was
correctly and verifiably applied throughout v3. This condition is satisfied
in the sense that the gate's outcome is confirmed and traceable -- not in
the sense that v1's tokenizer "passed" (it did not; it failed, triggering
the pre-registered revert, which is what happened).

## Condition 2: Plan's cross-check

**Not yet done.** This report (AD's numbers, delivered in the same session
as this declaration) is the input Plan needs to perform that cross-check.
Plan must review before v3 can be called sealed.

## Known inconsistency, recorded rather than silently fixed

The commit message already pushed at `ef8883e27d34deac198ab14b7db6601aedaefb14`
(subject: "Item J: ATCE ablation - exploratory (K) + diagnostic v2 (W) +
sealed v3 runs") describes v3 as "SEALED, manuscript-candidate" in its body
text. That predates this declaration and predates Plan's ruling 13 as
written in the v1.6 handoff. It is NOT corrected retroactively (commit
messages are not amended). This declaration is the authoritative status as
of 2026-07-27: v3 is CANDIDATE, not sealed, pending Plan's review of the
numbers reported alongside this entry.

