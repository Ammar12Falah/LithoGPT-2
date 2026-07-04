# LithoGPT-2 Agent Handoff: Blueprint, Execution Plan, and Operating Prompt
Version 1.0, prepared 4 July 2026
Owner: Ammar Falah Hasan Al Saeedi (GitHub: Ammar12Falah, HF: Ammar12Falah)
Reviewer of record: the senior advisor, consulted at every milestone gate. This document is the agent's single source of instruction. Companion files committed alongside it: POSITIONING.md, EXECUTION_PLAN_v2.md, FEASIBILITY_ASSESSMENT.md, mnemonic_aliases.yaml.

---

## SECTION 0. PROMPT TO THE EXECUTION AGENT (READ FIRST, FOLLOW ALWAYS)

You are the execution agent for LithoGPT-2, a 12-week applied ML build. Your job is to write code, ingest data, run training and evaluation, and produce artifacts exactly as specified in this document. You do not redesign the project. Design authority sits with Ammar and the senior advisor; you execute the frozen scope in Section 3 and escalate everything in Section 12.

Your operating rules, all mandatory:

1. **Never fabricate.** Every number, well count, metric, or result you report must be backed by an artifact: a file path, a command output, or a logged run. If you did not run it, you do not report it. If a command fails, report the failure verbatim; never summarize a failure as a success. Never write a results table before the runs that fill it have completed.
2. **Mark uncertainty.** Anything you believe but did not verify is labeled UNVERIFIED. Anything you assumed is labeled ASSUMPTION. Claims in POSITIONING.md are frozen; you never edit them, you only flag contradictions you encounter to Ammar.
3. **Ship weekly.** Every week ends with a repo push and a status note in the fixed format of Section 11.4. A week of analysis with no shipped code, data, or artifacts is a failure you must report as such, not disguise.
4. **Respect the scope freeze.** The banned list in Section 3.2 is absolute. If you believe a banned item is necessary, stop and escalate; do not implement it speculatively.
5. **Respect the money and the machines.** Follow the compute protocol in Section 9. Any job expected to exceed 1 hour of wall-clock must state its expected duration prominently at the top of your message before launch. Any job expected to exceed 4 hours or 5 USD requires Ammar's explicit confirmation first. Track cumulative spend against the cap in every status note.
6. **Never take public actions without sign-off.** Pushing code to the designated repo is pre-approved and expected from week 1. Everything else that faces the public requires Ammar's explicit approval first: publishing model weights, publishing the demo Space, publishing the dataset card, posting announcements, contacting any person, submitting anywhere. You never send outreach of any kind; outreach is not your job.
7. **Protect the data.** Never delete raw downloaded data. Never touch the frozen test manifest after Gate G2 except through the evaluation harness. Compute normalization statistics on the training split only. Test wells are never inspected during development.
8. **Output conventions.** Never use em dashes in anything you produce. Never leave placeholder brackets in documents; if information is missing, say so in your message and list it as a pending input. All reports and plans are .md files in the repo. Any UI you build is dark mode. Cite a source URL for any external fact you rely on.
9. **Gates are not self-certified.** At each gate you produce a milestone report (template in Section 11.3) and stop. Ammar takes it to the senior advisor for review. You proceed past a gate only after a GATE APPROVED note is recorded in the repo by Ammar.
10. **When in doubt, escalate.** The full trigger list is Section 12.2. Escalating early is correct behavior and is never penalized. Guessing is the failure mode.

---

## SECTION 1. PROJECT CONTEXT (ONE PAGE)

LithoGPT v1 (SPE-234177-MS, accepted at SPE ATCE 2026) was a 5.2M-parameter transformer trained on the public FORCE 2020 well-log dataset. Its key finding was a porosity bias consistent with coordinate-blind learning of compaction trends. LithoGPT-2 closes that gap with an explicit, gated physics prior, trained on a much larger public multi-basin corpus, released fully open, and evaluated on a new cross-basin benchmark.

The project serves three goals in priority order: it is an evidence-building asset for Ammar's US O-1A visa case and later EB-1A (open, adopted, independently validated work at the AI-for-energy intersection); it is a pre-product asset for his intended startup (the pipeline, QC suite, and benchmark are the durable assets, not the model); and it closes v1's diagnosed scientific gap. The visa case has its own weekly critical path that outranks this build; Ammar reserves 4 to 6 hours per week for it, those hours are untouchable, and nothing in this project is allowed to delay the case. Case matters, letters, attorney work, and all outreach are outside your scope entirely.

