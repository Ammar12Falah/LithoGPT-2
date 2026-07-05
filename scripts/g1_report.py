"""Generate the Gate G1 milestone report from REAL run artifacts only.

This produces reports/status_g1.md in the fixed heading order from HANDOFF
Section 11.3. It never invents numbers: every metric is read from a committed
artifact, and the script refuses to run until the QC record CSVs exist (so a
results table cannot be written before the runs exist, HANDOFF Section 0 Rule 1).

Definitions mirror scripts/combine_qc.py (keep in sync):
  QC-passing  = rows with min_interval_pass == True
  G1 target   = 5,000 QC-passing wells across 2+ continents (8,000 stretch)

Human-only sections (spend, deviations, blockers) are filled from small optional
input files if present, otherwise from the current, factual repo state; the
script prints a reminder to confirm them before the report goes to the advisor.
No bracket placeholders are ever written (Ammar output rule).

Usage:  python scripts/g1_report.py [--out reports/status_g1.md] [--allow-partial]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

# Mirrors scripts/combine_qc.py. Keep these two in sync.
SOURCES = {
    "force2020": {"label": "FORCE 2020 (Norway, North Sea)", "continent": "Europe"},
    "kgs": {"label": "KGS (Kansas, USA)", "continent": "North America"},
    "nlog": {"label": "NLOG (Netherlands)", "continent": "Europe"},
}
G1_TARGET = 5000
G1_STRETCH = 8000
HOUR_CAP = 150

REPORTS = Path("reports")


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _read_optional_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _unmapped_count(src: str) -> int:
    """Rows of unmapped mnemonics for a source.

    The KGS path writes reports/kgs_unmapped_mnemonics.csv; the FORCE runner
    writes the un-prefixed reports/unmapped_mnemonics.csv. Resolve either, and
    count only rows whose source column matches (the un-prefixed file could in
    principle hold more than one source).
    """
    candidates = [REPORTS / f"{src}_unmapped_mnemonics.csv"]
    if src == "force2020":
        candidates.append(REPORTS / "unmapped_mnemonics.csv")
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p)
            if "source" in df.columns:
                return int((df["source"] == src).sum())
            return len(df)
    return 0


def _source_rows() -> tuple[list[dict], set[str], int, int]:
    rows: list[dict] = []
    continents: set[str] = set()
    total_wells = total_pass = 0
    for src, meta in SOURCES.items():
        f = REPORTS / f"{src}_qc_records.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f)
        wells = len(df)
        passing = int(df["min_interval_pass"].sum()) if "min_interval_pass" in df else 0
        fail_f = REPORTS / f"{src}_failures.csv"
        n_fail = len(pd.read_csv(fail_f)) if fail_f.exists() else 0
        n_unmapped = _unmapped_count(src)
        rows.append({
            "source": src, "label": meta["label"], "continent": meta["continent"],
            "records_path": str(f), "wells": wells, "qc_passing": passing,
            "unreadable": n_fail, "unmapped": n_unmapped,
        })
        continents.add(meta["continent"])
        total_wells += wells
        total_pass += passing
    return rows, continents, total_wells, total_pass


def _spend_section() -> str:
    log = REPORTS / "spend_log.json"
    if log.exists():
        d = json.loads(log.read_text(encoding="utf-8"))
        gpu = d.get("gpu_hours", 0)
        usd = d.get("usd", 0)
        note = d.get("notes", "")
        return (f"GPU hours: {gpu}. USD: {usd}. Cumulative against the {HOUR_CAP}-hour "
                f"cap. {note}").strip()
    return (
        "No paid compute or GPU hours recorded to date. Weeks 1 to 2 ran on CPU "
        f"pods and the free FORCE and GitHub paths. Cap: {HOUR_CAP} hours. "
        "CONFIRM before advisor review."
    )


def _deviations_section() -> str:
    txt = _read_optional_text(REPORTS / "g1_deviations.md")
    if txt:
        return txt
    return "None recorded for weeks 1 to 2. CONFIRM before advisor review."


def _blockers_section(rows: list[dict], continents: set[str]) -> str:
    txt = _read_optional_text(REPORTS / "g1_blockers.md")
    if txt:
        return txt
    have = {r["source"] for r in rows}
    lines = []
    if "kgs" not in have:
        lines.append(
            "- KGS QC records not present. The KGS pull and QC pass have not been "
            "run on the pod yet; this is the G1 volume anchor."
        )
    if "nlog" not in have:
        lines.append(
            "- NLOG LAS file-list API still pending (two URLs to capture, "
            "docs/NLOG_ACCESS.md). NLOG is NOT on the G1 critical path."
        )
    return "\n".join(lines) if lines else "None."


def _pending_inputs() -> str:
    """Genuinely-open inputs only (STATE doc Section 7).

    HANDOFF 12.3 also named the repo URL, ingestion contact email, and RunPod
    credit confirmation; those were closed at kickoff, so they are omitted here.
    Prune this list as items close. An optional reports/pending_inputs.md
    overrides it if you want to manage the list outside the code.
    """
    override = _read_optional_text(REPORTS / "pending_inputs.md")
    if override:
        return override
    return (
        "- NLOG per-borehole LAS file-list API: the two request URLs "
        "(file-list JSON and file-download), captured per docs/NLOG_ACCESS.md. "
        "NOT on the G1 critical path.\n"
        "- Direct Hugging Face hub and GitHub search confirming no existing "
        "open-weights well-log pretrained model (closes the POSITIONING.md hedge).\n"
        "- G2 tokenizer bar sign-off (proposed default: 5 percent relative degradation).\n"
        "- Benchmark name decision (week 3, collision-checked vs WellLogBench)."
    )


def build_report(out_path: Path, allow_partial: bool) -> int:
    rows, continents, total_wells, total_pass = _source_rows()
    if not rows:
        print("No per-source QC record CSVs found in reports/. Run "
              "run_qc_force.py and run_qc_kgs.py first. Refusing to write an "
              "empty report (HANDOFF Rule 1).")
        return 1

    have_kgs = any(r["source"] == "kgs" for r in rows)
    if not have_kgs and not allow_partial:
        print("KGS QC records are missing, so this would be a FORCE-only, "
              "pre-G1 draft. Re-run after the KGS pod pass, or pass "
              "--allow-partial to emit a clearly-labelled interim draft.")
        return 2

    interim = not have_kgs
    commit = _commit()
    today = date.today().isoformat()

    crit_count = total_pass >= G1_TARGET
    crit_cont = len(continents) >= 2
    lic = Path("docs/LICENSE_MATRIX.md")
    crit_lic = lic.exists()

    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    shipped = "\n".join(
        f"- {r['label']}: {r['wells']} wells harmonized and QC'd, records at "
        f"`{r['records_path']}`."
        for r in rows
    )
    shipped += (
        f"\n- Combined G1 dashboard: `reports/qc_combined/index.html` "
        f"(from scripts/combine_qc.py).\n"
        f"- Repo state at commit `{commit}`."
    )

    metrics = "\n".join(
        f"- {r['label']}: wells={r['wells']}, QC-passing (min-interval)="
        f"{r['qc_passing']}, unreadable={r['unreadable']}, unmapped rows="
        f"{r['unmapped']}. Backing: `{r['records_path']}`."
        for r in rows
    )
    metrics += (
        f"\n- TOTAL: wells={total_wells}, QC-passing={total_pass}, "
        f"continents={len(continents)} ({', '.join(sorted(continents))}). "
        f"Backing: the per-source CSVs above and `scripts/combine_qc.py` stdout."
    )

    criteria = (
        f"- {mark(crit_count)}: 5,000+ QC-passing wells (8,000 stretch). "
        f"Actual QC-passing = {total_pass}. Evidence: per-source records CSVs.\n"
        f"- {mark(crit_cont)}: two or more continents. Actual = "
        f"{len(continents)} ({', '.join(sorted(continents))}). Evidence: source map.\n"
        f"- {mark(crit_lic)}: license matrix complete. "
        f"Committed at `docs/LICENSE_MATRIX.md` (FORCE redistributable; NLOG and "
        f"KGS raw-redistribution unclear; release posture is pipeline plus weights "
        f"plus attribution, no raw mirror, which is safe for all three)."
    )

    gate_state = "MET" if (crit_count and crit_cont and crit_lic) else "NOT MET"

    header = "# Gate G1 milestone report"
    if interim:
        header += " (INTERIM DRAFT, FORCE-only, KGS pending)"

    doc = f"""{header}

