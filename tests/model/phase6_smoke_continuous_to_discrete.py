#!/usr/bin/env python3
"""Phase 6 smoke test: continuous input -> discrete output, the hardest structural case in the
architecture contract (docs/architecture/6p5_architecture_contract_2026-07-25.md). Synthetic
data only, no real training, no real curves loaded. Verifies the swappable-head interface is
actually wireable end to end: ContinuousInputHead -> tiny passthrough encoder -> CodebookOutputHead
-> cross-entropy loss -> one backward pass with finite gradients.
"""
import sys, traceback
sys.path.insert(0, "src")
import torch
import torch.nn as nn
from lithogpt2.model.arch_heads import build_input_head, build_output_head

PATCH = 16
D_MODEL = 64
CODEBOOK_SIZE = 15360   # matches cb15360, the config in use
BATCH = 8


def run_smoke():
    torch.manual_seed(20260715)
    input_head = build_input_head("continuous", patch=PATCH, d_model=D_MODEL)
    # tiny passthrough "encoder": a single linear + GELU standing in for the transformer body,
    # sufficient to prove gradients flow through the whole input->output path
    body = nn.Sequential(nn.Linear(D_MODEL, D_MODEL), nn.GELU())
    output_head = build_output_head("codebook", d_model=D_MODEL, codebook_size=CODEBOOK_SIZE)

    patch_batch = torch.randn(BATCH, PATCH)
    target_codes = torch.randint(0, CODEBOOK_SIZE, (BATCH,))

    embed = input_head(patch_batch)
    assert embed.shape == (BATCH, D_MODEL), f"input head shape wrong: {embed.shape}"

    hidden = body(embed)
    assert hidden.shape == (BATCH, D_MODEL), f"body shape wrong: {hidden.shape}"

    logits = output_head(hidden)
    assert logits.shape == (BATCH, CODEBOOK_SIZE), f"output head shape wrong: {logits.shape}"
    assert torch.isfinite(logits).all(), "non-finite logits"

    loss = nn.functional.cross_entropy(logits, target_codes)
    assert torch.isfinite(loss), f"non-finite loss: {loss}"

    loss.backward()
    n_params_with_grad = 0
    n_params_total = 0
    for name, p in list(input_head.named_parameters()) + list(body.named_parameters()) + list(output_head.named_parameters()):
        n_params_total += 1
        if p.grad is None:
            raise AssertionError(f"parameter {name} got no gradient")
        if not torch.isfinite(p.grad).all():
            raise AssertionError(f"parameter {name} got non-finite gradient")
        n_params_with_grad += 1

    print(f"SMOKE PASS: embed={tuple(embed.shape)} hidden={tuple(hidden.shape)} "
          f"logits={tuple(logits.shape)} loss={loss.item():.4f} "
          f"params_with_finite_grad={n_params_with_grad}/{n_params_total}")
    return True


if __name__ == "__main__":
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            run_smoke()
            print(f"PHASE6_SMOKE_PASS attempt={attempt}")
            sys.exit(0)
        except Exception as e:
            print(f"SMOKE FAILURE attempt={attempt}/{max_attempts}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print("PHASE6_SMOKE_FAILED_ALL_ATTEMPTS")
    sys.exit(1)
