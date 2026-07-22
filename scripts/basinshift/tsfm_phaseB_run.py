#!/usr/bin/env python3
"""TS-FM Stage 1 Phase B paid run (schedule LOCKED by Plan). 12-cell single-target, 3 systems:
pretrained-A, pretrained-B (dev-select winner), control(random-init) on the winning config.
36 adapter fits = 3 systems x 12 cells. Batch 32, 600 steps/cell, LoRA q,v r=8 a=16, seed 20260715.

Everything scores through eval_harness.py (sole scorer, physical units, population identity asserted).
Same 12 BasinShift cells as the XGBoost baseline. blind_force NEVER loaded. Streaming batches
(windows are never materialized in bulk). Resumable: one result file per fit; existing files skipped.
Outside the hashed set; corpus freeze d5b35a00 untouched.
"""
import os, sys, time, json, hashlib, argparse
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ.setdefault("HF_HOME", "/workspace/.hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import numpy as np
import torch
import pyarrow.parquet as pq
sys.path.insert(0, "/workspace/LithoGPT-2/scripts/basinshift")
import eval_harness as H
import tsfm_lora_harness as T

DEV = "cuda"
SEQ = T.SEQ
RESDIR = H.ROOT / "reports/basinshift/phaseB/results"
RESDIR.mkdir(parents=True, exist_ok=True)

# dev pools (kgs + nlog have dev; force has none) added to the scorer's POOLS map
H.POOLS["kgs_dev"] = H.wells_of("kgs", "dev")
H.POOLS["nlog_dev"] = H.wells_of("nlog", "dev")
DEV_OF = {"A_cross_to_norway": ["kgs_dev", "nlog_dev"], "B_cross_to_kansas": ["nlog_dev"],
          "C1_in_kansas": ["kgs_dev"], "C2_in_norway": []}   # dev = in-train basins, held out
DEV_WELLS_CAP = 30   # per dev pool, seeded subsample -> bounds selection-inference cost

CELLS = [(name, tp, testp, tgt) for (name, tp, testp) in H.RUNS for tgt in H.TARGETS]  # 12

# ---- compact per-well sorted float32 cache (train path; avoids pandas double-cache) ----
_WA = {}
def well_arrays(src, safe, wid):
    k = (src, safe)
    if k in _WA:
        return _WA[k]
    if str(wid) in H.BLIND or str(safe) in H.BLIND:
        raise RuntimeError(f"REFUSED blind {src}/{safe}")
    df = pq.read_table(H.ROOT / f"data/processed/{src}/{safe}.parquet").to_pandas()
    depth = df["depth_m"].to_numpy("float64"); order = np.argsort(depth, kind="stable")
    a = {"depth_m": depth[order].astype("float32"), "_L": len(order)}
    for c in H.CANON:
        v = df[c].to_numpy("float64"); m = df[c + "_mask"].to_numpy().astype(bool)
        a[c] = np.where(m, v, np.nan).astype("float32")[order]
    _WA[k] = a
    return a


def curve_stats(train_pools):
    n = {c: 0 for c in H.CANON}; s = {c: 0.0 for c in H.CANON}; ss = {c: 0.0 for c in H.CANON}
    for p in train_pools:
        for (src, safe, wid) in H.POOLS[p]:
            a = well_arrays(src, safe, wid)
            for c in H.CANON:
                v = a[c]; v = v[~np.isnan(v)]
                if len(v):
                    n[c] += len(v); s[c] += float(v.sum()); ss[c] += float((v.astype("float64") ** 2).sum())
    st = {}
    for c in H.CANON:
        if n[c] > 0:
            mu = s[c] / n[c]; var = max(ss[c] / n[c] - mu * mu, 0.0)
            st[c] = (mu, float(np.sqrt(var) + 1e-6))
        else:
            st[c] = (0.0, 1.0)
    return st


def train_index(train_pools, target):
    """Window descriptors (src,safe,wid,start) with >=1 valid target sample."""
    idx = []
    for p in train_pools:
        for (src, safe, wid) in H.POOLS[p]:
            a = well_arrays(src, safe, wid); L = a["_L"]; y = a[target]
            for s0 in range(0, L, SEQ):
                if np.isfinite(y[s0:s0 + SEQ]).any():
                    idx.append((src, safe, wid, s0))
    return idx


def make_batch(descs, target, stats, in_curves):
    B = len(descs); Cin = len(in_curves)
    X = np.zeros((B, Cin, SEQ), "float32"); M = np.zeros((B, SEQ), "float32")
    Y = np.zeros((B, SEQ), "float32"); V = np.zeros((B, SEQ), bool)
    mu_t, sd_t = stats[target]
    for bi, (src, safe, wid, s0) in enumerate(descs):
        a = well_arrays(src, safe, wid); L = a["_L"]; n = min(s0 + SEQ, L) - s0
        M[bi, :n] = 1.0
        for ci, c in enumerate(in_curves):
            mu, sd = stats[c]; col = a[c][s0:s0 + n]
            X[bi, ci, :n] = (np.where(np.isnan(col), mu, col) - mu) / sd
        yc = a[target][s0:s0 + n]; vy = ~np.isnan(yc)
        Y[bi, :n][vy] = (yc[vy] - mu_t) / sd_t; V[bi, :n][vy] = True
    return X, M, Y, V


def train_cell(model, tidx, target, stats, in_curves, in_curve_ids, target_id, steps, batch, lr, rng, log):
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    model.train()
    first_gn = None
    losses = []
    for step in range(steps):
        descs = [tidx[i] for i in rng.integers(0, len(tidx), batch)]
        X, M, Y, V = make_batch(descs, target, stats, in_curves)
        Xt = torch.tensor(X, device=DEV); Mt = torch.tensor(M, device=DEV)
        Yt = torch.tensor(Y, device=DEV); Vt = torch.tensor(V, device=DEV)
        pred = model(Xt, Mt, in_curve_ids, target_id)
        if Vt.sum() == 0:
            continue
        loss = ((pred - Yt)[Vt] ** 2).mean()
        opt.zero_grad(); loss.backward()
        if step == 0:
            first_gn = sum(float(p.grad.norm()) ** 2 for n, p in model.named_parameters()
                           if p.requires_grad and "lora" in n.lower() and p.grad is not None) ** 0.5
        opt.step()
        losses.append(loss.item())
        if step == 0 or (step + 1) % 150 == 0:
            log(f"      step {step+1}/{steps} loss={loss.item():.4f}")
    return first_gn, float(np.mean(losses[-50:]))


def run_fit(init, cfg, cell, steps, batch, lr, log):
    name, train_pools, test_pool, target = cell
    fn = RESDIR / f"{init}__{cfg}__{name}__{target}.json"
    if fn.exists():
        log(f"  [skip existing] {fn.name}")
        return json.loads(fn.read_text())
    in_curves = [c for c in H.CANON if c != target]
    in_curve_ids = torch.tensor([T.CANON_IDX[c] for c in in_curves], dtype=torch.long, device=DEV)
    target_id = T.TARGET_IDX[target]
    stats = curve_stats(train_pools)
    tidx = train_index(train_pools, target)
    torch.manual_seed(T.SEED); np.random.seed(T.SEED); rng = np.random.default_rng(T.SEED)
    t0 = time.time()
    model = T.TSFMBaseline(cfg, init, device=DEV)
    tparams = sum(p.numel() for p in model.parameters() if p.requires_grad)
    gn, last_loss = train_cell(model, tidx, target, stats, in_curves, in_curve_ids, target_id,
                               steps, batch, lr, rng, log)
    t_train = time.time() - t0
    # test predictions -> score through the shared harness (population identity asserted)
    grid = H.build_grid(test_pool, target)
    preds = T.predict_pool(model, test_pool, target, stats, in_curves, in_curve_ids, target_id, grid, DEV)
    metrics = H.score(grid, preds, target)
    # dev predictions (for selection), subsampled, in-train basins only
    dev_preds = {}; dev_rmse = {}
    for dp in DEV_OF[name]:
        dgrid = sorted(H.build_grid(dp, target), key=lambda g: g[0])[:DEV_WELLS_CAP]
        if not dgrid:
            continue
        dpreds = T.predict_pool(model, dp, target, stats, in_curves, in_curve_ids, target_id, dgrid, DEV)
        dm = H.score(dgrid, dpreds, target)
        dev_preds[dp] = {str(w): [float(x) for x in dpreds[w]] for w in dpreds}
        dev_rmse[dp] = dm["pooled_rmse"]
    t_total = time.time() - t0
    res = dict(init=init, cfg=cfg, cell=name, target=target, trainable_params=tparams,
               lora_grad_norm0=gn, last_loss=last_loss, n_train_windows=len(tidx),
               t_train_s=round(t_train, 1), t_total_s=round(t_total, 1),
               metrics=metrics, dev_rmse=dev_rmse,
               test_preds={str(w): [float(x) for x in preds[w]] for w in preds},
               dev_preds=dev_preds)
    fn.write_text(json.dumps(res))
    log(f"  [{init}/{cfg}/{name}/{target}] tparams={tparams:,} gn0={gn:.2e} "
        f"test_rmse={metrics['pooled_rmse']:.4f} n={metrics['n_samples']} "
        f"dev={ {k: round(v,3) for k,v in dev_rmse.items()} } t={t_total:.0f}s")
    del model
    torch.cuda.empty_cache()
    return res


def dev_metric(results):
    """Scale-fair selection: mean over targets of (pooled dev RMSE / dev-target std)."""
    per_t = {t: {"se": 0.0, "n": 0} for t in H.TARGETS}
    for r in results:
        for dp, rm in r["dev_rmse"].items():
            # weight by dev sample count via re-deriving from preds length
            npts = sum(len(v) for v in r["dev_preds"].get(dp, {}).values())
            per_t[r["target"]]["se"] += (rm ** 2) * npts
            per_t[r["target"]]["n"] += npts
    # target std over dev pools (for normalization)
    norm = {}
    for t in H.TARGETS:
        vals = []
        for dp in ["kgs_dev", "nlog_dev"]:
            for (src, safe, wid) in H.POOLS[dp][:DEV_WELLS_CAP]:
                a = well_arrays(src, safe, wid); v = a[t]; v = v[~np.isnan(v)]
                if len(v):
                    vals.append(v)
        norm[t] = float(np.concatenate(vals).std()) if vals else 1.0
    rel = []
    for t in H.TARGETS:
        if per_t[t]["n"] > 0:
            rmse = (per_t[t]["se"] / per_t[t]["n"]) ** 0.5
            rel.append(rmse / (norm[t] + 1e-9))
    return float(np.mean(rel)) if rel else float("inf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--dry", action="store_true", help="one fit (pretrained-A, first cell) then exit")
    args = ap.parse_args()
    logf = open(H.ROOT / "reports/basinshift/phaseB/run_log.txt", "a")
    def log(*a):
        s = " ".join(str(x) for x in a); print(s, flush=True); logf.write(s + "\n"); logf.flush()

    log(f"\n=== PHASE B RUN @ {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    log(f"36 adapter fits = 3 systems x 12 cells. steps={args.steps} batch={args.batch} lr={args.lr} "
        f"LoRA q,v r=8 a=16 seed={T.SEED}")
    t0 = time.time()

    if args.dry:
        c2 = next(c for c in CELLS if c[0] == "C2_in_norway" and c[3] == "DTC")  # light cell
        log("[DRY] single fit pretrained-A, C2_in_norway/DTC")
        run_fit("pretrained", "A", c2, args.steps, args.batch, args.lr, log)
        print("PHASEB_DRY_DONE", flush=True)
        return

    # Phase 1: pretrained-A and pretrained-B over all 12 cells
    res = {"pretrained_A": [], "pretrained_B": []}
    for cfg in ["A", "B"]:
        log(f"\n--- SYSTEM pretrained-{cfg} (12 cells) ---")
        for cell in CELLS:
            res[f"pretrained_{cfg}"].append(run_fit("pretrained", cfg, cell, args.steps, args.batch, args.lr, log))

    mA = dev_metric(res["pretrained_A"]); mB = dev_metric(res["pretrained_B"])
    winner = "A" if mA <= mB else "B"
    log(f"\n=== DEV SELECTION: rel-metric A={mA:.4f} B={mB:.4f} -> WINNER pretrained-{winner} ===")

    # Phase 2: control (random-init) on winning config
    log(f"\n--- SYSTEM control random-{winner} (12 cells) ---")
    ctrl = []
    for cell in CELLS:
        ctrl.append(run_fit("random", winner, cell, args.steps, args.batch, args.lr, log))

    summary = dict(winner=winner, dev_metric_A=mA, dev_metric_B=mB, steps=args.steps,
                   batch=args.batch, lr=args.lr, n_fits=36, elapsed_s=round(time.time() - t0, 1))
    (H.ROOT / "reports/basinshift/phaseB/summary.json").write_text(json.dumps(summary, indent=2))
    log(f"\n[done] winner=pretrained-{winner} elapsed={time.time()-t0:.0f}s")
    print("PHASEB_RUN_DONE", flush=True)


if __name__ == "__main__":
    main()
