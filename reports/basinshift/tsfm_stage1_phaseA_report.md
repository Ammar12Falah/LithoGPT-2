# TS-FM Stage 1 (R7, roadmap 6.2) — Phase A report: LoRA harness + CPU smoke + A40 cost STOP

Date 2026-07-21. CPU-only, zero paid A40 spend this session. Outside the hashed set; corpus freeze
`d5b35a00` and `qc_code_sha256 e12d4b64` untouched. Blind-10 never loaded (uses `eval_harness.POOLS`,
which refuse blind). This is the Phase-A **cost STOP**: numbers below, then HOLD for Ammar's go.

## 0. Preflight (all PASS)
- HEAD local `caf77a9` == origin/main `caf77a9` (remote confirmed via public GitHub API; pod
  `git ls-remote` wedges the proxied PTY so the API was used).
- Anti-blank-sibling: kgs processed parquets = 9307; `reports/nlog_qc_records.csv` = 5005 lines.
- `eval_harness.py`, `harness_validation.txt`, `split_assignment.csv`, MOMENT cache all present.

## 1. Harness built (2 PRE-DECLARED head configs — recorded BEFORE any full result)
`scripts/basinshift/tsfm_lora_harness.py`. Frozen `AutonLab/MOMENT-1-large` encoder, LoRA on `q,v`
`r=8 alpha=16 dropout=0.05` (identical across A, B, and control). Per-patch sibling embeddings
`[B,C,64,1024]` come from replicating `MOMENT.embed(reduction="none")`. A curve-identity embedding
(perm-invariant tag) is added to each channel before pooling. Shared 2-layer GELU MLP head
`Linear(1024->512) -> GELU -> Linear(512->8)`, unpatched to the 512-sample target window.

- **Config A "channel-mean"**: mean-pool sibling per-patch embeddings over the channel axis
  (permutation-invariant), then the shared MLP. Trainable params **1,326,600**.
- **Config B "channel-attention"**: learned attention pooling over sibling channels, query from a
  target-curve-type embedding, then the SAME shared MLP. Trainable params **2,379,272**.
- MLP head identical across A and B; only the pooling differs. Optimizer/LR/steps/batch/seed
  identical across A, B, control. Head selected on DEV only, no further search.

**Matched random-init control**: same architecture, encoder + patch_embedding parameters randomized
(no pretrained information); identical trainable budget (same LoRA + same head). (a)-(b) delta =
measured pretraining contribution. Backbone frozen in both; only LoRA + head + pooling train.

**Task framing mirrors the committed XGBoost BasinShift baseline exactly**: hide one canonical target
(DTC/RHOB/NPHI); predict per depth-sample from the remaining canonical curves + depth_m (BS excluded;
resistivity log10; masked-valid only). Depth = sequence axis, MOMENT 512-sample windows. Input NaNs
filled with the TRAIN-global per-curve mean before RevIN; head predicts in TRAIN-global-standardized
space, de-standardized to physical before the scorer (targets are physical -> inverse_transform is
identity). Scored ONLY through `scripts/basinshift/eval_harness.py`.

### Engineering decisions recorded (reversible, my authority)
1. **`eval_harness.py` made importable**: its XGBoost self-validation block was wrapped under
   `if __name__ == "__main__":` so `build_grid/score/load_well/POOLS/RUNS` can be imported by the
   TS-FM harness. `python eval_harness.py` behaviour is byte-identical (re-validated, see §4). The
   scorer remains the single instrument all systems flow through.
2. **Gradient checkpointing disabled on the encoder.** MOMENT enables it by default; with the frozen
   patch-embedding feeding the encoder, the checkpointed segment received no `requires_grad` input
   and **LoRA gradients came back None** (only the head trained). Disabling it makes the LoRA
   adapters actually train — confirmed by the grad-norm check in §2. Cost impact folded into §3.
3. **Env pin.** Installing pandas/pyarrow/xgboost unpinned pulled numpy to 2.4.6; forced back to the
   validated **numpy 1.25.2**. Env now matches the committed snapshot `tsfm_stage1_env_2026-07-20`
   (numpy 1.25.2, pandas 2.2.3, pyarrow 25.0.0, xgboost 3.2.0, torch 2.4.1+cu124, transformers
   4.33.3, peft 0.13.2, momentfm 0.1.4). Fresh freeze committed as `tsfm_stage1_env_2026-07-21.txt`.
4. **Connection**: the `lithopod_key` authenticates this pod; the handoff-named `id_ed25519` does NOT
   (Permission denied publickey).

## 2. CPU smoke — BOTH paths, all cells ACCEPTED by the shared scorer
Direction `C2_in_norway`, target DTC, 4 combos, 8 steps, batch 4, 8 train wells, `--max-test-wells 3`
(grid sliced consistently so population identity stays exact). `reports/basinshift/tsfm_smoke.json`.

