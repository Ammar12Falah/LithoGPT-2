# Pod runbook: produce the real Gate G1 evidence

Verified against the code in this repo on 4 July 2026 (commit shown by
`git rev-parse --short HEAD`). This is the ordered, copy-paste path to the one
thing the advisor wants for G1: a real cross-continent QC-passing count. Run it
on a pod with open internet (browser Jupyter, CPU is fine), not the laptop
(Forcepoint blocks the data domains).

## Durations and spend (read first, HANDOFF Rule 5)

- Setup and tests: 1 to 6 min. No spend.
- KGS download (G1 subset, ~3.06 GB, 9,324 LAS): tens of minutes, bandwidth
  bound. The 2 s/host throttle adds only seconds (about 4 requests). No spend.
- KGS unpack (9,324 files): a few minutes. No spend.
- KGS QC pass: THIS IS THE LONG POLE. A single all-at-once run is an estimated 3
  to 6.5 hours on CPU (rough extrapolation from the FORCE rate of 98 wells in 2 to
  4 min, not a measured figure), which crosses the 4-hour bar in HANDOFF Rule 5.
  The runner is now incremental, so the intended path is to shard by year (step
  4b): each year is processed once and skipped thereafter, so no run exceeds the
  largest single year (2024, ~3,810 wells, about 1.3 to 2.6 hours), staying under
  the bar with no reprocessing. No GPU, no paid compute. A parallel option would
  bring the whole subset under an hour and is recommended as a follow-up; it is
  not in the runner yet (see the note at the end of step 4b).
- combine and G1 report: seconds. No spend.

Nothing here uses GPU or paid compute. Cap is 150 hours; track it.

## Preconditions

- FORCE was already ingested and QC'd (98/98, real, committed in `reports/`). You
  do not need to rerun it for G1. Steps 0 to 1 just re-verify the environment.
- This runbook adds one new file, `scripts/g1_report.py`, which emits the G1
  milestone report in the fixed HANDOFF 11.3 format from real artifacts only.

## Step 0. Environment and tests (1 to 6 min)

Running scripts in browser Jupyter: run them as files, not by pasting the body
into a cell. In a cell use either `%run scripts/run_qc_kgs.py --max-wells 50` or
`!python scripts/run_qc_kgs.py --max-wells 50`, from a cell whose working
directory is the repo root (check with `!pwd`, change with `%cd /path/to/LithoGPT-2`).
Pasting a script's contents into a cell breaks: a cell has no `__file__`, and
argparse then sees the Jupyter kernel's arguments instead of yours. The scripts
now fall back gracefully if `__file__` is missing, but `%run` or `!python` is the
correct way regardless. This applies to every `python scripts/...` command below.

```
pip install -e ".[dev]"          # if requires-python complains: pip install -r requirements.txt
ruff check src tests scripts     # expect: clean
python -m pytest -q              # expect: 48 passed (41 prior + 7 new incremental tests)
```

Sanity check: 48 passed, ruff clean. If the editable install did not take, prefix
later module commands with `PYTHONPATH=src`.

Note: the repo is at 9 commits, not 8. The handoff's "8 commits" was written just
before its own commit landed. Cosmetic only.

## Step 1. FORCE re-verify (optional, ~2 to 4 min)

Only if you want a fresh FORCE pass. Otherwise skip; the committed FORCE records
are real.

```
python scripts/run_qc_force.py
```

Expected stdout: `minimum-interval pass: 98/98`, `washout flagged (BS present,
washed intervals): 59`, `no bit size (washout skipped): 29`.

Washout wording, so nobody trips on it: the code reports 59 as the "washout
flagged" metric, which it defines as flagged AND washout_interval_m > 0. The raw
`washout_flagged` column in `reports/force2020_qc_records.csv` shows 68 (9 of
those have a 0 m washed interval). Both are correct; 59 is the intended metric.

## Step 2. KGS dry-run (instant)

```
python -m lithogpt2.ingest.kgs --dry-run
```

Expected: it prints the index URL and the three G1 archives, ending with
`planned LAS files across 3 archives: ~9324`. The three archives are
`2024.zip` (856 MB, 3810), `2014.zip` (1.2 GB, 3231), `2016.zip` (1.0 GB, 2283).

## Step 3. KGS pull (tens of minutes, download bound)

If you are sharding (recommended, step 4b), pull one year at a time there and
skip this all-at-once pull. To pull the whole G1 subset in one go:

```
python -m lithogpt2.ingest.kgs
```

This fetches the index and the three G1 archives to `data/raw/kgs/`, then unpacks
LAS into `data/raw/kgs/las/`. It is resumable: the PoliteFetcher keeps a manifest
and skips by sha256, so if it drops, just run it again.

Sanity check after it finishes:

```
ls data/raw/kgs/las/*.las | wc -l      # expect a number near 9,324 (minus dupes)
```

If the archive base or index 404s, do not guess a new URL. Stop and escalate
(HANDOFF Rule 8). The pinned URLs are in `src/lithogpt2/ingest/kgs.py`.

