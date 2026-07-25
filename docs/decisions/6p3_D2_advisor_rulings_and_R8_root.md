# R8 lineage root (verbatim, as supplied by the advisor via Plan, 2026-07-25)

Per Rule 17 (rulings on disk before compute) and R5 (quote the original in full, not an
ellipsis-truncated fragment). This is the text supplied to Pod for commit; it is recorded here
verbatim and is the root of the R8 lineage that `docs/decisions/6p3_gate_ruling_e1029b20.md`
(Part D.0/D.1) already documented as unrecoverable from any prior committed artifact.

> FSQ tokenizer accepted when the median per-curve relative degradation of XGBoost-imputation
> RMSE, using tokenized-then-reconstructed inputs versus raw inputs on the dev slice, is at most
> 5 percent, with no single canonical curve above 10 percent. The bar does not move silently;
> misses are escalated with numbers.

## Lineage note

`docs/decisions/6p3_gate_ruling_e1029b20.md` Part D.0 (committed 2026-07-24) searched
exhaustively for this text and found only an ellipsis-truncated quote in Part A ("FSQ accepted
when median per-curve relative degradation... is at most 5 percent, with no single canonical
curve above 10 percent"), concluding the full original was not recoverable from any committed
artifact at that time. This file is that root text, supplied directly and committed verbatim.

The 2026-07-24 D.1 amendment (headline curves 10%->8%, non-headline unchanged at 10%, median
unchanged at 5%, symmetry guard retired) is a stated AMENDMENT to this root text, not a
replacement of it -- both are preserved, in lineage order, per Rule 17.
