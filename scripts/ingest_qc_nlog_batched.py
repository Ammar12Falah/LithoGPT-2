"""NLOG fetch + QC under a fixed disk quota: delete-as-you-go, resumable.

The plain `nlog fetch` downloads every file before QC runs, which overruns a
small per-pod quota. This driver instead works one small batch of boreholes at
a time: download the batch's files, run harmonize + QC (writing records and
parquet, which persist), delete the batch's raw, move on. Peak raw on disk is
one batch, so it fits any quota by choosing --batch-mb.

Resumable: a borehole already in reports/nlog_qc_records.csv is skipped without
re-downloading, so a quota trip, restart, or Ctrl-C never loses finished work.

Selection: QC keeps one RawWell per borehole (the richest file), so a borehole
with many passes needs all its files present together; batching is therefore by
whole boreholes, never splitting a borehole across batches.

--select {all, primary}:
  all      every file per borehole (the 37-slice validation baseline).
  primary  download only the top metadata candidate per borehole, then run the
           per-borehole FALLBACK: any borehole that did not QC-pass on its
           primary and has more than one candidate has its remaining files
           fetched and is force-re-QC'd with the full set before a failure is
           recorded (advisor decision 2, the hybrid). Fallback is intrinsic to
           primary mode, so `--select primary` can never record a corrupted
           count from a bad first pick.
"""
from __future__ import annotations

import argparse
import csv
import re
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

from lithogpt2.ingest import USER_AGENT  # noqa: E402
from lithogpt2.ingest._http import FetchLog, PoliteFetcher  # noqa: E402
from lithogpt2.ingest.nlog import _EXT  # noqa: E402
from lithogpt2.pipeline.incremental import done_well_ids  # noqa: E402

REPORTS = ROOT / "reports"
REC_CSV = REPORTS / "nlog_qc_records.csv"


