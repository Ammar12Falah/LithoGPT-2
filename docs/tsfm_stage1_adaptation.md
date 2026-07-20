# TS-FM Stage 1 (R7, roadmap 6.2) — adaptation surgery + feasibility

Purpose: the LoRA-adapted TS-FM baseline that Stage 1 runs **vs the committed XGBoost opponent**
(per the R7 amendment `db30b10`: Stage 1 opponent is XGBoost only; escalate if TS-FM beats it by
>25% rel-RMSE on ALL three curves). Built against the frozen corpus `d5b35a00`; dev + open-10
wells only; **blind-10 never touched**. This document is the "adaptation surgery documented"
R7 requires. It is a Phase-A (CPU-only, no paid A40) feasibility record — no compute spend.

## 1. Model selection (feasibility PROVEN this session, read-only/CPU)
- **Chosen: `AutonLab/MOMENT-1-large`** — a time-series foundation model whose pre-trained head
  is **masked reconstruction (imputation)**. Reachable from the pod (HF `config.json` → HTTP 200),
  downloads to `/workspace/.hf_cache`, loads + inits in ~4.8 s (cached), **341.2M params**,
  backbone frozen by default (0 trainable → LoRA supplies the adapters). Masked-reconstruction
  forward returns the expected shape.
- Rejected alternatives: **Chronos** (`amazon/chronos-t5-small`, reachable 200) and **TimesFM**
  (`google/timesfm-1.0-200m` → 404) are **univariate forecasting** models — wrong paradigm for
  curve imputation. MOMENT is the only reachable imputation-native TS-FM.

## 2. Architecture map (probed)
`RevIN normalizer → Patching (patch_len 8, seq_len 512 ⇒ 64 patches) → PatchEmbedding →
T5Stack encoder (d_model 1024) → PretrainHead (reconstruction)`. `embed()` returns a pooled
`[B, 1024]` (mean over patches). LoRA-targetable linears in the encoder: `q, k, v, o` (24 each)
and FFN `wi_0, wi_1, wo`. `peft` 0.13.2 installed.

## 3. Well-log → TS-FM input mapping (the surgery, part 1)
- **Depth is the time axis.** Each processed well is a depth-indexed series (`depth_m`); each
  canonical curve is a **channel**: `{GR, RHOB, NPHI, DTC, PEF, SP, CALI, RDEP, RMED, RSHA, DTS}`.
- **Masked-valid convention:** a curve value is real only where its `_mask` is True, else NaN.
  Resistivities are already stored as log10(ohm·m). `BS` (bit size) excluded (matches XGBoost).
- **Windowing:** the depth series is cut into MOMENT's fixed 512-sample windows; RevIN handles
  per-window per-curve scale, so no external normalization is needed (matches "trees are
  scale-invariant" — here the FM normalizes internally).
- Same targets and same eval directions/metrics as the committed XGBoost baseline, so Stage 1 is
  apples-to-apples: A cross(KGS+NLOG)→Norway open-10; B cross(NLOG+FORCE)→test_kgs; C1/C2 in-basin.

## 4. KEY FINDING — MOMENT-1 is channel-independent; BasinShift is cross-channel
Probed and confirmed: a multichannel input `(B=2, C=3, 512)` returns reconstruction `(2, 3, 512)`
with **each channel reconstructed from its own context only** — MOMENT-1 reshapes `[B,C,T]→[B·C,T]`
and processes channels independently (PatchTST-style). BasinShift, however, hides an **entire**
target curve and must predict it **from the sibling curves at the same depth**. Native MOMENT
cannot do this: a fully-masked channel has no self-context and cannot see other channels. So a
**cross-channel adaptation is mandatory** — this is the substantive part of the surgery.

## 5. Recommended cross-channel adaptation (FOR CONFIRMATION before building)
Frozen MOMENT encoder + **LoRA on `q,v`** used as a **per-curve encoder**: encode each *input*
curve (batched in the `B·C` dimension, one forward) to per-patch hidden states
`[C_in, 64, 1024]`; a small **trainable cross-channel head** aggregates across input curves per
patch (mean or a linear over the concatenation) → predicts the **target** curve's 512 values
(64 patches × 8). LoRA adapters + head are trained on the train split; scored on dev + open
exactly as XGBoost. Loss = MSE on masked-valid target samples.
- Alternative considered and rejected: pooled-`embed()` `[B,1024]` head — discards depth
  resolution, cannot predict a 512-length curve well.
- This is a real, recorded adaptation choice (not native MOMENT usage). It affects the
  apples-to-apples comparison and the paper's methodology, so it is surfaced for sign-off before
  the harness is built and the paid A40 run is estimated.

## 6. Cost shape (estimate to follow after the CPU smoke test)
Dominant cost = number of 512-windows across the train pool × per-window encoder forward/backward
(C_in≈10 curves batched). Windows ≈ total valid depth samples / 512. The full A40 wall-clock +
dollar estimate is produced from a CPU smoke test's per-step timing scaled to the A40, and is
reported at the Phase-A STOP for Ammar's go (paid run needs explicit confirmation; >4 h or >$5
requires it). Two-day budget is the hard ceiling.

## 7. Environment (Rule 13)
Stage-1 TS-FM env (snapshot `docs/tsfm_stage1_env_2026-07-20.txt`): torch 2.4.1+cu124 (CUDA, A40),
transformers **4.33.3** (pinned by momentfm), peft 0.13.2, accelerate, momentfm. **Note:** momentfm's
dependency constraint **downgraded numpy 1.26.3 → 1.25.2** in this env. This is the *TS-FM
adaptation* environment, explicitly NOT the ingestion/freeze environment — the frozen parquets are
ground truth and the corpus freeze `d5b35a00`, its manifest, and the XGBoost baseline were all
committed under their own clean pinned env (numpy 1.26.3) and are unaffected. Recorded per Rule 13.

## 8. Standing rules
Blind-10 never loaded (dev + open-10 only). Built against `d5b35a00`; no re-cut splits, no reopened
ingestion, no synthetic data. Evidence artifact, outside the hashed set; does not move
`qc_code_sha256` or `d5b35a00`. Predictions will be FROZEN at Stage-1 completion (immutable, so
Stage 2 cannot retune after seeing S-model numbers).
