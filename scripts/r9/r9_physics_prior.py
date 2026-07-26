#!/usr/bin/env python3
"""R9 physics prior: fit Athy compaction trends per basin group on frozen TRAIN wells
only, and validate the carbonate gate against FORCE 2020 lithofacies labels.

blind_force is NEVER loaded (checked explicitly against split_assignment.csv names,
belt-and-suspenders on top of the project's existing load_well refusal).
"""
import json, hashlib, sys, time
from pathlib import Path
sys.path.insert(0, "src")
sys.path.insert(0, "scripts/basinshift")

import numpy as np
import pandas as pd

import eval_harness as EH
from lithogpt2.pipeline.trend import (
    fit_athy_trend, carbonate_gate, density_from_porosity, sonic_from_porosity,
    AthyTrend,
)
from lithogpt2.pipeline.harmonize import HarmonizedWell
from lithogpt2.config import HarmonizationConfig

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift"

# FORCE 2020 lithology codes (public competition documentation; all 12 codes present
# in data/raw/force2020/train.csv accounted for).
FORCE_LITH_NAMES = {
    30000: "Sandstone", 65030: "Sandstone/Shale", 65000: "Shale",
    80000: "Marl", 74000: "Dolomite", 70000: "Limestone", 70032: "Chalk",
    88000: "Halite", 86000: "Anhydrite", 99000: "Tuff", 90000: "Coal", 93000: "Basement",
}
CARBONATE_CODES = {70000, 70032, 74000}   # Limestone, Chalk, Dolomite
# Marl (80000) is mixed clay-carbonate; reported separately, not counted as carbonate
# ground truth (avoids overstating precision/recall on a debatable inclusion).

sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str)
BLIND_NAMES = set(sp[sp.split == "blind_force"].well_id) | set(sp[sp.split == "blind_force"].safe_name)


def log(*a):
    print(" ".join(str(x) for x in a), flush=True)


def gather_basin_nphi(pool_key):
    """(tvd_m, nphi) pairs, finite only, from a basinshift TRAIN pool."""
    zs, phis = [], []
    for (src, safe, wid) in EH.POOLS[pool_key]:
        df = EH.load_well(src, safe, wid)
        z = df["depth_m"].to_numpy()
        phi = df["NPHI"].to_numpy()
        v = np.isfinite(z) & np.isfinite(phi)
        zs.append(z[v]); phis.append(phi[v])
    return np.concatenate(zs), np.concatenate(phis)


def force_train_wells():
    """FORCE train.csv rows for the 98 project-train wells only. Explicit blind_force
    name check (belt-and-suspenders on top of the split filter itself)."""
    df = pd.read_csv(ROOT / "data/raw/force2020/train.csv", sep=";")
    train_names = set(sp[(sp.source == "force2020") & (sp.split == "train")].well_id)
    assert not (train_names & BLIND_NAMES), "REFUSED: blind_force name leaked into train set"
    df = df[df["WELL"].isin(train_names)]
    assert not set(df["WELL"].unique()) & BLIND_NAMES, "REFUSED: blind_force well in loaded data"
    return df, sorted(train_names)


def build_harmonized_well(well_df, well_id):
    """Minimal HarmonizedWell for the carbonate-gate check, built directly from a
    FORCE train.csv well slice (already in canonical units/column names)."""
    well_df = well_df.sort_values("DEPTH_MD")
    depth = well_df["DEPTH_MD"].to_numpy(dtype=np.float64)
    steps = np.diff(depth)
    grid_step = float(np.median(steps[steps > 0])) if len(steps) else 0.1524
    curves, masks = {}, {}
    for c in ["GR", "RHOB", "NPHI", "DTC", "PEF", "SP", "CALI", "RDEP", "RMED", "RSHA", "DTS"]:
        if c in well_df.columns:
            v = well_df[c].to_numpy(dtype=np.float64)
            curves[c] = v
            masks[c] = np.isfinite(v)
        else:
            curves[c] = np.full(len(depth), np.nan)
            masks[c] = np.zeros(len(depth), dtype=bool)
    return HarmonizedWell(
        well_id=well_id, source="force2020", depth_m=depth, grid_step_m=grid_step,
        curves=curves, masks=masks, present_curves=list(curves.keys()), usable=True,
    )


