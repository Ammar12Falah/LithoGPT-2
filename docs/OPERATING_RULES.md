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
