#!/usr/bin/env python3
"""FSQ tokenizer for LithoGPT-2 well-log curves (R8 / roadmap 6.3).

Per-curve, per-patch Finite Scalar Quantization (FSQ, Mentzer et al. 2023) autoencoder:
  depth patch of PATCH samples on the 0.1524 m grid  ->  encoder MLP  ->  FSQ quantizer
  (no learned codebook, no commitment loss; straight-through round)  ->  continuous residual
  decoder MLP  ->  reconstructed patch.

Design notes (Phase A, proposed for pre-registration lock; nothing here self-certifies R8):
- One independent tokenizer per canonical curve so per-curve dynamic range is respected.
- Curves live in the SAME space the committed XGBoost baseline consumes: resistivity in
  log10, everything else physical (see eval_harness.inverse_transform / load_well). On top of
  that space the tokenizer applies a TRAIN-global per-curve z-score for numerical stability and
  de-standardizes on decode, so reconstructions are returned in the baseline's stored space.
- Patches are cut on the depth grid (contiguous samples), NOT on valid-only positions, so depth
  alignment and the per-sample mask are preserved. Masked (NaN) samples inside a patch are set
  to the standardized mean (0.0) for encode; on decode we re-impose the original NaN mask so the
  reconstruction has byte-identical missing-value structure to the raw curve.
- "Continuous residual decoder": the decoder is a continuous function of the discrete FSQ code,
  so it reconstructs sub-quantization detail the finite code alone cannot carry.

Read-only over frozen splits (d5b35a00). blind_force is NEVER loaded here. Outside hashed set.
"""
import numpy as np
import torch
import torch.nn as nn

PATCH = 32          # 32 * 0.1524 m = 4.877 m depth window; 512-sample Stage-1 window = 16 patches
HIDDEN = 64
SEED = 20260715


# ---------------- FSQ quantizer ----------------
def _round_ste(z):
    """Round with straight-through gradient."""
    return z + (torch.round(z) - z).detach()


class FSQ(nn.Module):
    """Finite Scalar Quantization. `levels` = per-dim level counts; codebook = prod(levels).

    Each latent dim is squashed with tanh to +/-(L-1)/2, rounded to an integer level, then
    rescaled to [-1, 1] for the decoder. Gradient flows straight through the round.
    """

    def __init__(self, levels):
        super().__init__()
        levels = [int(x) for x in levels]
        self.levels_list = levels
        self.d = len(levels)
        self.codebook_size = int(np.prod(levels))
        self.register_buffer("levels", torch.tensor(levels, dtype=torch.float32))
        # buffer name must not shadow nn.Module.half(); use hlev = (L-1)/2 per dim
        self.register_buffer("hlev", (torch.tensor(levels, dtype=torch.float32) - 1.0) / 2.0)

    def quantize(self, z):
        """z: [..., d] -> quantized latent in [-1, 1], same shape."""
        zb = torch.tanh(z) * self.hlev          # bounded to +/-(L-1)/2
        zq = _round_ste(zb)                      # integer levels, STE gradient
        return zq / self.hlev                    # rescale to [-1, 1]

    def codes(self, z):
        """Integer code indices per dim in [0, L-1] (no gradient); for diagnostics."""
        zb = torch.tanh(z) * self.hlev
        idx = torch.round(zb) + self.hlev
        return idx.to(torch.int64)

    def forward(self, z):
        return self.quantize(z)


# ---------------- per-curve FSQ autoencoder ----------------
class FSQAutoEncoder(nn.Module):
    def __init__(self, levels, patch=PATCH, hidden=HIDDEN):
        super().__init__()
        d = len(levels)
        self.patch = patch
        self.enc = nn.Sequential(nn.Linear(patch, hidden), nn.GELU(), nn.Linear(hidden, d))
        self.fsq = FSQ(levels)
        self.dec = nn.Sequential(nn.Linear(d, hidden), nn.GELU(), nn.Linear(hidden, patch))

    def forward(self, x):
        z = self.enc(x)
        zq = self.fsq(z)
        xr = self.dec(zq)
        return xr


