# LithoGPT-2: Full Technical Dossier

Date: 9 July 2026. Status snapshot: G1 gate closed and approved. This document is a complete technical record of the LithoGPT-2 project: what it is, why it exists, how the pipeline and model are designed, what has been built and verified, and what remains. It uses only verified, artifact-backed facts. It deliberately contains no personal, salary, immigration, or case-strategy data; that material lives with the owner and the senior advisor and is out of scope here.

Positioning discipline: this document follows the project rule of no "first" or "largest" claims without live verification. Where a fact is a plan rather than a completed result, it is marked as such.

---

## 1. What LithoGPT-2 is

LithoGPT-2 is an open-weights foundation model for well logs (the depth-indexed geophysical sensor traces recorded in boreholes), trained on public multi-basin data and released fully open. Its headline scientific claim is cross-basin transfer: that a model pretrained on wells from some basins gives useful predictions on a geologically distinct basin it was not trained on.

The project has three deliverable pillars, and the durable value is in the assets around the model as much as the model itself:
1. An open, reproducible data pipeline (ingestion, harmonization, quality control) for public well-log repositories.
2. A named, versioned, multi-basin evaluation benchmark (BasinShift) with frozen manifests, a scoring harness, and honest baselines.
3. The open model weights and a live demo, with an honest evaluation report including limitations.

The model's intended capabilities: fill missing log curves (imputation) conditioned on the curves that are present; produce calibrated uncertainty and multiple stochastic realizations rather than single point predictions; generate learned embeddings for downstream tasks (lithology classification, formation correlation); and, as the central research question, transfer across basins.

## 2. Scientific context and positioning

Predecessor: LithoGPT v1 (SPE-234177-MS, accepted at SPE ATCE 2026) was a 5.2M-parameter transformer trained on the public FORCE 2020 well-log dataset. Its key diagnostic finding was a porosity bias consistent with coordinate-blind learning of compaction trends: the model learned depth-driven trends without a physical handle on them. LithoGPT-2 is designed to close that gap with an explicit, gated physics prior, a larger multi-basin public corpus, a full open release, and a new cross-basin benchmark.