## Gate and date
Gate G1 (target end of week 2). Date: {today}. Repo commit: `{commit}`.
Overall: {gate_state}.

## Shipped
{shipped}

## Metrics
{metrics}

## Gate criteria check
{criteria}

## Deviations from the handoff
{_deviations_section()}

## Blockers and escalations
{_blockers_section(rows, continents)}

## Spend
{_spend_section()}

## Pending inputs needed from Ammar
{_pending_inputs()}

## Next period plan
G2 (weeks 3 to 4): dedup finalization across sources; carbonate gate built and
validated on FORCE lithofacies labels; Athy trend fits per basin group; tokenizer
level sweep against the numeric bar; dataset card with real counts; test manifest
frozen and hashed; benchmark name collision-checked and decided. Model size set by
the HANDOFF Section 7.2 rule at G2.
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")

    print(f"Wrote {out_path}  (gate: {gate_state}"
          f"{', INTERIM/FORCE-only' if interim else ''})")
    print(f"  QC-passing total: {total_pass}  continents: {len(continents)}")
    print("  REMINDER: confirm Spend, Deviations, and Blockers sections before "
          "this goes to the advisor. Then stop for the GATE APPROVED note.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the Gate G1 milestone report.")
    ap.add_argument("--out", default="reports/status_g1.md")
    ap.add_argument("--allow-partial", action="store_true",
                    help="Emit a labelled interim draft even if KGS is missing.")
    args = ap.parse_args()
    raise SystemExit(build_report(Path(args.out), args.allow_partial))


if __name__ == "__main__":
    main()
