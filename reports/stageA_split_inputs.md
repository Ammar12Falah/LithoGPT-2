# Stage A: Split Input Verification (on the record, nothing hashed)

Date: 2026-07-11

## KGS coordinate join (ruling 1, via ks_las_files.zip)
- Key: our well_id (LAS-file KID = filename stem) matched to the URL filename stem in
  the KGS LAS-files registry (ks_las_files.zip, KGS_ID column is a DIFFERENT well-KID; 0 overlap).
- Sample join: 20/20. Corpus join: 9305/9307 = 99.98%.
- Unjoined -> TRAIN (residual policy): 2 wells: ['1046111018', '1055298308']
- Coordinates + PLSS (township-range-section) present in-file. Datum NAD27, recorded, no transform.
- Crosswalk: data/splits/kgs_coord_crosswalk.csv  sha256: 3b074650a482208f6877ca8050c94822d27d10edd87781567fa10ca2555cb653

## FORCE (ruling 2)
- 98 train + 10 open + 10 blind = 118, assertion PASSED (live files reconcile with pinned.json).
- Names extracted (names only; blind log-data/labels never loaded outside scoring).
- open-10: 15/9-14, 25/10-10, 25/11-24, 25/5-3, 29/3-1, 34/10-16 R, 34/3-3 A, 34/6-1 S, 35/6-2 S, 35/9-8
- blind-10: 15/9-23, 16/2-7, 16/7-6, 17/4-1, 25/10-9, 31/2-10, 31/2-21 S, 34/3-2 S, 35/11-5, 35/9-7

Both inputs verified. Ready for Stage B split build once CI-green on the runner is confirmed.
