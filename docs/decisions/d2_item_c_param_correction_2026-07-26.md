# Item C: v1 parameter count correction, 5.2M -> 4.8M (R5 stated-cause correction, with lineage)

**Original figure (preserved for lineage):** this repo's `docs/PROJECT_DOSSIER.md` and
`docs/HANDOFF.md` state "LithoGPT v1 (SPE-234177-MS...) was a 5.2M-parameter transformer."
This matches v1's own README.md verbatim ("a 5.2M parameter Transformer").

**Stated cause of the correction:** per instruction, the published paper (SPE-234177-MS)
states 4.8M parameters in section 2.2 and Table 4. This correction is made on that
stated authority; it has not been independently re-verified against the primary paper
text in this session (SPE/OnePetro papers are paywalled and were not fetched), and
could not be independently verified against v1's own checkpoint either, since
`lithogpt_pure.pth` fails to load (item B) and its true parameter count is therefore
unknown from direct inspection.

**Correction applied:** repo language updated from 5.2M to 4.8M parameters, with this
note preserving the original 5.2M figure and its provenance (v1's own README) rather
than silently overwriting it.
