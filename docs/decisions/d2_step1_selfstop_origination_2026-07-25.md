# D2 Step 1 — self-stop capability, originated record (Pod, 2026-07-25)

This is an ORIGINATION, not a correction of a committed record. No prior committed artifact stated
anything about self-stop or `runpodctl` (checked: `grep -rl "self-stop\|runpodctl" docs/ reports/`
returns nothing before this commit). The only prior statement existed in chat instructions from an
earlier session and was never written to this repository. Per instruction, that uncommitted prior
statement is not characterized or quoted here beyond noting that it existed and was never committed.

## Verified facts, as of this session (2026-07-25)

- `runpodctl` is authenticated **on Ammar's Mac only**. Binary at `/Users/ammar/runpodctl` (not on
  `$PATH`), API key at `~/.runpod/config.toml` (`apikey`, `apiurl = https://api.runpod.io/graphql`).
- Self-stop (`runpodctl stop pod <id>` / `runpodctl pod stop <id>`) works when run **from the Mac**,
  outside the pod, over the RunPod control-plane API. It was run this way and verified: `runpodctl
  pod list` showed `STATUS EXITED` immediately after.
- No `runpodctl` binary or RunPod API key was ever placed on the pod itself. The pod's own
  filesystem was never touched for this purpose; all pod interaction for training/git work goes
  over SSH (`lithopod_key`), which is a separate credential from the RunPod control-plane key.
- Self-stop is therefore NOT available from inside a pod session (no local `runpodctl`, no key), and
  IS available from the Mac session that has this repo's working context.

This record exists so that "is self-stop available" has one committed answer going forward instead
of being re-derived or mis-stated per session.
