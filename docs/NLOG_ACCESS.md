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
- Borehole index (UI): the Data center overview,
  https://www.nlog.nl/datacenter/brh-overview , and the interactive map,
  https://www.nlog.nl/nlog-mapviewer/ .
- Backing GIS server (the clean, queryable borehole index, no HTML scraping):
  an ArcGIS server under https://www.gdngeoservices.nl/arcgis/rest/services/nlog .
  This is the preferred index source: an ArcGIS feature layer returns every
  borehole with attributes as JSON, paginated, which becomes the ingester's
  well list.
- Log file identity: NLOG log files are named `NLOG_LIS_LAS_{fileid}_...`
  (example: `NLOG_LIS_LAS_7857_FMS_DSI_MAIN_LOG.DLIS`) and NLOG serves
  individual assets by numeric id (example: the Shell legend at
  https://www.nlog.nl/media/3367 ). So a per-borehole download resolves to a
  file-id endpoint, not a per-well guessable path.
- Whole-dataset spreadsheet: exists only for non-log datatypes (deviation
  surveys, gas composition, porosity/permeability, Rock-Eval, stratigraphy,
  vitrinite) at
  https://www.nlog.nl/sites/default/files/2026-06/thematische_data_boringen.zip .
  It does NOT contain LAS, so it is not the log source.
- Terms: https://www.nlog.nl/en/data and https://www.nlog.nl/en/disclaimer .
  Raw-redistribution license remains UNCLEAR (no named open license found), so
  the posture stays pipeline + weights + attribution, no raw mirror. Credit:
  "NLOG / TNO Geological Survey of the Netherlands, Ministry of Economic Affairs."

## Two URLs to confirm (one-time, not guessed)

1. The exact ArcGIS borehole layer query URL under the `nlog` folder above (the
   FeatureServer or MapServer layer whose `.../query?where=1=1&outFields=*&f=json`
   returns the borehole list). Browsing the folder root in a normal browser
   lists the services and their layers.
2. The per-file LAS download URL that the Data center returns in a borehole's
   file list (the file-id endpoint the "download" button points at).

### Two-minute capture

1. Open https://www.nlog.nl/datacenter/brh-overview , pick any released
   borehole, and open its Logs (LIS/LAS) tab.
2. Open the browser DevTools Network panel (F12), then click a LAS download.
3. Copy two request URLs from the Network list: the JSON call that returns the
   file list for that borehole, and the actual file-download URL. Paste both
   back here.

With those two URLs, `nlog.py` gets a small index-builder (query the ArcGIS
layer for the well list, resolve each borehole's LAS file-id, write the
`well_id,las_url` index) and the existing resumable fetch loop runs the bulk
job. Expected wall-clock at one request per two seconds is hours; it runs as a
resumable background job.

## Fallback if the capture is blocked

If the office network blocks DevTools capture, the same two URLs can be read by
browsing the ArcGIS services directory
(https://www.gdngeoservices.nl/arcgis/rest/services/nlog) in a browser to get
the borehole layer, and by inspecting one borehole's file list in the Data
center. Either path confirms the endpoints without guessing.
