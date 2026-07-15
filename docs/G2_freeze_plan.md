# G2 Freeze Plan (advisor-confirmed 2026-07-11, five amendments)

Last coverage loop CLOSED. Corpus freezes at: NLOG 2,355 passing / 5,004 processed;
combined ~8,789. Everything else -> future-work list.

## Hard preconditions (all before any hashing)
- CI GREEN on main (read actual error first; hypothesis pin numpy>=1.26.4,<2.0; then fix; then green).
- Final records/coverage/unmapped/failures CSVs cherry-picked onto MAIN (not full branch merge);
  verify by RUNNING the counting script, not eyeballing: 5,004 boreholes on main.
- Decision-capture commit LANDED (from-scratch + TS-FM tripwire ruling, verbatim, in decisions log
  and benchmark doc); ITS COMMIT HASH recorded here as a precondition (pre-registration must predate
  the tripwire baseline that runs after benchmark freeze).

## Amendment 1 — SPATIAL splits, not random
- Held-out KGS and held-out Netherlands: contiguous GEOGRAPHIC BLOCK holdouts, disjoint from
  training, using coordinates in the indices. Dev slice within training basins: also spatial block.
- Size: ~10% of each basin's passing wells, cap ~250, floor ~100, stratified by vintage where block allows.
- FORCE: official splits exactly (open 10 / blind 10, no re-cut). FORCE blind OUTSIDE everything, never inspected.
- ASSERT before hash: zero cross-source well collisions on location + depth fingerprint.

## Amendment 2 — manifest pins PROCESSING STATE
- Manifest header: git commit of split-gen code, RNG seed, sha256 of configs/mnemonic_aliases.yaml
  and the QC config. Well rows: well_id, source, split, coordinates. Any later alias/QC change breaks the hash.

## Amendment 3 — KGS SN/LN/LATL counts (before card finalizes)
- Pull counts from KGS unmapped-mnemonic records; record decision in card. Default stands: prospective
  future work. Asymmetry sentence: enriched aliases applied to NLOG at ingestion, to KGS prospectively.

## Amendment 5 — CARD ACCEPTANCE TEST (all required)
1. Outcome taxonomy, fixed denominators (5,004 processed / 2,355 passing / 363 hard-fail / remainder floor-fail).
2. Rail-rule NLOG impact decomposing +543 (alias gains vs sentinel losses).
3. All-but-5 borehole disposition, per-borehole reasons.
4. KGS counts-jump explanation (sample vs census).
5. NLOG index snapshot pinning: dates + both totals.
6. Pass-rate-by-vintage chart.
7. Alias-admission paragraph incl LATL exclusion + NEUT trap.
8. KGS sentinel-clean paragraph: exact values nulled (100000, 3777, 0.0), sample-vs-census
   reconciliation, GR edge-padding sentence, CALI rationale for rejecting the general spike rule.
9. Single-file-selection floor caveat.
10. Per-source licensing + PUBLIC_AS_OF provenance.
11. Unmapped-mnemonic future-work list.
12. KGS SN/LN/LATL decision (amendment 3).

## Freeze ORDER (strict, unchanged)
splits (one op) -> manifest hash -> norm stats on frozen TRAIN only -> card -> tarball
(+sha256, off-pod copy). Tarball contains: manifest, card, records + failures CSVs, split-gen code,
configs, norm stats. BOTH hashes exist before the word "freeze" is used.

Then G2 milestone report and STOP for advisor review at the gate. No model work crosses the manifest hash.
