# Item Z: transport gotcha, added to the pod SSH gotchas list (2026-07-26)

## base64-through-PTY corruption (new this session)

Transferring `scripts/atce/atce_ablation.py` (~22 KB) from the pod to the local
machine via `base64` piped through the interactive `ssh -tt` PTY session
corrupted the payload **at both tested wrap widths**:

- `base64 -w0` (single unwrapped ~30,000-char line): decoded to garbage binary,
  not valid Python (`base64.b64decode` succeeded but produced non-source bytes).
- `base64` default wrapping (76-char lines): also decoded to garbage, though a
  different failure than -w0 -- still not valid Python.

**Root cause suspected but not confirmed:** long lines interacting with the
PTY's terminal-width soft-wrap / echo behavior under `set -x`. `fold -w 1500`
(mentioned as the documented workaround in an earlier handoff) was **not
tried** before abandoning base64 -- try this first next time before assuming
base64 is unusable over this connection.

`scp`/`sftp` are confirmed blocked on this pod's SSH proxy (`subsystem request
failed on channel 0` -- proxy is interactive-shell-only, no file-transfer
subsystem).

## What worked, and should be the default

**Plain-text `cat`/heredoc push, with MD5 verification.** For both reading
remote files back (`cat -n file.py` piped through `ssh -tt`, reconstructed
locally after stripping ANSI escape codes and the echoed command/banner lines)
and writing local files to the remote (`cat > remote_path << 'EOF' ... EOF`
heredoc, built by a local Python script that embeds the exact file content
between the heredoc markers), plain text survived the PTY round-trip
byte-for-byte. Verified repeatedly this session via `md5sum` on both ends
matching exactly (e.g. `atce_ablation_v2.py`: `7ae6d9910799bfafb2cd61f762e8a89e`
both sides; `atce_ablation_v3.py`: `b20266100fba88d4d59abc3edbfe4dc5` both sides).

**Recommendation for future sessions:** default to heredoc push + `md5sum`
verification for code transfer over this pod's PTY-only SSH proxy. Reserve
another base64 attempt for cases where heredoc's delimiter-collision risk is a
real concern (binary content, or text containing an `EOF`-like line already
checked for) -- and try `fold -w 1500` first if base64 seems necessary.

## Other standing PTY gotchas (reconfirmed this session)

- Every SSH command to this pod requires `-tt` (forced PTY); plain `ssh ...
  "command"` without it fails immediately with `Error: Your SSH client doesn't
  support PTY`.
- `ssh -tt ... "command; exit"` (command passed inline as a string) reliably
  hangs and must be killed locally; piping a script file via `ssh -tt ... <
  script.sh` reliably completes. Prefer the piped-script form always.
