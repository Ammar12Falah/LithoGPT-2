# Item L: v1 source recovery, second pass -- git history/refs (2026-07-26)

20-minute hard timebox. The first pass (item B, prior brief) inspected only the
working tree of the read-only clone at `/workspace/v1_readonly/LithoGPT`. This
pass checks history and refs before accepting reimplementation, per instruction.

## Finding 0: the clone was shallow

`git rev-parse --is-shallow-repository` -> `true`. `.git/shallow` contained a
single sha (`d0a86f00...`), meaning the original clone (item B) only ever saw
ONE commit and could not have found deleted files or earlier revisions even if
they existed. This was corrected via `git fetch --unshallow origin` (read-only,
no push, outside the main repo, per standing instruction) before running any of
the checks below.

## Full history (post-unshallow): 3 commits, not 1

```
093114a  Add files via upload      (oldest -- initial content commit)
a7cdd1c  Update README.md
d0a86f0  Update README.md          (HEAD, origin/main)
```

No other branches (`git branch -a`: only `main`/`origin/main`/`origin/HEAD`), no
tags (`git tag`: empty).

## File listing is IDENTICAL across all 3 commits

`git ls-tree -r --name-only <commit>` for all three commits returns the same 10
files: `README.md`, 3 PNGs under `assets/`, `baselines/__init__.py`,
`lithogpt/__init__.py`, `requirements.txt`, and the 3 checkpoint files
(`kmeans_pure.joblib`, `lithogpt_pure.pth`, `scaler_pure.joblib`). `git diff --stat`
between consecutive commits shows only `README.md` changing (28 insertions/11
deletions, then 1 deletion) -- never any other file.

## Deleted files across all history: none

`git log --all --diff-filter=D --name-only` returns empty. Nothing was ever
removed from this repo at any point in its history.

## Every .py/.ipynb blob that ever existed, across all commits: 2

`git rev-list --all --objects | grep -iE '\.py$|\.ipynb$'` returns exactly:
`baselines/__init__.py` and `lithogpt/__init__.py` -- the same two stub
placeholders found in the working tree by item B. No other Python source file,
notebook, or script has ever been committed to this repository.

## The checkpoint blob is unchanged since the very first commit

`git rev-list --all --objects | grep -iE '\.pth$'` shows exactly one blob sha
(`1ad318aa5fc9f5a4a0700c49c435c2a5b8da7ee8`) for `checkpoints/lithogpt_pure.pth`,
present identically in all three commits. Extracting it from the oldest commit
(`git show 093114a:checkpoints/lithogpt_pure.pth`) and hashing it
(sha256=`907337c50a0beb6e95da08484e30ee95c6103022f3e747067a7ba5fce41d6224`) then
attempting `torch.load` reproduces the exact same failure as the working-tree
copy: `RuntimeError: PytorchStreamReader failed reading zip archive: failed
finding central directory`. The checkpoint was corrupted (or never valid) at the
moment of its original upload, not corrupted later by a git operation, LFS
misconfiguration, or a subsequent commit.

## `git lfs` / `.gitattributes`

`git lfs ls-files` fails (`git: 'lfs' is not a git command` -- lfs not installed
in this environment). `.gitattributes` does not exist. No LFS pointer files are
present in the tree listings above (the checkpoint blob is the raw 4,194,304-byte
content itself, not an LFS pointer stub), so the absence of `git-lfs` tooling
does not hide anything relevant here.

## Conclusion

v1's public repository **never contained real model/training/eval source code
at any point in its history**, and its checkpoint was corrupted from the moment
it was first committed. This is a stronger, more precise version of item B's
working-tree-only finding: it rules out the possibility that source code was
deleted later, or that an earlier, valid checkpoint was overwritten. Item J's
Arm A remains a reimplementation from the paper's specification (narrowed per
item S to using v1's authentic tokenizer/scaler, which are the only genuinely
usable artifacts in the repo).

Nothing was pushed to the v1 repo. The unshallow fetch is a read-only history
inspection performed against the local clone under `/workspace/v1_readonly/`,
outside `/workspace/LithoGPT-2`.
