# Item Y: lasio drift resolved (2026-07-26)

The boot-time pin assertion (item J's FIRST ACTION) lists `lasio` alongside
numpy/pandas/pyarrow/xgboost/scikit-learn/torch. `lasio` is not installed on
this pod (`pip freeze | grep -i lasio` empty; `python3 -c "import lasio"` ->
`ModuleNotFoundError`), and was flagged as drift rather than silently ignored.

## Resolution: recorded, not installed

`grep -rn "lasio" scripts/atce/` returns **zero matches**. The ATCE ablation
path (`scripts/atce/atce_ablation_v3.py` and everything it imports --
`load_98_train_wells`, `well_curves`, the tokenizer/model/training/generation
code) reads FORCE well data directly via `pandas.read_csv` and never touches
`lasio` at any point. `lasio` was needed earlier in this session for a
different module (`src/lithogpt2/pipeline/harmonize.py`, which is not part of
this item's execution path).

This is recorded as the entry that resolves the pin-assertion drift for item
J/K/T/U/V/W/X: `lasio`'s absence does not affect this experiment's correctness,
proven by the grep above rather than assumed. `lasio` is not installed, since
nothing in the executed path requires it.
