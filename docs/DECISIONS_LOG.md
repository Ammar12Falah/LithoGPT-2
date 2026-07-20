# LithoGPT-2 Decisions Log

## G1 diversity condition: GATE APPROVED (recorded 2026-07-09)

CLOSED as MET. 1,812 QC-passing European wells against the 1,500 bar.
Bound to milestone report docs/milestone_G1_nlog.md at commit 9a1f5e1 and
evidence tarball sha256 037dc72abc357052a89c338936e848a3789abd8e08a3cfedc20ac295352f7019,
verified off-pod. Approved by senior advisor. Agent may proceed to G2 Task C.

## 2026-07-10  KGS sentinel-clean (agent, advisor-ruled)

Confirmed processing fills nulled in data/processed/kgs (values->NaN, mask->False, never
clipped): resistivity ceiling 100000 ohmm (log10 5.0) in RDEP 3634w / RMED 1217w /
RSHA 44w; GR floor 0.0 gAPI 4248w; RDEP=3777 ohmm exact (log10 3.5771469848275252,
bit-exact across 219+ wells) ~254w. Verified: residual fill 0 on all targets, value/mask
consistent both directions across 9307 files, physical controls intact (RHOB 2.55 5807w,
CALI 7.0 1347w, NPHI 0.0 2904w).

Rulings applied: rail-welded masses are censoring events, safe to null (advisor). General
isolated-spike detector WITHDRAWN, falsified by measurement (real CALI bit-size clustering
scores as isolated as fill, iso-ratio ~1e11 both). Mid-range fills handled only via
explicit reviewed exact values (RDEP 3777), not by shape. Flagged-not-nulled: PEF 20.0 (1w),
RDEP 3.5507 (3w). Last coverage loop per advisor: corpus freezes at whatever the numbers are.

Process corrections disclosed (full detail in reports/kgs_sentinel_clean_report.md): first
clean pass under-nulled via an erroneous per-well frequency gate and left masks unset;
corrected by ungated exact-value null + a mask-consistency repair (1316 files, 993094 cells);
two verifier cells were themselves buggy (cwd trap, single-file over-generalization) and were
caught. All counts reconcile across dry-run/clean/repair/verify.

## 2026-07-11 Architecture decision capture (advisor ruling, reviewed not absorbed silently)

Verbatim ruling:
"Method for the transfer track is a from-scratch decoder-only transformer. A LoRA-adapted open time-series foundation model runs as a two-day baseline immediately after benchmark freeze, evaluated on dev and open-leaderboard wells only. Pre-registered tripwire: if the adapted TS-FM beats the from-scratch S-model cross-basin on the dev slice by more than 10 percent relative RMSE on at least two of three target curves, a scope amendment is brought before further training spend. The FORCE blind wells are touched once, by the final scoring path, and never by selection, comparison, or tripwire evaluation."

Recorded per advisor amendment 4; pre-registration predates the post-benchmark-freeze TS-FM tripwire baseline. Attribution: advisor. Reviewed at capture.

### 2026-07-19 — Ruling 2 amendment: borehole vs file partition axes (landed 2026-07-20)

Supersedes the taxonomy sentence in the corpus state that conflated two partition levels.
The 363 NLOG failures are a FILE-level count spanning 174 distinct boreholes; the earlier
"266 never produced a QC record" is likewise file-level and does NOT slot into the
borehole-level 1,605 as previously framed.

Authoritative borehole-level taxonomy:
  6,609 released = 1,563 (no log document) + 42 (log-bearing, never processed) + 5,004
  processed. Within 5,004: 2,355 passing + 2,649 floor-fail.
  The 42 = 15 failure-blocked + 27 fetched-but-silently-dropped (never-fetched = 0,
  verified by byte+sha download evidence).

File-level failures are reported separately (363 file reads across 174 boreholes; 159 of
those boreholes recovered via alternate files, 15 not) and never blended with the
borehole-level counts.

