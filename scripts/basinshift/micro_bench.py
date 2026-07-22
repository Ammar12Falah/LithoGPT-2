#!/usr/bin/env python3
"""A40 micro-benchmark: measure real per-window fwd+bwd (train) and fwd (infer) at batch 32,
for cfg A and cfg B, to replace the assumed CPU->A40 speedup. ~1 min, pennies."""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"           # set BEFORE harness import (its setdefault won't override)
os.environ.setdefault("HF_HOME", "/workspace/.hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import sys, time
import torch
sys.path.insert(0, "/workspace/LithoGPT-2/scripts/basinshift")
import tsfm_lora_harness as T
import eval_harness as H

DEV = "cuda"
BATCH = 32
print("CUDA=%s DEV=%s" % (torch.cuda.is_available(), torch.cuda.get_device_name(0)))

# CPU reference per-window fwd+bwd (from the committed smoke, batch 4)
CPU_SPW = {"A": 17.09 / 4, "B": 29.14 / 4}

train_pools = ["force_train"]; target = "DTC"
in_curves = [c for c in H.CANON if c != target]
in_curve_ids = torch.tensor([T.CANON_IDX[c] for c in in_curves], dtype=torch.long, device=DEV)
stats = T.train_curve_stats(train_pools)
X, M, Y, V = T.gather_windows(train_pools, target, stats, in_curves, max_wells=16)
Xt = torch.tensor(X, device=DEV); Mt = torch.tensor(M, device=DEV)
Yt = torch.tensor(Y, device=DEV); Vt = torch.tensor(V, device=DEV)
n = Xt.shape[0]
print("bench_windows=%d" % n)

results = {}
for cfg in ["A", "B"]:
    torch.manual_seed(T.SEED)
    model = T.TSFMBaseline(cfg, "pretrained", device=DEV)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-3)
    g = torch.Generator().manual_seed(T.SEED)
    model.train()
    def step():
        idx = torch.randint(0, n, (BATCH,), generator=g)
        pred = model(Xt[idx], Mt[idx], in_curve_ids, 0)
        v = Vt[idx]
        loss = ((pred - Yt[idx])[v] ** 2).mean()
        opt.zero_grad(); loss.backward(); opt.step()
        return loss.item()
    for _ in range(3):        # warmup (cudnn autotune, alloc, kernel compile) -- NOT timed
        step()
    # confirm LoRA grads flow under gradient-checkpointing + requires_grad fix
    lg = sum(float(p.grad.norm()) ** 2 for n, p in model.named_parameters()
             if p.requires_grad and "lora" in n.lower() and p.grad is not None) ** 0.5
    nlg = sum(1 for n, p in model.named_parameters()
              if p.requires_grad and "lora" in n.lower() and p.grad is not None)
    ntot = sum(1 for n, p in model.named_parameters() if p.requires_grad and "lora" in n.lower())
    print("  gradcheck cfg%s lora_grad_norm=%.4e lora_params_w_grad=%d/%d" % (cfg, lg, nlg, ntot))
    torch.cuda.synchronize()
    NS = 20; t0 = time.time()
    for _ in range(NS):
        step()
    torch.cuda.synchronize()
    sps = (time.time() - t0) / NS
    spw = sps / BATCH
    speedup = CPU_SPW[cfg] / spw
    results[cfg] = dict(s_per_step=sps, s_per_window=spw, speedup=speedup)
    print("BENCH cfg%s batch%d s/step=%.4f s/window=%.5f  CPU_s/window=%.3f  speedup=%.1fx"
          % (cfg, BATCH, sps, spw, CPU_SPW[cfg], speedup))
    mem = torch.cuda.max_memory_allocated() / 1e9
    print("  peak_gpu_mem_GB=%.2f" % mem)
    del model, opt; torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()

# inference throughput (fwd only), cfg A
torch.manual_seed(T.SEED)
model = T.TSFMBaseline("A", "pretrained", device=DEV); model.eval()
with torch.no_grad():
    _ = model(Xt[:BATCH], Mt[:BATCH], in_curve_ids, 0)   # warmup
    torch.cuda.synchronize(); NB = 15; t0 = time.time()
    for _ in range(NB):
        _ = model(Xt[:BATCH], Mt[:BATCH], in_curve_ids, 0)
    torch.cuda.synchronize()
    ispw = (time.time() - t0) / NB / BATCH
print("BENCH_INFER cfgA batch%d s/window=%.5f" % (BATCH, ispw))
print("MICRO_DONE")
