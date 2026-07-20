import sys, os
sys.path.insert(0, "/workspace/LithoGPT-2/src")

import json, hashlib, subprocess, datetime
from pathlib import Path
import pandas as pd

CANONICAL = Path("/workspace/LithoGPT-2")
# ROOT is redirectable so this committed builder can regenerate the freeze without
# a hand-edited copy (no orphan producer). It REFUSES to write into the canonical
# tree, enforcing "never overwrite frozen files" in code (standing rule).
ROOT = Path(os.environ.get("MANIFEST_ROOT", str(CANONICAL))).resolve()
SEED = 20260715
EXPECT = {
    "total": 8809,
    "counts": {
        ("kgs","train"):5734, ("kgs","dev"):339, ("kgs","test_kgs"):263,
        ("nlog","train"):1757, ("nlog","dev"):257, ("nlog","test_nlog"):341,
        ("force2020","train"):98, ("force2020","test_force_open"):10, ("force2020","blind_force"):10,
    },
    "kgs_redundant_copies": 395, "kgs_cross_well_groups": 9,
    "commit_prefix": "d4113797", "alias_prefix": "e888ac7", "crosswalk_prefix": "3b074650",
    "vintage_prefix": "60fbb409",
}

# The 24-file QC set pinned as qc_code_sha256: sha256 over the raw bytes of these files
# concatenated in C-locale (byte-lexicographic) sorted path order, no separators.
# Python's default str sort is code-point order == C-locale for these ASCII paths.
# NOTE: qc_code_sha256 is intentionally NOT prefix-guarded -- it is designed to change
# when a hashed file (e.g. requirements.txt / pyproject.toml) changes.
QC_FILES = sorted([
    "configs/mnemonic_aliases.yaml",
    "pyproject.toml",
    "requirements.txt",
    "scripts/combine_qc.py",
    "scripts/ingest_qc_nlog_batched.py",
    "scripts/run_qc_force.py",
    "scripts/run_qc_kgs.py",
    "scripts/run_qc_nlog.py",
    "src/lithogpt2/config.py",
    "src/lithogpt2/ingest/__init__.py",
    "src/lithogpt2/ingest/_http.py",
    "src/lithogpt2/ingest/force2020.py",
    "src/lithogpt2/ingest/kgs.py",
    "src/lithogpt2/ingest/las_dir.py",
    "src/lithogpt2/ingest/nlog.py",
    "src/lithogpt2/ingest/well_dir.py",
    "src/lithogpt2/io/__init__.py",
    "src/lithogpt2/io/dlis.py",
    "src/lithogpt2/io/las.py",
    "src/lithogpt2/pipeline/__init__.py",
    "src/lithogpt2/pipeline/batch.py",
    "src/lithogpt2/pipeline/harmonize.py",
    "src/lithogpt2/pipeline/incremental.py",
    "src/lithogpt2/pipeline/qc.py",
])

def die(m): raise SystemExit(f"\n*** STOP: {m} ***")
def sha_file(p):
    p = Path(p)
    if not p.exists(): die(f"pin file missing: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()

def qc_code_sha(root):
    if len(QC_FILES) != 24: die(f"QC set size {len(QC_FILES)} != 24")
    h = hashlib.sha256()
    for rel in QC_FILES:
        p = root/rel
        if not p.exists(): die(f"QC pin file missing: {p}")
        h.update(p.read_bytes())
    return h.hexdigest()

print("="*70); print("BUILD MANIFEST (RECONSTRUCTED, seven-pin)  |  CSV-only, ~10-30s"); print("="*70)

# safety: never write into the frozen canonical tree
if ROOT == CANONICAL.resolve():
    die("ROOT is the canonical repo. Set MANIFEST_ROOT to a redirect dir; refusing to overwrite frozen files.")

# 0. HEAD must be the split-gen commit (override hard-sets the recorded field; NO checkout)
head = os.environ.get("MANIFEST_HEAD")
if not head:
    head = subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],
                          capture_output=True, text=True).stdout.strip()
if not head.startswith(EXPECT["commit_prefix"]):
    die(f"head {head[:12]} != split-gen commit {EXPECT['commit_prefix']}")
print(f"[ok] split_gen_commit {head[:12]}")

# 1. load FROZEN splits (never regenerate)
sp_path = ROOT/"data/splits/split_assignment.csv"
if not sp_path.exists(): die(f"frozen splits missing: {sp_path}")
sp = pd.read_csv(sp_path); sp["well_id"] = sp["well_id"].astype(str)
print(f"[ok] frozen splits: {sp_path}  rows={len(sp)}")
if len(sp) != EXPECT["total"]: die(f"row count {len(sp)} != {EXPECT['total']}")
got = sp.groupby(["source","split"]).size()
for k,v in EXPECT["counts"].items():
    if int(got.get(k,0)) != v: die(f"count {k}={int(got.get(k,0))} != {v}")
