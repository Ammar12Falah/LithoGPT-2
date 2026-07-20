# LithoGPT-2 — G2 Milestone Report
Status: freeze closed, evidence durable off-pod, HOLD for advisor GATE APPROVED. No model, tokenizer, or benchmark work has crossed the gate and none will until the advisor records GATE APPROVED.
Prepared for advisor review. Every figure traces to a committed artifact on `origin/main` or to a hash verified this session. Where a figure is unrecoverable, the report says so.
1. Freeze summary
The Stage-B corpus is frozen against manifest `d5b35a00` (`d5b35a00ffa49aab7f7e634013c238aa1fc989a17e3ad1c5a5d83f7606e3a8a9`).

* Regenerable from committed code. The manifest builder (`build_manifest.py` @ `212faed9`) reproduces `d5b35a00` by construction, ROOT-redirected with the recorded head field. This closed a real gap: the prior manifest was not regenerable from committed code (see §3, breach 1).
* Tamper-evident. `qc_code_sha256 = e12d4b64`, a hash over the 24 QC source files. The runtime-pin fold-in moved it from `4221fa54` by editing exactly two files (`requirements.txt`, `pyproject.toml`) and nothing else — the pin visibly did its job.
* Determinism-proven. `build_splits.py` @ `d4113797` (seed `20260715`) regenerates `split_assignment.csv` byte-identical; norm-stats reconfirmed byte-identical this session under fresh scipy/lasio/pyarrow. Two independent reproducibility results.
* Lineage: `f497206b → 88255b43 (pin-set completion) → d5b35a00 (runtime pin fold-in + dlisio declaration reconciliation)`. Splits unchanged throughout; `row_count` 8,809 and all nine split counts invariant.

Corpus: 8,789 QC-passing wells (KGS 6,336 / NLOG 2,355 / FORCE 98); manifest 8,809 (+20 FORCE open/blind). Spatial-block splits only. Full numbers in the dataset card.
2. Durability (Rule 5 satisfied)
For the first time, no evidence lives only on the pod. Two independent durable copies:

* GitHub: `origin/main` at `bfa3b1d`. Freeze chain `9168d83 → 212faed9 → 41e0e51`, extended by evidence/remediation commits `2272118 → 568c951 → ca11341 → a181af7 → ced8dd7 → 9c6b9fc → bfa3b1d`. Push via SSH deploy key; the previously-leaked token stays revoked.
* Off-pod tarball: `lithogpt2_G2_evidence_2026-07-20.tar.gz`, sha256 `a7244b3515…cea5e6cc`, downloaded to Ammar's machine and hash-verified byte-identical this session. 24 files, self-describing via an inner per-file `MANIFEST.txt` whose embedded hashes all cross-check against the recorded pins.

Both hashes (manifest `d5b35a00`, tarball `a7244b35`) are recorded off-pod. The freeze is closed by the project's own definition.
3. Process gaps found and fixed this session (stated honestly)
Two gaps were discovered mid-session and closed. Both are reported as deviations with cause, not smoothed over.
Breach 1 — orphaned manifest producer (no-orphan-producers rule). The `88255b43` pin-completion last session generated a committed manifest from code that was never committed (an ad-hoc JSON edit; the committed builder emitted only 5 of 7 pins and reproduced the superseded `f497206b`). This violated the no-orphan-producers rule, written after the first builder loss, in the first session after it was written. Remedy: a reconstructed 7-pin builder (`212faed9`) that regenerates `88255b43` byte-identical from the current tree and `d5b35a00` after the fold-in. The freeze is now regenerable from committed code. Caveat on the record: byte-identity proves the builder can regenerate the manifest, not that it is the same builder that originally produced it (the original was never saved) — same epistemic limit as the earlier manifest reconstruction, redeemed the same way.
Breach 2 — the Ruling 2 amendment was never committed. The taxonomy amendment ruled 2026-07-19 (borehole-vs-file partition axes) was never written to the decisions log. It has now been committed (`ced8dd7`), dated 07-19 in text with a landed-07-20 note; the git commit is today, not backdated.
Security gap — the ordered pre-commit secret scan never landed. After the token incident, a pre-commit secret scan was ordered; only a manual scrub script ever existed. A genuine pre-commit hook is now installed (`9c6b9fc`, `.githooks/pre-commit` via `core.hooksPath`), tested to actually block a staged token pattern (verified: it refused a commit containing a fake `ghp_` token, exit nonzero, HEAD unchanged). Honest caveats: it is a convenience guard, bypassable with `--no-verify`, and does nothing about the already-revoked token. It survives stop/start (config on the persistent volume) but a fresh clone must re-run `git config core.hooksPath .githooks`.
4. Dataset card: four corrections to the 07-19 review
The card is finalized (`docs/DATASET_CARD.md`, sha256 `6f938018…`, committed `bfa3b1d`). In finalizing it, four figures from the 07-19 review were corrected against committed data. Each is flagged in the card text; none silently overwritten. Surfaced here so the divergence is visible:

