#!/usr/bin/env python3
"""Item J: the ATCE v1.5 ablation, v3 (items T-Z amendments applied 2026-07-26,
on top of v2's K-S amendments). Arms A (prior-off), B-linear (prior-on: additive
rank-1 linear depth embedding on PER-WELL relative position, kept exactly as
built per item O/V -- not silently fixed), B-abs (prior-on: additive rank-1
linear depth embedding on ABSOLUTE depth, corpus-wide standardized, item V), B2
(prior-on: richer depth featurization sharing B-abs's absolute reference frame
-- corpus-wide standardized depth + Athy exp decay + multiscale sin/cos, item
V amendment to item O's original B2 spec), C (external baseline: continuous MSE
head), D (optional: explicit trend-residual, Phase 7 Norway Athy fit).

v3 amendments vs the v2 run (committed under item W as DIAGNOSTIC, not sealed):
  - item U (BLOCKING): v1's tokenizer/scaler, while confirmed to use the correct
    feature order [GR,RDEP,NPHI,RHOB] and the correct units (raw ohm-m RDEP, no
    log10 mismatch), reconstructs THIS ablation's actual data materially worse
    than a fresh refit -- NPHI (the primary metric) RMSE is 3x worse (0.0403 vs
    0.0136). Per the pre-registered validation-gate rule, this REVERTS to a
    fresh refit on this ablation's own 80 train wells for all arms. See
    docs/decisions/d2_item_u_tokenizer_validation_2026-07-26.md.
  - item V: the item-O blocking precheck's dnorm finding (per-well relative
    position, not absolute depth) meant B-linear-vs-B2 changed TWO variables at
    once (depth reference frame AND featurization) -- a confound. Arm B-abs is
    added to isolate them: B-linear vs B-abs isolates the reference-frame
    defect; B-abs vs B2 isolates the featurization. B2's first feature is
    changed from per-well dnorm to the same corpus-wide standardized absolute
    depth B-abs uses (previously per item O it was dnorm) so that B-abs vs B2
    varies ONLY featurization richness. B-linear is kept exactly as built and
    reported as built, not silently fixed.

Held fixed: 98 FORCE wells, 80/10/8 wellbore split (absolute counts, not percentages
-- 80+10+8=98) within those 98 only, k=1000 4-feature tokenizer (GR/RDEP/NPHI/RHOB),
6 layers, 8 heads, d256, context 512, lr 3e-4, identical seed/steps/batch size
across arms.

blind_force is never loaded: asserted explicitly against split_assignment.csv names,
on top of the fact that the 98-well pool is itself the project's "train" split,
categorically disjoint from blind_force's 10 named wells.
"""
import json, hashlib, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans
from scipy.stats import wasserstein_distance

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift/atce_ablation_v3"
OUT.mkdir(parents=True, exist_ok=True)

V1_CKPT_DIR = Path("/workspace/v1_readonly/LithoGPT/checkpoints")

SEED = 20260715
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
FEATURES = ["GR", "RDEP", "NPHI", "RHOB"]
NPHI_IDX = FEATURES.index("NPHI")
RHOB_IDX = FEATURES.index("RHOB")
GR_IDX = FEATURES.index("GR")
K = 1000
CONTEXT = 512
D_MODEL = 256
N_LAYERS = 6
N_HEADS = 8
LR = 3e-4
BATCH_SIZE = 32
N_STEPS = 3000          # fixed before any run, documented, not tuned post hoc
N_REALIZATIONS = 5       # generation realizations per held-out well
N_BOOTSTRAP = 1000
PRIME_FRAC = 0.25         # fraction of each held-out well used as generation context
# item P: cap raised so it never binds for this well pool (max observed remaining-
# after-prime across the 8 test wells is 13047 samples); previously 1000 samples
# (152 m) covered as little as 7.7% of a well's post-prime depth range. Kept as an
# explicit ceiling (not removed) so a future larger well pool fails loudly/visibly
# in the coverage-pct diagnostic rather than silently truncating again.
MAX_GEN_LEN = 20000

# Phase 7 Norway Athy fit (Arm D, and Arm B2's exp-decay feature)
ATHY_PHI0 = 0.6052
ATHY_LAMBDA_M = 4068.0
# item O: Arm B2's multiscale sin/cos wavelengths, log-spaced 10 m to 5000 m
B2_WAVELENGTHS_M = np.logspace(np.log10(10.0), np.log10(5000.0), 5).tolist()
B2_DEPTH_FEAT_DIM = 1 + 1 + 2 * len(B2_WAVELENGTHS_M)  # dnorm + exp + 5*(sin,cos) = 12

_LINES = []
def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); _LINES.append(s)
    (OUT / "run_log.txt").write_text("\n".join(_LINES) + "\n")


# ---------------- data ----------------
sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str)
BLIND_NAMES = set(sp[sp.split == "blind_force"].well_id) | set(sp[sp.split == "blind_force"].safe_name)


def load_98_train_wells():
    df = pd.read_csv(ROOT / "data/raw/force2020/train.csv", sep=";")
    train_names = set(sp[(sp.source == "force2020") & (sp.split == "train")].well_id)
    assert not (train_names & BLIND_NAMES), "REFUSED: blind_force name in the 98-well pool"
    df = df[df["WELL"].isin(train_names)]
    loaded_names = set(df["WELL"].unique())
    assert not (loaded_names & BLIND_NAMES), "REFUSED: blind_force well present in loaded rows"
    assert len(train_names) == 98, f"expected 98 wells, got {len(train_names)}"
    return df, sorted(train_names)