print("[ok] all 9 source/split counts match frozen expectation")

# 2. pins
alias_sha   = sha_file(ROOT/"configs/mnemonic_aliases.yaml")
cw_sha      = sha_file(ROOT/"data/splits/kgs_coord_crosswalk.csv")
force_sha   = sha_file(ROOT/"configs/force2020/pinned.json")
vintage_sha = sha_file(ROOT/"data/splits/kgs_vintage_crosswalk.csv")
qc_sha      = qc_code_sha(ROOT)
if not alias_sha.startswith(EXPECT["alias_prefix"]): die(f"alias sha {alias_sha[:8]}")
if not cw_sha.startswith(EXPECT["crosswalk_prefix"]): die(f"crosswalk sha {cw_sha[:8]}")
if not vintage_sha.startswith(EXPECT["vintage_prefix"]): die(f"vintage sha {vintage_sha[:8]}")
print(f"[ok] alias {alias_sha[:12]}  crosswalk {cw_sha[:12]}  force_pinned {force_sha[:12]}")
print(f"[ok] vintage {vintage_sha[:12]}  qc_code {qc_sha[:12]}")

# 3. passing loaders + dup_group from dedup_hash (all sources, reversible)
def passing(src, rel):
    d = pd.read_csv(ROOT/rel); d["well_id"] = d["well_id"].astype(str)
    d = d[d["min_interval_pass"].astype(bool)].copy(); d["source"] = src
    return d
kgs, nlog, force = (passing("kgs","reports/kgs_qc_records.csv"),
                    passing("nlog","reports/nlog_qc_records.csv"),
                    passing("force2020","reports/force2020_qc_records.csv"))
def dup_map(d, src):
    dd = d[d["dedup_hash"].notna()].copy()
    dd = dd[dd.groupby("dedup_hash")["well_id"].transform("size") > 1]
    dd["dg"] = src + ":" + dd["dedup_hash"].str.slice(0,16)
    return {(src, str(w)): g for w,g in zip(dd["well_id"], dd["dg"])}
dgm = {}; [dgm.update(dup_map(d,s)) for d,s in [(kgs,"kgs"),(nlog,"nlog"),(force,"force2020")]]
print(f"[ok] dup_group members: {len(dgm)}")

# 4. KGS self-checks: 395 redundant, 9 cross-well
cw = pd.read_csv(ROOT/"data/splits/kgs_coord_crosswalk.csv")
cw["well_id"] = cw["well_id"].astype(str); cw["well_kgs_id"] = cw["well_kgs_id"].astype(str)
km = kgs.merge(cw[["well_id","well_kgs_id"]], on="well_id", how="left")
kd = km[km["dedup_hash"].notna()]
sizes = kd.groupby("dedup_hash").size(); dupg = sizes[sizes>1]
redundant = int(dupg.sum() - len(dupg))
print(f"[--] KGS redundant copies: {redundant} (expect {EXPECT['kgs_redundant_copies']})")
if redundant != EXPECT["kgs_redundant_copies"]: die(f"redundant {redundant} - dup drift, reconcile vs advisor 395")
cross = kd.groupby("dedup_hash")["well_kgs_id"].nunique(); cross = cross[cross>1]
print(f"[--] KGS cross-well groups: {len(cross)} (expect {EXPECT['kgs_cross_well_groups']})")
if len(cross) != EXPECT["kgs_cross_well_groups"]: die(f"cross-well {len(cross)} != 9")

# 5. straddle: cross-well groups must sit one side of train/holdout
smap = dict(zip(sp["well_id"], sp["split"])); straddle = []
for dh in cross.index:
    members = km[km["dedup_hash"]==dh]["well_id"].tolist()
    hits = {smap.get(w,"MISSING") for w in members}
    holdout_hits = {s for s in hits if s.startswith("test") or s=="dev"}
    if holdout_hits and "train" in hits:
        straddle.append((dh, {w:smap.get(w) for w in members}))
if straddle:
    for dh,mm in straddle: print("   STRADDLE", dh[:16], mm)
    die(f"{len(straddle)} cross-well group(s) straddle train/holdout - SILENT LEAKAGE")
print(f"[ok] no straddle across all {len(cross)} cross-well groups")

# 6. cross-source collision
allq = pd.concat([kgs[["well_id","source","dedup_hash"]], nlog[["well_id","source","dedup_hash"]],
                  force[["well_id","source","dedup_hash"]]], ignore_index=True)
