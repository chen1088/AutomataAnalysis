# Fixed exact budgets before heuristic search

All results here use **k=N/A**: the oracle enumerates complete binary-word
layers and finds equal full endpoint profiles. It does not use a greedy
window. The same fixed budget is applied to every supplied graph:

- Maximum word depth 24.
- Maximum full layer 16,777,216 words.
- Maximum packed array payload 256 MiB.
- No clock limit and no graph-specific score or witness hint.

The implementation accounts for all words using the proved simultaneous
complement symmetry; this is an exact quotient, not sampling.

| Pool | Cases | Exact scores | Unknown results | Certified lower after an unknown |
|---|---:|---:|---:|---|
| All m=6 exact near-top graphs | 69 | 69 | 0 | — |
| Preserved m=7 nonwinner frontier | 47 | 0 | 47 | H≥24 |

The 69 m6 answers match every individual exhaustive score, and all new pairs
pass independent replay over all 64 original masks: 4,416 pair/mask checks.
The existing scored-seed native harness was configured with joint k=4, but
its exact fallback solved every case and invoked zero seed attempts and
zero joint-search nodes. The actual pair-producing k is therefore N/A.
Its exact layer counter totals 266,328,512 word evaluations. Approximate
four-process elapsed time from the sealed manifest to the last native flush
was 4.63 seconds.

Every m7 query instead exhausts collision-free layers through 23 and stops
before a layer would exceed the payload cap. These are UNKNOWN results with
rigorous H≥24, not exact scores. The peak packed payload is 234,889,984 bytes
(about 224 MiB). Native time per case is median 1.850 seconds and maximum 2.011
seconds; summed native time is 87.54 seconds and approximate four-process
elapsed time 22.69 seconds. The counter totals 788,529,058 words. Timings were
observed under concurrent work and are not controlled speed comparisons.

For any m≤6 graph, a full endpoint profile has at most three 64-bit planes.
The first-collision layer through length 23 stores at most 2^22 complement
representatives:96 MiB for profiles plus 32 MiB for hash indices and small
fixed arrays. Thus the independently certified global H≤23 for m≤6 fits
this fixed 256 MiB budget. This supports exact recovery throughout those
sizes without hardcoding a graph's answer. The 69-case experiment tests the
hardest preserved m6 score band directly; it is not a rerun of every 192,181
six-state class.

The source probe is tests/Family1ExactBudgetBenchmark.cpp. Build it with:

    g++ -std=c++23 -O3 -I . tests/Family1ExactBudgetBenchmark.cpp \
      Family1ExactPacked.cpp Family1LargeGraph.cpp -o out/ExactBudgetBenchmark

Then pass a complete file of canonical keys and the fixed depth/memory caps:

    out/ExactBudgetBenchmark keys.txt 24 256 > out/exact-budget-records.jsonl

Each public cases.csv lists every supplied key and all returned pair words
and D traces. The m7 rows preserve the stopping reason, payload peak and
certified lower bound. The source/executable fingerprints and complete
output seals accompany both tables.
