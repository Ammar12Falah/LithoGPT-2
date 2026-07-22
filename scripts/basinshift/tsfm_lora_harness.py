#!/usr/bin/env python3
"""TS-FM Stage 1 LoRA harness (R7, roadmap 6.2). Phase A: build + CPU smoke.

The LoRA-adapted MOMENT-1-large baseline scored vs the committed XGBoost opponent THROUGH the
shared, validated scorer scripts/basinshift/eval_harness.py (population identity asserted; physical
units). Outside the hashed set; blind-10 never loaded (reuses eval_harness POOLS which refuse blind).

Two PRE-DECLARED head configs (fixed before any result is seen; select on dev, no further search):
  Config A "channel-mean": mean-pool sibling-curve per-patch embeddings over the channel axis
    (permutation-invariant), then the shared 2-layer GELU MLP to the hidden target curve.
  Config B "channel-attention": learned attention pooling over sibling channels, query derived from
    the target-curve-type embedding, then the SAME shared 2-layer GELU MLP.
The MLP head is IDENTICAL across A and B; only the pooling differs. LoRA(q,v r=8 alpha=16) and the
optimizer/LR/steps/batch/seed are identical across A, B, and the random-init control.

Matched random-init control: same architecture, encoder + patch_embedding parameters randomized
(no pretrained information), identical trainable budget (same LoRA + same head). (a)-(b) delta =
measured pretraining contribution. Backbone is FROZEN in both; only LoRA + head + pooling train.

Task framing mirrors the committed BasinShift XGBoost baseline exactly: hide one canonical target
(DTC/RHOB/NPHI); predict it per depth-sample from the remaining canonical curves + depth_m
(BS excluded; resistivity log10; masked-valid samples only). Depth is the sequence axis; MOMENT
processes fixed 512-sample windows. Input NaNs filled with the TRAIN-global per-curve mean before
RevIN; the head predicts the target in TRAIN-global-standardized space, de-standardized to physical
before it reaches the scorer (targets DTC/RHOB/NPHI are physical -> inverse_transform is identity).
"""
import os, sys, time, json, argparse
os.environ.setdefault("HF_HOME", "/workspace/.hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")  # Phase A is CPU-only; overridden by --device cuda
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "/workspace/LithoGPT-2/scripts/basinshift")
import eval_harness as H  # importable now (validation under __main__ guard)
from momentfm import MOMENTPipeline
from momentfm.utils.masking import Masking
from peft import LoraConfig, get_peft_model

SEQ, PATCH, NPATCH, DMODEL = 512, 8, 64, 1024
CANON, TARGETS = H.CANON, H.TARGETS
CANON_IDX = {c: i for i, c in enumerate(CANON)}
TARGET_IDX = {t: i for i, t in enumerate(TARGETS)}
SEED = 20260715


# ----------------------------- data ------------------------------------------
def train_curve_stats(train_pools):
    """TRAIN-global per-curve mean/std over observed samples (running sum/sumsq; no giant concat)."""
    n = {c: 0 for c in CANON}; s = {c: 0.0 for c in CANON}; ss = {c: 0.0 for c in CANON}
    for p in train_pools:
        for (src, safe, wid) in H.POOLS[p]:
            df = H.load_well(src, safe, wid)
            for c in CANON:
                v = df[c].to_numpy(dtype="float64"); v = v[~np.isnan(v)]
                if len(v):
                    n[c] += len(v); s[c] += float(v.sum()); ss[c] += float((v * v).sum())
    stats = {}
    for c in CANON:
        if n[c] > 0:
            mu = s[c] / n[c]; var = max(ss[c] / n[c] - mu * mu, 0.0)
            stats[c] = (mu, float(np.sqrt(var) + 1e-6))
        else:
            stats[c] = (0.0, 1.0)
    return stats


