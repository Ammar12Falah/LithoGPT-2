#!/usr/bin/env python3
"""AA-series brief items AM, AN, AO: CPU-only recompute over
atce_ablation_v3_raw_results_2026-07-26.json. No GPU, no retraining, no new
arms -- pure arithmetic over already-generated/saved data, plus a fresh
refit of the (deterministic, documented) tokenizer for AO's reconstruction-
bias analysis, using the exact same functions as the original run script
(imported, not reimplemented) to avoid transcription drift.
"""
import json, sys, hashlib, time
from pathlib import Path
import numpy as np

ROOT = Path("/workspace/LithoGPT-2")
sys.path.insert(0, str(ROOT / "scripts/atce"))
import atce_ablation_v3 as ref  # noqa: E402  (import triggers no main(), only module-level setup)

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans

RAW_PATH = ROOT / "reports/basinshift/atce_ablation_v3/atce_ablation_v3_raw_results_2026-07-26.json"
OUT_DIR = ROOT / "reports/basinshift/atce_ablation_v3"
BOOT_SEED = ref.SEED  # 20260715, reused for traceability, stated explicitly in every output section
N_BOOT = 10000

ARMS = ["A", "B-linear", "B-abs", "B2", "C", "D"]

t_start = time.time()
print(f"=== LOADING RAW RESULTS ({RAW_PATH.name}) ===", flush=True)
with open(RAW_PATH) as f:
    raw_results = json.load(f)
print(f"loaded in {time.time()-t_start:.1f}s, arms present: {list(raw_results.keys())}", flush=True)

NPHI_IDX, RHOB_IDX, GR_IDX = ref.NPHI_IDX, ref.RHOB_IDX, ref.GR_IDX
TEST_WELLS = list(raw_results["A"].keys())
print(f"test wells ({len(TEST_WELLS)}): {TEST_WELLS}", flush=True)


def get_arrays(arm, well):
    d = raw_results[arm][well]
    real = np.array(d["real"], dtype=np.float64)              # [n,4]
    gens = np.array(d["generated_realizations"], dtype=np.float64)  # [5,n,4]
    return real, gens


# ============================================================
# AM: recompute bias statistics from raw results
# ============================================================
print("\n" + "=" * 70)
print("AM. BIAS STATISTICS RECOMPUTED DIRECTLY FROM RAW RESULTS")
print("=" * 70)

am_results = {}
for arm in ARMS:
    print(f"\n--- Arm {arm} ---")
    per_well_real_mean = {}
    per_well_gen_mean = {}          # realization-pooled generated mean, per well
    per_well_rel_bias = {}          # (gen_mean_well - real_mean_well)/real_mean_well * 100
    all_well_realization_biases = []  # matches the OLD estimator's pooled list (40 values)
    pooled_real_samples = []
    pooled_gen_samples = []

    for w in TEST_WELLS:
        real, gens = get_arrays(arm, w)
        real_nphi = real[:, NPHI_IDX]
        real_mean_w = float(real_nphi.mean())
        per_well_real_mean[w] = real_mean_w
        pooled_real_samples.append(real_nphi)

        gen_nphi_all_realizations = gens[:, :, NPHI_IDX]  # [5, n]
        gen_mean_w = float(gen_nphi_all_realizations.mean())  # pooled across realizations AND samples
        per_well_gen_mean[w] = gen_mean_w
        pooled_gen_samples.append(gen_nphi_all_realizations.reshape(-1))

        per_well_rel_bias[w] = (gen_mean_w - real_mean_w) / real_mean_w * 100.0

        for r in range(gen_nphi_all_realizations.shape[0]):
            b = float(gen_nphi_all_realizations[r].mean() - real_mean_w)
            all_well_realization_biases.append(b)

    # 1. Signed absolute NPHI mean bias (primary metric): mean over the 40
    #    (well, realization) bias values -- same definition as the script's
    #    own abs_bias list, recomputed fresh from raw arrays as a check.
    signed_abs_bias = float(np.mean(all_well_realization_biases))

    # 2. Ratio of pooled means (NEW estimator, requested explicitly)
    pooled_real_flat = np.concatenate(pooled_real_samples)
    pooled_gen_flat = np.concatenate(pooled_gen_samples)
    pooled_real_mean = float(pooled_real_flat.mean())
    pooled_gen_mean = float(pooled_gen_flat.mean())
    pooled_ratio_pct = (pooled_gen_mean - pooled_real_mean) / pooled_real_mean * 100.0

    # 3/4. Per-well relative biases: median/min/max + individual values
    rel_biases = np.array([per_well_rel_bias[w] for w in TEST_WELLS])
    median_rel = float(np.median(rel_biases))
    min_rel = float(rel_biases.min())
    max_rel = float(rel_biases.max())

    print(f"Signed absolute NPHI mean bias (generated - real, NPHI units): {signed_abs_bias:+.6f}")
    print(f"Pooled means: pooled_real_mean={pooled_real_mean:.6f} (n={len(pooled_real_flat)}), "
          f"pooled_generated_mean={pooled_gen_mean:.6f} (n={len(pooled_gen_flat)})")
    print(f"Ratio of pooled means: (gen-real)/real * 100 = {pooled_ratio_pct:+.4f}%")
    print(f"Per-well relative bias %: median={median_rel:+.4f} min={min_rel:+.4f} max={max_rel:+.4f}")
    print("Eight individual per-well relative bias values (%):")
    for w in TEST_WELLS:
        print(f"    {w:12s}  {per_well_rel_bias[w]:+.4f}")

    am_results[arm] = dict(
        signed_abs_bias_nphi_units=signed_abs_bias,
        pooled_real_mean=pooled_real_mean,
        pooled_real_n=len(pooled_real_flat),
        pooled_generated_mean=pooled_gen_mean,
        pooled_generated_n=len(pooled_gen_flat),
        pooled_ratio_pct=pooled_ratio_pct,
        per_well_relative_bias_pct=per_well_rel_bias,
        per_well_real_mean=per_well_real_mean,
        per_well_generated_mean=per_well_gen_mean,
        median_per_well_relative_bias_pct=median_rel,
        min_per_well_relative_bias_pct=min_rel,
        max_per_well_relative_bias_pct=max_rel,
    )

