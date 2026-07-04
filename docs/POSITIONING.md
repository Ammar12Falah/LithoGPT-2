# LithoGPT-2 Positioning (single source of truth)

Verification date: 4 July 2026. Method: live web search. Update this file whenever a claim is re-verified or contradicted. No claim below may appear in the paper, model card, or a pitch unless its status is VERIFIED.

## 1. Landscape claims and verification status

### TGS well-log foundation model: VERIFIED
60M-parameter well log vision transformer trained with masked autoencoding (ViT-MAE), pretrained on 1.1 million North American well logs for imputation, extended to prompt-based, geologist-guided formation-top interpretation. Fine-tuned on 271,972 human-interpreted formation tops from 44,062 Permian Basin wells covering 37 formations. Presented at IMAGE 2025, Houston, August 25 to 28, 2025. Authors: Lasscock, Sansal, Gonzalez, Valenciano. DOI: 10.1190/image2025-4311806.1.
Closed weights, closed data. TGS's commercial library is on the order of 1.9 million LAS files and over 17 million digitized raster logs.
References: pubs.geoscienceworld.org/segeab/proceedings/SEGEAB.44/1/2910/725127 and tgs.com/products-services/well-data

### WLFM: VERIFIED
arXiv 2509.18152 (September 2025). Qi, Yu, Wang, Zhao, Li, Lv (USTC and Hefei institutes). Pretrained on multi-curve logs from 1,200 wells. Three stages: tokenization of log patches into geological tokens, masked-token modeling plus stratigraphy-aware contrastive learning, multi-task adaptation with few-shot fine-tuning. Reported results: 0.0041 MSE porosity estimation, 74.13 percent lithology accuracy (78.10 with fine-tuning). Interpretation-focused. Authors note systematic reconstruction offsets in shallow and ultra-deep intervals, which is consistent with the depth-trend gap LithoGPT-2 targets.
Reference: arxiv.org/pdf/2509.18152

### Adjacent systems found during verification
- TimeGPT fine-tuned for well-log forecasting and anomaly detection, KFUPM, arXiv 2412.05681 (December 2024). Time-series foundation model adapted to logs, not a from-scratch log FM.
- GEM 3D, promptable subsurface foundation model using well-log prompts for property modeling, arXiv 2507.00419.

### Still UNVERIFIED (do not use until checked)
- LithoGPT-Mini (Li et al., ADIPEC 2025) name-collision details.
- BB-GeoGPT, EnergyLLM (Aramco, ATCE 2025).
- March 2026 ScienceDirect paper on vector-quantized autoregressive well-log modeling.
- Whether any open-weights well-log foundation model already exists on Hugging Face or GitHub. Search HF hub directly before claiming "first open." Until then the claim is "to our knowledge, no open-weights equivalent exists," stated with that hedge.

## 2. Positioning consequences (post-verification)

"First foundation model for well logs" is confirmed taken by TGS at industrial scale (1.1M wells) and by WLFM at research scale (1,200 wells). Three doors remain open and compound:

1. Open. TGS is closed weights and closed data; WLFM is small and, as of verification, no open-weights release at meaningful scale is known. LithoGPT-2 at 5,000 to 15,000 QC-passing public wells is 4x to 12x WLFM's corpus and fully reproducible. Do not compare corpus size against TGS except to state the openness difference.
2. Generative. TGS and WLFM are interpreters (impute, classify, pick tops). LithoGPT-2 is a simulator: calibrated stochastic realizations positioned against SGS/MPS geostatistics workflows.
3. Physics. Explicit trend-residual decomposition with a gated compaction prior. WLFM's own reported shallow and ultra-deep offsets are third-party evidence that the depth-trend problem is real and unsolved; cite it in the paper's motivation.

## 3. Basin framing correction (advisor note, accepted)

Dutch offshore acreage in NLOG is geologically North Sea. Norway-to-Netherlands is within-distribution diversity, not a cross-basin transfer claim, and a reviewer would say so. The transfer claim rests on Kansas (US midcontinent, carbonate-dominated, older log vintages): train North Sea plus Netherlands, test zero-shot on Kansas, and the reverse. Frame it exactly that way in the paper.

## 4. Scale claim wording (approved forms)

- Approved: "trained on N QC-passing public wells across North Sea, Dutch onshore/offshore, and US midcontinent basins, roughly Kx the largest previously reported open pretraining corpus for well logs" (with N and K filled from the dataset card at release).
- Banned: "largest well-log foundation model," "first well-log foundation model," any unhedged "first open" prior to the HF hub check in item 1.
