import json
from pathlib import Path

ROOT = Path("/workspace/LithoGPT-2")
ORPH = ["Q08-A-03","Q08-B-01","WYK-13","WYK-16","WYK-17-S1","WYK-34","WYK-35","WYK-36"]

print("=== A. .github/workflows/ci.yml ===")
print((ROOT / ".github/workflows/ci.yml").read_text())

print("\n=== B. RUFF / PYTEST CONFIG IN pyproject.toml ===")
pp = (ROOT / "pyproject.toml").read_text()
for line in pp.split("\n"):
    print("   ", line)

print("\n=== C. THE SCRATCH NOTEBOOKS: DID THEY WRITE THE ORPHANS? ===")
for nb_name in ["Untitled.ipynb", "Untitled1.ipynb"]:
    p = ROOT / "reports/alias_audit" / nb_name
    if not p.exists():
        print(f"  {nb_name}: MISSING")
        continue
    nb = json.loads(p.read_text())
    cells = nb.get("cells", [])
    print(f"\n--- {nb_name}: {len(cells)} cells")
    src_all = "\n".join("".join(c.get("source", [])) for c in cells)
    hits = [o for o in ORPH if o in src_all]
    print(f"    orphan well ids referenced in source: {hits or 'NONE'}")
    print(f"    mentions 'to_parquet': {'to_parquet' in src_all}")
    print(f"    mentions 'processed/nlog': {'processed/nlog' in src_all}")
    print("    --- source (first 60 lines) ---")
    for line in src_all.split("\n")[:60]:
        print("      ", line)
