# LithoGPT-2 Feasibility Assessment and Scope Ruling

Date: 4 July 2026. Basis: live verification searches on diffusion for well logs, GAN synthetic logs, LoRA adaptation of foundation models to logs, and existing well-log benchmarks. This document rules on the five proposals raised on 4 July and gives the full go/no-go assessment requested.

## 1. Bottom line

GO, with a scope freeze. The project as planned (open weights, three-source public corpus, physics-gated trend-residual decomposition, cross-basin transfer evaluation) occupies a verified gap. Four of the five new proposals are rejected because verification shows they are already published, which is precisely the reinventing-the-wheel failure this project must avoid. One proposal, creating a benchmark, is accepted in scoped form and is the highest-leverage addition raised so far.

## 2. Rulings, with evidence

### 2.1 Synthetic data to justify a bigger model: REJECTED
Generating synthetic logs from our own corpus adds no new information; a model trained on data derived from a smaller dataset cannot learn more than the smaller dataset contains, and self-training loops degrade quality. It is also prior art twice over: sequence-GAN frameworks for synthetic well-log generation and imputation are published (TSGAN plus SeqGAN, Scientific Reports 2025), and a 2025 framework already pretrains a conditional score-based diffusion imputer on synthetic logs generated from empirical petrophysical formulas, combined with core-calibrated LoRA. Accepted narrow forms only: augmentation transforms already in the plan (curve dropout, masking, mild noise, depth jitter), which improve robustness without pretending to grow the corpus. Physics-forward-modeled synthetic wells are legitimate future work for v2.1, not v2.
Parameter count is the wrong objective regardless. If a larger corpus is wanted later, add real basins (Australia, UK) in v2.1; that dominates synthetic data on every axis.

### 2.2 Bigger model as a goal: REJECTED
A 25M to 50M model matched to a 100M to 300M token corpus is correct science and a product feature: it runs on a laptop, fine-tunes in minutes, and embeds in a Petrel or Techlog plugin, which is the startup wedge. Reviewers and adjudicators reward results and adoption, not parameter counts. The G2 decision rule from EXECUTION_PLAN_v2 stands.

### 2.3 Diffusion pivot: REJECTED as the headline method
Conditional denoising diffusion for well-log imputation is published in SPE Journal (2024), motivated by exactly the uncertainty arguments we would make, and diffusion is now among the best-performing and most active directions for general time-series imputation. A diffusion pivot is therefore joining the existing trend, not departing from it. The decoder-only FSQ-token model stays, for three concrete reasons: one model natively covers imputation (fill-in-the-middle), simulation (causal generation), and transferable embeddings for the lithology and few-shot evaluations; token likelihoods plus the continuous NLL head give calibrated uncertainty directly; and the training loop is simpler and cheaper to debug in the time available. The SPE diffusion paper becomes related work and, if its protocol permits, a comparison row; reproducing it as a baseline is time-boxed to two days at week 8 or dropped.

### 2.4 Fusing existing models with LoRA: REJECTED as the headline method
Adapting a time-series foundation model to well logs is published (TimeGPT adaptation, KFUPM, arXiv 2412.05681), and LoRA-on-diffusion for logs exists (the CCLoRA framework above). Accepted narrow form: one LoRA-adapted open time-series foundation model (Chronos or Moirai class) as a single baseline row at week 8, time-boxed to two days, because beating a generic adapted foundation model strengthens the domain-pretraining claim. It is a baseline, never the method.

### 2.5 Create a benchmark: ACCEPTED, SCOPED
Verified landscape: FORCE 2020 is a single-task lithology contest on one shelf region with a leaderboard; the SPWLA PDDA contests cover property estimation on a handful of wells from one field (nine training wells, five blind) and sonic prediction; a GitHub benchmark exists for imputation algorithms; and WellLogBench (OpenReview, 2026) is an expert-curated QA benchmark for LLM reasoning over logs, a different modality of evaluation entirely. No verified benchmark covers multi-basin, signal-level evaluation with standardized cross-basin transfer splits and calibrated-uncertainty metrics. That is exactly the evaluation suite already being built in weeks 3 to 9, so packaging it as a named public benchmark costs roughly 30 to 40 additional hours of documentation, harness cleanup, and baseline tables, and yields the project's most citable artifact: benchmarks routinely out-cite the models evaluated on them, and independent teams submitting to a benchmark Ammar created is near-ideal original-contribution evidence for O-1A and EB-1A.
Constraints: exactly one benchmark, not several. The name must not collide with WellLogBench; decide the name in week 3 after a collision check. Frozen, hashed test manifests; released scoring harness; strong classical baselines reported honestly; LithoGPT-2 does not need to top every task, and the benchmark's credibility improves if it does not. Existing benchmarks (FORCE 2020, SPWLA tasks) are incorporated as sub-tracks with attribution rather than duplicated. External submissions invited from the week-12 outreach list.

