# KGS Access Map

Verification date: 4 July 2026. Source: the Kansas Geological Survey's own
Magellan and PRS pages, read live. KGS is the volume anchor for Gate G1.

## What is verified

- KGS (Kansas Geological Survey, kgs.ku.edu, the University of Kansas survey in
  Lawrence) publishes digital LAS wireline logs. As of 31 December 2024 there
  were 21,780 digital LAS logs, which alone clears the G1 target of 5,000
  QC-passing wells. LAS files for released wells are free to download after a
  two-year confidentiality period, for public service and research (stated at
  https://www.kgs.ku.edu/Publications/Bulletins/LA/02_digital.html ).
- Do not confuse this with the Kansas Geological SOCIETY (kgslibrary.com,
  Wichita), a separate paid library. The source here is the SURVEY.

## Access model (bulk, cleaner than per-well)

The whole LAS corpus is published as per-year archive ZIPs, plus a metadata
index that connects LAS files to wells. So ingestion is a handful of bulk
requests, not 21,780 polite ones.

- Metadata index: https://www.kgs.ku.edu/PRS/Ora_Archive/ks_las_files.zip
  ("a pre-created file containing the data for all the wells with LAS files").
  Unzips to a delimited text file; `kgs.parse_index()` sniffs the delimiter and
  exposes the columns as-is (KID, API, lease, location, etc.) without inventing
  any.
- Per-year LAS archives, base https://www.kgs.ku.edu/PRS/Scans/Log_Summary/ :
  1999.zip, 2001_2005.zip, 2006_2011.zip, 2012.zip ... 2025.zip. Sizes and file
  counts are pinned in `kgs.ARCHIVE_ZIPS` (e.g. 2024.zip = 856 MB, 3,810 files;
  2014.zip = 1.2 GB, 3,231 files). Two hrefs were confirmed explicitly on the
  archive page (2001_2005.zip and 2006_2011.zip); the remaining year zips are
  listed in that same directory and share the confirmed base path. A full pull
  is several GB; state the wall-clock before launching.
- Recommended G1 subset (`kgs.RECOMMENDED_G1_YEARS`): 2024.zip + 2014.zip +
  2016.zip, about 9,324 LAS files, which clears 5,000 in three downloads.

## License posture

Redistribution of raw KGS LAS is UNCLEAR and stays an escalation item: some
KGS-hosted data (pre-1987 production, certain scanned/IHS-licensed material) may
not be redistributed to third parties
(https://www.kgs.ku.edu/Magellan/Elog/tif_zip.html ). The LAS wireline logs
themselves are the free public set, but under the default posture we release
pipeline + weights + attribution with no raw mirror. Attribution: "Kansas
Geological Survey (KGS), University of Kansas."

## Ingester usage

```
python -m lithogpt2.ingest.kgs --dry-run                 # plan only
python -m lithogpt2.ingest.kgs --index-only              # fetch + parse index
python -m lithogpt2.ingest.kgs                           # G1 subset + unpack
python -m lithogpt2.ingest.kgs --years 2024.zip 2016.zip # pick archives
```
