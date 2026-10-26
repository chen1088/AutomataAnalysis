# Adaptive finder budgets and calibration

`--max-expansions` is a budget for **one initial prefix pair**, shared by all
beam parents and all subsequent window rounds. The sampler resets it at each
outer seed. Native `module_stats.expanded_nodes` sums the work across seeds.
This audit reads the current code and existing results; it runs no new search.

The relevant code is [the generic finder](../HardPairFinder.h), especially
lines 247-258 and 340-389, and [the Family 1 adapter](../family1_sample.cpp),
lines 1198-1232. Each call to `append_common` in the window DFS consumes one
expansion. Prefix preprocessing, initial-pair simulation, viability/distance
analyses, exact-tail BFS, successful tail replay and scalar witness validation
are outside that counter. Exact tails have their own state budget and at most
16 calls per seed.

## Full window cost

Without pruning or an earlier goal, a binary window of span k visits
`2^(k+1)-2` child nodes and has `2^k` leaves. The effective span is
`min(k, remaining_suffix_length)`. `window_blocks` counts **leaves visited**,
not complete window rounds. For k16, one full window contributes 131,070
expansions and 65,536 blocks.

The first round has one beam parent. For an unpruned suffix budget S and beam
width W, the exact append-count ceiling is computed by:

```text
parents = 1; count = 0
while S > 0:
    span = min(k, S)
    count += parents * (2^(span+1)-2)
    parents = min(W, parents * 2^span)
    S -= span
```

For a pair-length cap at most 51, S=50 is conservative because the initial
words have positive length. It covers the current leaders of length 52/51/50 when
each is queried below its existing upper bound.

| k | Exact ceiling, W4 | Practical budget, W4 | Exact ceiling, W16 | Practical budget, W16 |
|---:|---:|---:|---:|---:|
| 8 | 10,734 | 16,000 | 41,406 | 50,000 |
| 10 | 34,782 | 50,000 | 132,990 | 150,000 |
| 12 | 106,494 | 150,000 | 401,406 | 500,000 |
| 16 | 1,179,654 | 1,500,000 | 4,325,406 | 5,000,000 |

A 50,000 budget cannot cover an unpruned span16 window. It can cover a
complete span14 window: for example, the calibrated seven-state target cap 34
with a prefix of length 20 has only 14 suffix letters. Proof pruning or an early
hit can also make a larger window affordable. Inspect
`expansion_limits_reached`; an incomplete window alone can mean pruning or an
early successful stop. The practical budgets above bound window appends, not
wall time or exact-tail work.

## Existing seven-state evidence

The [controlled lookahead grid](../results/family1-finder-lookahead-grid-v2/README.md)
keeps 128 seeds, beam width 4, tail threshold 8, prefix coverage, cap 76 and one million expansions
per seed fixed. Only k varies. All eight graphs independently have H=34.

| Setting | Found lengths in ordinal order | Maximum L | Active top ties | H inside informal [L-2,L] |
|---|---|---:|---:|---:|
| k2 | 38,38,37,41,36,36,38,39 | 41 | 1 | 2/8 |
| k8 | 37,36,38,39,34,36,38,40 | 40 | 1 | 3/8 |
| k12 | 36,36,35,39,35,36,38,38 | 39 | 1 | 5/8 |
| k16 | 35,36,36,39,34,36,38,39 | 39 | 2 | 5/8 |

There were zero expansion-cap events across all 64 runs. Larger k reduced some
artificial leaders, but did not eliminate the ranking differences between
graphs whose true scores are equal. At k16, keeping only the two largest-L
ties would leave six genuine tied maximizers inactive. This is a selected
cohort of known maximizers, not a measurement of their frequency among graphs.
The informal L-1 point estimate and [L-2,L] band remain planning hints; the
coverage counts above are not confidence probabilities for new eight-state
graphs.

The [calibrated two-stage portfolio](../results/family1-finder-calibrated-portfolio/README.md)
eventually recovered 34 on all eight, removing those artificial differences.
Its five successful k16 invocations nevertheless accumulated 270 expansion-cap
events over their many prefix seeds. Its increased prefix coverage, common
prefix diversity, distance pruning and ranking also changed, so this outcome
cannot be attributed to k alone. Both reports and their failed/longer outcomes
remain unchanged.

## Controller implications

Recompute the active maximum and **all its ties from the retained full pool**
after every shorter witness. For example, when a leader of length 52 falls to 49,
an inactive record at length 51 becomes the estimated leader. Deactivation should
not erase its graph, prior witnesses or eligibility to reactivate. Records
without a verified length remain unresolved rather than receiving a numeric
estimate.

Record the effective suffix span, per-seed expansion budget, cap-event count,
seed/prefix coverage and wall timeout with each attempt. A crowded top band is
a useful trigger to spend more search work; the benchmark shows why the
active ranking can change as that work increases. It does not itself certify
which graph has the largest true H. Frozen PDF labels continue to use only
certified intervals until a new verified score observation is available.

Machine-readable tables, source SHA-256 pins, successful prefix/suffix lengths
and all controlled-grid measurements are in
`out/family1-adaptive-budget-audit/audit.json`.