## 3. Full assessment

### Problem
Real and already monetized. Missing and unreliable curves are ubiquitous in public and commercial archives, petrophysicists spend large fractions of project time on QC and reconstruction, and TGS sells predicted missing curves as a product line (ARLAS), which is direct commercial validation of the pain point. The open, reproducible version of that capability does not exist as of verification.

### Method
Sound but not exotic, and that is fine. Every individual component has precedent somewhere: transformers on logs, diffusion imputers, GAN synthesis, physics-informed trends, adapted foundation models. The defensible contribution is the combination plus openness plus rigor: the first open-weights, reproducible well-log model at multi-thousand-well public scale (hedged per POSITIONING.md until the Hugging Face hub check closes), with a gated physics prior whose value is measured by a designed three-way ablation, evaluated on a new cross-basin transfer and calibration benchmark that outlives the model. The paper states this honestly. Groundbreaking is a judgment others award for adoption and rigor; it is not a design input, and chasing it through architecture novelty is how the schedule and the case both slip.

### Outcome
Unchanged from blueprint section 8, with the benchmark adding a second adoption surface that keeps accruing citations and submissions after week 12, on the timeline the EB-1A stage needs. Failure shape remains publishable: if transfer is weak, the benchmark quantifying that weakness is still a contribution.

### Feasibility
Money: under 200 USD compute worst case, confirmed. Time: roughly 300 to 350 focused hours over 12 weeks alongside the rotation and the case; the benchmark adds 30 to 40 hours; the rejected pivots would each have added 60 to 150 hours, which is the strongest practical argument for rejecting them. Energy: the binding risk is scope, not difficulty; every hard technical task (harmonization, gating, tokenizer) is already scheduled with gates. Verdict: feasible if and only if the scope freeze in section 4 holds and the weekly 4 to 6 protected O-1 hours are never raided.

### Relation to the primary goal
This project does not accelerate the O-1 filing and must never delay attorney work, letters, or the ATCE contingency. It is, however, the strongest evidence-builder available that fits around the critical path: letters with genuine basis of knowledge, an original-contribution exhibit with independent uptake, and a plausible press angle. If a week ever forces a choice, the case wins and the build slips.

## 4. Scope freeze (banned from v2, revisit only after week 12)

1. Diffusion or flow-matching backbone.
2. Synthetic-data corpus inflation of any kind beyond standard augmentation transforms.
3. Model fusion or LoRA adaptation as the method (one adapted baseline row permitted, time-boxed).
4. More than one benchmark.
5. Models above 100M parameters.
6. Data sources beyond FORCE 2020, NLOG, KGS.

## 5. Open verification item carried forward

Direct Hugging Face hub and GitHub search for any existing open-weights well-log pretrained model. Until closed, all "first open" language stays hedged as written in POSITIONING.md section 1.

## 6. References from this verification pass

- CDDPM well-log imputation: onepetro.org/SJ/article/29/05/2165/540807
- TSGAN and SeqGAN for log generation and imputation: nature.com/articles/s41598-025-95709-0
- CSDI on synthetic logs plus core-calibrated LoRA: researchgate.net/publication/350476826 (framework described in linked recent work)
- TimeGPT adapted to well logs: arxiv.org/pdf/2412.05681
- WellLogBench (LLM reasoning benchmark): openreview.net/forum?id=RzMqCe2xVK
- SPWLA PDDA contest summary: onepetro.org/petrophysics/article/65/01/108/540802
- FORCE 2020 leaderboard host: thinkonward.com/app/c/challenges/force-well-logs/overview