Cause: binding ruling history is amended on the record when shown wrong, never silently
reconciled. The originally-ordered entry (ruled 07-19) was not committed at the time; this
records it, late, with the landing date stated.


## 2026-07-20  GATE G2 APPROVED -- Stage-B corpus freeze closed (advisor ruling)

Advisor recorded GATE APPROVED for Gate G2, the Stage-B corpus freeze, closed 20 July 2026,
bound to manifest d5b35a00, freeze HEAD chain 9168d83 -> 212faed9 -> 41e0e51 with evidence
commits through bfa3b1d, evidence tarball a7244b35...cea5e6cc hash-verified off-pod, splits
invariant at 8,809 rows across all nine counts, regenerable from committed code, tamper-evident
under the completed pin set.

Activation condition (MET): CI green at bfa3b1d. GitHub Actions run 29764701685 concluded
success at bfa3b1d (https://github.com/Ammar12Falah/LithoGPT-2/actions/runs/29764701685) --
ci.yml installs the `==`-pinned deps fresh on the runner, then ruff + pytest. This resolves the
11 July concern about hashing a freeze against an unverified runner state after the runtime-pin
fold-in. Post-gate sequence unchanged (BasinShift construction -> TS-FM tripwire baseline ->
FSQ tokenizer -> physics gate -> G3 training); the blind-10 rule travels with all of it.
Nothing crosses G2 until this entry stands. Attribution: advisor. Reviewed at capture.

## 2026-07-20  Unpacker contradiction resolved (first-session audit task)

The 07-19 review flagged a contradiction: dataset-card Correction 1 states the nested-archive
recovery mechanism "appears in zero committed artifacts," while the 11 July session report
attributed the KGS reprocess recovery to a nested-archive unpacker "fixed at f41cc8a." Settled
by git log: f41cc8a EXISTS on main (full f41cc8a4b17418394f871f0f1766ae4430c96a79, dated
2026-07-05, subject "kgs.unpack_las handles nested archives; run_qc_kgs --fresh truncates"), an
ancestor of HEAD, touching src/lithogpt2/ingest/kgs.py (+34/-7) and scripts/run_qc_kgs.py (+4);
a second commit d80b2c5 also carries fetch/unpack machinery.

Outcome: the session-report hash was NOT fabricated -- the audit trail is clean. The CARD is
wrong on the narrow point: the mechanism does appear in a committed artifact (code at f41cc8a).
Cause: the card's "zero committed artifacts" was written checking committed data/reports, not
the ingest-code history. Remedy: one-line card correction at the next evidence commit --
Correction 1 to read that the nested-archive unpacker is committed as code at f41cc8a, while
the specific count-growth attribution remains only what the committed before/after counts
support.

## 2026-07-20  Conductivity-conversion parking recorded (chat-only ruling, now on record)

The conductivity-to-resistivity conversion for COND(DI) and CILD (via reciprocal transform)
was genuinely ruled approved future work, but the ruling lived only in chat. Recorded here with
that provenance so it does not vanish. It is parked, not admitted: no conductivity-conversion
item exists in committed artifacts today (0 "conductivity" hits repo-wide), and the dataset
card's parked-item line names the resistivity-channel disambiguation (SN/LN/LATL) it can
source. Governing principle reaffirmed: chat-only facts are not authoritative; committed
artifacts are. Attribution: advisor. Reviewed at capture.


## 2026-07-20  R7 TS-FM tripwire amendment: split into Stage 1 (6.2) and Stage 2 (6.5) (advisor ruling)

Supersedes the single pre-registered tripwire captured 2026-07-11, whose text conflated two
distinct comparisons into one impossible sentence.

Original R7 text (2026-07-11, verbatim):
"Method for the transfer track is a from-scratch decoder-only transformer. A LoRA-adapted open
time-series foundation model runs as a two-day baseline immediately after benchmark freeze,
evaluated on dev and open-leaderboard wells only. Pre-registered tripwire: if the adapted TS-FM
beats the from-scratch S-model cross-basin on the dev slice by more than 10 percent relative RMSE
on at least two of three target curves, a scope amendment is brought before further training
spend. The FORCE blind wells are touched once, by the final scoring path, and never by selection,
comparison, or tripwire evaluation."

The conflation: one sentence merges (a) a TS-FM baseline run "immediately after benchmark freeze,"
when the only committed opponent is XGBoost, with (b) a decisive tripwire comparing TS-FM against
the from-scratch S-model. These cannot both hold: the S-model does not exist until 6.5, so TS-FM
cannot be compared against it "immediately after benchmark freeze." The early baseline (vs
XGBoost) and the decisive tripwire (vs S-model) are two different events at two different times,
wrongly registered as one.

Superseding two-stage structure (advisor):
- Stage 1 (roadmap 6.2, now): LoRA-adapted TS-FM vs the committed XGBoost baseline, on dev +
  open-leaderboard wells only. Predictions are FROZEN at completion (pre-registered; no later
  retuning). Escalation clause: if TS-FM beats XGBoost by more than 25 percent relative RMSE on
  ALL three target curves, an immediate scope amendment is brought before proceeding.
- Stage 2 (roadmap 6.5): the decisive R7 tripwire, LoRA-TS-FM vs the from-scratch S-model, more
  than 10 percent relative RMSE on at least two of three target curves, brought before the main
  training run.
- Recorded rule: proxy comparators (XGBoost, or any TS-FM stand-in) are BANNED as the decisive
  tripwire opponent; the Stage 2 tripwire opponent must be the S-model itself. XGBoost is the
  Stage 1 opponent only.
- FORCE blind wells remain untouched throughout both stages; touched once, by the final scoring
  path at G3 (6.6).

Prerequisites (verified read-only this session; the ruling referenced a state predating recent
sessions): BasinShift is built and its test manifest is frozen
(reports/basinshift/basinshift_test_manifest.json sha256
e5f653077587f2fa80aa4bf1c236e45735798d1421329c735e7dbb620bcfbb71, commit bd344e5); the XGBoost
standing opponent (scripts/basinshift/basinshift_baseline.py) and its outputs are committed; CI is
green at bfa3b1d (GitHub Actions run 29764701685, conclusion success). The prerequisites the
ruling listed as open are already met.

Attribution: advisor. Reviewed at capture. Outside the hashed set; d5b35a00 untouched.


### 2026-07-20 — Interpretation annex to the amended R7 (TS-FM Stage 1)

Clause text, threshold (>25% rel-RMSE on all three curves), and comparator (XGBoost) are
UNCHANGED from the R7 amendment. This annex adds two things and moves no goalposts:

1. A matched random-initialization control. The Stage-1 surgery (frozen MOMENT encoder +
   LoRA q,v + trainable cross-channel head) is run twice — pretrained MOMENT-1-large and
   the same architecture randomly initialized, identical trainable budget — so the
   pretraining contribution is measured (the pretrained-minus-random delta) rather than
   argued. The >25% clause fires on the full adapted system (plan-protection); the delta
   informs what a firing conversation concludes: large delta = generic temporal pretraining
   transfers, from-scratch premise under pressure; small delta = a small trained
   cross-channel module beats XGBoost, evidence FOR the from-scratch design (the S-model is
   that module grown up).

2. A shared evaluation harness. One scorer for all systems (XGBoost, TS-FM, S-model, main),
   asserting evaluation-population identity (count + per-well mask hash) and refusing to
   score on mismatch, in physical units after inverse-transform. Prevents a denominator
   artifact from firing the clause spuriously — structurally, not by care.

Guardrails: all adaptation training on frozen TRAIN only; dev/open eval-only; head
pre-declared (two candidate configs, selected on dev, no further search). Blind-10
untouched. The frozen committed predictions Stage 2 compares against are the full adapted
system's dev+open predictions; control predictions committed alongside.