def well_curves(df, wid):
    w = df[df.WELL == wid].sort_values("DEPTH_MD")
    depth = w["DEPTH_MD"].to_numpy(dtype=np.float64)
    feats = w[FEATURES].to_numpy(dtype=np.float64)
    valid = np.isfinite(feats).all(axis=1)
    return depth[valid], feats[valid]


def make_split(well_names, seed=SEED):
    rng = np.random.default_rng(seed)
    names = list(well_names)
    rng.shuffle(names)
    return names[:80], names[80:90], names[90:98]   # train, dev, test -- absolute counts


def b2_depth_features(depth_m, depth_abs_std):
    """item V amendment to item O's Arm B2 featurization: corpus-wide standardized
    ABSOLUTE depth (same signal Arm B-abs uses -- NOT per-well dnorm, which item
    O's blocking precheck found conflates position-within-well with real depth)
    + Athy exp-decay(absolute depth) + 5 log-spaced sin/cos pairs (absolute
    depth). Sharing B-abs's exact first feature means B-abs vs B2 varies ONLY
    featurization richness, not depth reference frame -- the clean comparison
    item V calls for."""
    feats = [depth_abs_std.astype(np.float32)]
    feats.append(np.exp(-depth_m / ATHY_LAMBDA_M).astype(np.float32))
    for wl in B2_WAVELENGTHS_M:
        feats.append(np.sin(2 * np.pi * depth_m / wl).astype(np.float32))
        feats.append(np.cos(2 * np.pi * depth_m / wl).astype(np.float32))
    return np.stack(feats, axis=-1)  # [n_samples, B2_DEPTH_FEAT_DIM]


