# Item Q: v1's code-availability statement is false as published (2026-07-26)

Committing this as a finding, per instruction. No manuscript language drafted --
Ammar decides how the new availability statement reads.

## The finding

v1's GitHub repository (`github.com/Ammar12Falah/LithoGPT`) does not contain the
model, training, or evaluation source code its publication's availability
statement implies. Specifically, as of commit `d0a86f00bfeb2c725572e41b2cfa179becbd4a19`
(HEAD, `origin/main`), and confirmed unchanged across the repository's full
history (all 3 commits: `093114a`, `a7cdd1c`, `d0a86f0` -- see item L):

- `lithogpt/__init__.py` and `baselines/__init__.py` are stub placeholders (each
  a single trivial line), not real package source.
- No `scripts/` directory exists, despite the README describing one.
- `checkpoints/kmeans_pure.joblib` (MiniBatchKMeans, k=1000, 4 features) and
  `checkpoints/scaler_pure.joblib` (StandardScaler) load cleanly -- but item U's
  validation gate found they reconstruct this project's own FORCE data materially
  worse than a fresh refit (NPHI RMSE 3x worse), so even these two functional
  artifacts are not usable as-is for this project's manuscript-candidate result.
- `checkpoints/lithogpt_pure.pth` (4,194,304 bytes) fails to load as a PyTorch
  checkpoint (`RuntimeError: PytorchStreamReader failed reading zip archive:
  failed finding central directory`), identically from the very first commit
  that introduced it (see item M). It is not hex- or base64-encoded text (item
  M rules this out on distinct-byte-value grounds alone). Item X upgrades this
  finding: the file's internal zip structure (43 recoverable `PK` local-file
  headers matching a genuine `torch.save` layout -- `data.pkl`, numbered tensor
  storage blobs, format/alignment/byteorder metadata) and its size (4,194,304
  bytes, ~19.5% of the 21.5 MB an fp32 checkpoint of this project's own
  5,383,144-parameter architecture would need) together point to **truncation
  at a fixed upload-size ceiling**, not deliberate corruption or a placeholder
  upload. The file was very likely a genuine checkpoint once, cut short.
- No other branches or tags exist that might hold a working version. Confirmed
  twice: locally (`git branch -a`, `git tag`, item L) and against the remote
  directly (`git ls-remote --heads --tags`, item X) -- both show exactly one ref,
  `refs/heads/main`.

## What this means

Whatever code-availability statement v1's publication makes, it cannot be
satisfied by cloning the linked repository: a reader following it would be able
to obtain a tokenizer and scaler (though not one validated as usable for
out-of-population data, per item U), but not the model architecture, training
procedure, or the published checkpoint's exact weights. This item's ablation
(item J) worked around this by reimplementing the architecture from the paper's
stated specification and refitting a tokenizer/scaler on its own data (item U),
with the reimplementation caveat stated explicitly in all outputs.

## Disposition

This is recorded as a finding only. The new availability statement's wording is
Ammar's decision, not drafted here.
