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
- Canonical source: Zenodo DOI 10.5281/zenodo.4351156. Scoring artifacts
  (penalty matrix, starter notebook) pinned in `configs/force2020/` with sha256
  in `configs/force2020/pinned.json`.
- Terms pages: https://zenodo.org/records/4351156 ;
  https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition ;
  https://creativecommons.org/licenses/by/4.0/ ;
  https://data.norge.no/nlod/en/2.0
- Verified counts (4 July 2026): open leaderboard test = 10 wells (matches
  handoff). The 98-well training count is NOT yet verified against the Zenodo
  release: the copy reachable in the GitHub repo
  (`lithology_competition/code/GIR/train.csv`) is a 28-well team subset. The
  ingester must verify 98 against the Zenodo download. See pending inputs.

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
- Bulk endpoint: PENDING INPUT. The exact Datacenter bulk index / per-borehole
  LAS URL pattern is not pinned; the ingester is index-driven and must be
  supplied a confirmed index (do not guess the endpoint).

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
