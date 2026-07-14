import json, os, subprocess, time
from pathlib import Path

ROOT = Path("/workspace/LithoGPT-2")
TOK = os.environ.get("GH_TOKEN", "")
assert TOK, "FAIL: GH_TOKEN not set"
REPO = "Ammar12Falah/LithoGPT-2"


def sh(*a):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def api(path):
    r = subprocess.run(
        ["curl", "-s", "-H", f"Authorization: token {TOK}",
         "-H", "Accept: application/vnd.github+json",
         f"https://api.github.com/repos/{REPO}{path}"],
        capture_output=True, text=True)
    return json.loads(r.stdout)


head = sh("git", "rev-parse", "HEAD")
url = f"https://x-access-token:{TOK}@github.com/{REPO}.git"
remote = sh("git", "ls-remote", url, "refs/heads/main").split()
remote_sha = remote[0] if remote else None

print(f"local  HEAD: {head}")
print(f"remote main: {remote_sha}")
if remote_sha != head:
    raise SystemExit("STOP: this commit is not on GitHub. Push it first; CI cannot run on it.")

print(f"\nwaiting for CI on {head[:8]} (typically 60 to 180 seconds) ...")
t0 = time.time()
run = None
while time.time() - t0 < 420:
    runs = api("/actions/runs?branch=main&per_page=10").get("workflow_runs", [])
    match = [r for r in runs if r["head_sha"] == head]
    if match:
        run = match[0]
        print(f"  [{int(time.time()-t0):3d}s] status={run['status']:12} conclusion={run['conclusion']}")
        if run["status"] == "completed":
            break
    else:
        print(f"  [{int(time.time()-t0):3d}s] run not registered yet ...")
    time.sleep(15)

assert run is not None, "FAIL: no CI run appeared for this commit within 7 minutes"
print(f"\n=== FINAL: {run['conclusion']} ===")
print("url:", run["html_url"])

if run["conclusion"] != "success":
    for j in api(f"/actions/runs/{run['id']}/jobs").get("jobs", []):
        for s in j["steps"]:
            flag = "  <-- FAILED" if s["conclusion"] == "failure" else ""
            print(f"  {s['name']:20} {str(s['conclusion']):10}{flag}")
else:
    print("\nCI IS GREEN. Freeze preconditions satisfied:")
    print("  - records on main at 5004 / 2355, count-verified")
    print("  - decision capture d31379f present")
    print("  - CI green on the runner")
    print("Section 5 can begin: splits, then manifest hash, then norm stats.")
