# Item M: checkpoint forensics -- hex/base64 hypothesis (2026-07-26)

10-minute hard timebox. Leading hypothesis stated in the brief: the 4,194,304-byte
`lithogpt_pure.pth` is hex-encoded or base64-encoded text, not corrupt binary,
based on the file size being exactly 2 MiB of hex or 3 MiB of base64.

## The leading hypothesis is refuted, quickly, without needing the decode attempts

```
distinct byte values: 256
min,max byte: 0 255
all bytes in hex alphabet: False
all bytes in base64 alphabet: False
```

A hex-encoded file can only ever contain 16 distinct byte values (`0-9a-fA-F`); a
base64-encoded file can only contain 64 (plus `=` padding). This file contains
**all 256 possible byte values**, spanning the full 0-255 range. This alone rules
out both encodings -- the byte-frequency-bracket argument in the brief (~262,144
occurrences per hex symbol bracketing the reported 150k-416k range) does not
survive the more basic check of how many distinct symbols appear at all.

## Decode attempts confirm the refutation

- `xxd -r -p` on the raw file "succeeds" (hex decoding is permissive of
  non-hex-alphabet input in some implementations) but produces a byte stream that
  still fails to unpickle: `UnpicklingError('unpickling stack underflow')`.
- `base64 -d` similarly "succeeds" at the shell level but produces
  `UnpicklingError("invalid load key, '<'.")`.
- `gzip -t` on both candidates: `not in gzip format`.
- `torch.load` on the original file: unchanged
  `RuntimeError: PytorchStreamReader failed reading zip archive: failed finding
  central directory` (same failure reported in item B).

## Git-history check (folded in from item L's unshallow fetch)

The checkpoint blob (`sha256=907337c5...`) is byte-identical across all 3 commits
in v1's full history, present unchanged since the very first upload commit
(`093114a`). `torch.load` on that oldest-commit copy fails identically. The
corruption (or invalidity) is original to the file as first committed, not
introduced later.

## Conclusion

The checkpoint is not hex- or base64-encoded text. It is either genuinely
corrupted binary or was never a valid PyTorch checkpoint to begin with; this
experiment cannot distinguish those two explanations from the file alone, and
does not attempt to reconstruct or fabricate a working checkpoint from it.

## M outcome, per the pre-registered ruling

"If it does not load, reimplementation stands and item J's manuscript statement
applies, as narrowed by item S." The checkpoint does not load under any tested
hypothesis. **No Arm A0 is added.** Arm A remains a transformer reimplemented
from the paper's specification, trained on v1's authentic tokenizer/scaler
(item S), not v1's original weights.
