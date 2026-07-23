# 6.3 (R8) Gate Ruling and Diagnostic-Round Pre-Registration

Context: LithoGPT-2 roadmap 6.3 (FSQ tokenizer, R8). Phase B sweep at HEAD
`e1029b20aeccb824b7cb87625f45796769d6c8cf` found no config meets R8: PEF ~19-20% degradation flat
across a 240x codebook range (structural, not capacity), DTC marginal at 9.99%. The advisor ruled
GATE NOT APPROVED and directed one bounded diagnostic round before ruling on PEF's scope.

This document is committed BEFORE any diagnostic compute (advisor Part IV item 12). It contains the
advisor's ruling verbatim, and the Pod pre-registration of the two metrics, the two patches, the
exact matched-metric cross-basin configuration, and the outcome tree, all fixed ahead of the numbers.

Frozen splits (d5b35a00) untouched; holdouts (test_kgs, test_nlog, open-10) RESERVED and not used;
blind_force NEVER loaded. Outside the hashed set.

---

## PART A — ADVISOR'S RULING (VERBATIM)

Disposition: GATE NOT APPROVED. R8 held exactly as signed. One bounded diagnostic round directed before I rule on PEF's scope. 6.4 stays gated.

The sweep is clean: pre-registered, pushed at e1029b20, every config through the committed harness, nothing sealed, bar untouched. The rule selected nothing and escalated, which is the mechanism working as designed. And executing the literal reading first was the right order, not a limitation, because literal is the strict floor and it is what makes a clean pass (branch 1 below) possible. Now the ruling.

The diagnosis is right, and I want to be explicit about why, because it drives everything below. PEF failing ~19-20% flat across a 240x codebook range is not a capacity problem. If scalar-quantization resolution were the bottleneck you would see monotone improvement with codebook size; a flat response means the information is destroyed upstream of the codebook, in the patching. PEF is the mechanically obvious curve for that: narrow dynamic range (most formation values sit in a tight band, roughly 1.5 to 6) and blocky, step-like structure at lithology boundaries. A patch-32 window averages across those steps, and because the range is compressed, small absolute smearing reads as large relative degradation. So "structural, patch size" is almost certainly correct and growing the codebook is correctly ruled out.

That diagnosis is exactly why I will not carve PEF out on this evidence. The line I am holding:

R8 was signed as "FSQ accepted when median per-curve relative degradation... is at most 5 percent, with no single canonical curve above 10 percent." PEF is a canonical curve. Deciding, after watching PEF fail, that PEF was never really in scope is silent bar-moving dressed as a technicality, and it is precisely the move this apparatus exists to prevent. A carve-out chosen because PEF is inconvenient is a concession. A carve-out chosen because we have demonstrated PEF is un-tokenizable at any reasonable config is a finding. They look identical on the page and are opposite in integrity, and the only thing separating them is running the cheap test first.

DP1, is PEF in scope: yes, for now. No carve-out from a position of not-yet-knowing whether PEF is rescuable. Note the two carve-out flavors are different calls: excluding PEF from the acceptance bar while still tokenizing it (minor) versus excluding PEF from the tokenized set entirely (a change to model inputs, since PEF is an informative lithology predictor for the real targets). I am not touching the latter, and I reach the former only as a documented finding if the round forces it.

DP2, retry or rule now: one bounded retry, plus one added metric, both pre-registered here before any new number.

(1) The matched-pipeline metric (imputer retrained on reconstructed train), which you correctly flagged as defensible. Not a tiebreaker: arguably the more faithful metric, and here is why that is not metric-shopping. R8's text is silent on whether the imputer trains on raw or reconstructed data, so both readings live inside the signed bar. The literal reading measures pure reconstruction fidelity. But the real downstream consumer is a transformer trained on tokens, which never sees raw curves. That is a matched pipeline by construction, so the matched metric better predicts real downstream impact. The teeth, so this cannot be a one-way ratchet toward "pass": the matched metric must be evaluated cross-basin (imputer trained on tokenized train, scored on the transfer direction), because an imputer that rescues PEF by learning basin-specific compensation on Kansas that will not transfer to Norway is a false pass, and BasinShift is entirely about transfer. Report the exact train/eval basin configuration so I can verify it. And the symmetry guard: if the matched cross-basin metric comes back worse than literal on any of the three headline curves (DTC/RHOB/NPHI), that is disqualifying even if literal passed. I want this metric able to sink the tokenizer, not only rescue it.

(2) One structural retry: patch 16, single value, largest codebook only. Not a sweep, not patch 8, not a per-curve PEF path (that is an architecture change and premature). Patch 16 is the direct test of the patching hypothesis, and it earns its spend for a second reason: DTC at 9.99% is a headline target sitting on the bar, which concerns me more than PEF failing, because DTC is not expendable and PEF is. A headline curve 0.01% inside a 10% bar lands on either side on a different dev draw or re-seed; it is effectively at the bar, not inside it. A smaller patch should give DTC real headroom, so patch 16 is DTC insurance as much as a PEF rescue. That reframes the retry as improving the headline result, not chasing a minor curve.

