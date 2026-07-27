# Item X: closing L and M for the record (2026-07-26)

10-minute timebox. Neither finding changes the arm set. Arm A0 is not reopened.

## L: closed permanently

`git ls-remote --heads --tags https://github.com/Ammar12Falah/LithoGPT.git`
(against the remote directly, not the local clone) returns exactly one ref:

```
d0a86f00bfeb2c725572e41b2cfa179becbd4a19  refs/heads/main
```

No other branches, no tags exist on the remote. The concern that the earlier
`--unshallow` fetch (item L, second pass) might have been `--single-branch`-limited
and missed other branches is resolved: there was nothing else to miss. The local
branch enumeration (`git branch -a`) was already complete. **L is closed.**

## M: upgraded from "corrupt, cause unknown" to a precise, innocent explanation

`lithogpt_pure.pth` is a zip archive (as `torch.save` always produces). Scanning
the raw bytes for `PK\x03\x04` local-file-header signatures finds **43 entries**,
including recoverable filenames consistent with a genuine PyTorch checkpoint's
internal zip layout: `lithogpt_pure/data.pkl`, `.format_version`,
`.storage_alignment`, `byteorder`, and numbered tensor storage blobs
`data/0` through at least `data/15`. This is not placeholder junk or deliberate
corruption -- it is the real internal structure of a `torch.save` output,
consistent with the file having been a genuinely valid checkpoint at some point.

**Size check confirms truncation, not corruption:** this experiment's own
code-verified parameter count (item N) is 5,383,144. An fp32 checkpoint of that
many parameters is 5,383,144 x 4 bytes = 21,532,576 bytes (~21.5 MB). The actual
file is exactly 4,194,304 bytes (4 MiB) -- **19.5% of the expected size**, i.e.
"roughly the first fifth," matching the brief's estimate almost exactly. A zip
archive's central directory sits at the END of the file; a file truncated at a
fixed byte ceiling (4 MiB is a suspiciously round number, consistent with an
upload size limit) would cut off before the central directory every time,
producing exactly the observed error: `PytorchStreamReader failed reading zip
archive: failed finding central directory`.

**This does not restore Arm A0.** A checkpoint missing ~80% of its tensor data
(and its entire central directory, which a zip reader needs to know where each
entry's data ends) cannot be reconstructed into a loadable model, and no attempt
was made to do so. What changes is the finding's precision: the checkpoint was
very likely truncated by an upload-size limit, not deliberately corrupted or
uploaded as a non-functional placeholder. This is the fairer statement to
publish in item Q's finding, and item Q's doc is updated accordingly.

Arm A0 remains not reopened. The arm set for the sealed run is A, B-linear,
B-abs, B2, C, D.