def well_windows(df, target, stats, in_curves):
    """Cut a depth-sorted well into non-overlapping 512 windows.
    Returns X [nw,C_in,512] (standardized+filled), M [nw,512] input_mask (1 real / 0 pad),
    ystd [nw,512] standardized target, yvalid [nw,512] bool observed-target mask, L original length."""
    df = df.sort_values("depth_m")
    L = len(df)
    starts = list(range(0, L, SEQ)) if L > 0 else []
    if not starts:
        return None
    Xc = {c: df[c].to_numpy(dtype="float32") for c in in_curves}
    yt = df[target].to_numpy(dtype="float32")
    mu_t, sd_t = stats[target]
    nw = len(starts); Cin = len(in_curves)
    X = np.zeros((nw, Cin, SEQ), dtype="float32")
    M = np.zeros((nw, SEQ), dtype="float32")
    ystd = np.zeros((nw, SEQ), dtype="float32")
    yvalid = np.zeros((nw, SEQ), dtype=bool)
    for k, s0 in enumerate(starts):
        seg = slice(s0, min(s0 + SEQ, L)); n = min(s0 + SEQ, L) - s0
        M[k, :n] = 1.0
        for ci, c in enumerate(in_curves):
            mu, sd = stats[c]
            col = Xc[c][seg]
            filled = np.where(np.isnan(col), mu, col)
            X[k, ci, :n] = (filled - mu) / sd
        ycol = yt[seg]
        vy = ~np.isnan(ycol)
        ystd[k, :n][vy] = (ycol[vy] - mu_t) / sd_t
        yvalid[k, :n][vy] = True
    return X, M, ystd, yvalid, L, starts


# ----------------------------- model -----------------------------------------
class CrossChannelHead(nn.Module):
    """Aggregate per-patch sibling embeddings [B,C,64,1024] -> target curve [B,512] (standardized)."""
    def __init__(self, cfg):
        super().__init__()
        assert cfg in ("A", "B")
        self.cfg = cfg
        self.curve_emb = nn.Embedding(len(CANON), DMODEL)   # curve-identity (perm-invariant tag)
        if cfg == "B":
            self.target_emb = nn.Embedding(len(TARGETS), DMODEL)
            self.q_proj = nn.Linear(DMODEL, DMODEL)
        self.mlp = nn.Sequential(nn.Linear(DMODEL, 512), nn.GELU(), nn.Linear(512, PATCH))

    def forward(self, enc_out, in_curve_ids, target_id):
        # enc_out [B,C,64,1024]; in_curve_ids [C] long; target_id int
        ce = self.curve_emb(in_curve_ids)                 # [C,1024]
        h = enc_out + ce[None, :, None, :]
        if self.cfg == "A":
            pooled = h.mean(dim=1)                         # [B,64,1024]
        else:
            q = self.q_proj(self.target_emb(torch.tensor(target_id, device=enc_out.device)))
            scores = (h * q[None, None, None, :]).sum(-1) / (DMODEL ** 0.5)   # [B,C,64]
            w = torch.softmax(scores, dim=1).unsqueeze(-1)                    # [B,C,64,1]
            pooled = (w * h).sum(dim=1)                    # [B,64,1024]
        out = self.mlp(pooled)                             # [B,64,8]
        return out.reshape(out.shape[0], NPATCH * PATCH)   # [B,512]


class TSFMBaseline(nn.Module):
    def __init__(self, cfg, init, lora_r=8, lora_alpha=16, device="cpu"):
        super().__init__()
        self.device = device
        model = MOMENTPipeline.from_pretrained(
            "AutonLab/MOMENT-1-large", model_kwargs={"task_name": "reconstruction"})
        model.init()
        # MOMENT keeps gradient checkpointing ON (required to fit batch 32 on the A40 48GB). But with
        # the frozen patch-embedding feeding the encoder, reentrant checkpointing sees no input that
        # requires grad and returns None gradients for the LoRA adapters. Fix: in encode() during
        # training we mark the encoder input as requiring grad, so gradients flow to the LoRA adapters
        # while activation memory stays low. (Confirmed by the grad-norm check in the smoke/report.)
        if init == "random":
            _randomize_backbone(model)
        # frozen backbone pieces we use
        self.normalizer = model.normalizer
        self.tokenizer = model.tokenizer
        self.patch_embedding = model.patch_embedding
        for p in self.patch_embedding.parameters():
            p.requires_grad = False
        # LoRA on encoder q,v
        lcfg = LoraConfig(r=lora_r, lora_alpha=lora_alpha, target_modules=["q", "v"],
                          lora_dropout=0.05, bias="none")
        self.encoder = get_peft_model(model.encoder, lcfg)
        self.head = CrossChannelHead(cfg)
        self.to(device)

    def encode(self, x_enc, input_mask):
        # replicate MOMENT.embed(reduction="none"): x_enc [B,C,512] -> [B,C,64,1024]
        B, C, _ = x_enc.shape
        xe = self.normalizer(x=x_enc, mask=input_mask, mode="norm")
        xe = torch.nan_to_num(xe, nan=0, posinf=0, neginf=0)
        xe = self.tokenizer(x=xe)
        enc_in = self.patch_embedding(xe, mask=input_mask)
        n_patches = enc_in.shape[2]
        enc_in = enc_in.reshape(B * C, n_patches, DMODEL)
        if self.training and not enc_in.requires_grad:
            enc_in.requires_grad_(True)   # let reentrant grad-checkpointing flow grads to LoRA
        pv = Masking.convert_seq_to_patch_view(input_mask, PATCH).to(x_enc.device)
        attn = pv.repeat_interleave(C, dim=0)
        out = self.encoder(inputs_embeds=enc_in, attention_mask=attn).last_hidden_state
        return out.reshape(B, C, n_patches, DMODEL)

    def forward(self, x_enc, input_mask, in_curve_ids, target_id):
        enc_out = self.encode(x_enc, input_mask)
        return self.head(enc_out, in_curve_ids, target_id)   # [B,512] standardized