| init | cfg | trainable | grad_check (LoRA / head) | HARNESS |
|---|---|---|---|---|
| pretrained | A | 1,326,600 | lora 2.23e-3 (96/96) / head 3.36e-1 (5/5) | ACCEPTED n=33445 wells=3 |
| pretrained | B | 2,379,272 | lora 2.66e-3 (96/96) / head 5.62e-1 (8/8) | ACCEPTED n=33445 wells=3 |
| random     | A | 1,326,600 | lora 9.15e-2 (96/96) / head 7.94e-1 (5/5) | ACCEPTED n=33445 wells=3 |
| random     | B | 2,379,272 | lora 1.95e-1 (96/96) / head 1.95e+0 (8/8) | ACCEPTED n=33445 wells=3 |

All four: both paths train (LoRA 96/96 params receive gradients — 24 layers x q,v x lora_A/B),
run inference, pass `eval_harness.score()` population identity (equal count + equal sha256 mask;
popsig `d4f0854fdd50`). RMSE ~29-31 is meaningless at 8 steps — this is plumbing, not accuracy.

## 3. A40 cost estimate (`scripts/basinshift/cost_model.py`)
Method (brief Part 3): CPU smoke per-step -> per-window fwd+bwd -> x CPU->A40 speedup ->
x proposed window-presentation budget; inference is a minor additive term.

**Measured CPU primitives** (batch 4, MOMENT load excluded): cfgA **4.27 s/window**, cfgB
**7.29 s/window** fwd+bwd; inference ~1.5 s/window fwd-only.

**CPU->A40 speedup assumption (stated explicitly)**: per-window fwd+bwd on the A40 (48GB, tensor
cores, and the larger batch the A40 affords) vs this 96-core CPU at batch 4. Bracketed
**40x (high cost) / 75x (expected) / 120x (low cost)** for a 341M-param transformer. This is the
dominant uncertainty; a 1-minute A40 micro-benchmark would replace it with a measured number (I did
NOT run it — respecting the no-paid-A40 hold; offered on request).

**A40 rate**: runpod.io/pricing, A40 48GB — Community **$0.35/hr**, Secure **$0.44/hr**. Pod is a
persistent EU/secure volume -> expected **$0.44/hr**. (Confirm the pod's actual rate.)

**Proposed full-run schedule (RECOMMENDED; the knob to lock)**: 12 cells/config (4 directions x 3
targets, faithful apples-to-apples with XGBoost's 12 fits), **batch 32, 600 steps/cell** =
230,400 window-presentations/config. **3 trainings**: pretrained-A, pretrained-B, control on the
dev-winning config. Inference over dev (head selection) + all 12 test cells. AdamW, LR 1e-3 with 50-
step warmup + cosine decay, seed 20260715. Train only on windows containing >=1 valid target sample.

| scenario | train_hr | infer_hr | total_hr | USD |
|---|---|---|---|---|
| LOW  (S=120, control=A, $0.35) | 8.4 | 0.4 | **8.9** | **$3.10** |
| EXPECTED (S=75, control=A, $0.44) | 13.5 | 0.7 | **14.2** | **$6.24** |
| HIGH (S=40, control=B, $0.44) | 30.1 | 1.3 | **31.4** | **$13.82** |

Speedup sensitivity (expected schedule, $0.44): 40x->26.6h/$11.70, 60x->17.7h/$7.80,
75x->14.2h/$6.24, 90x->11.8h/$5.20, 120x->8.9h/$3.90.

**Two-day (48 h) budget: FITS even at HIGH (31.4 h).** Balance ~$340 -> affordable at every bracket.
Every bracket exceeds 4 h and expected exceeds $5, so this **requires Ammar's explicit go** before any
paid launch (which is exactly this STOP). `STEPS_PER_CELL` is the primary cost lever; a per-direction
multi-target structure (4 cells/config instead of 12) would cut training ~3x if Plan prefers it.

## 4. Harness integrity re-check
`python eval_harness.py` re-run under this env to confirm the `__main__` guard changed nothing —
result and diff vs the committed `harness_validation.txt` recorded in
`reports/basinshift/harness_revalidation_2026-07-21.txt`.

## 5. STOP
No paid A40. Awaiting Ammar's confirmation of the cost number and Plan's lock of the full-run
schedule (structure: 12-cell vs 4-cell multi-target; steps/cell; batch; LR). On go: build the locked
schedule, run 3 trainings (TRAIN-only, dev-select head), score all vs XGBoost through the shared
harness in physical units with population identity asserted, compute the (a)-(b) control delta, check
the >25%-on-all-three clause, and FREEZE + hash both systems' dev+open predictions.
