# Deterministic full-joint hard-pair calibration, 2026-10-26

The benchmark verifies certificates and measures heuristic error. It does not establish a near-shortest error bound. Every result states joint lookahead **k**, and every positive result stores its actual two words plus independently replayed D at every prefix. Misses remain in the records.

`quality-validation.json` applies the explicit empirical criterion that every
exact-reference case must be found within two of H. Every tested ranking/k
configuration fails that criterion. The seven passing semantic CTests verify
implementation correctness; they do not certify near-shortest quality.

The frozen comparison has 52 cases at each joint k=2,4,6,8: 20 certified rooted Family1 maximizers through m=7; 7 hand-built edge cases; 12 saved generated heterogeneous DFA families; their 12 complete unions of Family1 closures; and the held-out m=8 graph with an existing upper certificate of 50. Generated bases have 2..5 states and may contain unreachable states. These small generated families are a calibration set, not a representative distribution of difficult eight-state graphs.

The only pseudo-random operation was generating fixture transition tables with the saved seed 0x20261026. Normal benchmark runs read those complete tables and invoke no random generator. Family1 closure means every fixed per-state swap of the two binary transition ports, keeping each DFA root fixed. The union is deduplicated by exact transition table and root. D counts these distinct concrete DFAs, without mask multiplicity or isomorphism deduplication. All closures are independently checked under every local swap generator.

Each search has B=1, diagonal beam=1, unequal beam=0, maximum pair length 80, and 2,000,000 node expansions **per attempt**. A full joint k-step window enumerates all 4^k leaves over 00,01,10,11 and checks every intermediate depth. No window was partial and no attempt reached its expansion cap. Length limits and all failed attempts are retained. The c=2 modes exhaust all 14 starts: every common binary prefix of length 0,1,2 followed by both first differences 01 and 10. Every start gets its own full budget; the first greedy ranking comes after k full steps following that difference. No best-score target or witness hint shortens a run.

Total-D ranking orders by (D, first word, second word). The optional permutation-first ranking orders by (P,D, first word, second word), where P counts unequal coordinates whose two letter maps are both permutations. Both rankings retain every coordinate and require distinct words with total D=0 for success. P is a heuristic priority, with no pruning or error guarantee.

| Ranking/startup | joint k | Family1 found / 20 | Exact / 20 | Largest gap among positives | m=7 found / 8 |
|---|---:|---:|---:|---:|---:|
| Total D, empty root | 2 | 5 | 3 | 11 | 0 |
| Total D, empty root | 4 | 4 | 4 | 0 | 0 |
| Total D, empty root | 6 | 7 | 4 | 8 | 0 |
| Total D, empty root | 8 | 8 | 4 | 7 | 0 |
| Total D, c=2 | 2 | 6 | 3 | 11 | 0 |
| Total D, c=2 | 4 | 7 | 4 | 4 | 0 |
| Total D, c=2 | 6 | 8 | 5 | 5 | 0 |
| Total D, c=2 | 8 | 8 | 6 | 3 | 0 |
| Permutation D then total D, c=2 | 2 | 8 | 4 | 21 | 0 |
| Permutation D then total D, c=2 | 4 | 14 | 5 | 41 | 2 |
| Permutation D then total D, c=2 | 6 | 14 | 5 | 37 | 2 |
| Permutation D then total D, c=2 | 8 | 17 | 7 | 43 | 5 |

An empty cell cannot hide a miss: full records contain upper_bound=null and the actual stopping flags. A successful gap is L-H; it says nothing about a failed case. The optional priority rule recovers additional cases but still has large errors and misses. The previously suggested error of at most one or two is unsupported by this calibration.

The exact reference has **k=N/A**. It enumerates single binary words by length and detects equal full heterogeneous endpoint vectors. It independently recovers H for all 31 new fixtures and all 10 certified cases through m=5. On the remaining 10 certified m=6,7 cases and the held-out m=8 graph, its cap stops after fully verifying collision-free lengths through 16: UNKNOWN, H>=17, not an exact score. Certified H=23 or H=34 labels are attached afterward from the separately referenced certificates. The m=8 case retains unknown H and only the existing upper 50. Source answers and source witness strings never enter the native input.