def _randomize_backbone(model):
    """Matched-arch control: strip pretrained information from encoder + patch_embedding."""
    def reinit(m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, std=0.02)
        elif hasattr(m, "weight") and getattr(m, "weight") is not None and "Norm" in type(m).__name__:
            nn.init.ones_(m.weight)
            if getattr(m, "bias", None) is not None:
                nn.init.zeros_(m.bias)
    model.encoder.apply(reinit)
    model.patch_embedding.apply(reinit)


def trainable_params(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# ----------------------------- train / infer ---------------------------------
def gather_windows(pool_names, target, stats, in_curves, max_wells=None):
    Xs, Ms, Ys, Vs = [], [], [], []
    wells = [w for p in pool_names for w in H.POOLS[p]]
    if max_wells:
        wells = wells[:max_wells]
    for (src, safe, wid) in wells:
        df = H.load_well(src, safe, wid)
        r = well_windows(df, target, stats, in_curves)
        if r is None:
            continue
        X, M, ystd, yvalid, L, _ = r
        Xs.append(X); Ms.append(M); Ys.append(ystd); Vs.append(yvalid)
    if not Xs:
        return None
    return (np.concatenate(Xs), np.concatenate(Ms), np.concatenate(Ys), np.concatenate(Vs))


def train_model(model, data, in_curve_ids, target_id, steps, batch, lr, device, log):
    X, M, Y, V = data
    X = torch.tensor(X, device=device); M = torch.tensor(M, device=device)
    Y = torch.tensor(Y, device=device); V = torch.tensor(V, device=device)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    g = torch.Generator().manual_seed(SEED)
    n = X.shape[0]
    model.train()
    for step in range(steps):
        idx = torch.randint(0, n, (min(batch, n),), generator=g)
        pred = model(X[idx], M[idx], in_curve_ids, target_id)      # [b,512]
        v = V[idx]
        if v.sum() == 0:
            continue
        loss = ((pred - Y[idx])[v] ** 2).mean()
        opt.zero_grad(); loss.backward()
        if step == 0:
            def _gn(pred_fn):
                tot = 0.0; ng = 0; nt = 0
                for n, p in model.named_parameters():
                    if p.requires_grad and pred_fn(n):
                        nt += 1
                        if p.grad is not None:
                            tot += float(p.grad.norm()) ** 2; ng += 1
                return tot ** 0.5, ng, nt
            lg, lng, lnt = _gn(lambda n: "lora" in n.lower())
            hg, hng, hnt = _gn(lambda n: "lora" not in n.lower())
            log(f"    grad_check: lora_grad_norm={lg:.4e} ({lng}/{lnt} params w/ grad) | "
                f"head_grad_norm={hg:.4e} ({hng}/{hnt} params w/ grad)")
        opt.step()
        if step == 0 or (step + 1) % max(1, steps // 5) == 0:
            log(f"    step {step+1}/{steps} loss(std)={loss.item():.4f}")
    return model


@torch.no_grad()
def predict_pool(model, test_pool, target, stats, in_curves, in_curve_ids, target_id,
                 grid, device, batch=64):
    """Predict physical-unit target at each grid well's valid indices -> preds_by_well."""
    model.eval()
    mu_t, sd_t = stats[target]
    grid_wells = {wid: valid for (wid, valid, _y) in grid}
    preds = {}
    for (src, safe, wid) in H.POOLS[test_pool]:
        if wid not in grid_wells:
            continue
        df = H.load_well(src, safe, wid).sort_values("depth_m")
        r = well_windows(df, target, stats, in_curves)
        X, M, _ystd, _yv, L, starts = r
        full = np.zeros(L, dtype="float64")
        Xt = torch.tensor(X, device=device); Mt = torch.tensor(M, device=device)
        outs = []
        for b0 in range(0, Xt.shape[0], batch):
            pr = model(Xt[b0:b0 + batch], Mt[b0:b0 + batch], in_curve_ids, target_id)
            outs.append(pr.cpu().numpy())
        pr = np.concatenate(outs)  # [nw,512] standardized
        for k, s0 in enumerate(starts):
            n = min(s0 + SEQ, L) - s0
            full[s0:s0 + n] = pr[k, :n] * sd_t + mu_t     # de-standardize -> physical
        valid = grid_wells[wid]
        preds[wid] = H.inverse_transform(target, full[valid])   # identity for DTC/RHOB/NPHI
    return preds


# ----------------------------- driver ----------------------------------------
def run_cell(direction, target, init, cfg, args, log):
    name, train_pools, test_pool = direction
    in_curves = [c for c in CANON if c != target]         # 10 sibling channels (fixed)
    in_curve_ids = torch.tensor([CANON_IDX[c] for c in in_curves], dtype=torch.long,
                                device=args.device)
    target_id = TARGET_IDX[target]
    stats = train_curve_stats(train_pools)
    grid = H.build_grid(test_pool, target)
    if args.max_test_wells:
        grid = sorted(grid, key=lambda g: g[0])[:args.max_test_wells]  # smoke: fewer wells, still exact
    n_pop, sig = H.population_signature(grid)
    log(f"[{name}/{target}] init={init} cfg={cfg} grid_wells={len(grid)} n_samples={n_pop} "
        f"popsig={sig[:12]}")
    torch.manual_seed(SEED); np.random.seed(SEED)
    model = TSFMBaseline(cfg, init, device=args.device)
    log(f"    trainable_params={trainable_params(model):,}")
    tr = gather_windows(train_pools, target, stats, in_curves, max_wells=args.max_train_wells)
    log(f"    train_windows={tr[0].shape[0]}")
    t0 = time.time()
    train_model(model, tr, in_curve_ids, target_id, args.steps, args.batch, args.lr, args.device, log)
    t_train = time.time() - t0
    t1 = time.time()
    preds = predict_pool(model, test_pool, target, stats, in_curves, in_curve_ids, target_id,
                         grid, args.device)
    t_infer = time.time() - t1
    metrics = H.score(grid, preds, target)   # asserts population identity; physical units
    log(f"    HARNESS ACCEPTED: n={metrics['n_samples']} wells={metrics['n_wells']} "
        f"pooled_rmse={metrics['pooled_rmse']:.4f} macro={metrics['macro_well_rmse']:.4f}")
    return dict(direction=name, target=target, init=init, cfg=cfg, popsig=sig,
                train_windows=int(tr[0].shape[0]), trainable_params=trainable_params(model),
                t_train_s=round(t_train, 2), t_infer_s=round(t_infer, 2), metrics=metrics)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--configs", default="A,B")
    ap.add_argument("--inits", default="pretrained,random")
    ap.add_argument("--directions", default="C2_in_norway")
    ap.add_argument("--targets", default="DTC")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-train-wells", type=int, default=8, dest="max_train_wells")
    ap.add_argument("--max-test-wells", type=int, default=0, dest="max_test_wells")
    ap.add_argument("--out", default="/workspace/LithoGPT-2/reports/basinshift/tsfm_smoke.json")
    args = ap.parse_args()

    dmap = {r[0]: r for r in H.RUNS}
    lines = []
    def log(*a):
        s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)

    log("=== TS-FM LoRA harness (Phase A smoke) ===")
    log(f"device={args.device} steps={args.steps} batch={args.batch} lr={args.lr} "
        f"max_train_wells={args.max_train_wells}")
    results = []
    for dname in args.directions.split(","):
        for tgt in args.targets.split(","):
            for init in args.inits.split(","):
                for cfg in args.configs.split(","):
                    results.append(run_cell(dmap[dname], tgt, init, cfg, args, log))
    payload = dict(kind="tsfm_stage1_smoke", device=args.device, steps=args.steps,
                   batch=args.batch, lr=args.lr, max_train_wells=args.max_train_wells,
                   results=results, log=lines)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    log(f"[written] {args.out}")
    print("TSFM_SMOKE_DONE", flush=True)


if __name__ == "__main__":
    main()
