"""NLOG fetch + QC under a fixed disk quota: delete-as-you-go, resumable."""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


def _repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[1]
    except NameError:
        here = Path.cwd().resolve()
        for cand in (here, *here.parents):
            if (cand / "src" / "lithogpt2").is_dir():
                return cand
        return here


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "src"))

from lithogpt2.ingest import USER_AGENT
from lithogpt2.ingest._http import FetchLog, PoliteFetcher
from lithogpt2.ingest.nlog import _EXT
from lithogpt2.pipeline.incremental import done_well_ids

REPORTS = ROOT / "reports"
REC_CSV = REPORTS / "nlog_qc_records.csv"


def _to_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def group_by_borehole(log_index: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    with log_index.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            wid = (row.get("well_id") or "").strip()
            if wid and (row.get("download_url") or "").strip():
                groups[wid].append(row)
    return groups


def build_batches(wellids, groups, batch_bytes):
    batches, cur, cur_bytes = [], [], 0
    for wid in wellids:
        wb = sum(_to_int(r.get("file_size")) for r in groups[wid])
        if cur and cur_bytes + wb > batch_bytes:
            batches.append(cur)
            cur, cur_bytes = [], 0
        cur.append(wid)
        cur_bytes += wb
    if cur:
        batches.append(cur)
    return batches


def _passing_count():
    if not REC_CSV.exists():
        return 0, 0
    total = passing = 0
    with REC_CSV.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            total += 1
            if str(row.get("min_interval_pass", "")).strip().lower() in ("true", "1"):
                passing += 1
    return passing, total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-index", default="data/raw/nlog/log_index.csv")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--batch-mb", type=int, default=250)
    ap.add_argument("--max-boreholes", type=int, default=None)
    args = ap.parse_args()

    log_index = Path(args.log_index)
    if not log_index.exists():
        print(f"No log index at {log_index}. Run `nlog resolve` first."); return

    groups = group_by_borehole(log_index)
    done = done_well_ids(REC_CSV)
    pending = [w for w in sorted(groups) if w not in done]
    if args.max_boreholes is not None:
        pending = pending[:args.max_boreholes]
    if not pending:
        p, t = _passing_count()
        print(f"Nothing pending. {t} boreholes done, {p} QC-passing."); return

    batches = build_batches(pending, groups, args.batch_mb * 1_000_000)
    n_files = sum(len(groups[w]) for w in pending)
    wells_dir = Path(args.raw_root) / "nlog" / "wells"
    est_min = n_files * 2 / 60
    print(f"NLOG batched fetch+QC: {len(pending)} boreholes, {n_files} files, "
          f"{len(batches)} batches of ~{args.batch_mb} MB. "
          f"Download floor ~{est_min:.0f} min; QC adds a few min per batch.",
          flush=True)

    fetcher = PoliteFetcher("nlog", raw_root=args.raw_root, user_agent=USER_AGENT)
    t0 = time.time()
    for bi, batch in enumerate(batches, 1):
        log = FetchLog()
        bfiles = 0
        for wid in batch:
            for r in groups[wid]:
                ext = _EXT.get((r.get("file_type") or "").upper(), "bin")
                fid = (r.get("file_id") or "").strip()
                fetcher.fetch(r["download_url"].strip(),
                              rel_path=f"wells/{wid}__{fid}.{ext}", log=log)
                bfiles += 1
        print(f"[batch {bi}/{len(batches)}] downloaded {len(log.ok)} "
              f"(skipped {len(log.skipped)}, failed {len(log.failed)}) "
              f"of {bfiles} files for {len(batch)} boreholes", flush=True)

        subprocess.run([sys.executable, str(ROOT / "scripts" / "run_qc_nlog.py"),
                        "--well-dir", str(wells_dir)], check=False)

        removed = 0
        for wid in batch:
            for p in wells_dir.glob(f"{wid}__*"):
                try:
                    p.unlink(); removed += 1
                except OSError:
                    pass
        passing, total = _passing_count()
        elapsed = (time.time() - t0) / 60
        print(f"[batch {bi}/{len(batches)}] deleted {removed} raw files. "
              f"cumulative: {total} boreholes, {passing} QC-passing. "
              f"{elapsed:.0f} min elapsed.\n", flush=True)

    passing, total = _passing_count()
    print(f"DONE. {total} boreholes processed, {passing} QC-passing. records: {REC_CSV}")


if __name__ == "__main__":
    main()