print("\n--- Reconciling the previously-reported relative-bias column ---")
print("""The old `nphi_relative_bias_pct_vs_real_mean` field (atce_ablation_v3.py,
lines 630-636) is NOT (aggregate abs_bias mean) / overall_real_mean_nphi * 100.
It is bootstrap_ci() applied to a pooled list of 40 (8 wells x 5 realizations)
per-REALIZATION ratios, each computed as:
    rel_bias_vals.append(b / m["real_mean_nphi"] * 100)
where b is that realization's signed bias and m["real_mean_nphi"] is THAT
WELL'S OWN real NPHI mean (not the single overall_real_mean_nphi=0.328 shown
alongside it as a separate, unweighted mean-of-per-well-means). Because
different wells have different real NPHI means, this is a mean-of-ratios
using per-well denominators, not a ratio-of-pooled-means using one shared
denominator -- the two do not commute, which is why back-calculating
(abs_bias.mean / 0.32809 * 100) never reproduces the reported figure for any
arm.""")

# Verify by reproducing the OLD estimator exactly and comparing to the
# previously reported (committed) numbers.
print("--- Verification: reproducing the OLD estimator to confirm the diagnosis ---")
for arm in ARMS:
    old_style_ratios = []
    for w in TEST_WELLS:
        real, gens = get_arrays(arm, w)
        real_mean_w = float(real[:, NPHI_IDX].mean())
        gen_nphi_all = gens[:, :, NPHI_IDX]
        for r in range(gen_nphi_all.shape[0]):
            b = float(gen_nphi_all[r].mean() - real_mean_w)
            old_style_ratios.append(b / real_mean_w * 100.0)
    print(f"  {arm:10s} reproduced old-estimator mean = {np.mean(old_style_ratios):+.4f}%  "
          f"(n={len(old_style_ratios)})")


# ============================================================
# AN: well-level bootstrap intervals
# ============================================================
print("\n" + "=" * 70)
print(f"AN. WELL-LEVEL BOOTSTRAP INTERVALS. N={N_BOOT} resamples, seed={BOOT_SEED}")
print("=" * 70)

METRICS = ["nphi_bias", "gr_bias", "rhob_bias", "ac_rmse"]


def autocorr(x, max_lag=20):
    return ref.autocorr(x, max_lag=max_lag)


