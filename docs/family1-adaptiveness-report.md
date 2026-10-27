# When to change the edit search or the hard-pair finder

2026-10-26. Graph generation and exhaustive references use **k=N/A**. Finder
results below use **joint k**, meaning all four symbols 00,01,10,11 and
4^k leaves per complete window.

Follow-up: the [finder-strategy report](family1-finder-strategies-report.md)
implements a stronger exact/heuristic pipeline (exact k=N/A, joint k=4,
beam 16). It passes the 20-winner within-one calibration and recovers the
hard m=6 cases exactly, while broader m=7 counterexamples remain. The
controlled candidate-policy results below retain their original settings.

We should change the edit strategy first when the candidate pool misses true
champions. The exhaustive benchmark supports broadening the previous-size
parent set before increasing edit radius. But the present pair finder also
needs work: its errors and misses are too large to rank hard graphs reliably.
Changing candidate generation does not correct an inflated pair length on
a graph already in the pool.

Champion rarity is useful background, but a crowded or quiet top band does
not identify which component failed. We tested both changes separately, both
together, and the actual crowding gate. The gate can fail to request either
change when both are needed.

## Ground truth and experiment boundaries

The references are the complete exhaustive findings, including every tie:

| m | Rooted classes | Exact maximum H | Champion rooted classes |
|---|---:|---:|---:|
| 1 | 1 | 1 | 1 |
| 2 | 6 | 3 | 1 |
| 3 | 57 | 6 | 2 |
| 4 | 678 | 10 | 1 |
| 5 | 10,398 | 15 | 5 |
| 6 | 192,181 | 23 | 2 |
| 7 | 4,166,855 | 34 | 8 |

These are exact-reference results, **k=N/A**. The m=7 champions comprise four
underlying shapes. Its complete certificate proves H≤33 for every other
rooted class. This supplies complete champion membership, but does not give
an exact numerical H for every nonchampion.

We regenerated the complete m=5 exact run and matched its entire score
histogram and winner keys to the preserved exhaustive findings. Exact
per-graph truth is available locally through m=5. Full older journals are
absent from the checkout; their hashes and the surviving compact certificates
are recorded in the artifacts.

All candidate generation and search choices were deterministic. Generation
used only previous-size parents, target size, radius and fixed rules; target
winner membership was joined after the candidate key sets were sealed.
Finders received graph tables and fixed parameters, without reference
scores or reference word pairs.

We generated 20 complete neighborhoods, with fixed-root and all-root views
giving 40 comparisons: radius 1 for target m=2..7, and radius 2 for m=2..5.
Every member was evaluated: exact scoring through m=5 (**k=N/A**), and full
joint **k=2** baseline queries on all 11,693 m=6 and 13,329 m=7 union members.
There were no unevaluated candidate keys. The independent
[evaluation audit](../results/family1-adaptiveness-20261026/evaluation-audit.json)
covers 36,162 distinct graphs, replays 20,387 final pairs on 1,142,914
original static-mask coordinates, and checks 25,468,194 prefix updates.
A completed bounded query may still miss a pair; those misses remain recorded.

## Changing the edit strategy with the finder fixed

Parents were either every previous-size champion or every previous-size
graph with exact H at least the previous maximum minus two. Parent-set
completeness through m=6 was checked against the exhaustive histograms.
Root closure is a separate operation after root-fixed edits; it is not
silently counted as a zero-cost edit.

The decisive m=7 comparison is:

| Complete radius-1 strategy | Candidates | True champions present / 8 |
|---|---:|---:|
| Two m=6 winners, fixed root | 123 | 1 |
| Two m=6 winners, all roots | 391 | 3 |
| All 69 m=6 parents with H=21..23, fixed root | 3,581 | 8 |
| All 69 m=6 parents with H=21..23, all roots | 13,329 | 8 |

These are generation/coverage measurements, **k=N/A**. Broadening parents
recovers the missing winners; changing the pair finder cannot recover graphs
that were never generated. At m=7 the fixed-root broader-parent pool is also
smaller than its root closure and already contains every winner.

Increasing radius alone is less dependable. At m=5, winner parents with
complete radius 2 and all roots contain 1,510 candidates and only 3 of the
5 winners. Near-top parents with radius 1 and fixed roots contain 1,065
candidates and all 5 winners. Near-top parents with radius 1 and all roots
recover every exhaustive winner tie for every target m=2..7.

