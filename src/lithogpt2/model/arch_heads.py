#!/usr/bin/env python3
"""6.5 architecture contract scaffold (Phase 4, ATCE critical path). Swappable input/output
heads behind one interface each, per docs/architecture/6p5_architecture_contract_2026-07-25.md.
Ruling-independent: instantiating either implementation is a config choice, not a code branch.
No training here -- Phase 6 smoke-tests this end to end with synthetic data.
"""
import torch
import torch.nn as nn


class InputHead(nn.Module):
    """patch_batch [B, patch] -> embedding [B, d_model]."""
    def forward(self, patch_batch):
        raise NotImplementedError


class ContinuousInputHead(InputHead):
    def __init__(self, patch, d_model):
        super().__init__()
        self.proj = nn.Linear(patch, d_model)

    def forward(self, patch_batch):
        return self.proj(patch_batch)


class CodebookInputHead(InputHead):
    """Wraps a trained FSQ encoder+quantizer (fsq_tokenizer.FSQAutoEncoder pieces). The
    quantizer's per-dim integer codes are flattened to one index into an embedding table."""
    def __init__(self, fsq_autoencoder, d_model):
        super().__init__()
        self.encoder = fsq_autoencoder.enc
        self.fsq = fsq_autoencoder.fsq
        self.codebook_size = self.fsq.codebook_size
        self.embed = nn.Embedding(self.codebook_size, d_model)
        # per-dim level counts, for flattening a multi-dim code into one index
        self.register_buffer("_level_strides", self._make_strides(self.fsq.levels_list))

    @staticmethod
    def _make_strides(levels):
        strides = [1]
        for L in reversed(levels[1:]):
            strides.append(strides[-1] * L)
        return torch.tensor(list(reversed(strides)), dtype=torch.int64)

    def forward(self, patch_batch):
        z = self.encoder(patch_batch)
        codes = self.fsq.codes(z)                       # [B, d] integer levels per dim
        flat_idx = (codes * self._level_strides).sum(dim=-1)   # [B] single index in [0, codebook_size)
        return self.embed(flat_idx)


class OutputHead(nn.Module):
    """hidden [B, d_model] -> prediction."""
    def forward(self, hidden):
        raise NotImplementedError


class CodebookOutputHead(OutputHead):
    def __init__(self, d_model, codebook_size):
        super().__init__()
        self.proj = nn.Linear(d_model, codebook_size)

    def forward(self, hidden):
        return self.proj(hidden)   # logits


class ContinuousOutputHead(OutputHead):
    def __init__(self, d_model, patch):
        super().__init__()
        self.proj = nn.Linear(d_model, patch)

    def forward(self, hidden):
        return self.proj(hidden)   # regression target


def build_input_head(kind, patch, d_model, fsq_autoencoder=None):
    if kind == "continuous":
        return ContinuousInputHead(patch, d_model)
    if kind == "codebook":
        assert fsq_autoencoder is not None, "codebook input head needs a trained FSQAutoEncoder"
        return CodebookInputHead(fsq_autoencoder, d_model)
    raise ValueError(f"unknown input head kind: {kind}")


def build_output_head(kind, d_model, patch=None, codebook_size=None):
    if kind == "continuous":
        assert patch is not None
        return ContinuousOutputHead(d_model, patch)
    if kind == "codebook":
        assert codebook_size is not None
        return CodebookOutputHead(d_model, codebook_size)
    raise ValueError(f"unknown output head kind: {kind}")