def _to_int(v: str | None, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


# Tool codes that mark an image/array log with no scalar canonical curves.
_IMAGE_TOKENS = frozenset({
    "FMS", "FMI", "CBIL", "UBI", "STAR", "EMI", "OBMI", "XRMI",
    "ARI", "IMAGE", "DIPMETER",
})
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _is_image_name(name: str) -> bool:
    """True iff a whole alphanumeric token of the filename is an image tool code.

    Whole-token (not substring) matching: 'ARI' matches a file with ARI as its
    own token but not CLARITY or MARINE; 'EMI' does not match CHEMISTRY; 'STAR'
    does not match STARTER. Rare glued forms that slip through are caught by the
    per-borehole fallback, so a real log is never demoted by accident.
    """
    return any(tok in _IMAGE_TOKENS for tok in _TOKEN_RE.findall(name.upper()))


def _span_m(r) -> float:
    try:
        return float(r.get("bottom_depth") or 0) - float(r.get("top_depth") or 0)
    except (TypeError, ValueError):
        return 0.0


def primary_candidates(rows: list[dict]) -> list[dict]:
    """Order a borehole's files most-log-like first: non-image, widest span, size.

    Heuristic for --select primary (advisor decision 2, validate against
    reports/nlog_selected_files.csv before trusting at scale). Paired with the
    per-borehole fallback in main(), so a wrong first pick costs one extra
    download, never a corrupted count.
    """
    def key(r):
        not_image = 0 if _is_image_name(r.get("file_name") or "") else 1
        return (not_image, _span_m(r), _to_int(r.get("file_size")))
    return sorted(rows, key=key, reverse=True)


def group_by_borehole(log_index: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    with log_index.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            wid = (row.get("well_id") or "").strip()
            if wid and (row.get("download_url") or "").strip():
                groups[wid].append(row)
    return groups


def build_batches(
    wellids: list[str], groups: dict[str, list[dict]], batch_bytes: int
) -> list[list[str]]:
    """Pack whole boreholes into batches under ``batch_bytes`` of raw files.

    A single borehole larger than the cap still forms its own batch (we never
    split a borehole), so the cap is a target, not a hard guarantee.
    """
    batches: list[list[str]] = []
    cur: list[str] = []
    cur_bytes = 0
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


def _passing_count() -> tuple[int, int]:
    if not REC_CSV.exists():
        return 0, 0
    total = passing = 0
    with REC_CSV.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            total += 1
            if str(row.get("min_interval_pass", "")).strip().lower() in ("true", "1"):
                passing += 1
    return passing, total


def _passing_map() -> dict[str, bool]:
    """well_id -> True iff it currently has a QC-passing record. Drives fallback."""
    m: dict[str, bool] = {}
    if REC_CSV.exists():
        with REC_CSV.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                wid = (row.get("well_id") or "").strip()
                if wid:
                    m[wid] = str(row.get("min_interval_pass", "")).strip().lower() in ("true", "1")
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-index", default="data/raw/nlog/log_index.csv")
    ap.add_argument("--raw-root", default="data/raw")
    ap.add_argument("--batch-mb", type=int, default=250,
                    help="target raw MB per batch; peak disk use is one batch")
    ap.add_argument("--max-boreholes", type=int, default=None)
    ap.add_argument("--select", choices=["all", "primary"], default="all",
                    help="all = every file per borehole (37-slice); "
                         "primary = top metadata candidate + per-borehole fallback (full crawl)")
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
    est_min = n_files * 2 / 60  # 2 s/file download floor, plus QC
    print(f"NLOG batched fetch+QC (--select {args.select}): {len(pending)} boreholes, "
          f"{n_files} files, {len(batches)} batches of ~{args.batch_mb} MB. "
          f"Download floor ~{est_min:.0f} min; QC adds a few min per batch.",
          flush=True)

    fetcher = PoliteFetcher("nlog", raw_root=args.raw_root, user_agent=USER_AGENT)
    run_qc = [sys.executable, str(ROOT / "scripts" / "run_qc_nlog.py"),
              "--well-dir", str(wells_dir)]
    fb_ids_file = REPORTS / "_nlog_fallback_ids.txt"
    t0 = time.time()
    for bi, batch in enumerate(batches, 1):
        # --- phase 1: download the primary (or every) file per borehole ---
        log = FetchLog()
        bfiles = 0
        for wid in batch:
            files = groups[wid] if args.select == "all" else primary_candidates(groups[wid])[:1]
            for r in files:
                ext = _EXT.get((r.get("file_type") or "").upper(), "bin")
                fid = (r.get("file_id") or "").strip()
                fetcher.fetch(r["download_url"].strip(),
                              rel_path=f"wells/{wid}__{fid}.{ext}", log=log)
                bfiles += 1
        print(f"[batch {bi}/{len(batches)}] downloaded {len(log.ok)} "
              f"(skipped {len(log.skipped)}, failed {len(log.failed)}) "
              f"of {bfiles} files for {len(batch)} boreholes", flush=True)
        subprocess.run(run_qc, check=False)

        # --- phase 2 (primary mode only): per-borehole fallback ---
        # Any borehole that did not QC-pass on its primary and has more than one
        # candidate file gets its remaining candidates fetched (skipping files
        # already on disk, so a resume never double-downloads), then a forced
        # re-QC of just those boreholes with the full set. merge_keyed upserts on
        # well_id, so a now-passing record overwrites the primary-only failure.
        if args.select == "primary":
            passing = _passing_map()
            fb_ids = [wid for wid in batch
                      if len(groups[wid]) > 1 and not passing.get(wid, False)]
            if fb_ids:
                fb_log = FetchLog()
                fetched = 0
                for wid in fb_ids:
                    for r in primary_candidates(groups[wid]):
                        ext = _EXT.get((r.get("file_type") or "").upper(), "bin")
                        fid = (r.get("file_id") or "").strip()
                        if (wells_dir / f"{wid}__{fid}.{ext}").exists():
                            continue  # primary (or an earlier retry) already present
                        fetcher.fetch(r["download_url"].strip(),
                                      rel_path=f"wells/{wid}__{fid}.{ext}", log=fb_log)
                        fetched += 1
                fb_ids_file.write_text("\n".join(fb_ids), encoding="utf-8")
                subprocess.run(run_qc + ["--reprocess-ids-file", str(fb_ids_file)],
                               check=False)
                fb_ids_file.unlink(missing_ok=True)
                gained = sum(1 for wid in fb_ids if _passing_map().get(wid, False))
                print(f"[batch {bi}/{len(batches)}] fallback: {len(fb_ids)} boreholes "
                      f"below pass on primary, {fetched} extra files fetched, "
                      f"{gained} now passing", flush=True)

        # --- delete-as-you-go: remove this batch's raw; records + parquet persist ---
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
    print(f"DONE. {total} boreholes processed, {passing} QC-passing. "
          f"records: {REC_CSV}")


if __name__ == "__main__":
    main()
