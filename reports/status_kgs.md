# KGS ingester status note

Shipped:
- KGS ingester built against verified endpoints (docs/KGS_ACCESS.md): the
  metadata index ks_las_files.zip and the per-year LAS archive ZIPs under
  PRS/Scans/Log_Summary/. Functions: fetch_index (download + unzip), parse_index
  (delimiter-sniffing, columns exposed as-is, none invented), fetch_archives
  (resumable, checksummed, per-year), unpack_las (extract .las from archives),
  and ingest (index -> archives -> unpack) with --dry-run, --index-only,
  --years, verified via `python -m lithogpt2.ingest.kgs --dry-run`.
- ARCHIVE_ZIPS pins each year zip's size and file count from the live listing.
  RECOMMENDED_G1_YEARS = [2024.zip, 2014.zip, 2016.zip] = ~9,324 LAS files,
  which clears the G1 5,000-well target in three downloads.
- 6 KGS unit tests (index parse comma + tab, unknown-year rejection, archive URL
  construction, G1-subset sizing, dry-run), no network. Suite at 36 passing,
  ruff clean.

Verified facts (from KGS pages, 4 July 2026):
- 21,780 digital LAS wireline logs as of 31 Dec 2024 (the G1 volume anchor).
- LAS free after a two-year confidentiality period for public service and
  research (https://www.kgs.ku.edu/Publications/Bulletins/LA/02_digital.html).
- Redistribution UNCLEAR / partly restricted: some KGS-hosted data is
  IHS-licensed and non-redistributable; posture stays pipeline + weights, no raw
  mirror. Attribution: Kansas Geological Survey (KGS), University of Kansas.

Not guessed: two archive hrefs were confirmed explicitly (2001_2005.zip,
2006_2011.zip); the other year zips are listed in that same directory and share
the confirmed base path. The ks_las_files index columns are read from the file
at run time (sniffed), not assumed.

Blocked: nothing. A live run downloads several GB, so it executes on a pod with
open internet (any CPU pod). No GPU, no RunPod spend.

Spend cumulative: 0 A40-hours, 0 USD.

Next: run the KGS G1 subset on the pod (a few minutes to tens of minutes,
download-bound), unpack LAS, then harmonize + QC the KGS wells through the same
pipeline used for FORCE, which produces the cross-continent QC-passing count for
Gate G1. NLOG slots in once the two DevTools URLs arrive; it is not on the G1
path.