| Ranking/startup | joint k | New fixtures exact / 31 | Closure unions exact / 13 | m=8 returned upper | All-case node expansions |
|---|---:|---:|---:|---:|---:|
| Total D, empty root | 2 | 24 | 7 | miss | 33,680 |
| Total D, empty root | 4 | 26 | 8 | miss | 270,640 |
| Total D, empty root | 6 | 27 | 9 | miss | 2,501,320 |
| Total D, empty root | 8 | 31 | 13 | miss | 26,388,760 |
| Total D, c=2 | 2 | 26 | 8 | miss | 243,604 |
| Total D, c=2 | 4 | 28 | 10 | miss | 1,836,192 |
| Total D, c=2 | 6 | 28 | 10 | miss | 18,232,332 |
| Total D, c=2 | 8 | 31 | 13 | miss | 199,392,724 |
| Permutation D then total D, c=2 | 2 | 26 | 8 | miss | 220,760 |
| Permutation D then total D, c=2 | 4 | 29 | 11 | miss | 1,523,772 |
| Permutation D then total D, c=2 | 6 | 29 | 11 | miss | 14,228,800 |
| Permutation D then total D, c=2 | 8 | 31 | 13 | miss | 162,401,044 |

The m=7 graph order in summary.json is lexicographic key order, matching fixtures.json. Node counts sum every configured attempt. Runtime fields are native search seconds, exclude the reference oracle and Python replay, and were collected with the three modes running concurrently; they are not controlled speed comparisons.

The common-prefix-essential fixture has table [[1,2],[1,1],[2,2]] and exact H=2 (reference k=N/A). For joint k=2, c=0 forced divergence is impossible to repair because the two words enter separate sinks; c=2 finds the length-2 pair. This checks why common prefixes cannot be cancelled. The smoke tests also cover unary/coincident ports, permutations, heterogeneous sizes, nonzero roots, agreement loss, closure deduplication, all 14 startup starts, and both ranking policies.

Artifacts: fixtures.json stores every concrete family and base table; records-<mode>-k<k>.jsonl stores every result and per-start outcome; run-<mode>.json pins options, source hashes and executable; summary.json provides aggregates. The ignored local evidence/ directory freezes the exact native header, native adapter and runner used for this comparison. The versioned source files below match those frozen hashes. Earlier exploratory runs remain under out/hard-pair-joint-benchmark-20261026 and are excluded from these tables. Their first header differed only in comments and an error diagnostic; the final comparison recompiles all modes from the frozen source.

Compile the matching versioned source using GCC 14.1 (standard-library only):

```sh
g++ -std=c++23 -O2 -I . tests/HardPairJointBenchmark.cpp \
  -o /tmp/HardPairJointBenchmark
python3 tests/hard_pair_joint_benchmark.py --exe /tmp/HardPairJointBenchmark --self-test
python3 tests/hard_pair_joint_benchmark.py --exe /tmp/HardPairJointBenchmark \
  --out out/reproduction-c2 --k 2,4,6,8 --diagonal 1 --max-length 80 \
  --expansions 2000000 --startup-common-depth 2 --include-m8
```

Use a fresh output directory for each run. Omit --startup-common-depth for the empty-root baseline; add --prioritize-permutation for the optional priority mode. Fixture regeneration is a separate explicit --regenerate-fixtures action and is not part of search.

The [complete local witness gallery](../../out/hard-pair-joint-benchmark-figures-20261026/index.md)
draws all 468 positive results alongside their actual two words and full D
traces. Its index retains all 624 rows, including all 156 misses, at joint
k=2,4,6,8. Every positive is independently scalar-replayed against its whole
saved family; the figures draw only the base graphs and label family size,
startup/ranking, reference H and gap. The manifest pins every source row,
data/configuration input and output. The generated gallery stays local; create
it in a fresh directory with:

```sh
python3 scripts/hard_pair_benchmark_figures.py \
  --benchmark results/hard-pair-joint-benchmark-20261026 \
  --out out/hard-pair-joint-benchmark-figures-20261026
```

A subsequent **post-hoc native diagnostic at joint k=8, c=7** exhausts all 510 starts on the eight m=7 winners and the held-out m=8 leader (B=1, diagonal=0, maximum length 80, 2,000,000 expansions per attempt, target 0; later length caps use only actual positives). It was motivated by known witness common-prefix lengths [0,6,6,7,0,6,6,6], which does not prove long prefixes are necessary for all optima. Total-D misses all nine graphs; permutation-first gives m=7 lengths [38,43,48,47,42,41,47,44] against H=34 (errors 4–14), and m=8 upper 53 against the existing upper 50. All 9,180 starts ran with no partial windows or expansion caps. Every final and improvement witness passed independent all-mask replay. See deep-startup-summary.json, deep-startup-records.jsonl, deep-startup-improvements.jsonl and out/hard-pair-joint-deep-startup-20261026/README.md. These observations supplement the scoped c=2 matrix; they do not establish a near-shortest error bound.

The deeper native joint k=8, c=7 results also have [nine paired-word figures and all nine misses](../../out/hard-pair-joint-deep-startup-figures-20261026/index.md). Each positive displays the actual pair, full D trace, startup and ranking.