def main():
    t0 = time.time()
    log("=== R9 physics prior: fit Athy trend per basin group (TRAIN wells only) ===")

    trends = {}
    for basin, pool_key in [("kgs", "kgs_train"), ("nlog", "nlog_train"), ("force2020", "force_train")]:
        z, phi = gather_basin_nphi(pool_key)
        t0b = time.time()
        trend = fit_athy_trend(z, phi, basin_group=basin)
        trends[basin] = trend
        log(f"[{basin}] n={len(z)} phi0={trend.phi0:.4f} lambda_m={trend.lambda_m:.1f} "
            f"fit_time={time.time()-t0b:.1f}s")

    # derived transforms, reported for completeness (density/sonic from the fitted trend)
    derived = {}
    for basin, trend in trends.items():
        z_sample = np.linspace(500, 4000, 5)
        phi_sample = trend.phi0 * np.exp(-z_sample / trend.lambda_m)
        derived[basin] = dict(
            depth_samples=z_sample.tolist(), phi_samples=phi_sample.tolist(),
            rhob_from_phi=density_from_porosity(phi_sample).tolist(),
            dtc_from_phi=sonic_from_porosity(phi_sample).tolist(),
        )

    log("=== Carbonate gate validation against FORCE 2020 lithofacies (train wells only) ===")
    force_df, train_names = force_train_wells()
    log(f"FORCE train wells for validation: {len(train_names)}")

    config = HarmonizationConfig.load()
    force_trend = trends["force2020"]

    tp = fp = tn = fn = 0
    marl_flagged = marl_total = 0
    n_wells_scored = 0
    for wid in train_names:
        wdf = force_df[force_df["WELL"] == wid]
        if len(wdf) < 20:
            continue
        hw = build_harmonized_well(wdf, wid)
        washout_masks = {"PEF": np.ones(len(hw.depth_m), dtype=bool)}  # no washout data in train.csv; treat as clean
        confidence = carbonate_gate(hw, washout_masks, config, fitted_trend=force_trend,
                                    trend_curve_name="NPHI")
        gated = confidence < 0.5   # gate fired (flagged as carbonate/invalid)

        facies = wdf.sort_values("DEPTH_MD")["FORCE_2020_LITHOFACIES_LITHOLOGY"].to_numpy()
        if len(facies) != len(gated):
            continue
        is_carbonate = np.isin(facies, list(CARBONATE_CODES))
        is_marl = facies == 80000

        tp += int(np.sum(gated & is_carbonate))
        fp += int(np.sum(gated & ~is_carbonate & ~is_marl))
        tn += int(np.sum(~gated & ~is_carbonate & ~is_marl))
        fn += int(np.sum(~gated & is_carbonate))
        marl_flagged += int(np.sum(gated & is_marl))
        marl_total += int(np.sum(is_marl))
        n_wells_scored += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    marl_flag_rate = marl_flagged / marl_total if marl_total > 0 else None

    log(f"wells scored: {n_wells_scored}")
    log(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    log(f"precision={precision} recall={recall}")
    log(f"Marl (80000, excluded from ground truth) flag rate: {marl_flag_rate} "
        f"({marl_flagged}/{marl_total})")

    result = dict(
        computed_at="R9 physics prior, ATCE Phase 7 (2026-07-26)",
        trends={b: dict(phi0=t.phi0, lambda_m=t.lambda_m, basin_group=t.basin_group)
                for b, t in trends.items()},
        derived_transforms=derived,
        carbonate_gate_validation=dict(
            n_wells_scored=n_wells_scored, tp=tp, fp=fp, tn=tn, fn=fn,
            precision=precision, recall=recall,
            marl_flag_rate=marl_flag_rate, marl_flagged=marl_flagged, marl_total=marl_total,
            carbonate_codes_used={str(k): v for k, v in FORCE_LITH_NAMES.items() if k in CARBONATE_CODES},
            note="Marl (80000) is mixed clay-carbonate, excluded from ground-truth carbonate "
                 "set and reported separately rather than counted toward precision/recall.",
        ),
        pinned_bounds=dict(phi0_bounds=[0.2, 0.7], lambda_bounds_m=[500.0, 5000.0],
                           pef_carbonate_threshold=config.prior_gate.pef_carbonate_threshold,
                           residual_variance_gate_z=config.prior_gate.residual_variance_gate_z),
        total_wall_s=round(time.time() - t0, 1),
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    out_path = OUT / "r9_physics_prior_2026-07-26.json"
    out_path.write_text(payload)
    sha = hashlib.sha256(payload.encode()).hexdigest()
    (OUT / "r9_physics_prior_2026-07-26.sha256").write_text(sha + "\n")
    log(f"WRITTEN {out_path}")
    log(f"sha256: {sha}")
    log(f"total_wall_s: {result['total_wall_s']}")


if __name__ == "__main__":
    main()
