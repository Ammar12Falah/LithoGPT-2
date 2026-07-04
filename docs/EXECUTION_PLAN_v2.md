# LithoGPT-2 Execution Plan v2 (corrected 4 July 2026)

This file records the deltas against the blueprint after landscape verification and review of the prior advisor's notes. Where this file and the blueprint disagree, this file wins. Verified landscape claims live in POSITIONING.md.

## 1. Advisor notes: disposition

All three corrections are accepted, two with modifications.

1. Data descope: ACCEPTED, MODIFIED. Australia, NSTA, Sodir bulk, and stretch US states are out of v2 scope. v2 sources are exactly three: FORCE 2020, NLOG, KGS. Modification: no hard cap at 5,000 wells. NLOG and KGS are bulk-friendly, so we take everything that passes an aggressive QC bar from these three sources; the realistic yield is 5,000 to 15,000 wells, which still supports the scale wording in POSITIONING.md section 4. Quality bar over well count, exactly as the note argues.
2. Physics prior gating: ACCEPTED IN FULL. The Athy-form clastic compaction trend is invalid in the carbonate-dominated US midcontinent. Fitting it blindly to Kansas would force the transformer to unlearn a wrong prior, and the prior-off ablation could then beat prior-on cross-basin, gutting the paper's spine. Fix: per-basin-group robust fits (already planned), plus an automated applicability gate (PEF carbonate flag where PEF exists, RHOB-NPHI separation heuristic otherwise, residual-variance gate as backstop), plus a prior_confidence channel as model input. The ablation becomes three-way: prior-off, prior-on-ungated, prior-on-gated. This converts the predicted failure mode into a designed experiment; if ungated loses to off on Kansas, that is now a result, not an ambush.
3. Letter writers embedded early: ACCEPTED. Moves from week 12 to week 1, inside the protected O-1 hours, not the build hours. See section 5.

One correction to the note itself: Norway-to-Netherlands is not cross-basin; Dutch offshore is North Sea. Kansas is the transfer test. POSITIONING.md section 3 records the approved framing.

## 2. New issue found in this review: token budget vs model size

The descope shrinks the corpus roughly 5x to 10x versus the blueprint's assumption, and this changes the right model size. Estimate: a 1,500 m Kansas triple-combo well yields roughly 1,200 tokens (9,800 samples per curve at 0.1524 m, patch 32, about 4 curves); a 3,500 m North Sea well with 8 curves yields roughly 5,700 tokens. Blended 2,500 to 5,000 tokens per well. At 8,000 to 12,000 wells the unique corpus is roughly 20M to 60M tokens; at 3 to 5 epochs, 100M to 300M trained tokens.

A 100M-parameter model over 100M to 300M tokens is far off the roughly 20-tokens-per-parameter compute-optimal ratio and will saturate early. Decision rule, set now: at Gate G2, if unique corpus tokens are below 150M, the primary release model is S-scale (25M to 50M parameters) and the 100M model runs once as a scale ablation only. This is honest, cheaper, and avoids shipping an overparameterized headline model. Log data is highly redundant, so 3 to 5 epochs is acceptable; do not exceed 6.

## 3. Compute budget (A40 on RunPod, verified pricing 4 July 2026)

Pricing basis: A40 48GB at 0.44 USD per hour on RunPod community cloud, billed per second; network volume storage 0.05 to 0.07 USD per GB-month, which keeps billing while a pod is stopped, so volumes are deleted between work sessions. An RTX 4090 at a similar rate is a valid substitute with higher bf16 throughput; 48 GB of A40 VRAM is not needed for a 25M to 100M model at context 4096.

FLOPs math, main run, 100M parameters, 200M trained tokens: 6 x 1e8 x 2e8 = 1.2e17 FLOPs. A40 dense bf16 peak is roughly 75 TFLOPS; at 25 to 30 percent utilization, roughly 20 TFLOPS sustained, giving about 6,000 seconds, under 2 hours. With checkpointing, rolling eval, and dataloader overhead, plan 2 to 4 hours per main run. Every stated duration below is wall-clock on one A40.

