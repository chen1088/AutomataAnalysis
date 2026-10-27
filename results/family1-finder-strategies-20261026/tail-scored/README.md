# Common-tail distance as a seed-ranking preference

Both configurations use the same graph-only catalogue and fixed budgets:
complete prefix word layers through 20, at most 1,048,576 words per layer,
16,384 canonically selected compatible candidate pairs and 512 selected starts.
Candidates are ranked separately within each (length, actual LCP) channel.
Every selected pair then receives full joint **k=4**, beam 16,
permutation-first search over 00,01,10,11, maximum length 80 and 2,000,000
nodes per attempt. The exact prefix phase has **k=N/A**, depth 24,
16,777,216 words per layer and 256 MiB array-payload budget.

The new metric is the exact shortest **common suffix** needed to merge each
concrete DFA's two endpoint states. It is computed by reverse BFS with two
same-letter pair edges. Unlike independent joint distance, it depends on the
static mask and can be infinite for unequal permutation endpoints or other
unmergeable pairs.

All original masks contribute, including coincident-port multiplicities.
The two deterministic rankings are:

1. (number of infinite distances, maximum finite distance, sum of finite
   distances, D, first word, second word).
2. (number of infinite distances, sum of finite distances, maximum finite
   distance, D, first word, second word).

This is only a preference among starting pairs. Infinite common-tail distance
does not prune a joint branch: later unequal symbols remain available.

## Controlled result on all 22 development cases

Both rankings return identical final lengths:

| Measurement | Matched full-D baseline | Both common-tail rankings |
|---|---:|---:|
| Certified winner graphs tested | 20 | 20 |
| Pairs matching exact reference H | 16 | 18 |
| Winner cases within one | 18 | 20 |
| Largest winner gap L−H | 2 | 1 |
| Eight m=7 winner lengths | 35,36,34,35,34,36,34,34 | 35,34,34,35,34,34,34,34 |
| Separate m=7 case with verified prior upper 32 | 45 | 43 |
| m=8 leader with verified prior upper 50 | 53 | 52 |

The baseline has the same exact-word budget, catalogue generation and full
joint k=4/beam16 settings. Its source hashes and the two new query files are
pinned in summary.json and query-manifest.json. Both new configurations score
exactly the same catalogue bytes; their catalogue SHA256 values match for
every case where the exact phase does not return first.

“Matching H” is measured against separate exhaustive findings. A joint query
can return an optimal pair without itself proving minimality. The exact H
of the two extra cases is unknown; comparisons against 32 and 50 are only
comparisons with previously verified uppers.

All 44 configured queries completed with no partial windows or expansion
caps. Max-first uses 107,751,872 joint nodes; sum-first uses 107,804,992.
Both improve the champion calibration while leaving substantial general
accuracy problems. These graphs were used for method development and are
not a held-out quality guarantee.

## Evidence and reproduction

[cases.csv](cases.csv) retains every result, both actual words, full D trace,
producing k and known-reference comparisons.
[summary.json](summary.json) records the matched baseline and limitations.
The native scalar replay is repeated independently in Python for every
final pair; all 5,586 mask checks, including matched baseline and prior
certificates, pass.

The distance tables also passed independent forward BFS from **every**
ordered pair in every concrete DFA: 81,858 comparisons across the 22 graphs.

Compile the tracked isolated runner:

    g++ -std=c++23 -O3 -I . tests/Family1TailScoredBenchmark.cpp \
      Family1ExactPacked.cpp Family1LargeGraph.cpp -o out/tail-scored-benchmark

It accepts a graph-only list of two-digit canonical keys, rank mode 0 or 1,
and an output path:

    out/tail-scored-benchmark KEYS 0 OUTPUT_MAX
    out/tail-scored-benchmark KEYS 1 OUTPUT_SUM
    out/tail-scored-benchmark --verify-only KEYS

The original keys, immutable executable, frozen source snapshot and complete
native outputs remain under out/family1-finder-strategies-20261026/tail-scored.
Its manifest.json pins all query parameters and source hashes.
The first 20 keys come from the complete certified winner tables; the extras
are 0102000304050203000604050003 and
01020003040501060003020705060407.
No reference H or saved witness enters a query.

scripts/family1_tail_strategy_report.py seals both complete query files before
joining reference labels, replays all pairs, checks known-H lower bounds and
minimality claims, compares matched budgets and exports this compact evidence.