All pools matched an independent Python enumeration of the relevant
insertion and retarget paths. No generation cap or interruption occurred.
See the [40 coverage rows](../results/family1-adaptiveness-20261026/edit/coverage.csv)
and the [coverage figure](../output/figures/family1-adaptiveness/coverage.svg).
These retrospective findings support the parent policy; they do not prove
it captures unknown m=8 or m=9 champions.

## Changing the finder on the same graphs

The fixed-pool matrix has 1,005 distinct graphs: the complete universes
through m=4, all 139 exact m=5 near-top parents, all 69 exact m=6 near-top
parents, and the preserved 55-row m=7 upper-compatible frontier. That last
frontier contains eight exact winners and 47 bounded nonwinners; it is not
55 proven near-top graphs.

Each graph ran at joint **k=2,4,6**, with total-D and experimental
permutation-first ranking. All 124 m=6,7 frontier graphs also ran at joint
**k=8** with both rankings. Every query used divergence startup c=2
(14 common-prefix/first-difference starts enumerated), beam 1, diagonal and unequal
beams 0, maximum length 80, target upper 0, and 2,000,000 expansions per
attempt. All evaluated windows were complete; no expansion cap was reached.
Later starts can be skipped or their lengths capped only when a pair actually
found in that query proves they cannot improve the current upper.

| Fixed pool | Joint k / score | Misses | Pairs with L=H | Largest L−H among positives |
|---|---|---:|---:|---:|
| All 678 m=4 graphs | 2 / total D | 28 | 468 | 7 |
| All 678 m=4 graphs | 4 / permutation first | 0 | 609 | 3 |
| All 678 m=4 graphs | 6 / total D | 0 | 656 | 2 |
| Eight m=7 winners | 8 / total D | 8 | 0 | — |
| Eight m=7 winners | 8 / permutation first | 3 | 0 | 43 |

Thus joint k=6 reaches the empirical within-two criterion on the complete
m=4 universe, but it does not establish that accuracy at larger sizes.
Even joint k=8 with permutation priority gives the m=7 winner lengths
38,45,miss,miss,miss,41,77,44 against exact H=34.

Startup coverage is also part of the finder treatment. The separate
[joint k=8, c=7 diagnostic](../results/hard-pair-joint-benchmark-20261026/deep-startup-summary.json)
enumerates all 510 starts and finds all eight m=7 winners with permutation
priority, but returns lengths 38..48, still 4..14 above H=34. The controlled
c=2 matrix here does not isolate startup limits from ranking errors.

Increasing k is not monotone. Across the 1,005 fixed cases, independently
replacing total-D k=2 by total-D k=4 loses four existing positives and worsens
16 finite lengths. Refinement must retain the minimum of all previously
verified uppers. Its cost includes both queries, including unsuccessful work.
The [finder tables](../results/family1-adaptiveness-20261026/finder/summary.json)
retain all 6,278 queries, every miss, and actual words and full traces for
every final positive.

The earlier [generic benchmark](../results/hard-pair-joint-benchmark-20261026/README.md)
also tests saved arbitrary DFA families and complete unions of their Family 1
closures. Joint k=8 solves all 31 small new fixtures exactly under each
tested ranking/startup mode. Those easier cases do not establish accuracy
on the hard Family 1 graphs used here.

The same problem appears in the complete m=7 edit pool, not only on selected
champions. One graph has joint k=2 total-D upper 67 but joint k=4
permutation-first upper 17. The earlier upper exceeds its actual H by at
least 50; the exact H is not claimed. Its
[k=2 pair](../output/figures/family1-adaptiveness/m7-inflated-k2/witness.svg)
and [k=4 pair](../output/figures/family1-adaptiveness/m7-refined-k4/witness.svg)
are recorded beside their graphs and D traces. This is a post hoc illustration;
the complete tables, including failures, determine the comparison.

## Both changes, with cost and false survivors

We scored every member of the 13,329-class m=7 pool at joint k=2 total D,
k=4 total D, and k=4 permutation first. The primary controlled comparison
starts with the 123 fixed-root winner-parent candidates and broadens to
3,581 fixed-root near-top-parent candidates. Finder refinement below means
the minimum verified upper from total-D **k=2** and permutation-first **k=4**.

