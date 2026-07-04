"""Typed loader for configs/mnemonic_aliases.yaml.

This module is the single programmatic entry point to the harmonization and
QC configuration. Nothing else in the codebase parses the YAML directly; they
go through :class:`HarmonizationConfig` so that the alias table, unit
conversions, range gates, transforms, and prior-gate thresholds have exactly
one source of truth.

Contract:
  - The alias table is authoritative and is only ever *extended from observed
    data*, never guessed (handoff Section 4.3). This loader does not invent
    aliases; it exposes what the YAML declares and flags anything unmapped.
  - Unit conversions are multiplicative factors applied *before* range gates.
  - Range gates set out-of-range samples to missing, never clip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Repo root is three parents up from this file: src/lithogpt2/config.py -> repo/
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "mnemonic_aliases.yaml"


@dataclass(frozen=True)
class CurveSpec:
    """Specification for one canonical curve."""

    canonical: str
    aliases: tuple[str, ...]
    unit: str
    valid_range: tuple[float, float]
    transform: str  # "none" or "log10"
    trend_curve: bool
    convert: dict[str, float] = field(default_factory=dict)
    washout_sensitive: bool = False
    optional: bool = False


@dataclass(frozen=True)
class AuxCurveSpec:
    """Specification for an auxiliary QC-only curve (e.g. BS bit size).

    Auxiliary curves are harmonized and kept for QC (washout gate) but are
    never modeling targets and never count toward the canonical curve set or
    the minimum-usable-interval check.
    """

    canonical: str
    aliases: tuple[str, ...]
    unit: str
    valid_range: tuple[float, float]
    transform: str
    convert: dict[str, float] = field(default_factory=dict)
    role: str = "qc_only"
    used_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriorGate:
    pef_carbonate_threshold: float
    residual_variance_gate_z: float
    emit_confidence_channel: bool


@dataclass(frozen=True)
class QCParams:
    hampel_window: int
    hampel_n_sigmas: int
    hampel_log_modified_fraction: bool
    washout_cali_minus_bitsize_in: float
    washout_flag_curves: tuple[str, ...]
    washout_require_bitsize: bool
    dedup_hash_fields: tuple[str, ...]


class HarmonizationConfig:
    """Loaded, validated view of the mnemonic/QC/prior-gate YAML."""

    def __init__(self, raw: dict, source_path: Path | None = None) -> None:
        self._raw = raw
        self.source_path = source_path
        self.version: str = str(raw["version"])

        # Depth handling.
        depth = raw["depth"]
        self.depth_canonical: str = depth["canonical"]
        self.depth_aliases: tuple[str, ...] = tuple(depth["aliases"])
        self.depth_unit: str = depth["unit"]
        self.depth_convert: dict[str, float] = dict(depth.get("convert", {}))

        # Resample grid and usability thresholds.
        self.grid_step_m: float = float(raw["grid"]["step_m"])
        self.null_values: tuple[float, ...] = tuple(float(v) for v in raw["null_values"])
        self.min_interval_m: float = float(raw["min_usable"]["interval_m"])
        self.min_curves: int = int(raw["min_usable"]["min_curves"])

        # Curves.
        self._curves: dict[str, CurveSpec] = {}
        for canonical, spec in raw["curves"].items():
            self._curves[canonical] = CurveSpec(
                canonical=canonical,
                aliases=tuple(spec["aliases"]),
                unit=spec["unit"],
                valid_range=(float(spec["valid_range"][0]), float(spec["valid_range"][1])),
                transform=spec.get("transform", "none"),
                trend_curve=bool(spec.get("trend_curve", False)),
                convert={k: float(v) for k, v in spec.get("convert", {}).items()},
                washout_sensitive=bool(spec.get("washout_sensitive", False)),
                optional=bool(spec.get("optional", False)),
            )

        # Reverse alias index: raw mnemonic (upper) -> canonical name.
        self._alias_index: dict[str, str] = {}
        for canonical, spec in self._curves.items():
            for alias in spec.aliases:
                key = alias.strip().upper()
                if key in self._alias_index and self._alias_index[key] != canonical:
                    raise ValueError(
                        f"Alias collision: {alias!r} maps to both "
                        f"{self._alias_index[key]!r} and {canonical!r}"
                    )
                self._alias_index[key] = canonical
        self._depth_alias_set = {a.strip().upper() for a in self.depth_aliases}

        # Auxiliary QC-only curves (e.g. BS). Kept separate from canonical
        # curves: harmonized for QC, never modeling targets, never counted in
        # the canonical set or the min-usable check.
        self._aux_curves: dict[str, AuxCurveSpec] = {}
        for canonical, spec in (raw.get("auxiliary_curves") or {}).items():
            self._aux_curves[canonical] = AuxCurveSpec(
                canonical=canonical,
                aliases=tuple(spec["aliases"]),
                unit=spec["unit"],
                valid_range=(float(spec["valid_range"][0]), float(spec["valid_range"][1])),
                transform=spec.get("transform", "none"),
                convert={k: float(v) for k, v in spec.get("convert", {}).items()},
                role=spec.get("role", "qc_only"),
                used_by=tuple(spec.get("used_by", ())),
            )
        self._aux_alias_index: dict[str, str] = {}
        for canonical, spec in self._aux_curves.items():
            for alias in spec.aliases:
                key = alias.strip().upper()
                if key in self._alias_index:
                    raise ValueError(
                        f"Auxiliary alias {alias!r} collides with canonical "
                        f"curve {self._alias_index[key]!r}"
                    )
                self._aux_alias_index[key] = canonical

        qc = raw["qc"]
        self.qc = QCParams(
            hampel_window=int(qc["hampel"]["window"]),
            hampel_n_sigmas=int(qc["hampel"]["n_sigmas"]),
            hampel_log_modified_fraction=bool(qc["hampel"]["log_modified_fraction"]),
            washout_cali_minus_bitsize_in=float(qc["washout"]["cali_minus_bitsize_in"]),
            washout_flag_curves=tuple(qc["washout"]["flag_curves"]),
            washout_require_bitsize=bool(qc["washout"].get("require_bitsize", True)),
            dedup_hash_fields=tuple(qc["dedup"]["hash_fields"]),
        )

        pg = raw["prior_gate"]
        self.prior_gate = PriorGate(
            pef_carbonate_threshold=float(pg["pef_carbonate_threshold"]),
            residual_variance_gate_z=float(pg["residual_variance_gate_z"]),
            emit_confidence_channel=bool(pg["emit_confidence_channel"]),
        )

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: Path | str | None = None) -> HarmonizationConfig:
        p = Path(path) if path is not None else DEFAULT_CONFIG_PATH
        with p.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls(raw, source_path=p)

    @property
    def canonical_curves(self) -> tuple[str, ...]:
        return tuple(self._curves.keys())

    def curve(self, canonical: str) -> CurveSpec:
        return self._curves[canonical]

    def auxiliary_curves(self) -> tuple[str, ...]:
        return tuple(self._aux_curves.keys())

    def aux_curve(self, canonical: str) -> AuxCurveSpec:
        return self._aux_curves[canonical]

    def resolve_aux_alias(self, raw_mnemonic: str) -> str | None:
        """Return the auxiliary curve name for a raw mnemonic, or None."""
        return self._aux_alias_index.get(raw_mnemonic.strip().upper())

    def resolve_alias(self, raw_mnemonic: str) -> str | None:
        """Return the canonical curve name for a raw mnemonic, or None.

        Matching is case-insensitive and strips surrounding whitespace. A
        return of None means the mnemonic is unmapped and must be logged to
        reports/unmapped_mnemonics.csv rather than silently dropped.
        """
        return self._alias_index.get(raw_mnemonic.strip().upper())

    def is_depth_alias(self, raw_mnemonic: str) -> bool:
        return raw_mnemonic.strip().upper() in self._depth_alias_set

    def trend_curves(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self._curves.items() if spec.trend_curve)

    def washout_sensitive_curves(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self._curves.items() if spec.washout_sensitive)