def per_well_point_estimates(arm):
    """One point estimate per well per metric, averaged over the 5 realizations
    (collapses the nested realization structure before the well-level bootstrap,
    so wells -- the true independent sampling unit -- are what gets resampled)."""
    pts = {m: {} for m in METRICS}
    for w in TEST_WELLS:
        real, gens = get_arrays(arm, w)
        real_nphi, real_rhob, real_gr = real[:, NPHI_IDX], real[:, RHOB_IDX], real[:, GR_IDX]
        real_mean_nphi = real_nphi.mean()
        real_ac = autocorr(real_nphi)
        nphi_biases, gr_biases, rhob_biases, ac_rmses = [], [], [], []
        for r in range(gens.shape[0]):
            g = gens[r]
            nphi_biases.append(g[:, NPHI_IDX].mean() - real_mean_nphi)
            gr_biases.append(g[:, GR_IDX].mean() - real_gr.mean())
            rhob_biases.append(g[:, RHOB_IDX].mean() - real_rhob.mean())
            gen_ac = autocorr(g[:, NPHI_IDX])
            ac_rmses.append(np.sqrt(np.nanmean((real_ac - gen_ac) ** 2)))
        pts["nphi_bias"][w] = float(np.mean(nphi_biases))
        pts["gr_bias"][w] = float(np.mean(gr_biases))
        pts["rhob_bias"][w] = float(np.mean(rhob_biases))
        pts["ac_rmse"][w] = float(np.mean(ac_rmses))
    return pts


point_estimates = {arm: per_well_point_estimates(arm) for arm in ARMS}

# Confirm the Arm C degeneracy cause: are all 5 realizations byte-identical?
print("\n--- Arm C degeneracy check ---")
real_c, gens_c = get_arrays("C", TEST_WELLS[0])
identical = all(np.allclose(gens_c[0], gens_c[r]) for r in range(1, gens_c.shape[0]))
print(f"Arm C, well {TEST_WELLS[0]}: all {gens_c.shape[0]} stored realizations identical = {identical}")
print("Cause (one sentence): Arm C is generated at temperature=0.0 (atce_ablation_v3.py "
      "line 551: `temperature=(1.0 if arm_name != \"C\" else 0.0)`), which makes decoding "
      "purely greedy/argmax (line 284: `int(np.argmax(p))` when temperature<=0), so with an "
      "identical prime and a deterministic eval-mode model, all N_REALIZATIONS=5 stored "
      "realizations are the same rollout -- the per-well bootstrap in the original script "
      "resamples those 5 identical values and is therefore mathematically guaranteed to be "
      "degenerate (ci_low=ci_high=mean), independent of any bug in bootstrap_ci() itself.")
print("Fix: this well-level bootstrap resamples across the 8 WELLS (which do differ, since "
      "each has a different prime and different real data), not across Arm C's 5 identical "
      "realizations -- so it is well-defined and non-degenerate for Arm C. Confirmed below.")


def bootstrap_well_level(values_by_well, n_boot=N_BOOT, seed=BOOT_SEED):
    rng = np.random.default_rng(seed)
    wells = list(values_by_well.keys())
    vals = np.array([values_by_well[w] for w in wells])
    n = len(vals)
    boots = np.array([rng.choice(vals, size=n, replace=True).mean() for _ in range(n_boot)])
    return dict(mean=float(vals.mean()), ci_low=float(np.percentile(boots, 2.5)),
                ci_high=float(np.percentile(boots, 97.5)), n_wells=n)


def bootstrap_paired_diff(vals_a_by_well, vals_b_by_well, n_boot=N_BOOT, seed=BOOT_SEED):
    """Paired well-level bootstrap on (b - a): same resampled well indices used
    for both arms in each resample, so the comparison stays matched."""
    rng = np.random.default_rng(seed)
    wells = list(vals_a_by_well.keys())
    assert wells == list(vals_b_by_well.keys())
    a = np.array([vals_a_by_well[w] for w in wells])
    b = np.array([vals_b_by_well[w] for w in wells])
    n = len(a)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        diffs.append(b[idx].mean() - a[idx].mean())
    diffs = np.array(diffs)
    point_diff = float(b.mean() - a.mean())
    return dict(point_diff=point_diff, ci_low=float(np.percentile(diffs, 2.5)),
                ci_high=float(np.percentile(diffs, 97.5)))


an_per_arm = {}
print("\n--- Per-arm well-level bootstrap (all four metrics) ---")
for arm in ARMS:
    an_per_arm[arm] = {}
    print(f"\nArm {arm}:")
    for metric in METRICS:
        ci = bootstrap_well_level(point_estimates[arm][metric])
        an_per_arm[arm][metric] = ci
        print(f"  {metric:10s} mean={ci['mean']:+.6f}  95% CI=[{ci['ci_low']:+.6f}, {ci['ci_high']:+.6f}]  "
              f"n_wells={ci['n_wells']}  degenerate={'YES -- BUG' if ci['ci_low']==ci['ci_high'] else 'no'}")