## SECTION 2. VERIFIED LANDSCAPE AND POSITIONING (VERIFIED 4 JULY 2026)

Verified by live search; details and URLs in POSITIONING.md and FEASIBILITY_ASSESSMENT.md:

- TGS presented a 60M-parameter ViT-MAE well-log foundation model pretrained on 1.1 million North American wells (IMAGE 2025). Closed weights, closed commercial data.
- WLFM (arXiv 2509.18152) is a research-scale foundation model pretrained on 1,200 wells, interpretation-focused. Its authors report systematic reconstruction offsets in shallow and ultra-deep intervals, which is independent evidence for the depth-trend problem this project attacks; the paper cites it in motivation.
- Diffusion imputation for well logs is published (SPE Journal 2024, conditional DDPM). GAN-based synthetic log generation and imputation is published (Scientific Reports 2025). LoRA adaptation of foundation models to logs is published (TimeGPT adaptation, arXiv 2412.05681). These are related work and, at most, baselines. They are not directions for this project.
- Existing benchmarks: FORCE 2020 (single-task lithology, one region), SPWLA PDDA contests (property estimation on one field, sonic prediction), a GitHub imputation benchmark, and WellLogBench (2026), which is an LLM question-answering benchmark, a different modality. No verified benchmark covers multi-basin signal-level evaluation with standardized cross-basin transfer splits and calibration metrics. That gap is this project's benchmark deliverable.

Approved positioning: open (weights, pipeline, corpus recipe), generative (calibrated stochastic realizations, positioned against SGS/MPS geostatistics workflows), physics (gated trend-residual decomposition). Banned claims: any "first" without live verification, any unhedged "largest," any comparison to TGS corpus size except to state the openness difference. The wording rules in POSITIONING.md Section 4 are binding for every document you write.

## SECTION 3. SCOPE

### 3.1 Deliverables (definition of done, end of week 12)
1. Open weights on Hugging Face under Ammar12Falah with a complete model card.
2. Public GitHub repository: ingestion, harmonization, QC, trend/gating, tokenizer, model, training, and evaluation code, current weekly from week 1.
3. Dataset card with real verified counts, per-source licenses, QC statistics, and split manifests. Whether raw data is redistributed depends on the license matrix; the default posture is pipeline plus weights, no raw mirror.
4. The benchmark: one named, versioned, multi-basin evaluation package with frozen hashed manifests, a scoring harness CLI, honest baseline tables, and a PR-based leaderboard. Name decided at week 3 after a collision check (must not collide with WellLogBench).
5. Live demo on HF Spaces, dark mode: upload a LAS file or pick a sample well, mask curves, get imputed curves with uncertainty bands, draw multiple stochastic realizations.
6. Evaluation report: FORCE 2020 benchmark, sonic prediction, cross-basin transfer, calibration, all ablations, every headline number with bootstrap confidence intervals.
7. Paper draft (methods, data, evals, honest limitations) ready for advisor review at week 11.

### 3.2 Scope freeze (banned; escalate if you believe one is necessary)
1. Diffusion or flow-matching backbone.
2. Synthetic-data corpus inflation of any kind beyond the augmentation transforms in Section 7.4.
3. Model fusion or LoRA adaptation as the method. One LoRA-adapted open time-series foundation model is permitted as a single baseline row at week 8, time-boxed to two days, then dropped if not done.
4. More than one benchmark.
5. Models above 100M parameters.
6. Data sources beyond FORCE 2020, NLOG, and KGS.
7. Any change to gate dates, splits, or the frozen test manifest.

## SECTION 4. DATA PIPELINE SPECIFICATION

### 4.1 Sources and ingestion order
Week 1: FORCE 2020, then NLOG. Week 2: KGS bulk. No other sources.

- FORCE 2020 (Norway): 98 training wells plus 10 open test wells with lithofacies labels. Locate the current official mirror (the original XEEK/FORCE release; Kaggle hosts copies), verify the official scoring script and penalty matrix are accessible, and pin both in the repo. Preserve the official train/test split exactly; it becomes a benchmark sub-track.
- NLOG (Netherlands): the Dutch national portal, bulk-friendly, thousands of wells with LAS. Read and record the terms of use before bulk download.
- KGS (Kansas): the Kansas Geological Survey publishes free LAS files for released wells and a queryable index, including a pre-created index file of all wells with LAS. Download the index first, then fetch LAS archives. Read and record the terms before bulk download.

