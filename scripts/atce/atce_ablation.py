#!/usr/bin/env python3
"""Item J: the ATCE v1.5 ablation. Arms A (prior-off, reimplemented from spec since
v1's checkpoint is corrupted -- item B), B (prior-on: additive depth embedding),
C (external baseline: continuous MSE head), D (optional: explicit trend-residual,
Phase 7 Norway Athy fit).

Held fixed: 98 FORCE wells, 80/10/8 wellbore split (absolute counts, not percentages
-- 80+10+8=98) within those 98 only, k-means k=1000 on GR/RDEP/NPHI/RHOB, 6 layers,
8 heads, d256, context 512, lr 3e-4, identical seed/steps/batch size across arms.

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
OUT = ROOT / "reports/basinshift/atce_ablation"
OUT.mkdir(parents=True, exist_ok=True)

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
MAX_GEN_LEN = 1000        # cap on generated samples per well (documented scope choice, no KV-cache so autoregressive generation is O(gen_len); fixed before any results)

# Phase 7 Norway Athy fit (Arm D)
ATHY_PHI0 = 0.6052
ATHY_LAMBDA_M = 4068.0

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
                 use_depth_embed=False, output_head="discrete", n_features=4):
        super().__init__()
        self.context = context
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Embedding(context, d_model)
        self.use_depth_embed = use_depth_embed
        if use_depth_embed:
            self.depth_embed = nn.Linear(1, d_model)
        self.blocks = nn.ModuleList([GPTBlock(d_model, n_heads) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.output_head_type = output_head
        if output_head == "discrete":
            self.head = nn.Linear(d_model, vocab_size)
        else:
            self.head = nn.Linear(d_model, n_features)

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, tokens, depth_norm=None):
        B, T = tokens.shape
        pos = torch.arange(T, device=tokens.device).unsqueeze(0).expand(B, T)
        x = self.tok_embed(tokens) + self.pos_embed(pos)
        if self.use_depth_embed:
            assert depth_norm is not None
            x = x + self.depth_embed(depth_norm.unsqueeze(-1))
        mask = torch.triu(torch.full((T, T), float("-inf"), device=tokens.device), diagonal=1)
        for block in self.blocks:
            x = block(x, mask)
        x = self.ln_f(x)
        return self.head(x)


def build_batches(token_seqs, depth_norm_seqs, context, batch_size, n_steps, seed):
    rng = np.random.default_rng(seed)
    lengths = [len(s) for s in token_seqs]
    valid_wells = [i for i, l in enumerate(lengths) if l > context + 1]
    for _ in range(n_steps):
        widx = rng.choice(valid_wells, size=batch_size)
        xb, yb, db = [], [], []
        for i in widx:
            seq = token_seqs[i]; dnorm = depth_norm_seqs[i]
            start = rng.integers(0, len(seq) - context - 1)
            xb.append(seq[start:start + context])
            yb.append(seq[start + 1:start + context + 1])
            db.append(dnorm[start:start + context])
        yield (torch.tensor(np.stack(xb), dtype=torch.long),
               torch.tensor(np.stack(yb), dtype=torch.long),
               torch.tensor(np.stack(db), dtype=torch.float32))


def build_batches_continuous(token_seqs, feat_seqs, depth_norm_seqs, context, batch_size, n_steps, seed):
    rng = np.random.default_rng(seed)
    lengths = [len(s) for s in token_seqs]
    valid_wells = [i for i, l in enumerate(lengths) if l > context + 1]
    for _ in range(n_steps):
        widx = rng.choice(valid_wells, size=batch_size)
        xb, yb, db = [], [], []
        for i in widx:
            seq = token_seqs[i]; feats = feat_seqs[i]; dnorm = depth_norm_seqs[i]
            start = rng.integers(0, len(seq) - context - 1)
            xb.append(seq[start:start + context])
            yb.append(feats[start + 1:start + context + 1])
            db.append(dnorm[start:start + context])
        yield (torch.tensor(np.stack(xb), dtype=torch.long),
               torch.tensor(np.stack(yb), dtype=torch.float32),
               torch.tensor(np.stack(db), dtype=torch.float32))


def train_arm(name, model, token_seqs, depth_norm_seqs, feat_seqs=None, seed=SEED):
    t0 = time.time()
    model = model.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    losses = []
    if model.output_head_type == "discrete":
        gen = build_batches(token_seqs, depth_norm_seqs, CONTEXT, BATCH_SIZE, N_STEPS, seed)
        loss_fn = nn.CrossEntropyLoss()
    else:
        gen = build_batches_continuous(token_seqs, feat_seqs, depth_norm_seqs, CONTEXT, BATCH_SIZE, N_STEPS, seed)
        loss_fn = nn.MSELoss()
    for step, (xb, yb, db) in enumerate(gen):
        xb, yb, db = xb.to(DEVICE), yb.to(DEVICE), db.to(DEVICE)
        logits = model(xb, depth_norm=db if model.use_depth_embed else None)
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
def generate_batch(model, prime_tokens, prime_depth_norm, gen_len, n_realizations,
                    kmeans_centers=None, temperature=1.0, seed=SEED):
    """Batched generation: all n_realizations of one well generated together (batch dim),
    since there is no KV-cache, this at least amortizes the per-step Python/kernel-launch
    overhead across realizations instead of looping over them sequentially."""
    model.eval()
    device = next(model.parameters()).device
    B = n_realizations
    rng = np.random.default_rng(seed)
    tokens = np.tile(np.array(prime_tokens), (B, 1)).tolist()
    tokens = [list(t) for t in tokens]
    dnorm = [list(prime_depth_norm) for _ in range(B)]
    depth_step = prime_depth_norm[-1] - prime_depth_norm[-2] if len(prime_depth_norm) > 1 else 0.001
    centers_t = torch.tensor(kmeans_centers, dtype=torch.float32, device=device)
    outputs = np.zeros((B, gen_len, centers_t.shape[1]), dtype=np.float32)
    for i in range(gen_len):
        window = np.array([t[-CONTEXT:] for t in tokens])
        dwindow = np.array([d[-CONTEXT:] for d in dnorm], dtype=np.float32)
        x = torch.tensor(window, dtype=torch.long, device=device)
        d = torch.tensor(dwindow, dtype=torch.float32, device=device) if model.use_depth_embed else None
        logits = model(x, depth_norm=d)
        last = logits[:, -1]   # [B, K] or [B, n_features]
        next_dnorm = dwindow[:, -1] + depth_step
        if model.output_head_type == "discrete":
            probs = torch.softmax(last / temperature, dim=-1).cpu().numpy()
            for b in range(B):
                p = probs[b] / probs[b].sum()
                next_tok = rng.choice(K, p=p) if temperature > 0 else int(np.argmax(p))
                tokens[b].append(int(next_tok))
                outputs[b, i] = kmeans_centers[next_tok]
        else:
            feat = last.cpu().numpy()
            # nearest centroid, vectorized across the batch
            d2 = ((feat[:, None, :] - kmeans_centers[None, :, :]) ** 2).sum(axis=-1)
            next_toks = d2.argmin(axis=1)
            for b in range(B):
                outputs[b, i] = feat[b]
                tokens[b].append(int(next_toks[b]))
        for b in range(B):
            dnorm[b].append(float(next_dnorm[b]))
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
    log("=== ATCE v1.5 ablation (Item J) START ===")
    log(f"device={DEVICE} K={K} context={CONTEXT} d_model={D_MODEL} n_layers={N_LAYERS} "
        f"n_heads={N_HEADS} lr={LR} batch_size={BATCH_SIZE} n_steps={N_STEPS} seed={SEED}")

    df, well_names = load_98_train_wells()
    train_wells, dev_wells, test_wells = make_split(well_names)
    log(f"split: train={len(train_wells)} dev={len(dev_wells)} test={len(test_wells)}")
    assert not (set(test_wells) & BLIND_NAMES) and not (set(train_wells) & BLIND_NAMES), "REFUSED blind overlap"

    raw = {w: well_curves(df, w) for w in well_names}
    for w in well_names:
        assert len(raw[w][0]) > 0, f"well {w} has no valid rows"

    # standardize + tokenize, fit ONLY on the 80 train wells
    train_feats = np.concatenate([raw[w][1] for w in train_wells], axis=0)
    scaler = StandardScaler().fit(train_feats)
    kmeans = MiniBatchKMeans(n_clusters=K, random_state=SEED, n_init=3, batch_size=4096)
    kmeans.fit(scaler.transform(train_feats))
    log(f"tokenizer fit: {len(train_feats)} train samples, k={K}")

    token_seqs, depth_norm_seqs, feat_seqs = {}, {}, {}
    for w in well_names:
        depth, feats = raw[w]
        z = scaler.transform(feats)
        tok = kmeans.predict(z)
        dmin, dmax = depth.min(), depth.max()
        dnorm = (depth - dmin) / max(dmax - dmin, 1e-6)
        token_seqs[w] = tok
        depth_norm_seqs[w] = dnorm.astype(np.float32)
        feat_seqs[w] = z.astype(np.float32)

    kmeans_centers = kmeans.cluster_centers_   # in standardized space

    train_tok = [token_seqs[w] for w in train_wells]
    train_dnorm = [depth_norm_seqs[w] for w in train_wells]
    train_feat = [feat_seqs[w] for w in train_wells]

    # ---------------- Arm A: prior-off, discrete, no depth embed ----------------
    log("=== Arm A: prior-off (reimplemented from spec, not comparable to v1 Table 3) ===")
    model_a = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, use_depth_embed=False, output_head="discrete")
    model_a = train_arm("ArmA", model_a, train_tok, train_dnorm, seed=SEED)

    # ---------------- Arm B: prior-on, additive depth embedding ----------------
    log("=== Arm B: prior-on (additive learned depth embedding) ===")
    model_b = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, use_depth_embed=True, output_head="discrete")
    param_delta = model_b.n_params() - model_a.n_params()
    log(f"Arm B parameter delta vs Arm A: {param_delta} ({param_delta/model_a.n_params()*100:.4f}% of Arm A; "
        f"vs corrected v1 4.8M: {param_delta/4_800_000*100:.4f}%)")
    model_b = train_arm("ArmB", model_b, train_tok, train_dnorm, seed=SEED)

    # ---------------- Arm C: external baseline, continuous MSE head ----------------
    log("=== Arm C: external baseline (continuous MSE output head) ===")
    model_c = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, use_depth_embed=False, output_head="continuous", n_features=4)
    model_c = train_arm("ArmC", model_c, train_tok, train_dnorm, feat_seqs=train_feat, seed=SEED)

    arms = {"A": model_a, "B": model_b, "C": model_c}

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
        model_d = LithoGPTv15(K, D_MODEL, N_LAYERS, N_HEADS, CONTEXT, use_depth_embed=True, output_head="discrete")
        model_d = train_arm("ArmD", model_d, train_tok_resid, train_dnorm, seed=SEED)
        arms["D"] = model_d
    else:
        log(f"Arm D SKIPPED: {budget_elapsed_h:.2f}h elapsed after A-C, insufficient headroom under budget")

    # ---------------- generation + evaluation on the 8 held-out test wells ----------------
    log("=== Generation + evaluation on held-out test wells ===")
    results = {}
    for arm_name, model in arms.items():
        model.eval()
        per_well = {}
        for w in test_wells:
            depth, feats_real = raw[w]
            tok = token_seqs[w]
            dnorm = depth_norm_seqs[w]
            n = len(tok)
            prime_n = max(CONTEXT, int(n * PRIME_FRAC))
            if n <= prime_n + 10:
                continue
            gen_len = min(n - prime_n, MAX_GEN_LEN)
            real_segment = feats_real[prime_n:prime_n + gen_len]  # original (unstandardized) units

            gen_std_batch = generate_batch(model, list(tok[:prime_n]), list(dnorm[:prime_n]), gen_len,
                                            N_REALIZATIONS, kmeans_centers=kmeans_centers,
                                            temperature=(1.0 if arm_name != "C" else 0.0), seed=SEED)
            realizations = np.array([scaler.inverse_transform(g) for g in gen_std_batch])  # [N_REALIZATIONS, gen_len, 4]

            per_well[w] = dict(
                real=real_segment.tolist(),
                generated_realizations=realizations.tolist(),
                n_samples=gen_len,
            )
        results[arm_name] = per_well
        log(f"[{arm_name}] generated {len(per_well)} test wells x {N_REALIZATIONS} realizations")

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

    # per-well bootstrap CIs (bootstrap over realizations x samples within each well)
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
                    N_REALIZATIONS=N_REALIZATIONS, PRIME_FRAC=PRIME_FRAC),
        split=dict(train=train_wells, dev=dev_wells, test=test_wells),
        arm_a_params=model_a.n_params(),
        arm_b_params=model_b.n_params(),
        arm_b_param_delta_vs_a=param_delta,
        arm_c_params=model_c.n_params(),
        arm_d_run=run_d,
        w1_definition="scipy.stats.wasserstein_distance(real_NPHI_segment, generated_NPHI_segment), "
                       "own definition per item D's pre-registered fallback (v1's W1 definition unresolved)",
        nphi_relative_bias_definition="100 * (mean(generated_NPHI) - mean(real_NPHI)) / mean(real_NPHI), "
                                        "denominator = REAL/reference mean, per item D's corrected framing",
        metrics_summary=summary,
        total_wall_s=round(total_wall, 1),
    )
    payload = json.dumps(final, indent=2, sort_keys=True, default=str)
    out_path = OUT / "atce_ablation_summary_2026-07-26.json"
    out_path.write_text(payload)
    sha = hashlib.sha256(payload.encode()).hexdigest()
    (OUT / "atce_ablation_summary_2026-07-26.sha256").write_text(sha + "\n")

    # full per-well raw outputs, separate file (large)
    raw_path = OUT / "atce_ablation_raw_results_2026-07-26.json"
    raw_path.write_text(json.dumps(results, default=str))
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    (OUT / "atce_ablation_raw_results_2026-07-26.sha256").write_text(raw_sha + "\n")

    log(f"WRITTEN {out_path}, sha256={sha}")
    log(f"WRITTEN {raw_path}, sha256={raw_sha}")
    log(f"TOTAL WALL TIME: {total_wall:.1f}s = {total_wall/3600:.2f}h")
    log("ATCE_ABLATION_COMPLETE")


if __name__ == "__main__":
    main()