PAIRS = [("A", "B2"), ("A", "B-abs"), ("B-abs", "B-linear"), ("A", "C")]
print("\n--- Paired well-level bootstrap differences (matched resampling) ---")
an_pairs = {}
for base, other in PAIRS:
    an_pairs[f"{other}_minus_{base}"] = {}
    print(f"\n({other} - {base}):")
    for metric in METRICS:
        d = bootstrap_paired_diff(point_estimates[base][metric], point_estimates[other][metric])
        an_pairs[f"{other}_minus_{base}"][metric] = d
        sig = "excludes 0 (significant at 95%)" if (d["ci_low"] > 0) or (d["ci_high"] < 0) else "includes 0 (not significant at 95%)"
        print(f"  {metric:10s} point_diff={d['point_diff']:+.6f}  95% CI=[{d['ci_low']:+.6f}, {d['ci_high']:+.6f}]  {sig}")


# ============================================================
# AO: tokenizer reconstruction bias for NPHI
# ============================================================
print("\n" + "=" * 70)
print("AO. TOKENIZER RECONSTRUCTION BIAS FOR NPHI (held-out test wells)")
print("=" * 70)

print("\nRefitting the exact same tokenizer as atce_ablation_v3.py (imported functions, "
      "same SEED, same 80 train wells, same StandardScaler+MiniBatchKMeans params) "
      "-- CPU-only, deterministic, no GPU/training involved.")

df, well_names = ref.load_98_train_wells()
train_wells, dev_wells, test_wells_ref = ref.make_split(well_names)
assert test_wells_ref == TEST_WELLS or set(test_wells_ref) == set(TEST_WELLS), \
    f"test well set mismatch: {test_wells_ref} vs {TEST_WELLS}"
print(f"split reproduced: train={len(train_wells)} dev={len(dev_wells)} test={len(test_wells_ref)}")

raw_curves = {w: ref.well_curves(df, w) for w in well_names}
train_feats = np.concatenate([raw_curves[w][1] for w in train_wells], axis=0)
scaler = StandardScaler().fit(train_feats)
kmeans = MiniBatchKMeans(n_clusters=ref.K, random_state=ref.SEED, n_init=3, batch_size=4096)
kmeans.fit(scaler.transform(train_feats))
kmeans_centers = kmeans.cluster_centers_
print(f"tokenizer refit complete: k={ref.K}, {len(train_feats)} train samples")

# Validate the depth reconstruction against the stored "real" arrays before
# trusting per-sample depth for the decile breakdown.
print("\n--- Validating reconstructed depth/real arrays against stored raw results ---")
validation_ok = True
depth_segments = {}
real_segments_check = {}
for w in TEST_WELLS:
    depth, feats = raw_curves[w]
    n = len(depth)
    prime_n = max(ref.CONTEXT, int(n * ref.PRIME_FRAC))
    remaining = n - prime_n
    gen_len = min(remaining, ref.MAX_GEN_LEN)
    depth_seg = depth[prime_n:prime_n + gen_len]
    real_seg_recomputed = feats[prime_n:prime_n + gen_len]
    depth_segments[w] = depth_seg
    real_stored, _ = get_arrays("A", w)
    match = np.allclose(real_seg_recomputed, real_stored, atol=1e-6)
    validation_ok &= match
    print(f"  {w:12s} n_samples={gen_len:5d}  matches stored real array: {match}")
assert validation_ok, "STOP: depth/real reconstruction does not match stored raw results -- do not trust decile breakdown"
print("All 8 wells validated -- depth arrays are correctly aligned to the stored real segments.")

# Tokenize -> detokenize the held-out real NPHI (same scored window as the primary metric)
all_real4 = []
all_depth = []
all_well_id = []
for w in TEST_WELLS:
    real_stored, _ = get_arrays("A", w)
    all_real4.append(real_stored)
    all_depth.append(depth_segments[w])
    all_well_id.extend([w] * len(real_stored))
all_real4 = np.concatenate(all_real4, axis=0)     # [N,4]
all_depth = np.concatenate(all_depth, axis=0)     # [N]
all_well_id = np.array(all_well_id)

z = scaler.transform(all_real4)
tok = kmeans.predict(z.astype(np.float64))
recon_std = kmeans_centers[tok]
recon = scaler.inverse_transform(recon_std)

real_nphi = all_real4[:, NPHI_IDX]
recon_nphi = recon[:, NPHI_IDX]
residual = recon_nphi - real_nphi  # signed reconstruction bias, per sample

overall_mean_bias = float(residual.mean())
print(f"\nNPHI reconstruction mean bias (signed, reconstructed - real), pooled over "
      f"{len(residual)} held-out samples across {len(TEST_WELLS)} test wells: {overall_mean_bias:+.6f}")