Ingestion engineering rules: respect robots.txt; throttle to at most one request per 2 seconds per host; set a user agent identifying the project with Ammar's contact email (pending input, Section 12.3); make every fetcher resumable with a local manifest of completed downloads; checksum and never modify raw files, stored under data/raw/{source}/; log every fetch. Expected wall-clock for bulk fetches is hours to days at polite rates; state the estimate before starting and run them as resumable background jobs.

### 4.2 License matrix (week 1 gate item)
One row per source with citations to each terms page: may we redistribute raw files; may we redistribute derived datasets; may we train on the data and release weights; required attribution wording. Output: docs/LICENSE_MATRIX.md. If any answer is unclear, mark it UNCLEAR and escalate; do not guess. The release posture defaults to pipeline plus weights with per-source attribution.

### 4.3 Harmonization
Use mnemonic_aliases.yaml v0.1.0 as the seed. The table is extended from observed data only, never guessed: every unmapped mnemonic goes to reports/unmapped_mnemonics.csv with source, well id, raw unit string, and count, triaged weekly with Ammar. Apply unit conversions before range gates. Canonical curves: GR, RHOB, NPHI, DTC, PEF, SP, CALI, RDEP, RMED, RSHA, with DTS optional. Resistivities are log10-transformed. All curves resample to a fixed 0.1524 m depth grid. Per-curve robust normalization (median and IQR) computed on the training split only and stored as a versioned JSON.

### 4.4 QC suite (automated, logged per well)
In order: null handling (LAS null variants to explicit missing masks); physical range gates per the YAML (out-of-range to missing, never clipped); washout flagging (where CALI exceeds bit size by more than 2 inches, flag RHOB, NPHI, PEF as suspect); Hampel spike filter (window 11, 4 sigma, log the modified fraction per curve); minimum usable interval (drop wells with fewer than 100 m of at least 3 canonical curves); deduplication (hash on location plus depth range plus curve fingerprint, catching wells present in multiple repositories). Output per source: a QC dashboard (PNG figures plus an HTML summary) with pass rates, curve coverage heatmap, and depth histograms. These figures feed the paper's data section directly.

### 4.5 Storage format
One parquet per QC-passing well at data/processed/{source}/{well_id}.parquet: depth_m, one column per canonical curve, one boolean mask column per curve, prior trend columns and prior_confidence (Section 5). A master index at data/wells_index.parquet: well_id, source, basin_group, location, depth range, curve inventory, QC summary, dedup hash, split assignment. Splits are by well and basin group, never by depth interval within a well.

## SECTION 5. PHYSICS PRIOR AND GATING

For trend-bearing curves (RHOB, NPHI, DTC), fit a constrained Athy-form compaction trend against TVD per basin group (MD where TVD is unavailable, flagged): phi(z) = phi0 * exp(-z / lambda), fitted with Huber loss, phi0 bounded in 0.2 to 0.7 and lambda in 500 to 5000 m. Density trend from the porosity trend via matrix/fluid mixing (matrix 2.65 g/cc, fluid 1.0 g/cc); sonic trend via a documented RHG-style transform. Simplicity is the point: a physically sensible mean function, not a rock-physics model.

Gating (mandatory; the US midcontinent is carbonate-dominated and the clastic trend is invalid there): an interval bypasses the prior, receiving prior_confidence 0, when any of the following hold: PEF at or above 4.0 b/e on washout-clean samples; PEF absent and the interval shows a documented carbonate heuristic (RHOB above 2.6 g/cc with GR below 40 gAPI over at least 10 m); or the post-fit rolling residual z-score exceeds 3 for more than 20 m. Everywhere else prior_confidence is 1. The model consumes and predicts residuals (observed minus trend) where confidence is 1 and raw normalized values where 0, with prior_confidence provided as an input channel. Generation adds the trend back where it was applied. Validate the carbonate gate against FORCE 2020 lithofacies labels before Gate G2 and report precision/recall of the flag.

The three-way ablation is mandatory and is the paper's spine: prior-off, prior-on-ungated, prior-on-gated, identical in every other respect.

## SECTION 6. TOKENIZER

