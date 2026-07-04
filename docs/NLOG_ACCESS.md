# NLOG Access Map

Verification date: 4 July 2026. Purpose: pin how to reach NLOG borehole logs so
the index-driven ingester (`src/lithogpt2/ingest/nlog.py`) can run. Sources are
NLOG's own pages plus published NLOG-sourced work. Two concrete URLs still need
a one-time confirmation and are flagged; they are not guessed (handoff Rule 2).

## What is verified

- NLOG is the Dutch subsurface portal, run by TNO (Geological Survey of the
  Netherlands) for the Ministry of Economic Affairs. Administrative borehole
  data is public immediately; well logs (LIS/LAS/DLIS), reports, cuttings and
  cores are released only after a statutory five-year confidentiality period.
- Borehole index (CONFIRMED, live data checked 4 July 2026): NLOG's official
  GeoServer WFS. One GetFeature call returns every borehole as GeoJSON.
    base   : https://www.gdngeoservices.nl/geoserver/nlog/ows
    layer  : nlog:gdw_ng_wll_all_utm   ("All boreholes")
    format : outputFormat=json (GeoJSON), WFS 1.0.0
  Per-borehole attributes include BOREHOLE_CODE, BOREHOLE_NAME, UWI,
  NITG_NUMBER, ON_OFFSHORE_CODE, PUBLIC_AS_OF (the confidentiality release
  date), coordinates, and URL (the mapviewer detail link ending in a numeric
  borehole id, e.g. .../nlog-mapviewer/brh/872287025). `nlog.build_index()`
  turns this into a well-list CSV and is runnable now. The same page also
  offers direct shapefile/KML/GeoJSON/GML exports of this layer.
- Log file identity: NLOG log files are named `NLOG_LIS_LAS_{fileid}_...`
  (example: `NLOG_LIS_LAS_7857_FMS_DSI_MAIN_LOG.DLIS`) and NLOG serves
  individual assets by numeric id. The mapviewer borehole id (above) is the key
  the file-list API uses.
- Whole-dataset spreadsheet: exists only for non-log datatypes (deviation
  surveys, gas composition, porosity/permeability, Rock-Eval, stratigraphy,
  vitrinite) at
  https://www.nlog.nl/sites/default/files/2026-06/thematische_data_boringen.zip .
  It does NOT contain LAS, so it is not the log source.
- Terms: https://www.nlog.nl/en/data and https://www.nlog.nl/en/disclaimer .
  Raw-redistribution license remains UNCLEAR (no named open license found), so
  the posture stays pipeline + weights + attribution, no raw mirror. Credit:
  "NLOG / TNO Geological Survey of the Netherlands, Ministry of Economic Affairs."

## One hop still to confirm (not guessed)

The per-borehole LAS file-list API: given a mapviewer borehole id (from the WFS
`URL` field), the JSON call that lists that borehole's files, and the
file-download URL it returns. This is the only piece the index does not already
provide, and it is deliberately left unpinned rather than guessed.

### Two-minute capture

1. Open a released borehole in the map viewer, e.g. one of the ids from the
   index (https://www.nlog.nl/nlog-mapviewer/brh/106507075), and open its Logs
   tab.
2. Open the browser DevTools Network panel (F12), then click a LAS download.
3. Copy two request URLs: the JSON call that returns the file list for that
   borehole, and the actual file-download URL. Paste both back here.

With those two URLs, `nlog.resolve_las_urls()` is filled in (query the file list
per borehole id, filter to LAS, write a well_id,las_url index) and
`nlog.ingest_from_index()` runs the resumable bulk fetch. Expected wall-clock at
one request per two seconds is hours; it runs as a resumable background job.