print(f"(for scale: real NPHI mean={real_nphi.mean():.4f}, reconstructed NPHI mean={recon_nphi.mean():.4f})")

print("\n--- Reconstruction mean bias by depth decile ---")
depth_deciles = np.percentile(all_depth, np.linspace(0, 100, 11))
decile_rows = []
for i in range(10):
    lo, hi = depth_deciles[i], depth_deciles[i + 1]
    mask = (all_depth >= lo) & (all_depth <= hi) if i == 9 else (all_depth >= lo) & (all_depth < hi)
    n = mask.sum()
    bias = float(residual[mask].mean()) if n > 0 else float("nan")
    decile_rows.append(dict(decile=i + 1, depth_lo_m=float(lo), depth_hi_m=float(hi), n=int(n), mean_bias=bias))
    print(f"  decile {i+1:2d}  depth=[{lo:8.2f}, {hi:8.2f}] m  n={n:6d}  mean_bias={bias:+.6f}")

print("\n--- Reconstruction mean bias by NPHI quantile ---")
nphi_deciles = np.percentile(real_nphi, np.linspace(0, 100, 11))
quantile_rows = []
for i in range(10):
    lo, hi = nphi_deciles[i], nphi_deciles[i + 1]
    mask = (real_nphi >= lo) & (real_nphi <= hi) if i == 9 else (real_nphi >= lo) & (real_nphi < hi)
    n = mask.sum()
    bias = float(residual[mask].mean()) if n > 0 else float("nan")
    quantile_rows.append(dict(decile=i + 1, nphi_lo=float(lo), nphi_hi=float(hi), n=int(n), mean_bias=bias))
    print(f"  q{i+1:2d}  NPHI=[{lo:.4f}, {hi:.4f}]  n={n:6d}  mean_bias={bias:+.6f}")

print("\n--- Original vs reconstructed NPHI mean, per well ---")
per_well_recon = {}
for w in TEST_WELLS:
    mask = all_well_id == w
    r_real = float(real_nphi[mask].mean())
    r_recon = float(recon_nphi[mask].mean())
    per_well_recon[w] = dict(real_mean=r_real, recon_mean=r_recon, bias=r_recon - r_real)
    print(f"  {w:12s}  real={r_real:.4f}  reconstructed={r_recon:.4f}  bias={r_recon-r_real:+.6f}")

from scipy.stats import pearsonr
corr, corr_p = pearsonr(residual, all_depth)
print(f"\nPearson correlation between reconstruction residual and absolute depth: "
      f"r={corr:+.4f}  p={corr_p:.4g}  (n={len(residual)})")

if abs(corr) > 0.1:
    print("INTERPRETATION: |r| > 0.1 -- reconstruction bias shows a non-trivial systematic "
          "relationship with depth. This means at least part of the null/positive result "
          "structure may be a property of the tokenizer-model system rather than purely of "
          "depth conditioning.")
else:
    print("INTERPRETATION: |r| <= 0.1 -- reconstruction bias is close to depth-independent. "
          "Combined with the overall mean bias figure above, this bears on whether the "
          "B-abs effect (item V) reflects a real depth-conditioning signal.")

# ============================================================
# Write outputs
# ============================================================
out = dict(
    generated_at="2026-07-27",
    bootstrap_seed=BOOT_SEED,
    n_bootstrap=N_BOOT,
    AM=am_results,
    AN=dict(per_arm=an_per_arm, paired_diffs=an_pairs,
            arm_c_degenerate_realizations_confirmed=bool(identical)),
    AO=dict(
        overall_mean_bias=overall_mean_bias,
        real_nphi_mean=float(real_nphi.mean()),
        reconstructed_nphi_mean=float(recon_nphi.mean()),
        n_samples=int(len(residual)),
        by_depth_decile=decile_rows,
        by_nphi_quantile=quantile_rows,
        per_well=per_well_recon,
        pearson_r_residual_vs_depth=float(corr),
        pearson_p=float(corr_p),
    ),
)
out_path = OUT_DIR / "atce_v3_recompute_2026-07-27.json"
payload = json.dumps(out, indent=2, sort_keys=True, default=str)
out_path.write_text(payload)
sha = hashlib.sha256(payload.encode()).hexdigest()
(OUT_DIR / "atce_v3_recompute_2026-07-27.sha256").write_text(sha + "\n")
print(f"\nWRITTEN {out_path}, sha256={sha}")
print(f"TOTAL WALL TIME: {time.time()-t_start:.1f}s")
print("ATCE_V3_RECOMPUTE_COMPLETE")

