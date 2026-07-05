"""Incremental-resume helpers for large LAS corpora (KGS).

Pure pandas plus stdlib, with no LAS or lasio imports, so a dropped or sharded
run can resume cheaply: skip wells already recorded, and merge new per-well rows
into the existing per-source CSVs instead of overwriting them. Used by
scripts/run_qc_kgs.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

UNMAPPED_COLS = ["source", "raw_mnemonic", "raw_unit", "count"]


def _read_csv_safe(path: Path) -> pd.DataFrame:
    """Read a CSV, returning an empty frame for a missing/empty/headerless file."""
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def done_well_ids(records_csv: Path) -> set[str]:
    """Well ids already present in an existing per-source QC records CSV."""
    df = _read_csv_safe(records_csv)
    if "well_id" not in df.columns:
        return set()
    return set(df["well_id"].astype(str))


def merge_keyed(old_csv: Path, new_rows: list[dict], key: str = "well_id") -> pd.DataFrame:
    """Concatenate existing CSV rows with new rows, new wins on key collision."""
    new_df = pd.DataFrame(new_rows)
    old_df = _read_csv_safe(old_csv)
    if old_df.empty:
        return new_df
    if new_df.empty:
        return old_df
    combined = pd.concat([old_df, new_df], ignore_index=True)
    return combined.drop_duplicates(subset=[key], keep="last").reset_index(drop=True)


def merge_unmapped(
    old_csv: Path, new_tuples: list[tuple], legacy_csv: Path | None = None
) -> pd.DataFrame:
    """Union old and new unmapped-mnemonic rows, summing counts per mnemonic."""
    frames: list[pd.DataFrame] = []
    for c in (old_csv, legacy_csv):
        if c:
            df = _read_csv_safe(c)
            if not df.empty:
                frames.append(df)
    if new_tuples:
        nd = pd.DataFrame(
            new_tuples, columns=["source", "well_id", "raw_mnemonic", "raw_unit"]
        )
        agg = (
            nd.groupby(["source", "raw_mnemonic", "raw_unit"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        frames.append(agg)
    if not frames:
        return pd.DataFrame(columns=UNMAPPED_COLS)
    allrows = pd.concat(frames, ignore_index=True)
    for c in UNMAPPED_COLS:
        if c not in allrows.columns:
            allrows[c] = 0 if c == "count" else ""
    out = (
        allrows.groupby(["source", "raw_mnemonic", "raw_unit"], dropna=False)["count"]
        .sum()
        .reset_index()
    )
    return out.sort_values(["source", "count"], ascending=[True, False]).reset_index(drop=True)


def _as_bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


class _DashRec:
    __slots__ = (
        "well_id", "min_interval_pass", "n_grid", "washout_interval_m",
        "washout_flagged", "no_bitsize",
    )

    def __init__(self, well_id, min_interval_pass, n_grid, washout_interval_m,
                 washout_flagged, no_bitsize):
        self.well_id = well_id
        self.min_interval_pass = min_interval_pass
        self.n_grid = n_grid
        self.washout_interval_m = washout_interval_m
        self.washout_flagged = washout_flagged
        self.no_bitsize = no_bitsize


def records_from_df(df: pd.DataFrame) -> list[_DashRec]:
    """Rebuild dashboard-ready records from a merged QC records DataFrame."""
    recs: list[_DashRec] = []
    for row in df.itertuples(index=False):
        d = row._asdict()
        recs.append(_DashRec(
            well_id=str(d.get("well_id", "")),
            min_interval_pass=_as_bool(d.get("min_interval_pass", False)),
            n_grid=int(d.get("n_grid", 0) or 0),
            washout_interval_m=float(d.get("washout_interval_m", 0) or 0),
            washout_flagged=_as_bool(d.get("washout_flagged", False)),
            no_bitsize=_as_bool(d.get("no_bitsize", False)),
        ))
    return recs
