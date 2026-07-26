# Items B + D: v1 code recovery + Table 3 recompute (2026-07-26)

## B. v1 code recovery

`https://github.com/Ammar12Falah/LithoGPT` cloned successfully (public HTTPS, no auth
needed) to `/workspace/v1_readonly/LithoGPT`, **outside** `/workspace/LithoGPT-2`,
read-only, nothing committed to it.

**Contents are not what "the code is available" would suggest.** `lithogpt/` and
`baselines/` each contain only a stray placeholder file named `init.py` (note: not
`__init__.py` -- not a real Python package init, 15 and 25 bytes respectively). There is
no model class definition, no training loop, no evaluation/Table-3-generation script,
and no `scripts/` directory despite the README's own "Repository Structure" section
claiming one exists. README.md itself is present and detailed (methodology prose,
Table 3's published numbers, stated limitations) but is documentation, not code.

`checkpoints/` contains three files:
- `kmeans_pure.joblib` -- **loads successfully**: `sklearn.cluster.MiniBatchKMeans`,
  `n_clusters=1000` (matches k=1000), `cluster_centers_.shape=(1000,4)` (matches the
  four input curves GR/RDEP/NPHI/RHOB). This is v1's real, working tokenizer.
- `scaler_pure.joblib` -- **loads successfully**: `StandardScaler`,
  `mean_=[74.22, 4.84, 0.32, 2.34]`, `scale_=[32.64, 50.18, 0.123, 0.221]`.
- `lithogpt_pure.pth` -- **fails to load**: `RuntimeError: PytorchStreamReader failed
  reading zip archive: failed finding central directory`. The file is exactly 4,194,304
  bytes (4x1024x1024, a suspiciously round number for serialized weights) and its
  byte-frequency distribution is anomalous for genuine float32 tensors: byte value 0
  appears 416,008 times (~10% of the file) and three other specific byte values each
  appear 130,000-165,000 times, versus the near-uniform distribution real trained
  weights produce. Not a git-lfs pointer (no `.gitattributes`, and the content isn't
  LFS-pointer text). Whether this is upload corruption, an incomplete/placeholder
  artifact, or something else, it is not a usable PyTorch checkpoint as committed.

**Conclusion, stated plainly per the pre-registered instruction:** the repo did not
404 or auth-fail, but it does not provide usable trained weights or any source code.
**Arm A must be reimplemented from specification**, using v1's real, loadable tokenizer
artifacts (kmeans/scaler) where methodology-faithful, and a freshly-trained transformer
decoder (checkpoint is unusable). Per the pre-registered fallback: this arm's numbers
are **not directly comparable to v1's published Table 3**, and are reported as this
experiment's own baseline. Timeline moves to the 8-12h track.

## D. v1 Table 3 recompute (1h timebox; used well under 5 minutes since no v1 evaluation
code exists to inspect -- see below)

No evaluation/Table-3-generation code exists anywhere in the cloned repo (confirmed
above), so **"if the code is available, read it and report the exact expression"
does not apply** -- there is no expression to read. Per the pre-registered fallback,
v1's outputs are not reconstructed; the arithmetic checks below use only the numbers
already supplied, and are pure verification, not reconstruction.

**Both stated suspicions for GR and NPHI are confirmed exactly:**

| Check | Computed | Published | Match |
|---|---|---|---|
| GR: 74.1 - 46.4 | 27.7 | 27.7 | **exact** |
| NPHI: 0.43 - 0.29 | 0.14 | 0.14 | **exact** |
| NPHI relative bias vs REAL/reference (0.14/0.29) | 48.3% | -- | (this experiment's own, correct framing) |
| NPHI relative bias vs GENERATED (0.14/0.43) | 32.6% | ~32% | **matches the published figure** |

This is strong circumstantial evidence that v1's published "W1" column is not a real
Wasserstein-1 distance but a plain absolute mean difference, and that its published
relative-bias figure divided by the generated mean rather than the real/reference mean
-- but circumstantial only, since no source code exists to confirm the literal
expression. **RDEP's "0.11 equals its own real mean" suspicion is not verified here**:
it would require RDEP's actual real-data mean value, which was not supplied and is not
recoverable from the (non-existent) v1 code.

**Per the pre-registered fallback: v1's W1 definition is recorded as unresolved.** This
experiment computes its own W1 (Wasserstein-1 / earth-mover distance, via
`scipy.stats.wasserstein_distance` on the empirical real vs. generated NPHI
distributions) with the definition stated explicitly in the ablation's own report
(item J), not inferred from v1's ambiguous methodology.
