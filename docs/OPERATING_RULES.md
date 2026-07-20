# LithoGPT-2 Operating Rules


## Verification scripts must fail loudly on an empty target set (added 2026-07-10)

Earned by two false-green incidents in two days (log-space unit tests that never exercised
the production path; a verify cell run from the wrong working directory that scanned nothing
and reported success). A verifier that finds nothing to check and reports success is the most
dangerous artifact this project can produce. Every verification script MUST:
- resolve its target path to an ABSOLUTE path and PRINT it,
- assert the number of items scanned is non-zero (and, where a count is known, at least a
  sane lower bound) BEFORE reporting any pass,
- prefer absolute paths over cwd-relative ones so a wrong working directory cannot silently
  empty the target set.


## Rule 13 -- Environment snapshot at every value-producing session (consolidated hardening)

Every value-producing session begins by committing an environment snapshot (pip freeze or
lockfile) alongside its outputs, so the runtime that produced an artifact is always
recoverable. Metadata is captured at run time or paid for at freeze time.

Provenance: this is the fifth instance of the same lesson (mnemonics, provenance dates,
coordinates, the vintage crosswalk, now the runtime), and it is tied to the SECOND
no-orphan-producers breach (the 88255b43 pin-completion step was unrecorded; remedied by
the regenerable seven-pin builder at commit 212faed9). Ingestion-time parser versions for
this corpus were not recorded and cannot be reconstructed; the frozen parquets are ground
truth. Rule 13 exists so a sixth instance does not occur.


## Rule 14 — Mutation counters mandatory in ingestion (v2.1+)
Any value-mutating step in ingestion/QC code (sentinel nulling, rail rule, any fill or
drop) must carry a counter that records what it mutated, into the run records, at run
time. The NLOG rail rule (_null_rail_pileup) discarded its nulled-count, making the
historical NLOG rail impact permanently unrecoverable without reopening the frozen corpus
(the eighth instance of silent-metadata-at-freeze-time). Future ingestion (v2.1 onward)
makes mutation counters non-optional. Cited to the 2026-07-20 rail-impact finding.
