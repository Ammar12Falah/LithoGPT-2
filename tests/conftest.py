"""Synthetic LAS fixtures for harmonization tests.

No real well data is used in tests; these strings exercise the specific
harmonization behaviours (alias mapping, unit conversion before range gates,
null-to-missing, out-of-range-to-missing, log10, unmapped logging).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lithogpt2.config import HarmonizationConfig

# Metric well: DEPT in M, GR gAPI, RHOB g/cc, RDEP ohm.m (log10),
# one null (-999.25), one out-of-range RHOB (5.0), one unmapped curve (XYZ).
# Depths are multiples of 0.1524 so they land on the global grid.
LAS_METRIC = """~Version
 VERS.   2.0 :
 WRAP.   NO  :
~Well
 STRT.M  152.4000 :
 STOP.M  153.0096 :
 STEP.M  0.1524   :
 NULL.   -999.25  :
 WELL.   TESTWELL1 :
~Curve
 DEPT.M    : depth
 GR.gAPI   : gamma ray
 RHOB.g/cc : bulk density
 RDEP.ohm.m: deep resistivity
 XYZ.unit  : unmapped curve
~ASCII
152.4000  50.0  2.30    10.0  1.0
152.5524  60.0  2.35    20.0  1.0
152.7048 -999.25 2.40 -999.25 1.0
152.8572  70.0  5.00    40.0  1.0
153.0096  80.0  2.45   100.0  1.0
"""

# Imperial well: DEPT in FT (0.5 ft == 0.1524 m grid), DEN in kg/m3
# (alias of RHOB, must convert /1000), NPHI in pu (must convert *0.01).
LAS_IMPERIAL = """~Version
 VERS.   2.0 :
 WRAP.   NO  :
~Well
 STRT.FT 500.0 :
 STOP.FT 502.0 :
 STEP.FT 0.5   :
 NULL.   -999.25 :
 WELL.   TESTWELL2 :
~Curve
 DEPT.FT    : depth
 GR.gAPI    : gamma ray
 DEN.kg/m3  : bulk density (alias)
 NPHI.pu    : neutron porosity (percent units)
~ASCII
500.0  50.0  2300.0  15.0
500.5  55.0  2350.0  20.0
501.0  60.0  2400.0  25.0
501.5  65.0  2450.0  30.0
502.0  70.0  2500.0  35.0
"""


@pytest.fixture(scope="session")
def config() -> HarmonizationConfig:
    return HarmonizationConfig.load()


@pytest.fixture()
def metric_las(tmp_path: Path) -> Path:
    p = tmp_path / "testwell1.las"
    p.write_text(LAS_METRIC, encoding="utf-8")
    return p


@pytest.fixture()
def imperial_las(tmp_path: Path) -> Path:
    p = tmp_path / "testwell2.las"
    p.write_text(LAS_IMPERIAL, encoding="utf-8")
    return p