## Step 4a. KGS QC smoke first (about 1 to 2 min)

Before the multi-hour full pass, validate the path on a small slice:

```
python scripts/run_qc_kgs.py --max-wells 50
```

Expected stdout starts with `KGS QC pass: +50 wells this run.`, then a
`cumulative wells` line, a `minimum-interval pass (QC-passing)` count, and a
distinct-unmapped-mnemonics count. Confirm `reports/qc_kgs/index.html` renders and
`reports/kgs_qc_records.csv` exists. These 50 wells are recorded and will be
skipped (not reprocessed) by the sharded runs in step 4b.

## Step 4b. KGS QC pass, sharded and incremental (recommended)

The runner is now incremental: on each run it reads `reports/kgs_qc_records.csv`,
skips wells already recorded, processes only newly-unpacked LAS, and merges the
results into the existing CSVs. So sharding by year processes each year exactly
once and no single run exceeds the largest year (2024, ~3,810 wells, about 1.3 to
2.6 hours), which keeps every run under the 4-hour bar with no wasted reprocessing.
Start with the largest year and add the others:

```
python -m lithogpt2.ingest.kgs --years 2024.zip
python scripts/run_qc_kgs.py          # processes 2024 only

python -m lithogpt2.ingest.kgs --years 2014.zip
python scripts/run_qc_kgs.py          # skips 2024 (recorded), processes 2014 only

python -m lithogpt2.ingest.kgs --years 2016.zip
python scripts/run_qc_kgs.py          # skips 2024 + 2014, processes 2016 only
```

Each run prints `+N wells this run (M already done, skipped)` and a growing
`cumulative wells` count. The 50 wells from the step 4a smoke also count toward
the cumulative total and are not reprocessed. Use `--fresh` only to rebuild the
whole KGS records set from scratch.

Memory: leave `keep_harmonized=False` (the default in the runner). Do not flip it
on the full corpus; the batch engine streams so it stays memory-safe (HANDOFF
gotcha).

All-at-once alternative: `python scripts/run_qc_kgs.py` over the full
`data/raw/kgs/las/` in one go is an estimated 3 to 6.5 hours, which crosses the
4-hour bar, so confirm first if you go this route instead of sharding.

Recommended follow-up (not in the runner yet): the QC pass is embarrassingly
parallel and CPU-bound, so an opt-in multiprocess mode would bring the whole
subset under an hour on a multi-core pod and remove the duration question
entirely. I did not ship it here because I cannot run or validate multiprocessing
in the build sandbox, and I will not hand over concurrency code as done without a
run behind it. Say the word and I will add it as an opt-in `--workers` flag
(default stays serial, so nothing regresses) for you to validate with the step 4a
smoke before a full run.

## Step 5. Triage KGS unmapped mnemonics (agent step, needs your OK)

KGS LAS will surface many unmapped mnemonics in
`reports/kgs_unmapped_mnemonics.csv`. The alias table
`configs/mnemonic_aliases.yaml` is extended only from observed data, never
guessed, and only after you and the advisor triage the list (HANDOFF Rule 8, the
documented weekly step). Send me that CSV and I will propose additions for your
review; I will not edit the config unilaterally.

## Step 6. Combined count and the G1 report (seconds)

```
python scripts/combine_qc.py          # prints per-source and total QC-passing, MET/not
python scripts/g1_report.py           # writes reports/status_g1.md in the fixed 11.3 format
```

`combine_qc.py` defines QC-passing as `min_interval_pass` and G1 as 5,000+ across
2+ continents (8,000 stretch). `g1_report.py` reads the real CSVs only; it refuses
if KGS records are missing, and it fills Spend, Deviations, and Blockers from
optional files (`reports/spend_log.json`, `reports/g1_deviations.md`,
`reports/g1_blockers.md`) or from the current factual state, marking anything that
needs your confirmation. No bracket placeholders.

Before the report goes to the advisor, confirm the Spend, Deviations, and Blockers
sections (the script prints a reminder). If you keep a spend note, drop it in
`reports/spend_log.json` as `{"gpu_hours": 0, "usd": 0, "notes": "..."}`.

## Step 7. Ship and stop (gate protocol)

```
git add -A && git commit -m "Gate G1: real KGS QC pass + combined count + G1 report"
git push
```

Push uses the HTTPS token. If it is rejected as non-fast-forward, the remote is
ahead; `git pull --rebase` then push (HANDOFF gotcha).

Then STOP. G1 is not self-certified. You take `reports/status_g1.md` to the
advisor; the agent proceeds past the gate only after you record a GATE APPROVED
note in the repo (HANDOFF 11.3, Rule 9).

## If G1 count falls short

If the KGS subset plus FORCE does not clear 5,000 QC-passing, the pre-agreed
fallback (HANDOFF 11.2) is to extend ingestion by one week (add more KGS years
from `ARCHIVE_ZIPS`) and compress week 5. Do not pull in banned sources or inflate
the count. Report the real number and escalate.
