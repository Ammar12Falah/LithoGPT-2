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