Nearly free, because it falls out of the baseline: report PEF's raw baseline imputation RMSE and a quick per-basin PEF distribution check (KGS vs NLOG vs FORCE). If PEF is unit-inconsistent or barite-contaminated across basins, its baseline is already noise, the relative-degradation bar is doubly punitive on it, and that is both a stronger justification for any eventual carve-out and a data flag for BENCHMARK.md. Establish it, do not assume it.

Scope and cost: matched metric at the two largest codebooks (patch 32), plus one patch-16 run at the largest codebook scored under both metrics, with the PEF baseline and per-basin check alongside. Your ~$1-2 CPU / minutes estimate is fine; if the minimal decisive set differs given what the harness exposes, use judgment and tell me what you ran. This is one round. A flat PEF response at patch 16 (roughly unchanged from patch 32) closes the retry question. A strong-but-insufficient improvement (say 19% moving toward 12%) is a reason to come back to me with the number, not a blank check for patch 8; I decide whether one more halving is worth the sequence-length cost.

DP3, DTC: escalated, not waved through (above). Whatever config seals, DTC's degradation goes in the model card as a stated limitation with its dev-well count, never reported as "passing" without the margin. DTS at 3 dev wells is non-robust: label it so everywhere, and it gates nothing.

Pre-registered outcome tree (commit to the decisions log before running, so the meaning is fixed ahead of the numbers). Strictest-guarantee-first, cheapest sequence length as tiebreak:

Some config passes the LITERAL metric on all canonical curves (median <=5%, no curve >10%) with DTC comfortably inside -> clean GATE APPROVED, no bar interpretation, no carve-out; prefer the smaller sequence length among passers. (Patch 32 fails literal on PEF, so this branch is patch 16 clearing PEF and DTC.)
Literal unmeetable at both patches, but the matched cross-basin metric passes all curves, headline three comfortably inside and matched not worse than literal on them -> GATE APPROVED, ruling the matched cross-basin metric operative, recorded as an R8 disambiguation-amendment with the original literal text quoted in full; confirm the chosen patch's sequence length is inside the G3 budget before sealing.
Only PEF (and/or thin-sample DTS) fails under both metrics at both patches, headline three pass with margin -> PEF carve-out as a documented finding, flavor (a) only (still tokenized, still an input, not gating), approved at the config maximizing headline-curve margin, PEF's reconstruction carried into BENCHMARK.md and eval as a known limitation. Not a free pass.
Any headline curve fails or is marginal under the faithful metric -> NO approval; rethink patch, FSQ level allocation, or the tokenizer-vs-continuous question rather than paper over it.

For the agent: relay verbatim, same day, and commit this ruling before compute (Part IV item 12; a ruling once sat undelivered for three sessions). Both metrics, both patches, per-curve PEF and DTC, and the PEF baseline/per-basin check land as committed artifacts, not chat-only. 6.4 does not start until I record GATE APPROVED against branch 1, 2, or 3; this round is not approval.

---

## PART B — POD PRE-REGISTRATION (fixed before any diagnostic number is computed)

All arms route through the committed `scripts/basinshift/eval_harness.py` scorer (same XGBoost
params/SEED/transforms as the committed baseline; physical-unit scoring; population-identity
asserted). Tokenizer = the committed FSQ autoencoder (`fsq_tokenizer.py`), 30 epochs, TRAIN-global
per-curve z-score in the baseline's stored space (std floor 1e-6), identical to Phase B except
where patch size is the variable under test. Scope: all 11 canonical curves as imputation targets.
R8 bar unchanged: median per-curve relative degradation <=5% AND no single canonical curve >10%.

### B.1 The two patches
- patch 32 (Phase B value) at the two largest codebooks cb4375 [7,5,5,5,5] and cb15360 [8,8,8,6,5].
- patch 16 (structural retry) at the largest codebook cb15360 [8,8,8,6,5] only. Single run, not a
  sweep. No patch 8 and no per-curve PEF path in this round (advisor: those are his to authorize).

### B.2 The two metrics (degradation = (arm_RMSE - raw_reference_RMSE) / raw_reference_RMSE, per curve, physical units)
- LITERAL (pure reconstruction fidelity): imputer trained on RAW train; evaluated on the eval split
  with its FEATURE curves replaced by the tokenizer reconstruction (target-curve truth stays raw).
  This is the Phase B metric.
- MATCHED cross-basin (matched-pipeline, the added faithful metric): imputer RETRAINED on the
  RECONSTRUCTED source-basin train (feature curves reconstructed; regression TARGET stays the raw
  physical curve, because the downstream consumer predicts true values from tokens), then evaluated
  cross-basin on the RECONSTRUCTED target-basin eval features.
