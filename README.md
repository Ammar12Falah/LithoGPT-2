# LithoGPT-2

Open, physics-gated well-log modeling: a reproducible pipeline, QC suite, and
cross-basin benchmark for signal-level well-log imputation and simulation.

To our knowledge no open-weights well-log foundation model at multi-thousand
public-well scale currently exists (this claim stays hedged until a direct
Hugging Face hub and GitHub search closes it; see `docs/POSITIONING.md`).
Positioning rests on three compounding doors: open (weights, pipeline, corpus
recipe), generative (calibrated stochastic realizations positioned against
SGS/MPS geostatistics), and physics (a gated trend-residual decomposition).
Wording rules in `docs/POSITIONING.md` Section 4 are binding: no unhedged
"first" or "largest" claims.

## Status

Week 1 of a 12-week build. Shipped so far: repository scaffold with CI,
ingestion for FORCE 2020 and NLOG, harmonization against
`configs/mnemonic_aliases.yaml`, pinned FORCE scoring artifacts, and a verified
license matrix. See `reports/status_week1.md`.

## Layout

- `docs/` handoff, positioning, execution plan, feasibility, license matrix,
  milestone reports.
- `configs/` `mnemonic_aliases.yaml` and pinned FORCE 2020 scoring artifacts.
- `src/lithogpt2/ingest/` FORCE 2020 and NLOG ingesters (KGS in week 2).
- `src/lithogpt2/pipeline/` harmonization (week 1); QC (week 2); trend and
  gating (weeks 3 to 4).
- `src/lithogpt2/io/` LAS parsing.
- `tests/` unit tests for config and harmonization.
- `reports/` status notes, QC dashboards, unmapped mnemonics.

## Quickstart

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q

# FORCE 2020 ingest (run where zenodo.org is reachable):
python -m lithogpt2.ingest.force2020 --dry-run
python -m lithogpt2.ingest.force2020

# NLOG ingest (index-driven; supply a confirmed borehole index):
python -m lithogpt2.ingest.nlog --index-csv path/to/nlog_index.csv
```

## Sources and licenses

FORCE 2020 (Norway), NLOG (Netherlands), KGS (Kansas). No other sources in v2.
Per-source terms, redistribution rights, and attribution are in
`docs/LICENSE_MATRIX.md`. Default posture: pipeline + weights + attribution, no
raw-data mirror.

## Scope

Design authority sits with Ammar and the senior advisor. The banned list in the
handoff (diffusion or flow-matching backbone, synthetic corpus inflation, LoRA
or fusion as the method, more than one benchmark, models above 100M parameters,
sources beyond the three above) is absolute.