| Forced adjustment | Joint k used | Candidates | True winners present / 8 | Misses | False survivors | Expanded nodes |
|---|---|---:|---:|---:|---:|---:|
| Baseline | 2 | 123 | 1 | 112 | 117 | 1,262,272 |
| Edit strategy only | 2 | 3,581 | 8 | 2,934 | 3,407 | 35,859,156 |
| Finder only | 2 and 4 | 123 | 1 | 13 | 99 | 7,872,416 |
| Both | 2 and 4 | 3,581 | 8 | 378 | 2,709 | 224,433,644 |

For this retrospective audit, a graph survives if it has no pair or its
best verified upper is at least the known maximum 34. A false survivor is
a certified nonwinner still satisfying that rule. Every actual winner
present in a pool survives. The reference cutoff is used only after the
queries; it is not given to the finder.

Edit broadening improves coverage, while finder refinement reduces misses
and false survivors on the same graphs. The larger false-survivor count
after broadening reflects the much larger pool. Even both changes leave
2,709 known nonwinners unresolved by this cutoff. These configurations are
not ready to identify near-shortest pairs reliably.

The table is a forced factorial comparison, not a claim that the adaptive
gate chose these actions. See the [cost/quality figure](../output/figures/family1-adaptiveness/policy.svg),
[forced cells](../results/family1-adaptiveness-20261026/policy/m7/forced-factorial.csv)
and [actual gated cells](../results/family1-adaptiveness-20261026/policy/m7/crowding-gated.csv).

## Why rarity alone does not choose the adjustment

We tested the historical rule: count every finite upper within two of the
largest finite upper, and adapt if the count is at least three. Misses are
tracked separately, never counted as found champions.

* The initial 123-class m=7 pool at joint k=2 total D has only two top-band
  results, both nonwinners, and 112 misses. The gate does nothing, leaving
  candidate coverage at 1/8.
* The broader 3,581-class pool at the same joint k=2 has only one top-band
  result and 2,934 misses. A severe outlier makes the band less crowded.
* On the complete m=4 universe, joint k=2 total D has nine top-band results,
  all nonwinners, while missing the actual champion.
* With an exact finder, k=N/A, the m=4 top band of width two contains 48
  graphs, despite having only one champion. A larger band count can
  accompany better pair estimates.

A band of width two counts near-top graphs as well as champions.
There are also five actual rooted champions at m=5 and eight at m=7, so
three is not a valid universal bound even for an exact zero-width band.
Root multiplicity and deliberate enrichment of edit neighborhoods further
separate their frequencies from the global rarity rate.

The standalone finder matrix also records an exploratory count≥3 plus
10%-of-pool flag. That arbitrary flag is not the historical policy tested
above and is not a validated quality test.

## Recommended deterministic policy

1. **Broaden parents before increasing radius.** Use the complete prior-size
   near-top set when exact scores exist. Include root closure as an explicit
   stage; it is required for all-tie recovery at some small sizes. Evaluate
   every member of each declared neighborhood and reuse intersection results.
2. **Keep the finder fixed for candidate-policy comparisons.** Measure
   coverage and all-tie recall against exhaustive answers, independently of
   the heuristic ranking. This honors the preference to change the edit
   strategy first without disguising finder errors.
3. **Audit the finder independently.** Misses must request review even when
   the top band is quiet. Requery the entire declared unresolved audit set
   under a frozen refinement configuration; retain every earlier positive.
   Evaluate misses, exact gaps where known, champion retention and total work.
   Do not stop refinement merely because the apparent champions become rare.
4. **Require the accuracy benchmark before trusting m=8 ranks.** The present
   joint k=2,4,6,8 configurations fail on certified hard cases. A stronger
   finder needs testing on those cases and the previously saved arbitrary-DFA
   and complete-closure fixtures. Enlarging k or changing its score is not
   automatically an improvement.

This policy direction is supported by the controlled tests; a replacement
adaptive trigger has not yet passed a held-out quality benchmark. At m=8
the current length-50 pair remains a verified upper, and 49 remains a working
estimate (the historical pair's producing common-suffix k is unknown).
This experiment establishes neither its shortestness nor a better
global m=8 case. It does not justify proceeding to m=9 with a claimed
one-or-two-step finder error.

The [artifact index and reproduction instructions](../results/family1-adaptiveness-20261026/README.md)
include all source hashes, complete candidate evaluations, pair certificates,
misses and figures.
