# License Matrix

Verification date: 4 July 2026. Method: live web search of each source's terms
pages. Release posture default (handoff Section 4.2): pipeline + weights with
per-source attribution; no raw-data mirror unless a source clearly permits it.

Columns: may we redistribute raw files; may we redistribute derived datasets;
may we train and release weights; required attribution. UNCLEAR items are
escalation triggers (handoff Section 12.2), not to be guessed.

## FORCE 2020 (Norway, North Sea)

- Redistribute raw: YES. Well-log data is under the Norwegian License for Open
  Government Data (NLOD 2.0); lithofacies labels are under CC-BY-4.0.
- Redistribute derived: YES, with attribution (both licenses permit reuse and
  redistribution of derived work with credit).
- Train + release weights: YES.
- Required attribution: cite Bormann, P., Aursand, P., Dilib, F., Dischington,
  P., Manral, S. 2020, "2020 FORCE Machine Learning Contest"; state that logs
  are NLOD 2.0 and labels are CC-BY-4.0; use the wording "Lithofacies data was
  provided by the FORCE Machine Learning competition with well logs and seismic
  2020."
- Authoritative source for the labelled competition CSVs: the FORCE GitHub repo
  `bolgebrygg/Force-2020-Machine-Learning-competition` under
  `lithology_competition/data/` (raw.githubusercontent.com, no robots
  restriction). Files: `train.zip` (contains train.csv), plus
  `leaderboard_test_features.csv`, `leaderboard_test_target.csv`,
  `hidden_test.csv`, and `penalty_matrix.npy`. A LAS-format mirror plus NPD
  spreadsheets is on Zenodo DOI 10.5281/zenodo.4351156, but Zenodo's robots.txt
  blocks automated fetch of the file endpoints, so the LAS path is opt-in.
  Scoring artifacts are pinned in `configs/force2020/` with sha256 in
  `configs/force2020/pinned.json`.
- Terms pages: https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition ;
  https://zenodo.org/records/4351156 ;
  https://creativecommons.org/licenses/by/4.0/ ;
  https://data.norge.no/nlod/en/2.0
- Verified counts (4 July 2026, counted from the real files): train.csv = 98
  unique wells (1,170,511 rows), open leaderboard test = 10 wells (136,786
  rows), hidden test = 10 wells. This matches the handoff. The earlier 28-well
  copy (`code/GIR/train.csv`) is a team subset and the starter notebook's
  83-well figure is stale; neither is the official set.

## NLOG (Netherlands)

- Redistribute raw: UNCLEAR. NLOG data is public (managed by TNO, Geological
  Survey of the Netherlands, on behalf of the Ministry of Economic Affairs);
  well logs become public after a statutory five-year confidentiality period.
  No explicit named open-data license (e.g. CC-BY) was found on the terms
  pages, so raw redistribution is UNCLEAR. ESCALATE before mirroring raw.
- Redistribute derived: UNCLEAR (follows from the above).
- Train + release weights: LIKELY YES (data is public for use), but confirm.
  Under the default posture we train and release weights, not raw data.
- Required attribution: credit "NLOG / TNO Geological Survey of the
  Netherlands, on behalf of the Ministry of Economic Affairs."
- Terms pages: https://www.nlog.nl/en/data ;
  https://www.nlog.nl/en/boreholes ; https://www.nlog.nl/en/data-supply
- Access map: see docs/NLOG_ACCESS.md. The borehole index is CONFIRMED as
  NLOG's official GeoServer WFS (base gdngeoservices.nl/geoserver/nlog/ows,
  layer nlog:gdw_ng_wll_all_utm, GeoJSON), verified against live data;
  build_index() consumes it. One hop remains to confirm (the per-borehole LAS
  file-list API keyed by the mapviewer borehole id); the ingester is
  index-driven, so no endpoint is guessed.

## KGS (Kansas Geological Survey, kgs.ku.edu)

- Redistribute raw: UNCLEAR / likely restricted. KGS publishes free LAS for
  released wells after a two-year confidentiality period, for "public service
  and research purposes." Separately, some KGS-hosted data is third-party
  IHS-licensed and explicitly may NOT be re-packaged or disseminated to third
  parties, which shows KGS hosts mixed-rights content. Confirm the LAS logs
  themselves are not similarly encumbered before any raw redistribution.
  ESCALATE before mirroring raw.
- Redistribute derived: UNCLEAR (follows from the above).
- Train + release weights: LIKELY YES for research use; confirm. Default
  posture: pipeline + weights, no raw mirror.
- Required attribution: credit "Kansas Geological Survey (KGS), University of
  Kansas."
- Terms / index pages: https://www.kgs.ku.edu/Magellan/Logs/ (LAS index and the
  pre-created ZIP of all wells with LAS) ;
  https://kgs.ku.edu/data-resources-library-kansas-geological-survey ;
  https://www.kgs.ku.edu/Magellan/Elog/tif_zip.html (notes the IHS-licensed
  subset that is non-redistributable).
- Note: the Kansas Geological SOCIETY (kgslibrary.com, Wichita) is a different
  organization with a paid library and a user agreement; the handoff source is
  the Kansas Geological SURVEY (kgs.ku.edu, Lawrence). Do not conflate them.

## Summary

| Source | Redistribute raw | Train + release weights | Posture |
|---|---|---|---|
| FORCE 2020 | YES (NLOD 2.0 + CC-BY-4.0) | YES | may mirror raw with attribution |
| NLOG | UNCLEAR (escalate) | likely YES | pipeline + weights, no raw mirror |
| KGS | UNCLEAR / likely restricted (escalate) | likely YES | pipeline + weights, no raw mirror |

Across all three, the default posture (pipeline + weights + attribution, no raw
redistribution) is safe. The two UNCLEAR raw-redistribution rows are open
escalation items to resolve before any raw mirror.