if not (allq.dropna(subset=["dedup_hash"]).groupby("dedup_hash")["source"].nunique() <= 1).all():
    die("cross-source dedup_hash collision")
print("[ok] zero cross-source collisions")

# 7. assemble rows from FROZEN splits + dup_group; hash canonical payload
def mkrow(r):
    return {"well_id": str(r["well_id"]), "source": r["source"], "split": r["split"],
            "lat": None if pd.isna(r["lat"]) else round(float(r["lat"]),6),
            "lon": None if pd.isna(r["lon"]) else round(float(r["lon"]),6),
            "safe_name": str(r["safe_name"]),
            "dup_group": dgm.get((r["source"], str(r["well_id"])))}
rows = [mkrow(r) for _,r in sp.sort_values(["source","well_id"]).iterrows()]
if len(rows) != EXPECT["total"]: die("row assembly drift")
payload = {
    "schema": "lithogpt2.corpus_manifest.v1",
    "pins": {"split_gen_commit": head, "seed": SEED, "alias_yaml_sha256": alias_sha,
             "kgs_coord_crosswalk_sha256": cw_sha, "force_pinned_sha256": force_sha,
             "kgs_vintage_crosswalk_sha256": vintage_sha, "qc_code_sha256": qc_sha},
    "counts": {f"{s}/{sp_}": int(got[(s,sp_)]) for (s,sp_) in EXPECT["counts"]},
    "dedup_summary": {"kgs_redundant_copies": redundant, "kgs_cross_well_groups": int(len(cross)),
                      "dup_group_members_total": len(dgm)},
    "row_count": len(rows), "rows": rows,
}
canonical = json.dumps(payload, sort_keys=True, separators=(",",":"),
                       ensure_ascii=False, allow_nan=False).encode("utf-8")
manifest_sha = hashlib.sha256(canonical).hexdigest()
out = ROOT/"data/splits"
out.mkdir(parents=True, exist_ok=True)
(out/"corpus_manifest.json").write_bytes(canonical)
(out/"corpus_manifest.sha256").write_text(f"{manifest_sha}  corpus_manifest.json\n")
(out/"corpus_manifest_pretty.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))
(out/"corpus_manifest.meta.json").write_text(json.dumps({
    "generated_utc": datetime.datetime.utcnow().isoformat()+"Z",
    "provenance": "RECONSTRUCTED seven-pin builder; regenerable from committed code (MANIFEST_ROOT/MANIFEST_HEAD).",
    "reconstructed_from": ["build_splits.py","dupes_and_vintage.py","pre_hash_forensics.py",
                           "docs/G2_freeze_plan.md","docs/HANDOFF.md","HANDOFF_CONTINUING_AGENT"],
    "establishing_run": "Regenerates the committed corpus_manifest byte-identically; pins computed from source files.",
    "qc_code_pin_note": ("qc_code_sha256 = sha256 over the 24 QC files (C-locale sorted, concatenated, "
                         "no separators); see data/splits/qc_pin_manifest.txt for the file list and method."),
    "hashed_payload": "corpus_manifest.json (sort_keys, compact, allow_nan=False)",
    "not_in_hash": "meta file, pretty copy, timestamp",
    "lineage": "SET BY FREEZE-AMEND STEP (curated); see qc_pin_manifest.txt / commit message.",
}, indent=2))
print("\n"+"="*70); print("HEADER PINS (verify against handoff)"); print("="*70)
print(f"  split_gen_commit : {head[:8]}   (expect d4113797)")
print(f"  seed             : {SEED}   (expect 20260715)")
print(f"  alias_yaml_sha256: {alias_sha[:7]}   (expect e888ac7)")
print(f"  crosswalk_sha256 : {cw_sha[:8]}   (expect 3b074650)")
print(f"  vintage_sha256   : {vintage_sha[:8]}   (expect 60fbb409)")
print(f"  qc_code_sha256   : {qc_sha[:8]}   (current tree: expect 4221fa54)")
print(f"  force_pinned_sha : {force_sha[:8]}   (additive provenance pin)")
print(f"\nSELF-CHECKS: rows={len(rows)}, KGS redundant={redundant}, cross-well groups={len(cross)}, no straddle")
print("\n"+"#"*70); print(f"#  MANIFEST SHA256 (THE FREEZE):\n#  {manifest_sha}"); print("#"*70)
print(f"\nWrote corpus_manifest .json/.sha256/_pretty.json/.meta.json in {out}")
print("NOT pushed. Regenerable via MANIFEST_ROOT/MANIFEST_HEAD; never writes the canonical tree.")
