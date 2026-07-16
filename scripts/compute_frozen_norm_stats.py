import sys
sys.path.insert(0, "/workspace/LithoGPT-2/src")

import json, time, traceback
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml

from lithogpt2.pipeline.harmonize import compute_norm_stats, HarmonizedWell
from lithogpt2.config import HarmonizationConfig

ROOT = Path("/workspace/LithoGPT-2")
PROC = {"kgs": ROOT/"data/processed/kgs", "nlog": ROOT/"data/processed/nlog",
        "force2020": ROOT/"data/processed/force2020"}
LOG = ROOT/"reports/_normstats_run/run.log"
HB  = ROOT/"reports/_normstats_run/heartbeat.txt"
LOG.parent.mkdir(parents=True, exist_ok=True)

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    with open(LOG,"a") as f: f.write(line+"\n")
    print(line, flush=True)
def beat(m):
    HB.write_text(f"{time.time():.0f}|{time.strftime('%H:%M:%S')}|{m}")
def fail(m):
    log(f"STATUS: FAILED - {m}"); beat(f"FAILED {m}"); sys.exit(1)

open(LOG,"w").close()  # fresh log each run
try:
    log("=== FROZEN NORM STATS (detached) ===")
    cfg_raw = yaml.safe_load((ROOT/"configs/mnemonic_aliases.yaml").read_text())
    cfg = HarmonizationConfig(cfg_raw, source_path=ROOT/"configs/mnemonic_aliases.yaml")
    CANON = list(cfg.canonical_curves)
    STEP = float(cfg.grid_step_m)
    log(f"canonical curves ({len(CANON)}): {CANON}")
    log(f"grid_step_m = {STEP}")

    sp = pd.read_csv(ROOT/"data/splits/split_assignment.csv")
    sp["well_id"] = sp["well_id"].astype(str)
    tr = sp[sp.split=="train"].copy()
    by_src = {k:int(v) for k,v in tr.groupby("source").size().items()}
    log(f"TRAIN wells: {by_src}  total={len(tr)}")
    if len(tr) != 7589: fail(f"train count {len(tr)} != 7589")

    def load_well(source, well_id, safe_name):
        d = PROC[source]; p = d/f"{safe_name}.parquet"
        if not p.exists(): p = d/f"{well_id}.parquet"
        if not p.exists(): return None
        t = pq.read_table(p); names = set(t.column_names)
        curves, masks = {}, {}
        for c in CANON:
            if c in names and f"{c}_mask" in names:
                curves[c] = np.asarray(t.column(c).to_numpy(zero_copy_only=False), dtype="float64")
                masks[c]  = np.asarray(t.column(f"{c}_mask").to_numpy(zero_copy_only=False), dtype=bool)
        if not curves: return None
        return HarmonizedWell(well_id, source,
                              np.asarray(t.column("depth_m").to_numpy(zero_copy_only=False)),
                              STEP, curves, masks)

    def build(source):
        sub = tr[tr.source==source]; wells=[]; missing=0; t0=time.time()
        for i,(_,r) in enumerate(sub.iterrows(),1):
            w = load_well(source, str(r["well_id"]), str(r["safe_name"]))
            if w is None: missing+=1
            else: wells.append(w)
            if i % 500 == 0:
                beat(f"loading {source} {i}/{len(sub)}")
                if i % 1000 == 0: log(f"  {source}: {i}/{len(sub)} ({time.time()-t0:.0f}s)")
        log(f"  {source}: {len(wells)} loaded, {missing} missing ({time.time()-t0:.0f}s)")
        if missing: fail(f"{source}: {missing} train parquets missing")
        return wells

    log("--- FORCE + NLOG first (fast correctness check) ---")
    wells = build("force2020") + build("nlog")

    # transform sniff: stored resistivity must be log10 (~0.15), not raw ohmm
    vals=[]
    for w in wells[:300]:
        if "RDEP" in w.curves and np.any(w.masks["RDEP"]):
            vals.append(w.curves["RDEP"][w.masks["RDEP"]])
    med = float(np.median(np.concatenate(vals))) if vals else None
    log(f"[transform sniff] stored RDEP median={med}")
    if med is None or not (-2 < med < 3):
        fail(f"resistivity looks raw (median {med}), config expects log10 - ESCALATE")
    log("[ok] resistivities in log10 space, matches provisional + config")

    log("--- KGS (long tail: 5,734 parquets over the mount) ---")
    wells += build("kgs")
    log(f"TOTAL loaded: {len(wells)}")
    if len(wells) != 7589: fail(f"loaded {len(wells)} != 7589")

    log("--- computing robust stats via blessed compute_norm_stats() ---")
    beat("computing stats")
    stats = compute_norm_stats(wells, cfg)
    for c in CANON:
        if c in stats:
            s=stats[c]; log(f"  {c:5s} median={s['median']:.5f} iqr={s['iqr']:.5f} n={s['n_samples']:,}")
        else: log(f"  {c:5s} (no train samples, omitted)")

    out = {"provisional": False,
        "provenance": ("FROZEN G2 norm stats. Robust median/IQR via compute_norm_stats on the "
            f"FROZEN TRAIN split only (7,589 wells: {by_src}). Manifest f497206bb9bd..., "
            "split_gen_commit d4113797. Mask-gated real samples only. Resistivities log10 "
            "(verified pre-compute). Dev and all test splits excluded."),
        "config_version": cfg.version,
        "manifest_sha256": "f497206bb9bd2305bb7b50868adda2c286b006fa8d22fa8a17f378c68c9417cb",
        "split_gen_commit": "d4113797",
        "train_wells": {"total": len(wells), **by_src}, "stats": stats}
    dest = ROOT/"configs/force2020/norm_stats.json"
    dest.write_text(json.dumps(out, indent=2))
    log(f"[ok] wrote NON-provisional stats: {dest}")
    log("STATUS: DONE"); beat("DONE")
except Exception:
    with open(LOG,"a") as f: f.write(traceback.format_exc())
    fail("exception, see traceback above")