# ---------------- patchify helpers (numpy, depth-grid) ----------------
def standardize(arr, mean, std):
    """Stored-space curve -> standardized, NaN -> 0.0 (the standardized mean)."""
    z = (arr - mean) / std
    return np.where(np.isfinite(z), z, 0.0).astype("float32")


def patchify(std_arr, patch=PATCH):
    """1-D standardized curve -> [n_patches, patch], zero-padded tail. Returns (patches, L)."""
    L = len(std_arr)
    n = int(np.ceil(L / patch))
    buf = np.zeros(n * patch, dtype="float32")
    buf[:L] = std_arr
    return buf.reshape(n, patch), L


def unpatchify(patches, L):
    """[n_patches, patch] -> 1-D length L (drop padded tail)."""
    return patches.reshape(-1)[:L]


# ---------------- training / reconstruction ----------------
def compute_stats(curve_arrays):
    """curve_arrays: list of stored-space 1-D arrays (with NaN). Returns (mean, std) over all
    finite samples. std floored to 1e-6 to avoid divide-by-zero on flat curves."""
    vals = np.concatenate([a[np.isfinite(a)] for a in curve_arrays]) if curve_arrays else np.array([0.0])
    if len(vals) == 0:
        return 0.0, 1.0
    m = float(np.mean(vals))
    s = float(np.std(vals))
    return m, max(s, 1e-6)


def build_patch_bank(curve_arrays, mean, std, min_valid_frac=0.5, patch=PATCH, cap=None, seed=SEED):
    """Gather training patches from many wells for one curve. Keep only patches whose valid
    (finite) fraction >= min_valid_frac so the model does not train on mostly-padding. Optional
    random subsample to `cap` patches."""
    banks = []
    for a in curve_arrays:
        finite = np.isfinite(a).astype("float32")
        z = standardize(a, mean, std)
        p, L = patchify(z, patch)
        fm, _ = patchify(finite, patch)
        frac = fm.mean(axis=1)
        keep = p[frac >= min_valid_frac]
        if len(keep):
            banks.append(keep)
    if not banks:
        return np.zeros((0, patch), dtype="float32")
    bank = np.concatenate(banks, axis=0)
    if cap is not None and len(bank) > cap:
        rng = np.random.default_rng(seed)
        bank = bank[rng.choice(len(bank), cap, replace=False)]
    return bank


def train_tokenizer(bank, levels, epochs=8, batch=4096, lr=1e-3, patch=PATCH, hidden=HIDDEN,
                    seed=SEED, device="cpu", log=None):
    """Train one FSQ autoencoder on a patch bank (standardized). Returns the trained model."""
    torch.manual_seed(seed)
    model = FSQAutoEncoder(levels, patch=patch, hidden=hidden).to(device)
    if len(bank) == 0:
        return model
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    X = torch.from_numpy(bank).to(device)
    n = len(X)
    rng = np.random.default_rng(seed)
    for ep in range(epochs):
        perm = rng.permutation(n)
        tot = 0.0
        nb = 0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            xb = X[idx]
            xr = model(xb)
            loss = ((xr - xb) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss.detach())
            nb += 1
        if log is not None:
            log(f"      epoch {ep+1}/{epochs} mse={tot/max(nb,1):.5f}")
    return model


@torch.no_grad()
def reconstruct_curve(arr, model, mean, std, patch=PATCH, device="cpu"):
    """Stored-space curve (with NaN) -> reconstructed stored-space curve. Original NaN mask is
    re-imposed so missing-value structure is identical to the input."""
    mask = np.isfinite(arr)
    z = standardize(arr, mean, std)
    p, L = patchify(z, patch)
    xb = torch.from_numpy(p).to(device)
    xr = model(xb).cpu().numpy()
    rec_std = unpatchify(xr, L)
    rec = rec_std * std + mean            # de-standardize to stored space
    out = arr.astype("float64").copy()
    out[mask] = rec[mask]                 # only overwrite originally-valid positions
    out[~mask] = np.nan                   # preserve missing structure exactly
    return out.astype("float32")
