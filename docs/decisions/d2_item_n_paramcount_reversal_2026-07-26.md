# Item N: parameter count verified from code -- REVERSES item C (2026-07-26)

Per instruction: "Do not defer to the paper: it is the artifact under
correction, and two of its published figures are already confirmed wrong [W1
column, item D; 32% relative-bias denominator, item D]. If the computed count
contradicts 4.8M, REVERSE item C."

## Method

Built the Arm A model (`LithoGPTv15`, exactly as specified: 6 layers, 8 heads,
d_model=256, context=512, vocab k=1000, 4 input features) directly from
`scripts/atce/atce_ablation.py` and read `sum(p.numel() for p in
model.parameters())` with a full per-parameter breakdown via
`named_parameters()`. This is the architecture as literally built and trained
for item J's Arm A -- not a hand recomputation.

## Full breakdown (untied, as built)

```
tok_embed.weight   (1000, 256)   256,000
pos_embed.weight   (512, 256)    131,072
blocks (x6, 789,760 each)      4,738,560
ln_f                                 512
head.weight+bias (1000,256)+(1000) 257,000
                            ----------------
TOTAL                          5,383,144
```

Confirmed **untied**: `model_a.tok_embed.weight is model_a.head.weight` ->
`False`. `pos_embed` is a learned `nn.Embedding(512, 256)`, not sinusoidal.

## Variants tested (all the ones the brief named as possible explanations)

| variant                                      | total     | vs 4.8M |
|-----------------------------------------------|-----------|---------|
| as built (untied, learned pos, with bias)     | 5,383,144 | +12.15% |
| tied (head shares tok_embed)                  | 5,127,144 | +6.82%  |
| untied + sinusoidal pos (no pos_embed params) | 5,252,072 | +9.42%  |
| tied + sinusoidal pos                         | 4,996,072 | +4.08%  |
| bias-free (all 18,152 bias params removed)    | 5,364,992 | +11.77% |
| bias-free + tied                              | 5,108,992 | +6.44%  |
| bias-free + sinusoidal pos                    | 5,233,920 | +9.04%  |
| bias-free + tied + sinusoidal pos             | 4,977,920 | +3.71%  |

**None of the eight tested variants -- including every combination of the two
mechanisms the brief suggested -- equals 4.8M.** The closest (bias-free + tied +
sinusoidal-positions) still overshoots by 3.7%, and requires stacking three
simultaneous non-default choices (no biases anywhere, tied embeddings, and
sinusoidal rather than learned positions) that are not stated anywhere in the
paper or the repo. The as-built figure (5,383,144) and the repo's original,
uncorrected claim (5.2M) are far closer to each other (2.3% apart) than either
is to the paper's stated 4.8M (11-12% apart from the as-built figure).

## Ruling: item C is REVERSED -- N closeout wording (corrected framing)

Item C (prior brief) corrected the repo's original "5.2M" to "4.8M" per
SPE-234177-MS Section 2.2/Table 4, treating the paper as authoritative over the
repo. That correction is now contradicted by an independent, code-based
computation of the exact architecture as specified (6/8/256/512/k=1000/4feat),
under every tested variant. Per the N-closeout brief's precise wording
requirement:

**5,383,144 is reported as THIS PAPER's model** -- the parameter count of the
transformer this experiment actually built, trained, and evaluated (Arm A,
untied, as-built). This is not asserted as "what v1 had": v1's source code
never existed at any point in its history (item L) and its checkpoint does not
load (items M/X), so **v1's true parameter count is UNVERIFIABLE, not simply
wrong**. Neither 4.8M nor the repo's original 5.2M can be confirmed or refuted
against v1's actual weights -- there are none to check against.

**The defensible published claim is narrower than "v1 had X parameters":** the
paper's architecture specification (6/8/256/512/k=1000/4feat) and its stated
parameter count (4.8M) are mutually inconsistent -- literally building that
architecture, under every tested variant (tied/untied embeddings, learned/
sinusoidal positions, with/without biases, and every combination), never
produces 4.8M. The closest variant (bias-free + tied + sinusoidal positions)
still overshoots by 3.7%, and requires three simultaneous non-default choices
stated nowhere in the paper or repo.

- **4.8M and the repo's original 5.2M are both preserved as superseded
  figures**, with R5 lineage below -- neither is asserted as correct, and
  neither is discarded.
- **This paper's own model has a code-verified parameter count of 5,383,144**
  (untied, as trained for Arm A/B-linear/B-abs/B2/D's shared architecture; Arm
  C's continuous head is smaller at 5,127,172), independent of either figure.

## Lineage (R5 stated-cause correction, reversing a prior R5 correction)

- Original repo figure: 5.2M -- **superseded**, unverifiable (v1 source/checkpoint
  unavailable, items L/M/X), not asserted as correct.
- Item C correction (prior brief): 5.2M -> 4.8M, cause: SPE-234177-MS Section
  2.2/Table 4 -- **superseded**, contradicted by item N's code-based count under
  every tested architectural variant; also unverifiable against v1's actual
  weights for the same reason.
- Item N closeout (this entry): stops asserting either figure as v1's true count.
  Reports this paper's own code-verified parameter count (5,383,144) as the
  operative figure for this paper's model only. States the paper's spec and its
  stated count as mutually inconsistent, and states v1's true count as
  unverifiable rather than wrong.