| Item | Hours |
|---|---|
| FSQ tokenizer training and level sweep (4 to 6 configs) | 8 to 15 |
| S-model iteration runs (6 to 10 runs, 0.5 to 1.5 h each) | 8 to 15 |
| Main run, prior-on-gated | 2 to 4 |
| Twin runs: prior-off and prior-on-ungated | 4 to 8 |
| Remaining ablations at S scale (objective mix, basin embedding, scale) | 10 to 20 |
| Evaluation inference and generative sampling studies | 5 to 10 |
| Subtotal | 37 to 72 |
| Headroom x1.7 for failed runs and restarts | 63 to 122 |

Planning cap: 150 A40-hours, about 66 USD at community pricing. Absolute ceiling if the corpus doubles: 300 hours, about 132 USD. Storage during active weeks: 50 to 100 GB volume, 3 to 7 USD per month. All-in compute spend for the descoped scope: under 100 USD expected, under 200 USD worst case. Compute is confirmed not the constraint; data engineering is.

## 4. Revised timeline (deltas only; everything not listed is unchanged)

Week 1: repo public with scaffold, CI, POSITIONING.md, mnemonic_aliases.yaml, this plan. License matrix for three sources only (FORCE 2020 terms, NLOG terms, KGS terms), with citations to each terms page. Ingestion scripts for FORCE 2020 and NLOG written and running. Letter-writer shortlist of 5 contacted (section 5).
Week 2: KGS bulk ingestion, QC suite v1 with per-source dashboard, harmonization table extended from observed mnemonics.
Gate G1, end week 2, revised: 5,000+ QC-passing wells minimum with 8,000 target, two continents, three-source license matrix complete. Miss: extend ingestion one week, compress week 5, no new sources.
Weeks 3 to 4: no new sources. Dedup pass, carbonate and trend-applicability gate built and validated on labeled FORCE wells, tokenizer level sweep, dataset card with real counts, test manifest frozen and hashed. G2 numeric bar set with Ammar before tokenizer training starts. G2 adds the model-size decision from section 2.
Weeks 5 to 7: S runs, then main run and the two twins (three-way prior ablation). G3 unchanged.
Weeks 8 to 9: full evals; the headline transfer table is North Sea plus Netherlands to Kansas and the reverse, per POSITIONING.md section 3.
Weeks 10 to 12: unchanged (release, paper, outreach), except letter candidates are warm contacts by week 12, not cold ones.

## 5. Letter-writer engagement (week 1, O-1 protected hours)

Five candidates chosen from the verification pass, contacted with the v1 paper (SPE-234177-MS), one genuinely technical question about their own work, and a one-line statement that v2 is being built openly to close the bias v1 diagnosed. No ask beyond technical dialogue. Candidate pools: the WLFM authors (USTC; their reported shallow and ultra-deep offsets are exactly the problem the physics prior targets, which makes for a real technical question), the TGS IMAGE 2025 authors, the KFUPM TimeGPT-for-logs authors, FORCE 2020 competition organizers, and one open-geoscience community figure. Final five picked by Ammar; the advisor drafts the notes; monthly light-touch updates thereafter. Evidence protocol captures all replies from day one.

## 6. Immediate next actions

1. Ammar: create the public GitHub repo, commit POSITIONING.md, mnemonic_aliases.yaml, EXECUTION_PLAN_v2.md today.
2. Advisor, next working session: write ingest_force2020.py, ingest_nlog.py, and qc.py against the YAML config, plus the license matrix skeleton with the three terms-page citations.
3. Ammar: confirm RunPod credit balance against the 150-hour planning cap and confirm the G1 bar (5,000 minimum, 8,000 target).
4. Ammar: pick the five letter candidates from the pools above.
