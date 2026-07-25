# LithoGPT-2 6.5 architecture contract (Phase 4, ATCE critical path)

Ruling-independent: valid under every tokenizer disposition currently on the table (continuous
projection, FSQ codebook lookup, or a later carve-out). Nothing here selects a config; Phase 2
items 3/4 (input/output head choice) stay swappable behind one interface until the advisor rules
on tokenizer disposition. Model size stays at S until token/sequence counts are reported and
reviewed (Section 6).

## 1. Sequence assembly

- Sequences are assembled **per well**, from contiguous depth-grid patches (0.1524 m sample grid,
  patches of `patch` consecutive samples, matching the FSQ tokenizer's own patchify convention).
- Context length: **4096 depth samples minimum** per training sequence (a fixed budget in raw
  depth-samples, not in patch-count, so patch size only changes how many patches fill one
  sequence: 4096/32 = 128 patches/sequence at patch32; 4096/16 = 256 patches/sequence at patch16).
- RoPE (rotary position embedding) applied on **depth**, not on sequence index alone, so that
  patch position within a sequence carries physical depth meaning and two sequences from
  different starting depths remain comparable.
- Token/sequence counts at patch32 and patch16: see Section 6 (measured, not assumed, in this
  commit).

## 2. Conditioning inputs (per 6.5 spec)

- **TVD** (true vertical depth) -- scalar per patch position, continuous.
- **Basin group** -- categorical (Kansas / Netherlands / Norway), embedded.
- **Curve-availability mask** -- per-curve binary flag for the current well/section, so the model
  sees which curves are genuinely logged vs synthetically absent, distinct from a masked-for-
  training-objective flag.
- **Source** -- categorical (kgs / nlog / force2020), embedded, distinct from basin group since a
  single source can span basin-adjacent classification nuances already documented in the alias
  audit.
- **Curve-type embeddings** -- one embedding per canonical curve (GR, RHOB, NPHI, DTC, PEF, SP,
  CALI, RDEP, RMED, RSHA, DTS), added to every patch token so the model knows which curve a given
  patch belongs to independent of its position in the sequence.

## 3. Input head -- swappable module, one interface

```
class InputHead(nn.Module):
    """Two implementations behind one call signature: patch -> d_model embedding.
    Swapping is a config flag, not a rewrite, per the brief."""
    def forward(self, patch_batch: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError

class ContinuousInputHead(InputHead):
    """Direct linear projection of the raw (standardized) patch vector."""
    def __init__(self, patch, d_model):
        super().__init__()
        self.proj = nn.Linear(patch, d_model)
    def forward(self, patch_batch):
        return self.proj(patch_batch)

class CodebookInputHead(InputHead):
    """FSQ-quantized code -> embedding lookup. Wraps a trained fsq_tokenizer.FSQAutoEncoder's
    encoder+quantizer; the embedding table replaces the continuous decoder path used standalone."""
    def __init__(self, fsq_encoder, fsq_quantizer, codebook_size, d_model):
        super().__init__()
        self.encoder = fsq_encoder      # frozen or fine-tuned, config-controlled
        self.quantizer = fsq_quantizer
        self.embed = nn.Embedding(codebook_size, d_model)
    def forward(self, patch_batch):
        z = self.encoder(patch_batch)
        codes = self.quantizer.codes(z)          # integer indices, see fsq_tokenizer.FSQ.codes
        flat_idx = self._flatten_multi_index(codes)   # per-dim levels -> single codebook index
        return self.embed(flat_idx)
```

## 4. Output head -- swappable module, one interface

```
class OutputHead(nn.Module):
    """d_model -> next-patch prediction. Two implementations, config-selected."""
    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError

class CodebookOutputHead(OutputHead):
    """Predicts codebook logits (classification over the discrete vocabulary)."""
    def __init__(self, d_model, codebook_size):
        super().__init__()
        self.proj = nn.Linear(d_model, codebook_size)
    def forward(self, hidden):
        return self.proj(hidden)     # logits, cross-entropy against the true code index

class ContinuousOutputHead(OutputHead):
    """Predicts the raw (standardized) patch vector directly (regression)."""
    def __init__(self, d_model, patch):
        super().__init__()
        self.proj = nn.Linear(d_model, patch)
    def forward(self, hidden):
        return self.proj(hidden)     # regression target, MSE against the true patch
```

Input head and output head are chosen **independently** (four combinations are all structurally
valid: continuous-in/continuous-out is a plain autoencoder-style regressor; codebook-in/codebook-
out is the FSQ-native path; the two mixed combinations exist for ablation). Selection is a
constructor argument, not a code branch inside the model body.

## 5. Objectives

- **FIM (fill-in-the-middle) span corruption**: a contiguous span of patches is masked; the model
  predicts the masked span conditioned on both sides. Matches the curve-availability-mask
  conditioning input (Section 2) -- span corruption is a training-time analogue of a real missing-
  log gap.
- **Causal next-patch**: standard autoregressive next-token (next-patch) prediction along the
  depth axis, RoPE-aware.
- Both objectives share the same input/output head pair per run; loss is a weighted sum, weight
  ratio left as a training hyperparameter (not fixed here).

## 6. Sequence/token counts (measured, this commit)

See companion file `reports/basinshift/atce_sequence_counts_2026-07-25.json` for the actual
counts from the frozen train pools (kgs_train + nlog_train + force_train), at patch32 and patch16,
context=4096. Model size stays at **S (12 layers, d_model=512, 8 heads, ~25M params)** pending
review of these counts -- no self-authorized scale-up.

## 7. Basin-balanced sampling

Kansas capped at approximately 72% of any training batch/epoch (matching its share of the
combined train pool while preventing it from crowding out Netherlands and Norway, both
meaningfully smaller). Enforced at the sampler level (weighted sampling), not by discarding
Kansas rows.

## 8. Blind-well rule

`blind_force` is **never loaded**, in the data loader itself, not just upstream. The data loader
asserts on every well-id/safe-name lookup against the frozen `blind_force` split set (matching
`eval_harness.py`'s existing `BLIND` set-membership check and `RuntimeError(f"REFUSED blind ...")`
pattern) and **fails loudly** (raises, does not warn) if a blind well is ever requested by any
caller, training or otherwise. This mirrors the pattern already enforced in `eval_harness.load_well`.

## Boundaries

This is a **contract**, not a training run. No model is instantiated or trained here. Phase 6's
smoke test exercises this contract end-to-end (continuous input -> discrete output, the mixed
combination, as the hardest structural case) with synthetic/tiny data, not real training. Phase 2
items 3/4 (input/output head disposition) remain swappable until the advisor rules on the
tokenizer question; nothing here is a selection.