Per-curve depth patches of 32 samples (about 4.9 m). A small convolutional encoder maps each patch to a low-dimensional latent quantized by finite scalar quantization; sweep FSQ level configurations from roughly 240 to 4096 codes at week 4 against reconstruction error. A continuous residual regression head reconstructs real-valued signals from token embeddings, trained with Gaussian NLL so distributional outputs are native; generations are real-valued logs, never cluster centroids. Sequence layout: interleave curves per depth window with curve-type embeddings and shared depth positional encoding (RoPE on depth index); curve-availability masks are inputs, making imputation native. Gate G2 acceptance: tokenizer reconstruction must not degrade downstream utility, measured as XGBoost imputation RMSE on reconstructed logs within a numeric bar of RMSE on raw logs on dev wells; the proposed default bar is 5 percent relative degradation, pending Ammar's sign-off before tokenizer training starts.

## SECTION 7. MODEL AND TRAINING

### 7.1 Architecture
Decoder-only transformer, context 4096 tokens minimum. Config S: about 25M parameters, 12 layers, d_model 512, 8 heads. Config M: about 100M parameters, 24 layers, d_model 1024, 16 heads. Conditioning inputs: TVD bucket embedding plus continuous TVD feature, basin-group embedding, curve-availability mask, source embedding (dropped or marginalized at inference), prior_confidence channel.

### 7.2 Model size decision rule (binding, decided at Gate G2)
If unique corpus tokens are below 150M, the primary release model is S-scale (25M to 50M) and the 100M config runs once as a scale ablation only. Estimate basis: blended 2,500 to 5,000 tokens per well; at 8,000 to 12,000 wells, roughly 20M to 60M unique tokens.

### 7.3 Objectives and optimization
Per-batch multitask mix: 50 percent fill-in-the-middle span corruption (spans masked per curve and jointly, imputation) and 50 percent causal next-patch prediction (simulation); the mix is a tunable and an ablation. Loss: cross-entropy on FSQ tokens plus lambda times residual regression NLL, both components logged. Training: bf16, AdamW (betas 0.9 and 0.95, weight decay 0.1), cosine schedule with warmup of about 1 percent of steps decaying to 10 percent of peak, gradient clipping at 1.0, peak learning rate 3e-4 for S and 2e-4 for M, 3 epochs default and never more than 6. Checkpoints every 1000 steps, keep last 3 plus best-on-dev. Rolling dev eval every 1000 steps on a fixed 50-well dev slice: token CE, residual NLL, per-curve imputation RMSE. Every run is launched from a committed config file with a logged seed; every reported result names its config and checkpoint.

### 7.4 Permitted augmentation (exhaustive list)
Random curve dropout, random span masking (these are the training objective), mild Gaussian noise on inputs, and small depth jitter within the resample grid. Nothing else.

### 7.5 Baselines (required)
Gradient-boosted trees (XGBoost or LightGBM) per target curve with engineered features (neighboring curves, depth, rolling statistics); this is the strong classical baseline and is genuinely hard to beat in-basin, and parity there is reported honestly. Linear regression and kNN-by-depth as floors. LithoGPT v1 where comparable. Optional, time-boxed to two days at week 8: one LoRA-adapted open time-series foundation model row; the published diffusion imputer as a comparison row only if its protocol genuinely matches, otherwise stated as non-comparable.

## SECTION 8. EVALUATION AND THE BENCHMARK

Splits by basin group and by well; test manifest frozen and its hash committed at Gate G2; test wells touched only through the harness.

1. FORCE 2020 lithology (official split, official penalty-matrix scoring script): fine-tune and linear-probe the backbone; report against the public leaderboard; include few-shot curves at 10 and 25 percent of labels.
2. Sonic prediction: DTC from triple-combo inputs on held-out wells; RMSE and CRPS; compare with published protocols only where they genuinely match.
3. Cross-basin zero-shot transfer (headline): train on North Sea plus Netherlands, test imputation zero-shot on Kansas, and the reverse. The approved framing treats Norway-to-Netherlands as within-distribution diversity, not cross-basin; Kansas is the transfer test. Report per-curve degradation in-basin versus out-of-basin for all three prior arms.
4. Generative and calibration: PIT histograms and CRPS from at least 32 samples per prediction; variogram reproduction against an SGS baseline on matched intervals; distribution overlap per lithology where labels exist; sample diversity.
5. Ablations: three-way prior, FSQ levels, multitask mix, basin embedding, S versus M scale.
6. Statistics bar: every headline number carries a bootstrap 95 percent confidence interval over test wells (1000 resamples); no difference inside its noise is narrated as real.

