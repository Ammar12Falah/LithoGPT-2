"""LithoGPT-2: open, physics-gated well-log foundation model pipeline.

Week 1 scope: repository scaffold, ingestion (FORCE 2020, NLOG), and
harmonization against configs/mnemonic_aliases.yaml. Later weeks add QC,
trend/gating, tokenizer, model, training, evaluation, and the benchmark.

Design authority sits with Ammar and the senior advisor. This package
executes the frozen scope in the handoff (docs/HANDOFF.md). It never
fabricates: any reported number must be backed by a file, a command
output, or a logged run.
"""

__version__ = "0.1.0"
