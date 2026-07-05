# KGS alias unit and physics audit

Value ranges from a 400-well sample of the on-disk 2016 KGS LAS, 5 July 2026.

- DEN(CDL): median 2.44 g/cc, bulk density, mapped to RHOB, kept.
- GAMMA: median 20 API, gamma ray, mapped to GR, kept.
- RHOC: median 0.06, range about -0.5 to 0.3. This is a density-correction curve,
  not bulk density. Removed from RHOB.
- RLL3: median 4.37 ohm-m, resistivity. A Laterolog-3 is a moderate-investigation
  device, so it was moved from RDEP to RMED.
- CNLS: median 35 (percent), neutron porosity, mapped to NPHI. Curves with a
  percent unit convert to fraction correctly; curves with a blank unit do not
  convert and gate out. A percent-default rule for KGS neutron and the
  limestone-matrix assumption are recorded as G2 harmonization tasks.
- POR(NEU): absent from the 2016 sample, present in the deleted 2024 and 2014
  years, so its audit is deferred to the G2 reprocess.

Count impact: none on the 5,644 G1 total. RHOC values fall below the RHOB range
and contributed no coverage. Moving RLL3 relabels a resistivity curve rather than
removing one. The corrected config takes effect at the G2 reprocess.