- raw reference (shared denominator): imputer trained on RAW source-basin train, evaluated on RAW
  target-basin eval features. So LITERAL isolates reconstruction of the eval features under a
  raw-trained imputer; MATCHED additionally trains the imputer on tokens. Both are reported against
  the same raw_reference_RMSE on the same cross-basin split, so they are directly comparable.

### B.3 Exact matched-metric train/eval basin configuration (true cross-basin transfer, holdouts reserved)
FORCE has no dev split, so the two dev-eval cross-basin transfer directions are:
- Direction KGS->NLOG (Kansas-train, Norway-eval): source-basin train = `kgs_train` (Kansas);
  eval split = `nlog_dev` (Norway). This is the advisor's decisive honesty test (a PEF rescue that
  is really Kansas-specific compensation shows up here as a Norway-transfer failure).
- Direction NLOG->KGS (Norway-train, Kansas-eval): source-basin train = `nlog_train` (Norway);
  eval split = `kgs_dev` (Kansas). Reported for symmetry so neither direction can be cherry-picked.
Both directions reported for every config. Imputers use the committed XGBoost params/SEED. No test
holdout (test_kgs, test_nlog, open-10) and no blind_force is touched. The literal metric is also
computed on these same two cross-basin splits so LITERAL and MATCHED sit side by side per curve.

### B.4 Symmetry guard (disqualifying)
If MATCHED cross-basin degradation is WORSE than LITERAL on ANY of the three headline curves
(DTC, RHOB, NPHI) in a direction, the matched metric is disqualified for that direction even if
literal passed. Matched-vs-literal reported side by side for DTC/RHOB/NPHI in both directions.

### B.5 Boundaries (from the ruling; Pod does not decide these)
- No config sealing, no bar interpretation, no carve-out. Pod reports which outcome-tree branch the
  data indicates; the advisor rules. DTC never reported as "passing" without its margin + dev-well
  count. DTS (3 dev wells) labeled non-robust everywhere and gates nothing.
- If PEF at patch 16 improves strongly but insufficiently (e.g. ~19% moving toward ~12%), STOP and
  bring the number to the advisor; do NOT proceed to patch 8.

### B.6 Pre-registered OUTCOME TREE (Pod evaluates which branch the data lands in; does NOT rule)
- Branch 1 (clean pass candidate): some config passes the LITERAL metric on all 11 canonical curves
  (median <=5%, no curve >10%) with DTC comfortably inside. Per the ruling this can only be patch 16
  clearing PEF and DTC (patch 32 fails literal on PEF).
- Branch 2 (matched-metric pass candidate): literal unmeetable at both patches, BUT the matched
  cross-basin metric passes all curves, headline three comfortably inside, and matched NOT worse
  than literal on the headline three (symmetry guard holds).
- Branch 3 (PEF carve-out candidate, flavor a only): only PEF (and/or thin DTS) fails under BOTH
  metrics at BOTH patches, headline three pass with margin.
- Branch 4 (no-pass candidate): any headline curve fails or is marginal under the faithful metric.

### B.7 Cost pre-registration
CPU only. Estimate: retrain 3 tokenizers (cb4375-p32, cb15360-p32 ~22 min each; cb15360-p16 ~44 min
as patch count doubles) ~88 min; reconstruct kgs/nlog train+dev per config; raw + matched XGBoost
imputers (matched = per config x 2 directions x 11 curves). Projected ~2.5-3.3 h wall, ~$1.1-1.5 at
the A40 rate $0.44/hr. UNDER the money gate (<=$5 AND <=4 h). A running-projection guard halts before
any config that would cross ~92% of 4 h; completed work is written incrementally. No paid GPU.

---

## PART C — ERRATUM (appended 2026-07-23 by Pod; original Part A and Part B text above is UNCHANGED)

Stated cause: a basin was mislabeled in Part B.3. `nlog` is the **Netherlands** (Nederlandse Olie-
en Gasportaal), NOT Norway. **Norway is the FORCE2020 dataset (`force2020`).** Part B.3 wrote
"nlog_dev (Norway)" and "(Kansas-train, Norway-eval)"; the correct eval-basin label is
**Netherlands**. The EXPERIMENT is unchanged and correct: the two cross-basin dev directions are
`kgs_train -> nlog_dev` and `nlog_train -> kgs_dev`, i.e. **Kansas <-> Netherlands**. Only the
basin name in the prose was wrong; the pools, the driver, and every computed number are correct.

Consequence (surfaced here so it does not sit only in a config line): the cross-basin transfer
testable on the frozen DEV splits is **Kansas <-> Netherlands only. Kansas <-> Norway is NOT
testable on dev**, because FORCE (Norway) has no dev split. Norway is available as an eval basin
only via the **open-10 holdout**, which is a reported BasinShift eval set; selecting the tokenizer
on it would be selection on a test set. Pod does not use open-10. The advisor's stated concern
named Norway; the honesty test actually run is the Kansas<->Netherlands cross-basin proxy. Whether
Norway transfer is worth evaluating on the open-10 holdout is the advisor's call (Plan recommends
against, for the selection-on-a-test-set reason).
