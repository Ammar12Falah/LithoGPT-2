from pathlib import Path
import re
ROOT = Path("/workspace/LithoGPT-2")
p = ROOT / "reports/stageA_split_inputs.md"
txt = p.read_text()
print(f"=== {p.name} ({len(txt)} chars) ===")
print(txt)
names = sorted(set(re.findall(r"\b\d{2}/\d{1,2}-\d+\s*[A-Z]?\b", txt)))
print(f"\n=== FORCE-style well names found: {len(names)} ===")
print(names)
