# Rolling joint lookahead experiments

All finder results here use **joint k** over 00,01,10,11. Reference H has
**k=N/A** and comes from the complete certified winner lists through m=7.
Queries receive only canonical graph keys and fixed parameters. No reference
word, score, random choice, or clock limit enters a query.

The rolling strategy enumerates every 4^k lookahead leaf from a retained
state, checks positives at every intermediate depth, then commits one paired
symbol. This differs from the original whole-block advance. Complete full
endpoint profiles are retained, including agreeing coordinates.

The experiments compare:

* Ordinary beams at joint k=3,4,5,6.
* Grouping compatible starts by length, so starts of equal age share a beam.
* Additional quotas across immediate (priority,D) tiers.
* Optional avoidance of previously expanded complete states.
* Secondary lookahead ties by the number of best leaves or summed leaf scores.
* Exact independent-coordinate joint distances, aggregated by sum or maximum,
  with or without permutation priority.

The main table evaluates all 20 certified winner graphs under 12 configurations,
with actual words, full D traces, bounds, k, work and every query retained in
[cases.csv](cases.csv). None of the complete configurations meets the
within-two gate on all 20. Canonical prefix catalogue selection remains the
main limitation; increasing k alone does not repair it.

At joint k=4, beam 256, P-first with cycle avoidance and 1,024 compatible
prefix starts, all 20 are found and 18 are within two. The eight m=7 lengths
are 35,36,35,38,34,36,34,39 against exact H=34. Ordinary beam 64 instead gives
35,37,35,38,34,36,34,39. Joint k=5 or 6 does not improve the difficult cases.
The independent-coordinate distance objectives also fail to improve this
comparison; maximum-distance-first regresses.

The later [scored-subsets.csv](scored-subsets.csv) is explicitly exploratory.
It uses the new full-D scored catalogue of 16,384 candidate seeds from complete
word layers through depth 20, selecting 512 across (length,LCP) channels.
On all eight m=7 graphs, independent rolling starts at joint k=4, beam 16
return 35,36,34,35,34,36,34,34. This matches the cheaper whole-block strategy's
quality on these cases and costs more, so it does not justify changing the
default to rolling. Grouped rolling beam 64 loses the length-35 result on one
root, returning 38. Focused k=2,3 and alternative k=4 ties do not reduce the
two remaining length-36 examples.

## Validation

Every final pair in both published CSVs was independently scalar-replayed
through every original static mask, including duplicate realizations at
coincident ports. All prefix D traces matched. The main 240 queries and 22
exploratory queries, plus the small semantic reference, require 19,498
word-pair/mask replays.

A complete-frontier check at joint k=1, beam 4096, common-prefix depth c=2
recovers the exact H of all 64 rooted classes through m=3. The distance
aggregation test independently builds each concrete DFA's reverse pair graph
and checks 7,843 joint states across 553,102 scalar coordinates, including
unmergeable pairs, coincident ports and an m=8 graph.

Expanded-state cycle avoidance is a heuristic restriction in a pruned beam;
it is not treated as an exact exclusion proof. Bounded compatible-prefix
catalogues are deterministic selections, not every compatible pair in the
enumerated word layers. No shortestness guarantee follows from a verified
finite witness.

## Reproduction

Compile the isolated experiments from the repository root:

    g++ -std=c++23 -O3 -I . tests/HardPairJointRollingBenchmark.cpp \
      Family1ExactPacked.cpp Family1LargeGraph.cpp -o out/rolling-benchmark
    g++ -std=c++23 -O3 -I . tests/HardPairJointRollingDistanceBenchmark.cpp \
      Family1ExactPacked.cpp Family1LargeGraph.cpp -o out/rolling-distance-benchmark
    g++ -std=c++23 -O3 -I . tests/Family1JointRollingDistanceIndependent.cpp \
      Family1ExactPacked.cpp Family1LargeGraph.cpp -o out/rolling-distance-independent

Each main runner accepts:

    KEYS K BEAM COMMON_DEPTH SCORE DIVERSE CYCLE_AVOID GROUPED PREFIX_COUNT NODE_CAP OUTPUT [TIE_MODE]

The ordinary runner's score is 0=total D or 1=P then D. The distance runner's
score is 0=sum then maximum, 1=maximum then sum, or 2=P then sum. Ties are
0=immediate score/lexical, 1=best-leaf count, or 2=aggregate future score.
All main runs have common-depth 7, grouped starts, max length 80, complete
prefix word layers through 16 with 65,536 words per layer, and the recorded
prefix count. These word limits concern prefix generation; the pair alphabet
remains complete at every evaluated joint window.

The graph-only key input is the 20 canonical tables in
results/family1-m1-m6/maximizers.jsonl and results/family1-m7/maximizers.jsonl,
flattened using two decimal digits per target. Historical compact one-digit
keys must be regenerated from the tables. Native outputs and frozen original
source snapshots are under out/family1-finder-strategies-20261026/rolling.
[run-manifest.json](run-manifest.json) records their fingerprints.

For example, ordinary rolling beam 64:

    out/rolling-benchmark KEYS 4 64 7 1 0 0 1 1024 16000000 OUTPUT

Run scripts/family1_rolling_strategy_report.py after regenerating all original
query outputs. It seals the complete query files before reading reference H,
verifies each witness and exports the compact tables.