Verified landscape (as of 4 July 2026, per the project's positioning documents):
- A closed 60M-parameter ViT-MAE well-log foundation model pretrained on roughly 1.1 million North American wells was presented at IMAGE 2025 (closed weights, closed commercial data). LithoGPT-2 does not compete on scale with this; the difference it claims is openness, not size.
- A research-scale well-log foundation model (WLFM) pretrained on about 1,200 wells reports systematic reconstruction offsets in shallow and ultra-deep intervals, which is independent evidence for the depth-trend problem this project targets.
- Related published work exists on diffusion imputation, GAN-based synthetic log generation, and LoRA adaptation of time-series foundation models. These are treated as baselines or related work, not as directions for this project.
- No verified existing benchmark covers multi-basin signal-level evaluation with standardized cross-basin transfer splits and calibration metrics. That gap is the BasinShift deliverable.

Approved positioning axes: open (weights, pipeline, corpus recipe), generative (calibrated stochastic realizations positioned against geostatistics workflows), and physics (gated trend-residual decomposition). Banned claims: any unverified "first," any unhedged "largest," and any comparison to the closed model's corpus size except to state the openness difference.

## 3. Scope

### 3.1 Deliverables (definition of done)
1. Open weights on Hugging Face with a complete model card.
2. Public GitHub repository with all ingestion, harmonization, QC, trend/gating, tokenizer, model, training, and evaluation code.
3. Dataset card with real verified counts, per-source licenses, QC statistics, and split manifests. Default release posture: pipeline plus weights, no raw data mirror, subject to the license matrix.
4. The BasinShift benchmark: one versioned multi-basin evaluation package with frozen hashed manifests, a scoring harness CLI, honest baseline tables, and a PR-based leaderboard.
5. A live demo (dark mode): upload a LAS file or pick a sample well, mask curves, get imputed curves with uncertainty bands and multiple stochastic realizations.
6. Evaluation report: FORCE 2020 benchmark, sonic prediction, cross-basin transfer, calibration, and all ablations, every headline number with bootstrap confidence intervals.
7. A paper draft with honest limitations.

### 3.2 Scope freeze (banned unless escalated and approved)
Diffusion or flow-matching backbone; synthetic-data corpus inflation; model fusion or LoRA adaptation as the primary method (one LoRA-adapted time-series foundation model is permitted as a single baseline only); more than one benchmark; models above 100M parameters; data sources beyond FORCE 2020, NLOG, and KGS; any change to gate dates, splits, or the frozen test manifest.

## 4. Data pipeline

The pipeline reduces every LAS and DLIS file to a common RawWell representation (depth-indexed curves), then harmonizes, quality-controls, and stores each passing well as a uniform parquet.

### 4.1 Sources
- FORCE 2020 (Norway, North Sea): 98 training wells plus 10 open test wells with lithofacies labels. The official train/test split is preserved and becomes a benchmark sub-track. The 10 open test wells are for the leaderboard; a separate set of FORCE blind wells is reserved for final scoring only.
- NLOG (Netherlands): the Dutch national subsurface data portal. Bulk-accessible, thousands of wells with LAS and DLIS.
- KGS (Kansas): the Kansas Geological Survey, free LAS files and a queryable index for released wells.

### 4.2 Ingestion engineering
Respect robots.txt; throttle to at most one request per 2 seconds per host; identify the crawler with a project user-agent and contact email; make every fetcher resumable with a local manifest; checksum and never modify raw files; log every fetch. The NLOG access contract was probed and verified live: a WFS borehole index, a per-borehole log-document listing endpoint, and a per-file byte-download endpoint, all pinned in code.

### 4.3 Harmonization
A seed alias table (mnemonic_aliases.yaml) maps the many raw curve names to a canonical set: GR, RHOB, NPHI, DTC, PEF, SP, CALI, RDEP, RMED, RSHA, with DTS optional. The table is extended only from observed data, never guessed; every unmapped mnemonic is logged with source, raw unit, and count for weekly triage. Unit conversions are applied before range gates. Resistivities are log10-transformed. All curves resample to a fixed 0.1524 m depth grid. Per-curve robust normalization (median and IQR) is computed on the training split only.

### 4.4 QC suite (automated, logged per well)
In order: null handling to explicit missing masks; physical range gates (out-of-range set to missing, never clipped); washout flagging (where caliper exceeds bit size by more than 2 inches, density/neutron/PEF are flagged suspect); a Hampel spike filter; a minimum-usable-interval gate (drop wells with fewer than 3 canonical curves over at least 100 m); and deduplication by location, depth range, and curve fingerprint. Per-source QC dashboards (figures plus HTML) report pass rates, curve coverage, and depth histograms.

### 4.5 Storage
One parquet per QC-passing well with depth, one column per canonical curve, a boolean mask per curve, and physics trend columns with a prior-confidence channel. A master index records well id, source, basin group, location, depth range, curve inventory, QC summary, dedup hash, and split assignment. Splits are by well and basin group, never by depth interval within a well.

## 5. Physics prior and gating

For trend-bearing curves (RHOB, NPHI, DTC), a constrained Athy-form compaction trend is fit against true vertical depth per basin group: porosity as phi0 times exp of negative depth over lambda, with bounded parameters and Huber loss. Density and sonic trends derive from the porosity trend via documented mixing transforms. The point is a physically sensible mean function, not a full rock-physics model.

Gating is mandatory because the US midcontinent is carbonate-dominated and the clastic compaction trend is invalid there. An interval bypasses the prior (prior-confidence 0) when it looks carbonate (PEF at or above 4.0, or a documented density/gamma carbonate heuristic) or when the post-fit residual is large over a sustained interval; elsewhere prior-confidence is 1. The model predicts residuals (observed minus trend) where confidence is 1 and raw normalized values where it is 0, with prior-confidence supplied as an input channel; generation adds the trend back where it applied.

The three-way ablation (prior-off, prior-on-ungated, prior-on-gated) is the scientific spine of the paper and retains value even if cross-basin transfer turns out weak, because it characterizes when the physics prior helps.

## 6. Tokenizer

Per-curve depth patches of 32 samples (about 4.9 m). A small convolutional encoder maps each patch to a low-dimensional latent, quantized by finite scalar quantization (FSQ), with the code-book size swept against reconstruction error. A continuous residual regression head reconstructs real-valued signals (trained with Gaussian negative log-likelihood), so generations are real-valued logs, not cluster centroids. Curves are interleaved per depth window with curve-type embeddings and shared depth positional encoding; curve-availability masks are inputs, making imputation native. Acceptance bar: tokenizer reconstruction must not degrade downstream imputation utility beyond a signed threshold (median per-curve degradation at most 5 percent, no curve above 10 percent).

## 7. Model and training

Architecture: decoder-only transformer, context at least 4096 tokens. Config S is about 25M parameters (12 layers, d_model 512, 8 heads); Config M is about 100M parameters (24 layers, d_model 1024, 16 heads). Conditioning inputs include a depth bucket embedding and continuous depth feature, a basin-group embedding, the curve-availability mask, a source embedding, and the prior-confidence channel.

Model-size decision rule: if unique corpus tokens are below 150M, the primary release model is S-scale and the 100M config runs once as a scale ablation only. At the current corpus size (roughly 8,000 to 12,000 wells, an estimated 20M to 60M unique tokens), S-scale is the expected primary model. The small model is a deliberate match to the data size, not a limitation to apologize for.

Objectives: a per-batch mix of fill-in-the-middle span corruption (imputation) and causal next-patch prediction (simulation). Optimization uses bf16, AdamW, a cosine schedule with warmup, gradient clipping, and a small number of epochs. Every run is launched from a committed config with a logged seed, and every reported result names its config and checkpoint.

Baselines (required): gradient-boosted trees (XGBoost or LightGBM) per target curve are the strong classical baseline and are genuinely hard to beat in-basin; parity there is reported honestly rather than hidden. Linear regression and k-nearest-neighbors by depth are floors. One LoRA-adapted open time-series foundation model runs as a single time-boxed baseline.

## 8. Evaluation and the BasinShift benchmark

Splits are by basin group and by well; the test manifest is frozen and hashed at the corpus-freeze gate; test wells are touched only through the scoring harness. The FORCE blind wells are reserved for final scoring only and are never used for model selection, comparison, or tuning.

Benchmark tracks:
1. FORCE 2020 lithology, official split and official penalty-matrix scoring.
2. Sonic prediction (DTC from triple-combo inputs), reporting RMSE and CRPS.
3. Cross-basin zero-shot transfer (the headline): train on North Sea plus Netherlands, test imputation zero-shot on Kansas, and the reverse. Norway-to-Netherlands is treated as within-distribution diversity; Kansas is the transfer test.
4. Generative calibration: PIT histograms and CRPS from at least 32 samples, variogram reproduction against a geostatistics baseline, and sample diversity.
5. Ablations: the three-way prior, FSQ levels, multitask mix, basin embedding, and S-versus-M scale.
6. Statistics bar: every headline number carries a bootstrap 95 percent confidence interval over test wells; no difference within its noise is narrated as real.

Benchmark name: BasinShift. Confirmed after a public-web collision check (no existing benchmark, dataset, or model of that name; no collision with the existing WellLogBench, which is an LLM question-answering benchmark and a different modality). The name follows the common "[domain]Shift" ML-benchmark convention, chosen for legibility (it states in one word that the benchmark measures performance under basin-to-basin distribution shift). A final direct Hugging Face and GitHub name search is pending before any public use.

Architecture decision on record (transfer track): the method is a from-scratch decoder-only transformer, not an adaptation of a pretrained time-series foundation model. A LoRA-adapted time-series foundation model runs as a two-day baseline immediately after the benchmark freeze, evaluated on dev and open-leaderboard wells only. Pre-registered tripwire: if that adapted baseline beats the from-scratch S-model cross-basin on the dev slice by more than 10 percent relative RMSE on at least two of the three target curves, a scope amendment is brought before further training spend. Reasoning: the transfer problem is cross-curve conditional inference under lithology-regime shift, which generic temporal pretraining does not address, and the physics prior requires owning the backbone.

## 9. Current state and verified progress

Gate history:
- G1 (corpus floor and diversity): CLOSED and APPROVED as of 9 July 2026. Criteria: at least 5,000 QC-passing wells across two continents (met), and the diversity condition of at least 1,500 QC-passing European wells (met at 1,812). Bound to milestone report docs/milestone_G1_nlog.md at commit 9a1f5e1 and an evidence tarball with a recorded, off-pod-verified sha256.
- G2 (tokenizer and corpus freeze): in progress. The immediate remaining Task A item (NLOG ingestion) is complete.

Verified corpus counts (each backed by committed report CSVs):
- KGS (Kansas): 6,336 QC-passing wells.
- FORCE 2020 (Norway): 98 QC-passing wells.
- NLOG (Netherlands): 1,812 QC-passing wells, from 4,996 of about 5,009 log-bearing boreholes processed (13 boreholes pending a final retry-and-disposition). Overall NLOG pass rate 36.3 percent.
- Combined: about 8,246 QC-passing wells across two continents.

NLOG pass-rate note (interval discipline): the pass rate held near 44 percent through the first roughly 3,660 boreholes, then fell across the tail as the crawl reached old, sparse wells with no modern log suite (zero canonical curves), which cannot meet the 3-curve floor. The final count of 1,812 is reported over the mid-run projection of 2,112 to 2,273 precisely because the tail behaved differently from the middle; the cause is named rather than smoothed over.

Test suite: 63 tests passing. Two crawl fixes were made, tested, and committed during NLOG ingestion: a fallback-candidate cap (roughly halving runtime) and a re-QC argument fix that unblocked the fallback path.

Alias-triage status (round two, in the current work window): of 17,970 distinct unmapped NLOG mnemonics, only 248 appear in at least 50 boreholes, and of those only a small number are genuine canonical curves. Confident, unit-verified additions identified: RGR and ECGR to GR, SON to DTC, and RCAL/CAL1/CAL2 to CALI. An API-scaled NEUT channel was rejected as a wrong-scale trap (not calibrated neutron porosity). The high-count resistivity channels (SN, LN, LATL) are ambiguous against the canonical deep/medium/shallow scheme and are deferred to documented future work rather than force-mapped. This confirms the design's expectation that NLOG's pass rate, unlike KGS's, is not meaningfully alias-suppressed.

## 10. Compute and budget

Platform: RunPod. The ingestion crawl is a CPU-and-network-bound job (bounded by the 2-second polite fetch limit and single-threaded DLIS parsing), so it needs no GPU. Data persists on a network volume; the volume pins the pod to its datacenter region. Budget: a planning cap of 150 A40-hours (about 66 USD) and an absolute ceiling of 300 hours. The NLOG work cost about 15 USD actual (crawl plus debugging and idle pod time). Lesson recorded: CPU-only jobs should run on CPU pods, and pods should be stopped when idle, to keep the GPU budget reserved for training.

## 11. Repository structure

docs/ (handoffs, positioning, license matrix, dataset and model cards, milestone reports, this dossier, decisions log); configs/ (alias YAML, run configs); src/ ingest, io, pipeline, tokenizer, model, train, eval; scripts/ (the crawl driver and QC runner); demo/ (the dark-mode Space); reports/ (QC dashboards, unmapped mnemonics, records); tests/. Standards: pinned requirements, type hints, unit tests for harmonization, QC gates, trend fitting, and gating logic, deterministic seeds, and no reported result without a reproducing config.

## 12. Forward plan (advisor-sequenced)

Days one and two, in parallel: the alias-triage window (confident aliases applied, targeted re-QC, two reported numbers being wells added and per-target-curve coverage delta, then freeze regardless of result); the 13-borehole retry with per-borehole disposition; and the commit of the verbatim architecture-ruling decision-capture text.

Day three, the corpus freeze, in strict leakage-safe order: define all splits in one operation (train, dev, held-out KGS, held-out Netherlands, and the FORCE 10 open-leaderboard wells, with the FORCE blind wells outside everything); hash the full manifest; then compute normalization statistics on the frozen train split only; then write the dataset card (KGS alias-jump explanation, NLOG index snapshot pinning with dates and counts, the all-but-13 disposition line, the triage outcomes, and a pass-rate-by-vintage chart); then produce a freeze evidence tarball with its own recorded, off-pod-verified hash. The freeze is not done until both hashes exist (manifest and tarball).

Week two: BasinShift construction and XGBoost baselines committed as the standing opponent; then the post-freeze TS-FM tripwire baseline on dev and leaderboard wells only, which is a hard decision point before any training spend; then the FSQ tokenizer against the signed acceptance bar; then physics-gate validation with a carbonate report; then the G2 milestone report and a hold for approval. Estimated elapsed time: roughly two weeks of working sessions, ending at the G2 gate with training authorized but not yet started. No tokenizer or benchmark work begins before the freeze manifest hash exists.

## 13. Risk register (condensed)

Mnemonic harmonization consuming the schedule (the main engineering task of the early weeks); redistribution rights (managed by the license matrix, default posture pipeline plus weights); losing to XGBoost in-basin (expected and survivable, since the claims are transfer, coherence, and calibration, not raw in-basin accuracy); weak cross-basin transfer (if it happens, publish the honest characterization; the three-way prior ablation retains value either way); and compute overrun (bounded by the budget caps).

## 14. Glossary

Well log: a depth-indexed record of a physical property measured down a borehole. LAS/DLIS: standard well-log file formats. Canonical curves: the standardized target measurements (gamma ray GR, bulk density RHOB, neutron porosity NPHI, compressional sonic DTC, photoelectric factor PEF, spontaneous potential SP, caliper CALI, and deep/medium/shallow resistivity RDEP/RMED/RSHA). Basin: a geologically distinct subsurface region. Imputation: predicting a missing curve from present curves. Cross-basin transfer: applying a model to a basin it was not trained on. Mnemonic: the raw name a curve carries in a file. Washout: an enlarged borehole section that corrupts pad-contact measurements. FSQ: finite scalar quantization, the tokenizer's discretization method.

---

End of dossier. All figures are backed by committed artifacts in the repository as of commit 9a1f5e1 and the reports under reports/. This document contains no personal or case data by design.
