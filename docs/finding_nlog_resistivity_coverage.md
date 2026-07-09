# Finding for Advisor Review: NLOG Resistivity Coverage Gap

Date: 9 July 2026. Status: alias-triage window (G2, day 1-2). Seeking a decision before the corpus freeze. All numbers below are from committed reports at the current HEAD.

## Summary
The round-two alias triage surfaced a larger issue than SN alone. Canonical resistivity is mapped on only 953 of 4,996 NLOG wells (19 percent). The other 4,043 wells (81 percent) have zero mapped canonical resistivity (RDEP, RMED, RSHA all zero in reports/nlog_coverage.csv). Because resistivity is one of the most commonly acquired logs, this is very likely an alias-coverage gap, not a real absence of resistivity in the data.

## Evidence
- Wells with at least one canonical resistivity: 953 of 4,996. Source: reports/nlog_coverage.csv.
- The top three unmapped mnemonics by borehole count are all OHMM resistivity curves and none are in the current alias lists: SN (short normal, 1,536 wells), LN (long normal, 938), LATL (lateral, 721). Source: reports/nlog_unmapped_mnemonics.csv and configs/mnemonic_aliases.yaml.
- Current resistivity alias lists cover standard modern induction/laterolog names (ILD, LLD, AT90, etc.) but not the older normal/lateral tool names that dominate the NLOG unmapped list.

## Why this matters
Resistivity is a benchmark-relevant curve and a standard member of the canonical set. An 81 percent coverage gap materially affects corpus richness and the resistivity content available to the model and the benchmark. Some of these are already QC-passing wells that would gain a resistivity curve, which per prior guidance is worth more than a marginal recovered well. This is also the last exit: after the freeze the alias table is locked with the corpus, so any resistivity aliases must be decided before then.

## The complication (why this is not a quick add)
1. SN, LN, LATL are old-tool resistivities that do not map cleanly to the modern deep/medium/shallow (RDEP/RMED/RSHA) depth-of-investigation scheme. Short normal is roughly shallow, long normal roughly medium/deep, lateral deep-ish, but slot placement is genuinely ambiguous and a wrong mapping across 700 to 1,500 wells would corrupt a canonical channel.
2. These mnemonics are not recorded per-well anywhere on disk (the unmapped report is aggregated; the per-well "present" field lists only mapped canonical curves). So we cannot cheaply prove how many wells each would actually help, redundant where a well already has resistivity from another curve, valuable where it has none, without fetching and reading sample files.
3. A confirmation fetch is heavier than first estimated: the zero-resistivity wells are old and file-heavy (a 15-well sample carries about 500 files), and we cannot pre-confirm which contain SN, so the fetch is not cleanly targeted.

## Options
A. Ship as documented future work. Freeze at the current 1,812 with resistivity coverage as-is, and record the gap and the candidate mnemonics (SN/LN/LATL) in the dataset card. Lowest risk to the timeline; leaves real resistivity coverage on the floor.
B. Dedicated resistivity-alias pass before freeze. Value-check SN/LN/LATL against sample data, place them correctly, add the confident ones, and re-QC. Recovers coverage but expands the two-day window (fetching and value-checking are non-trivial for these file-heavy old wells), and carries corpus-corruption risk if slot placement is wrong.
C. Bounded middle. Value-check SN only (the highest-count, cleanest-to-place as RSHA), add it if it verifies, defer LN/LATL to documented future work. Smaller scope than B, still needs a sample fetch.

## The six confident non-resistivity aliases (independent of this decision)
Separately from resistivity, the triage found six confident, unit-verified additions ready to apply regardless of the above: RGR and ECGR to GR, SON to DTC, and RCAL/CAL1/CAL2 to CALI. These are unambiguous and carry no slot-placement risk. Recommend applying these now and re-QCing, independent of the resistivity decision.

## Recommendation
Apply the six confident aliases now. For resistivity, this is a scope-and-timeline call that affects the freeze, so it is put to you rather than decided in the window: A, B, or C. My lean is C if a resistivity pass is wanted at all, since SN is the highest-value and cleanest single addition, but I defer to your read on whether resistivity coverage justifies expanding the window or ships as documented future work.
