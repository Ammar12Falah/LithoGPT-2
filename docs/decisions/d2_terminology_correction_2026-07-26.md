# Terminology correction: "foundation model" -> "cross-basin generative transformer for well logs" (2026-07-26)

Stated correction, per instruction. "Foundation model" implies broad, general-purpose transfer
that has not been demonstrated for this project. LithoGPT-2 (and its planned successor work) is
a transformer trained for cross-basin well-log imputation/generation across a specific set of
basins (Kansas, Netherlands, Norway) with a specific, tested transfer claim (BasinShift), not a
broad-domain foundation model in the sense that term has come to imply (e.g. zero-shot transfer
to arbitrary downstream tasks, web-scale pretraining, emergent general capability). The original
term overclaimed scope this project has not shown.

Replaced across the repo (27 occurrences, 10 files): `README.md`,
`docs/AGENT_HANDOFF_STATE_2026-07-04.md`, `docs/BENCHMARK.md`, `docs/DECISIONS_LOG.md`,
`docs/FEASIBILITY_ASSESSMENT.md`, `docs/HANDOFF.md`, `docs/POSITIONING.md`,
`docs/PROJECT_DOSSIER.md`, `docs/tsfm_stage1_adaptation.md`, `src/lithogpt2/__init__.py`.

This is a correction, not a retroactive edit of history: prior commits and the decisions log's
own prior entries that used the old term are left as-is (they are a historical record of what
was written at the time); this commit changes only the current, living copy of the repo/docs/
dataset-card language going forward.
