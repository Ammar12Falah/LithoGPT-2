#!/usr/bin/env python3
"""Full-sweep sizing probe (Phase A, CPU). Counts the per-curve TRAIN patch-bank size at full
scale (cap=None) and measures clean FSQ training throughput (patch-steps/sec) so the sweep cost
can be estimated. No paid GPU, no sweep run. Writes fsq_sweep_sizing.json."""
import json, time
from pathlib import Path
import numpy as np, torch
import eval_harness as EH
import fsq_tokenizer as FT
import r8_acceptance as R8

OUT = EH.ROOT / "reports/basinshift"


def main():
    torch.set_num_threads(torch.get_num_threads())
    sizes = {}
    biggest = (None, 0, None)
    for c in EH.CANON:
        arrs = R8.curve_arrays_train(c)
        mean, std = FT.compute_stats(arrs)
        bank = FT.build_patch_bank(arrs, mean, std, cap=None)
        sizes[c] = int(len(bank))
        print(f"[bank {c}] patches={len(bank)}", flush=True)
        if len(bank) > biggest[1]:
            biggest = (c, len(bank), bank)
        else:
            del bank
    total = int(sum(sizes.values()))
    print(f"TOTAL train patches across {len(EH.CANON)} curves = {total}", flush=True)

    # throughput: time 3 epochs on a fixed 200k-patch real bank (steady-state CPU matmul rate)
    cname, _, bigbank = biggest
    probe = bigbank[:200_000] if len(bigbank) >= 200_000 else bigbank
    t0 = time.time()
    FT.train_tokenizer(probe, levels=(8, 5, 5, 5), epochs=3, log=None)
    dt = time.time() - t0
    patch_steps = len(probe) * 3
    rate = patch_steps / dt
    print(f"THROUGHPUT cpu curve={cname} probe_patches={len(probe)} epochs=3 "
          f"wall={dt:.1f}s rate={rate:.0f} patch-steps/sec", flush=True)

    res = dict(patch_bank_sizes=sizes, total_train_patches=total,
               cpu_throughput_patch_steps_per_sec=round(rate, 1),
               probe_curve=cname, probe_patches=int(len(probe)),
               torch_num_threads=torch.get_num_threads())
    (OUT / "fsq_sweep_sizing.json").write_text(json.dumps(res, indent=2))
    print("SIZING_DONE", flush=True)


if __name__ == "__main__":
    main()