# ---------------- model ----------------
class GPTBlock(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(nn.Linear(d_model, 4 * d_model), nn.GELU(), nn.Linear(4 * d_model, d_model))

    def forward(self, x, causal_mask):
        a, _ = self.attn(self.ln1(x), self.ln1(x), self.ln1(x), attn_mask=causal_mask, need_weights=False)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x


class LithoGPTv15(nn.Module):
    def __init__(self, vocab_size, d_model, n_layers, n_heads, context,
                 depth_feat_dim=0, output_head="discrete", n_features=4):
        super().__init__()
        self.context = context
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Embedding(context, d_model)
        self.depth_feat_dim = depth_feat_dim
        self.use_depth_embed = depth_feat_dim > 0
        if self.use_depth_embed:
            self.depth_embed = nn.Linear(depth_feat_dim, d_model)
        self.blocks = nn.ModuleList([GPTBlock(d_model, n_heads) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.output_head_type = output_head
        if output_head == "discrete":
            self.head = nn.Linear(d_model, vocab_size)
        else:
            self.head = nn.Linear(d_model, n_features)

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, tokens, depth_feat=None):
        B, T = tokens.shape
        pos = torch.arange(T, device=tokens.device).unsqueeze(0).expand(B, T)
        x = self.tok_embed(tokens) + self.pos_embed(pos)
        if self.use_depth_embed:
            assert depth_feat is not None
            x = x + self.depth_embed(depth_feat)
        mask = torch.triu(torch.full((T, T), float("-inf"), device=tokens.device), diagonal=1)
        for block in self.blocks:
            x = block(x, mask)
        x = self.ln_f(x)
        return self.head(x)


def build_batches(token_seqs, depth_feat_seqs, context, batch_size, n_steps, seed):
    rng = np.random.default_rng(seed)
    lengths = [len(s) for s in token_seqs]
    valid_wells = [i for i, l in enumerate(lengths) if l > context + 1]
    for _ in range(n_steps):
        widx = rng.choice(valid_wells, size=batch_size)
        xb, yb, db = [], [], []
        for i in widx:
            seq = token_seqs[i]; dfeat = depth_feat_seqs[i]
            start = rng.integers(0, len(seq) - context - 1)
            xb.append(seq[start:start + context])
            yb.append(seq[start + 1:start + context + 1])
            db.append(dfeat[start:start + context])
        yield (torch.tensor(np.stack(xb), dtype=torch.long),
               torch.tensor(np.stack(yb), dtype=torch.long),
               torch.tensor(np.stack(db), dtype=torch.float32))


def build_batches_continuous(token_seqs, feat_seqs, depth_feat_seqs, context, batch_size, n_steps, seed):
    rng = np.random.default_rng(seed)
    lengths = [len(s) for s in token_seqs]
    valid_wells = [i for i, l in enumerate(lengths) if l > context + 1]
    for _ in range(n_steps):
        widx = rng.choice(valid_wells, size=batch_size)
        xb, yb, db = [], [], []
        for i in widx:
            seq = token_seqs[i]; feats = feat_seqs[i]; dfeat = depth_feat_seqs[i]
            start = rng.integers(0, len(seq) - context - 1)
            xb.append(seq[start:start + context])
            yb.append(feats[start + 1:start + context + 1])
            db.append(dfeat[start:start + context])
        yield (torch.tensor(np.stack(xb), dtype=torch.long),
               torch.tensor(np.stack(yb), dtype=torch.float32),
               torch.tensor(np.stack(db), dtype=torch.float32))


def train_arm(name, model, token_seqs, depth_feat_seqs, feat_seqs=None, seed=SEED):
    t0 = time.time()
    model = model.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    losses = []
    if model.output_head_type == "discrete":
        gen = build_batches(token_seqs, depth_feat_seqs, CONTEXT, BATCH_SIZE, N_STEPS, seed)
        loss_fn = nn.CrossEntropyLoss()
    else:
        gen = build_batches_continuous(token_seqs, feat_seqs, depth_feat_seqs, CONTEXT, BATCH_SIZE, N_STEPS, seed)
        loss_fn = nn.MSELoss()
    for step, (xb, yb, db) in enumerate(gen):
        xb, yb, db = xb.to(DEVICE), yb.to(DEVICE), db.to(DEVICE)
        logits = model(xb, depth_feat=db if model.use_depth_embed else None)
        if model.output_head_type == "discrete":
            loss = loss_fn(logits.reshape(-1, K), yb.reshape(-1))
        else:
            loss = loss_fn(logits, yb)
        opt.zero_grad(); loss.backward(); opt.step()
        losses.append(loss.item())
        if step % 500 == 0 or step == N_STEPS - 1:
            log(f"  [{name}] step {step}/{N_STEPS} loss={loss.item():.4f} elapsed={time.time()-t0:.0f}s")
    log(f"[{name}] trained {N_STEPS} steps in {time.time()-t0:.1f}s, final loss={np.mean(losses[-50:]):.4f}, n_params={model.n_params()}")
    return model


@torch.no_grad()
def generate_batch(model, prime_tokens, prime_depth_feat, gen_len, n_realizations,
                    kmeans_centers=None, temperature=1.0, seed=SEED,
                    depth_feat_stepper=None):
    """Batched generation: all n_realizations of one well generated together (batch dim),
    since there is no KV-cache, this at least amortizes the per-step Python/kernel-launch
    overhead across realizations instead of looping over them sequentially.
    depth_feat_stepper(prev_depth_feat_row, step_index) -> next_depth_feat_row, so callers
    can advance either the 1-wide (B-linear) or 12-wide (B2) depth feature correctly."""
    model.eval()
    device = next(model.parameters()).device
    B = n_realizations
    rng = np.random.default_rng(seed)
    tokens = np.tile(np.array(prime_tokens), (B, 1)).tolist()
    tokens = [list(t) for t in tokens]
    dfeat = [list(prime_depth_feat) for _ in range(B)]
    centers_t = torch.tensor(kmeans_centers, dtype=torch.float32, device=device)
    outputs = np.zeros((B, gen_len, centers_t.shape[1]), dtype=np.float32)
    for i in range(gen_len):
        window = np.array([t[-CONTEXT:] for t in tokens])
        dwindow = np.array([d[-CONTEXT:] for d in dfeat], dtype=np.float32)
        x = torch.tensor(window, dtype=torch.long, device=device)
        d = torch.tensor(dwindow, dtype=torch.float32, device=device) if model.use_depth_embed else None
        logits = model(x, depth_feat=d)
        last = logits[:, -1]   # [B, K] or [B, n_features]
        if model.output_head_type == "discrete":
            probs = torch.softmax(last / temperature, dim=-1).cpu().numpy()
            for b in range(B):
                p = probs[b] / probs[b].sum()
                next_tok = rng.choice(K, p=p) if temperature > 0 else int(np.argmax(p))
                tokens[b].append(int(next_tok))
                outputs[b, i] = kmeans_centers[next_tok]
        else:
            feat = last.cpu().numpy()
            d2 = ((feat[:, None, :] - kmeans_centers[None, :, :]) ** 2).sum(axis=-1)
            next_toks = d2.argmin(axis=1)
            for b in range(B):
                outputs[b, i] = feat[b]
                tokens[b].append(int(next_toks[b]))
        if model.use_depth_embed:
            for b in range(B):
                dfeat[b].append(depth_feat_stepper(dfeat[b][-1], i))
    return outputs   # [B, gen_len, n_features]


def autocorr(x, max_lag=20):
    x = x - np.mean(x)
    n = len(x)
    if n < max_lag + 2:
        return np.full(max_lag, np.nan)
    var = np.var(x)
    if var < 1e-12:
        return np.zeros(max_lag)
    return np.array([np.mean(x[:n - lag] * x[lag:]) / var for lag in range(1, max_lag + 1)])


def main():
    t0 = time.time()
    log("=== ATCE v1.5 ablation v3 (Item J amended: T,U,V,W,X,Y,Z on top of K,L,M,N,S,O,P) START ===")
    log(f"device={DEVICE} K={K} context={CONTEXT} d_model={D_MODEL} n_layers={N_LAYERS} "
        f"n_heads={N_HEADS} lr={LR} batch_size={BATCH_SIZE} n_steps={N_STEPS} seed={SEED}")
    log("PREDECESSOR RUN NOTE: both the original run (item K) and the v2 run (item W) are "
        "labeled DIAGNOSTIC/EXPLORATORY, not sealed, not reported in the paper. This v3 run "
        "is the manuscript-candidate result, launched only after item U's tokenizer "
        "validation gate and item V's B-linear/B2 confound fix.")

    # item H / P: confirm token-to-metre mapping explicitly, in both units
    log(f"item H/P token-to-metre check: CONTEXT={CONTEXT} tokens is a raw per-depth-sample "
        f"context (one token per depth sample, NOT the FSQ tokenizer's patch16 grouping "
        f"used elsewhere in this project). Confirmed against real data below.")

    df, well_names = load_98_train_wells()
    train_wells, dev_wells, test_wells = make_split(well_names)
    log(f"split: train={len(train_wells)} dev={len(dev_wells)} test={len(test_wells)}")
    assert not (set(test_wells) & BLIND_NAMES) and not (set(train_wells) & BLIND_NAMES), "REFUSED blind overlap"

    raw = {w: well_curves(df, w) for w in well_names}
    for w in well_names:
        assert len(raw[w][0]) > 0, f"well {w} has no valid rows"

    all_deltas = np.concatenate([np.diff(raw[w][0]) for w in well_names])
    median_dz = float(np.median(all_deltas))
    log(f"item P: measured depth-grid spacing (median dz across all 98 wells) = {median_dz:.5f} m/sample")
    log(f"item P/H: CONTEXT={CONTEXT} tokens = {CONTEXT*median_dz:.3f} m (confirms v1's 512-token "
        f"context is ~78 m, NOT the patched 256-token/624 m context used by the FSQ tokenizer elsewhere)")

    # item U (BLOCKING, reverses item S for this sealed run): v1's tokenizer/scaler
    # were validated against this ablation's actual data before being trusted.
    # Feature order [GR,RDEP,NPHI,RHOB] confirmed correct (permutation search) and
    # units confirmed matching (RDEP raw ohm-m in both, no log10 mismatch) -- but
    # the validation gate found v1's tokenizer reconstructs this data materially
    # worse than a fresh refit, particularly on NPHI (3x worse RMSE, the primary
    # metric). Per the pre-registered rule ("a validated fresh fit beats an
    # authentic one that is silently wrong"), all arms use a tokenizer/scaler
    # freshly refit on this ablation's own 80 train wells. See docs/decisions/
    # d2_item_u_tokenizer_validation_2026-07-26.md for the full validation gate.
    train_feats = np.concatenate([raw[w][1] for w in train_wells], axis=0)
    scaler = StandardScaler().fit(train_feats)
    kmeans = MiniBatchKMeans(n_clusters=K, random_state=SEED, n_init=3, batch_size=4096)
    kmeans.fit(scaler.transform(train_feats))
    tokenizer_provenance = "refit_on_force_80_train_wells (item U: reverts item S after v1 tokenizer failed validation gate)"
    log("item U tokenizer provenance: REFIT fresh on this ablation's own 80 train wells "
        "-- v1's authentic artifacts were validated (item U) and found materially worse "
        "at reconstructing this data (NPHI RMSE 3x worse), so this run does NOT use them, "
        "reverting item S's decision per the pre-registered validation-gate rule.")
    log(f"tokenizer ready: {len(train_feats)} FORCE train samples available, k={K}, "
        f"provenance={tokenizer_provenance}")

    token_seqs, depth_norm_seqs, feat_seqs, depth_m_seqs = {}, {}, {}, {}
    for w in well_names:
        depth, feats = raw[w]
        z = scaler.transform(feats)
        tok = kmeans.predict(z.astype(np.float64))
        dmin, dmax = depth.min(), depth.max()
        dnorm = (depth - dmin) / max(dmax - dmin, 1e-6)
        token_seqs[w] = tok
        depth_norm_seqs[w] = dnorm.astype(np.float32)
        depth_m_seqs[w] = depth.astype(np.float32)
        feat_seqs[w] = z.astype(np.float32)

    kmeans_centers = kmeans.cluster_centers_   # in standardized space

    # item V: corpus-wide (not per-well) absolute-depth standardization for Arm
    # B-abs and Arm B2's shared first feature. Stats computed ONLY from the 80
    # train wells, matching how the tokenizer/scaler are fit.
    train_depth_pool = np.concatenate([depth_m_seqs[w] for w in train_wells])
    depth_abs_mean = float(train_depth_pool.mean())
    depth_abs_std_val = float(train_depth_pool.std())
    log(f"item V: corpus-wide absolute-depth standardization (80 train wells): "
        f"mean={depth_abs_mean:.3f} m, std={depth_abs_std_val:.3f} m")
    depth_abs_std_seqs = {w: ((depth_m_seqs[w] - depth_abs_mean) / depth_abs_std_val).astype(np.float32)
                           for w in well_names}

    # depth-feature arrays per mechanism (item O's generalization: depth_feat_dim
    # varies by arm, not just a single scalar)
    depth_feat_linear = {w: depth_norm_seqs[w][:, None] for w in well_names}       # [n,1] per-well dnorm (B-linear, D)
    depth_feat_abs = {w: depth_abs_std_seqs[w][:, None] for w in well_names}       # [n,1] corpus-wide abs depth (B-abs)
    depth_feat_b2 = {w: b2_depth_features(depth_m_seqs[w], depth_abs_std_seqs[w])  # [n,12] shares B-abs's ref frame
                     for w in well_names}

    train_tok = [token_seqs[w] for w in train_wells]
    train_dfeat_lin = [depth_feat_linear[w] for w in train_wells]
    train_dfeat_abs = [depth_feat_abs[w] for w in train_wells]
    train_dfeat_b2 = [depth_feat_b2[w] for w in train_wells]
    train_feat = [feat_seqs[w] for w in train_wells]

    # item O BLOCKING PRE-CHECK: report depth statistics as fed to the Linear(1,256)
    # layer BEFORE training Arm B-linear or interpreting any Arm B number.
    all_dnorm_train = np.concatenate([depth_norm_seqs[w] for w in train_wells])
    log("=== item O BLOCKING PRE-CHECK: depth stats fed to B-linear's Linear(1,256) ===")
    log(f"  depth_norm (per-well min-max normalized, [0,1] by construction): "
        f"min={all_dnorm_train.min():.4f} max={all_dnorm_train.max():.4f} "
        f"mean={all_dnorm_train.mean():.4f} std={all_dnorm_train.std():.4f}")
    log("  Standardization applied: per-WELL min-max to [0,1] -- (depth - well_min) / "
        "(well_max - well_min). NOT raw metres. Magnitude order matches the token "
        "embedding (order 1), so the raw-scale-mismatch failure mode the brief warned "
        "about (depth entering at order 2000-4000) does NOT apply here -- that specific "
        "defect is CLEARED.")
    log("  DEFECT FOUND (different from the anticipated one, reported per the same "
        "'report, do not silently fix' rule): depth_norm is position-WITHIN-WELL "
        "(0=this well's shallowest sample, 1=this well's deepest), not absolute depth. "
        "The same normalized value means different real depths in different wells "
        "(test wells span 340 m to 2646 m). Arm B-linear and Arm D's depth-embedding "
        "path (train_dfeat_lin) therefore cannot represent an absolute-depth compaction "
        "trend the same way Arm D's explicit Athy correction does (which correctly uses "
        "absolute depth in metres, decoupled from this dnorm feature). This is reported, "
        "not silently fixed, per item O's instruction -- Arm B-linear is kept exactly as "
        "built. item V adds Arm B-abs (same rank-1 Linear(1,256) mechanism, but on "
        "corpus-wide standardized ABSOLUTE depth) specifically to isolate this defect: "
        "B-linear vs B-abs varies ONLY the depth reference frame, holding the rank-1 "
        "linear mechanism fixed.")

    # ---------------- Arm A: prior-off, discrete, no depth embed ----------------
    log("=== Arm A: prior-off (fresh-refit tokenizer per item U, transformer reimplemented from spec) ===")
    model_a = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=0, output_head="discrete")
    model_a = train_arm("ArmA", model_a, train_tok, train_dfeat_lin, seed=SEED)

    # ---------------- Arm B-linear: prior-on, rank-1 linear depth embedding, PER-WELL relative ----------------
    log("=== Arm B-linear: prior-on (rank-1 additive linear depth embedding on PER-WELL "
        "relative dnorm, renamed from Arm B per item O, kept exactly as built per item V) ===")
    model_blin = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=1, output_head="discrete")
    param_delta_blin = model_blin.n_params() - model_a.n_params()
    log(f"Arm B-linear parameter delta vs Arm A: {param_delta_blin} "
        f"({param_delta_blin/model_a.n_params()*100:.4f}% of Arm A)")
    model_blin = train_arm("ArmBlinear", model_blin, train_tok, train_dfeat_lin, seed=SEED)

    # ---------------- Arm B-abs: prior-on, rank-1 linear depth embedding, ABSOLUTE ----------------
    log("=== Arm B-abs: prior-on (rank-1 additive linear depth embedding on corpus-wide "
        "standardized ABSOLUTE depth, item V -- isolates the B-linear reference-frame defect) ===")
    model_babs = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=1, output_head="discrete")
    param_delta_babs = model_babs.n_params() - model_a.n_params()
    log(f"Arm B-abs parameter delta vs Arm A: {param_delta_babs} "
        f"({param_delta_babs/model_a.n_params()*100:.4f}% of Arm A) -- expected 512, same "
        f"shape as B-linear's Linear(1,256), only the input feature differs")
    model_babs = train_arm("ArmBabs", model_babs, train_tok, train_dfeat_abs, seed=SEED)

    # ---------------- Arm B2: prior-on, richer depth featurization, shares B-abs's reference frame ----------------
    log("=== Arm B2: prior-on (corpus-wide absolute depth + Athy exp-decay + 5 log-spaced "
        "sin/cos pairs, item V amendment to item O's original B2 spec) ===")
    log(f"Arm B2 feature list ({B2_DEPTH_FEAT_DIM} dims): [depth_abs_std (shares B-abs's "
        f"reference frame), exp(-depth_m/{ATHY_LAMBDA_M})] + "
        f"sin/cos at wavelengths_m={['%.2f' % x for x in B2_WAVELENGTHS_M]}")
    model_b2 = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=B2_DEPTH_FEAT_DIM, output_head="discrete")
    param_delta_b2 = model_b2.n_params() - model_a.n_params()
    log(f"Arm B2 parameter delta vs Arm A: {param_delta_b2} "
        f"({param_delta_b2/model_a.n_params()*100:.4f}% of Arm A)")
    model_b2 = train_arm("ArmB2", model_b2, train_tok, train_dfeat_b2, seed=SEED)

    # ---------------- Arm C: external baseline, continuous MSE head ----------------
    log("=== Arm C: external baseline (continuous MSE output head) ===")
    model_c = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=0, output_head="continuous", n_features=4)
    model_c = train_arm("ArmC", model_c, train_tok, train_dfeat_lin, feat_seqs=train_feat, seed=SEED)

    arms_meta = {
        "A": dict(model=model_a, depth_feat_seqs=depth_feat_linear, depth_feat_dim=0),
        "B-linear": dict(model=model_blin, depth_feat_seqs=depth_feat_linear, depth_feat_dim=1),
        "B-abs": dict(model=model_babs, depth_feat_seqs=depth_feat_abs, depth_feat_dim=1),
        "B2": dict(model=model_b2, depth_feat_seqs=depth_feat_b2, depth_feat_dim=B2_DEPTH_FEAT_DIM),
        "C": dict(model=model_c, depth_feat_seqs=depth_feat_linear, depth_feat_dim=0),
    }

    # ---------------- Arm D: optional, trend-residual (only if budget allows) ----------------
    budget_elapsed_h = (time.time() - t0) / 3600
    run_d = budget_elapsed_h < 3.0   # leave generous headroom under the 8-12h ceiling
    if run_d:
        log(f"=== Arm D: explicit trend-residual (Norway Athy phi0={ATHY_PHI0} lambda_m={ATHY_LAMBDA_M}) ===")
        nphi_mean_std = scaler.mean_[NPHI_IDX]; nphi_scale_std = scaler.scale_[NPHI_IDX]

        def athy_trend_std(depth_m):
            phi = ATHY_PHI0 * np.exp(-depth_m / ATHY_LAMBDA_M)
            return (phi - nphi_mean_std) / nphi_scale_std

        train_feat_resid = []
        for w in train_wells:
            depth, _ = raw[w]
            f = feat_seqs[w].copy()
            f[:, NPHI_IDX] = f[:, NPHI_IDX] - athy_trend_std(depth)
            train_feat_resid.append(f)
        train_tok_resid = []
        for f in train_feat_resid:
            train_tok_resid.append(kmeans.predict(f.astype(np.float64)))
        model_d = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, depth_feat_dim=1, output_head="discrete")
        model_d = train_arm("ArmD", model_d, train_tok_resid, train_dfeat_lin, seed=SEED)
        arms_meta["D"] = dict(model=model_d, depth_feat_seqs=depth_feat_linear, depth_feat_dim=1)
    else:
        log(f"Arm D SKIPPED: {budget_elapsed_h:.2f}h elapsed after A/B-linear/B2/C, insufficient headroom under budget")

    # ---------------- generation + evaluation on the 8 held-out test wells ----------------
    log("=== Generation + evaluation on held-out test wells ===")
    log(f"item P: generation cap MAX_GEN_LEN={MAX_GEN_LEN} samples "
        f"({MAX_GEN_LEN*median_dz:.1f} m at measured spacing); window start is FIXED "
        f"(not randomized per realization) at prime_n=max(CONTEXT, PRIME_FRAC*well_len), "
        f"identical across realizations of a given well/arm; the real interval scored "
        f"against is feats_real[prime_n:prime_n+gen_len], i.e. matched exactly to the "
        f"generated window, not an independently chosen reference span.")

    results = {}
    coverage_stats = []
    depth_signal_during_generation = {}   # item V: range of the depth signal each conditioned arm sees during generation
    for arm_name, meta in arms_meta.items():
        model = meta["model"]
        model.eval()
        per_well = {}
        arm_gen_dfeat_mins, arm_gen_dfeat_maxs = [], []
        for w in test_wells:
            depth, feats_real = raw[w]
            tok = token_seqs[w]
            dfeat_full = meta["depth_feat_seqs"][w]
            n = len(tok)
            prime_n = max(CONTEXT, int(n * PRIME_FRAC))
            if n <= prime_n + 10:
                continue
            remaining = n - prime_n
            gen_len = min(remaining, MAX_GEN_LEN)
            coverage_pct = 100.0 * gen_len / remaining
            real_segment = feats_real[prime_n:prime_n + gen_len]  # original (unstandardized) units

            # true per-step depth trajectory for this well's remaining span (not an
            # approximation): slice the SAME precomputed depth-feature array used for
            # training/priming, so B2's absolute-depth-derived features stay exact.
            # item V: dnorm/depth_abs_std/B2 features are all computed over the FULL
            # well (see depth_norm_seqs/depth_abs_std_seqs/depth_feat_b2 construction
            # above, well before any prime_n/gen_len slicing) -- this slice is the
            # only place the generation window narrows them.
            future_dfeat = dfeat_full[prime_n:prime_n + gen_len]
            if model.use_depth_embed:
                arm_gen_dfeat_mins.append(float(future_dfeat.min()))
                arm_gen_dfeat_maxs.append(float(future_dfeat.max()))

            def stepper_factory(future_arr):
                def _step(prev_row, step_i):
                    return future_arr[step_i].tolist()
                return _step

            gen_std_batch = generate_batch(model, list(tok[:prime_n]), list(dfeat_full[:prime_n]), gen_len,
                                            N_REALIZATIONS, kmeans_centers=kmeans_centers,
                                            temperature=(1.0 if arm_name != "C" else 0.0), seed=SEED,
                                            depth_feat_stepper=stepper_factory(future_dfeat))
            realizations = np.array([scaler.inverse_transform(g) for g in gen_std_batch])  # [N_REALIZATIONS, gen_len, 4]

            per_well[w] = dict(
                real=real_segment.tolist(),
                generated_realizations=realizations.tolist(),
                n_samples=gen_len,
                depth_min_m=float(depth[prime_n]),
                depth_max_m=float(depth[min(prime_n + gen_len - 1, n - 1)]),
                coverage_pct_of_remaining=coverage_pct,
            )
            coverage_stats.append(dict(arm=arm_name, well=w, gen_len=gen_len, remaining=remaining,
                                        coverage_pct=coverage_pct,
                                        depth_min_m=float(depth[prime_n]),
                                        depth_max_m=float(depth[min(prime_n + gen_len - 1, n - 1)])))
        results[arm_name] = per_well
        log(f"[{arm_name}] generated {len(per_well)} test wells x {N_REALIZATIONS} realizations")
        if arm_gen_dfeat_mins:
            sig_min, sig_max = min(arm_gen_dfeat_mins), max(arm_gen_dfeat_maxs)
            depth_signal_during_generation[arm_name] = dict(min=sig_min, max=sig_max)
            log(f"item V: [{arm_name}] depth signal range actually seen during generation "
                f"(post prime_n:prime_n+gen_len slice): min={sig_min:.4f} max={sig_max:.4f} "
                f"(computed over the FULL well before slicing, not the capped window)")

    all_depth_mins = [c["depth_min_m"] for c in coverage_stats]
    all_depth_maxs = [c["depth_max_m"] for c in coverage_stats]
    log(f"item P: total depth range spanned across all wells/realizations/arms: "
        f"min={min(all_depth_mins):.2f} m, max={max(all_depth_maxs):.2f} m")
    log(f"item P: coverage_pct_of_remaining (min/median/max across all well x arm pairs): "
        f"{min(c['coverage_pct'] for c in coverage_stats):.1f}% / "
        f"{np.median([c['coverage_pct'] for c in coverage_stats]):.1f}% / "
        f"{max(c['coverage_pct'] for c in coverage_stats):.1f}%")

    # ---------------- metrics ----------------
    log("=== Computing predeclared metrics ===")

    def well_metrics(real, gen_realizations):
        real_nphi = real[:, NPHI_IDX]; real_rhob = real[:, RHOB_IDX]; real_gr = real[:, GR_IDX]
        real_mean_nphi = float(np.mean(real_nphi))
        bias_list, w1_list, rhob_bias_list, gr_bias_list, ac_rmse_list = [], [], [], [], []
        real_ac = autocorr(real_nphi)
        for real_gen in gen_realizations:
            gen_nphi = real_gen[:, NPHI_IDX]; gen_rhob = real_gen[:, RHOB_IDX]; gen_gr = real_gen[:, GR_IDX]
            bias_list.append(float(np.mean(gen_nphi) - real_mean_nphi))
            w1_list.append(float(wasserstein_distance(real_nphi, gen_nphi)))
            rhob_bias_list.append(float(np.mean(gen_rhob) - np.mean(real_rhob)))
            gr_bias_list.append(float(np.mean(gen_gr) - np.mean(real_gr)))
            gen_ac = autocorr(gen_nphi)
            ac_rmse_list.append(float(np.sqrt(np.nanmean((real_ac - gen_ac) ** 2))))
        return dict(real_mean_nphi=real_mean_nphi, abs_bias=bias_list, w1=w1_list,
                    rhob_bias=rhob_bias_list, gr_bias=gr_bias_list, ac_rmse=ac_rmse_list)

    metrics_by_arm = {}
    for arm_name, per_well in results.items():
        well_level = {}
        for w, d in per_well.items():
            real = np.array(d["real"]); gens = np.array(d["generated_realizations"])
            well_level[w] = well_metrics(real, gens)
        metrics_by_arm[arm_name] = well_level

    def bootstrap_ci(values, n_boot=N_BOOTSTRAP, seed=SEED):
        rng = np.random.default_rng(seed)
        values = np.array(values)
        boots = [np.mean(rng.choice(values, size=len(values), replace=True)) for _ in range(n_boot)]
        return dict(mean=float(np.mean(values)), ci_low=float(np.percentile(boots, 2.5)),
                    ci_high=float(np.percentile(boots, 97.5)))

    summary = {}
    for arm_name, well_level in metrics_by_arm.items():
        arm_summary = {}
        for metric in ["abs_bias", "w1", "rhob_bias", "gr_bias", "ac_rmse"]:
            all_vals = []
            per_well_summary = {}
            for w, m in well_level.items():
                vals = m[metric]
                per_well_summary[w] = bootstrap_ci(vals)
                all_vals.extend(vals)
            arm_summary[metric] = dict(per_well=per_well_summary, aggregate=bootstrap_ci(all_vals))
        real_means = [m["real_mean_nphi"] for m in well_level.values()]
        overall_real_mean = float(np.mean(real_means))
        rel_bias_vals = []
        for w, m in well_level.items():
            for b in m["abs_bias"]:
                rel_bias_vals.append(b / m["real_mean_nphi"] * 100)
        arm_summary["nphi_relative_bias_pct_vs_real_mean"] = bootstrap_ci(rel_bias_vals)
        arm_summary["overall_real_mean_nphi"] = overall_real_mean
        summary[arm_name] = arm_summary
        log(f"[{arm_name}] NPHI abs_bias={arm_summary['abs_bias']['aggregate']} "
            f"rel_bias%={arm_summary['nphi_relative_bias_pct_vs_real_mean']} "
            f"W1={arm_summary['w1']['aggregate']}")

    total_wall = time.time() - t0
    final = dict(
        config=dict(K=K, CONTEXT=CONTEXT, D_MODEL=D_MODEL, N_LAYERS=N_LAYERS, N_HEADS=N_HEADS,
                    LR=LR, BATCH_SIZE=BATCH_SIZE, N_STEPS=N_STEPS, SEED=SEED,
                    N_REALIZATIONS=N_REALIZATIONS, PRIME_FRAC=PRIME_FRAC, MAX_GEN_LEN=MAX_GEN_LEN),
        split=dict(train=train_wells, dev=dev_wells, test=test_wells),
        tokenizer_provenance=tokenizer_provenance,
        measured_depth_spacing_m=median_dz,
        context_tokens_to_metres=dict(context_tokens=CONTEXT, metres=CONTEXT * median_dz,
                                       note="raw per-depth-sample context, not the FSQ tokenizer's patch16 grouping"),
        arm_a_params=model_a.n_params(),
        arm_blinear_params=model_blin.n_params(),
        arm_blinear_param_delta_vs_a=param_delta_blin,
        arm_babs_params=model_babs.n_params(),
        arm_babs_param_delta_vs_a=param_delta_babs,
        arm_b2_params=model_b2.n_params(),
        arm_b2_param_delta_vs_a=param_delta_b2,
        arm_b2_feature_list=["depth_abs_std (corpus-wide standardized absolute depth, shares Arm B-abs's reference frame)",
                              f"exp(-depth_m/{ATHY_LAMBDA_M})"] +
                             [f"sin(2pi*depth_m/{wl:.2f}m)/cos(2pi*depth_m/{wl:.2f}m)" for wl in B2_WAVELENGTHS_M],
        depth_abs_standardization=dict(mean_m=depth_abs_mean, std_m=depth_abs_std_val,
                                        note="corpus-wide, computed from 80 train wells only, item V"),
        depth_signal_during_generation=depth_signal_during_generation,
        arm_c_params=model_c.n_params(),
        arm_d_run=run_d,
        depth_scale_precheck=dict(
            dnorm_min=float(all_dnorm_train.min()), dnorm_max=float(all_dnorm_train.max()),
            dnorm_mean=float(all_dnorm_train.mean()), dnorm_std=float(all_dnorm_train.std()),
            standardization="per-well min-max to [0,1]",
            scale_mismatch_defect_found=False,
            reference_frame_defect_found=True,
            reference_frame_defect_note="dnorm is position-within-well, not absolute depth; "
                                         "same normalized value means different real depths across wells",
        ),
        generation_cap=dict(
            max_gen_len_samples=MAX_GEN_LEN,
            max_gen_len_metres=MAX_GEN_LEN * median_dz,
            window_start_policy="fixed at prime_n=max(CONTEXT, PRIME_FRAC*well_len), not randomized per realization",
            real_interval_matching="real_segment = feats_real[prime_n:prime_n+gen_len], exact match to generated window",
            coverage_pct_min=min(c["coverage_pct"] for c in coverage_stats),
            coverage_pct_median=float(np.median([c["coverage_pct"] for c in coverage_stats])),
            coverage_pct_max=max(c["coverage_pct"] for c in coverage_stats),
            total_depth_range_m=[min(all_depth_mins), max(all_depth_maxs)],
        ),
        w1_definition="scipy.stats.wasserstein_distance(real_NPHI_segment, generated_NPHI_segment), "
                       "own definition per item D's pre-registered fallback (v1's W1 definition unresolved)",
        nphi_relative_bias_definition="100 * (mean(generated_NPHI) - mean(real_NPHI)) / mean(real_NPHI), "
                                        "denominator = REAL/reference mean, per item D's corrected framing",
        metrics_summary=summary,
        total_wall_s=round(total_wall, 1),
    )
    payload = json.dumps(final, indent=2, sort_keys=True, default=str)
    out_path = OUT / "atce_ablation_v3_summary_2026-07-26.json"
    out_path.write_text(payload)
    sha = hashlib.sha256(payload.encode()).hexdigest()
    (OUT / "atce_ablation_v3_summary_2026-07-26.sha256").write_text(sha + "\n")

    raw_path = OUT / "atce_ablation_v3_raw_results_2026-07-26.json"
    raw_path.write_text(json.dumps(results, default=str))
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    (OUT / "atce_ablation_v3_raw_results_2026-07-26.sha256").write_text(raw_sha + "\n")

    log(f"WRITTEN {out_path}, sha256={sha}")
    log(f"WRITTEN {raw_path}, sha256={raw_sha}")
    log(f"TOTAL WALL TIME: {total_wall:.1f}s = {total_wall/3600:.2f}h")
    log("ATCE_ABLATION_V3_COMPLETE")


if __name__ == "__main__":
    main()