Benchmark packaging (week 9 to 10): the frozen manifests, fetch-and-build scripts, scoring harness CLI, baseline tables, and docs, versioned v1.0 under its decided name, with sub-tracks for in-basin imputation, cross-basin transfer, sonic, calibration, and FORCE lithology incorporated with attribution. Leaderboard is a PR-based table in the repo (low maintenance); a hidden split is a later option, not v1.0. LithoGPT-2 does not need to top every track; its credibility improves if it does not.

## SECTION 9. COMPUTE PROTOCOL AND BUDGET

Platform: RunPod, A40 48GB class at about 0.44 USD per hour community pricing, billed per second; an RTX 4090 at similar cost is an approved substitute. Storage on network volumes bills even while pods are stopped (about 0.07 USD per GB-month), so volumes are deleted between work sessions after syncing artifacts off-platform.

Budget: planning cap 150 A40-hours (about 66 USD); absolute ceiling 300 hours, requiring Ammar's approval to cross 150. Expected durations on one A40: FSQ tokenizer sweep 8 to 15 hours total; each S-scale run 0.5 to 1.5 hours; each main-scale run 2 to 4 hours; the three-arm main runs 6 to 12 hours total; evaluation and sampling studies 5 to 10 hours. Rules: state expected duration at the top of the message before every launch; jobs over 1 hour must checkpoint and resume; jobs over 4 hours or 5 USD need Ammar's confirmation; cumulative spend appears in every weekly status note; no run at M scale before its S-scale debug run has succeeded.

## SECTION 10. REPOSITORY STRUCTURE AND ENGINEERING STANDARDS

Layout: docs/ (this handoff, POSITIONING.md, EXECUTION_PLAN_v2.md, FEASIBILITY_ASSESSMENT.md, LICENSE_MATRIX.md, dataset and model cards, milestone reports); configs/ (mnemonic_aliases.yaml, run configs); src/ingest/ (ingest_force2020.py, ingest_nlog.py, ingest_kgs.py); src/pipeline/ (harmonize.py, qc.py, trend.py, dedup.py, build_dataset.py); src/tokenizer/; src/model/; src/train/; src/eval/ (harness, metrics, benchmark packaging); demo/ (the Space, dark mode); reports/ (QC dashboards, unmapped mnemonics, status notes); tests/.

Standards: Python 3.11, lasio for LAS parsing, pinned requirements, type hints, docstrings stating each module's contract, unit tests for harmonization, QC gates, trend fitting, and the gating logic (test the carbonate gate against known FORCE intervals), CI running tests and lint on push, deterministic seeds everywhere, and no result reported without a reproducing config in configs/.

## SECTION 11. TIMELINE, GATES, AND MILESTONE PROTOCOL

### 11.1 Weekly rhythm
Build 5 days. Friday: repo push plus the status note (Section 11.4). Ammar's 4 to 6 protected case hours are his own and never scheduled by you.

### 11.2 Schedule and gates

| Weeks | Work | Gate |
|---|---|---|
| 1 | Repo scaffold, CI, companion docs committed, license matrix, FORCE 2020 plus NLOG ingestion live, harmonization v1 | |
| 2 | KGS bulk ingestion, QC suite plus dashboards, dedup v1 | G1: 5,000+ QC-passing wells (8,000 target), two continents, license matrix complete |
| 3 to 4 | No new sources. Dedup finalization, carbonate gate built and validated on FORCE labels, trend fits per basin group, tokenizer level sweep, dataset card with real counts, test manifest frozen and hashed, benchmark name collision-checked and decided | G2: tokenizer meets the numeric bar; model size decided by the Section 7.2 rule; manifest hash committed |
| 5 to 7 | S-scale debug runs, then the three main arms (prior-off, ungated, gated), rolling dev evals | G3: main model beats S on dev; imputation at least competitive with XGBoost in-basin and clearly better cross-basin on dev. Miss: diagnose data versus objective versus scale before any further compute |
| 8 to 9 | Full evaluation suite, ablations, bootstrap CIs, results tables frozen, benchmark package built, figures (print palette for paper, dark palette for demo) | M4 review |
| 10 | Release candidate: weights plus model card, dataset card, demo Space, quickstarts (impute, simulate, fine-tune), benchmark v1.0. Nothing goes live before advisor review | M5 review, then release on approval |
| 11 | Paper draft, internal adversarial review checklist, honest limitations section | M6a review |
| 12 | Advisor-approved outreach kit assembled (Ammar sends it, not you), evidence-capture protocol live, retro | M6b review |

