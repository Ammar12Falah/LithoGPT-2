from __future__ import annotations

import math


def test_version_and_grid(config):
    assert config.version == "0.1.0"
    assert math.isclose(config.grid_step_m, 0.1524, rel_tol=0, abs_tol=1e-9)
    assert config.min_curves == 3
    assert config.min_interval_m == 100


def test_canonical_curves_present(config):
    expected = {"GR", "RHOB", "NPHI", "DTC", "PEF", "SP", "CALI", "RDEP", "RMED", "RSHA", "DTS"}
    assert expected.issubset(set(config.canonical_curves))


def test_alias_resolution(config):
    assert config.resolve_alias("DEN") == "RHOB"
    assert config.resolve_alias("den") == "RHOB"  # case-insensitive
    assert config.resolve_alias("  DENS ") == "RHOB"  # whitespace-insensitive
    assert config.resolve_alias("ILD") == "RDEP"
    assert config.resolve_alias("HCAL") == "CALI"
    assert config.resolve_alias("NOT_A_REAL_MNEMONIC") is None


def test_depth_alias(config):
    assert config.is_depth_alias("MD")
    assert config.is_depth_alias("DEPT")
    assert not config.is_depth_alias("GR")


def test_transforms_and_trend_flags(config):
    assert config.curve("RDEP").transform == "log10"
    assert config.curve("GR").transform == "none"
    assert set(config.trend_curves()) == {"RHOB", "NPHI", "DTC", "DTS"}
    assert "RHOB" in config.washout_sensitive_curves()


def test_prior_gate(config):
    assert config.prior_gate.pef_carbonate_threshold == 4.0
    assert config.prior_gate.residual_variance_gate_z == 3.0
    assert config.prior_gate.emit_confidence_channel is True


def test_no_alias_collisions_loaded(config):
    # Loading succeeded in the fixture; assert the reverse index is 1-to-1.
    seen: dict[str, str] = {}
    for canonical in config.canonical_curves:
        for alias in config.curve(canonical).aliases:
            key = alias.upper()
            assert key not in seen or seen[key] == canonical
            seen[key] = canonical