1. KGS G1 baseline. The review's 8,182 / 5,644 is the KGS+FORCE combined G1 total; KGS-only was 8,084 / 5,546 (`reports/status_g1.md`). Also: the "nested-archive" recovery mechanism is committed as code (kgs.unpack_las, commit f41cc8a, 2026-07-05; related machinery in d80b2c5), but no committed artifact quantifies its contribution to the count growth — so the card states the before/after counts and asserts no recovery magnitude beyond what is committed.
2. Unmapped mnemonics. The review's 17,970 distinct NLOG mnemonics is committed but in dossier prose; the current committed CSV yields 14,315 distinct (18,690 rows). The card pins the CSV figure and notes the dossier snapshot rather than reconciling two silently. There is no separate KGS "flagged-ambiguous" subset (the CSV is the full 1,667).
3. Parked disambiguation item. "Conductivity conversion" is not in any committed artifact; the parked item is resistivity-channel disambiguation (SN/LN/LATL). The card reframes to what is committed.
4. Pass-rate-by-vintage chart. Resolves to the no-chart branch: the 44→36.3→47.1 trajectory is confirmed, but no vintage axis exists in any committed NLOG artifact, so the card documents the trajectory against crawl order and states the chart cannot be built. This is the fallback the review itself specified.

Two phantom numbers were also dissolved, not forced: the "~500 unaccounted" vintage wells were an omitted 2020s bin (506); the "5 permanent retry failures" has no committed source (traces only to a superseded G1 note) and is not carried as a bucket.
5. Report-verification items (logged by the advisor; addressed)

* 3777 RDEP reviewed-value null lives in the committed pipeline path. The nulling is the same `harmonize.py::_null_rail_pileup` function (no standalone sentinel script); confirmed in the committed path, so from-raw KGS regeneration reproduces the frozen parquets without a lost ad-hoc step. 3777 fill: ~254 wells / 79,446 samples, bit-identical float64.
* Pre-commit secret scan status. Resolved this session (§3) — was absent, now installed and tested.
* Ratifications. `mnemonic_aliases.yaml` double-pin intentional; V1 rail rule at `harmonize.py`; no standalone sentinel script — all carried in `qc_pin_manifest.txt`.
* trend.py. Deferred (training-time physics), deliberately outside the QC pin; gets its own pin at the pre-G3 training freeze.
* Runtime. Was unpinned; now pinned via the fold-in (pandas/numpy `==` reproduction- verified; the rest declared ranges, provably outside the manifest-path closure).

6. Operating rules added

* Rule 13 (env snapshot) — already committed a prior session; left untouched.
* Rule 14 (mutation counters, v2.1+) — committed this session (`bfa3b1d`). Any value-mutating ingestion step must record what it mutated, at run time. Cited to the NLOG rail-impact finding: `_null_rail_pileup` discarded its count, making the historical NLOG rail impact unrecoverable without reopening the frozen corpus (the residual-completeness scan returned N=0 survivors, the adjacent fact the frozen data can answer).

7. What is explicitly NOT done (waiting on the gate)
Per scope freeze, none of the following has started and none will before GATE APPROVED: BasinShift construction, TS-FM tripwire baseline, FSQ tokenizer, physics gate, G3 training, evaluation, release. The post-gate roadmap is unchanged.
Session cost: $10; remaining balance: $340.
HOLD — advisor GATE APPROVED required
The freeze is closed, durable in two independent locations, regenerable from committed code, tamper-evident, and documented by a finalized dataset card. Two process gaps and one security gap were found and remedied this session with honest caveats. Four card figures were corrected against committed data.
This report ends in a HOLD. No model, tokenizer, or benchmark work crosses G2 until the advisor records GATE APPROVED.