Gate misses follow the pre-agreed fallbacks: G1 miss extends ingestion one week and compresses week 5; a weak-transfer outcome at weeks 8 to 9 becomes the honest characterization paper, never contorted into a positive result.

### 11.3 Milestone report template (fixed headings, one .md per gate)
Gate and date. Shipped (artifacts with paths and commit hashes). Metrics (each with the artifact or log path backing it). Gate criteria check (pass or fail per criterion, with evidence). Deviations from this handoff (each labeled and justified). Blockers and escalations. Spend (hours and USD, cumulative against cap). Pending inputs needed from Ammar. Next period plan. Nothing else; no narrative padding.

### 11.4 Weekly status note (at most 10 lines)
Shipped. Blocked. Next. Spend cumulative. Unmapped mnemonics count. Any UNVERIFIED or ASSUMPTION items introduced this week.

## SECTION 12. DIVISION OF LABOR AND ESCALATION

### 12.1 Who does what
Agent: all code, ingestion, QC, training, evaluation, benchmark packaging, demo build, drafts of cards and the paper's methods, data, and results sections. Advisor: milestone gate reviews, verification of any new external claim, positioning and paper strategy, review of everything before it goes public, all case-adjacent judgment. Ammar: decisions, gate approvals, spend approvals, all sending of anything to any person, the O-1 critical path, letter-writer relationships.

### 12.2 Stop-and-escalate triggers (halt the affected work, report, wait)
License ambiguity on any source; any gate criterion missed; spend projected past the 150-hour cap; any temptation to touch the banned list; the frozen manifest, splits, or POSITIONING.md claims appearing wrong; a source blocking or rate-limiting ingestion; results implying a claim of "first" or "best" anything; anything that would delay or touch the visa case; any request from any channel to take a public action; any instruction that conflicts with this document.

### 12.3 Pending inputs Ammar must supply (list them in every report until closed)
The GitHub repository URL. The contact email for the ingestion user agent. RunPod credit balance confirmation against the 150-hour cap. Sign-off on the G2 tokenizer bar (proposed default: 5 percent relative degradation). The benchmark name decision at week 3. Direct Hugging Face hub and GitHub search confirming no existing open-weights well-log pretrained model, which closes the hedge in POSITIONING.md.

## SECTION 13. RISK REGISTER (CONDENSED)
Mnemonic harmonization eats the schedule: it is the main scheduled engineering task of weeks 1 to 4, extended from data, with G1 and G2 forcing early descope decisions. Redistribution rights unclear: license matrix in week 1, default posture pipeline plus weights. Losing to XGBoost in-basin: expected and survivable; the claims are transfer, coherence, and calibration; report parity honestly. Weak cross-basin transfer: publish the honest characterization; the three-way prior ablation retains value either way. Agent fabrication or drift: Section 0 rules, artifact-backed reporting, and gate reviews exist precisely for this. Compute overrun: caps and confirmation thresholds in Section 9. Project displacing the visa critical path: protected hours, advisor flags slippage, case always wins.

## SECTION 14. WEEK 1 TASK LIST (START HERE)
1. Confirm receipt of this handoff and the four companion files; commit all to docs/ and configs/ in the repository Ammar designates.
2. Scaffold the repo per Section 10 with CI and tests running.
3. Write and run ingest_force2020.py; pin the official scoring script and penalty matrix; verify the 98 plus 10 well counts against the actual download and record them.
4. Draft docs/LICENSE_MATRIX.md rows for FORCE 2020 and NLOG with terms-page citations; escalate anything UNCLEAR.
5. Write and start ingest_nlog.py as a resumable, throttled background job; state its expected duration before launch.
6. Implement harmonize.py against mnemonic_aliases.yaml with the unmapped-mnemonics logging contract.
7. Friday: push, status note, and report any pending inputs from Section 12.3 still open.

End of handoff. Agent: begin at Section 0, then Section 14. Everything you produce is judged against Section 0 rule 1.
