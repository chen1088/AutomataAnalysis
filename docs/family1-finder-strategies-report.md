# Optimizing the near-shortest hard-pair finder

2026-10-26. All searches in this comparison are deterministic.
**Joint k** means 4^k leaves over 00,01,10,11. Exact word-layer searches
have **k=N/A**. Auxiliary common-suffix experiments have a separately labeled
**common k**, with up to 2^k extensions after distinct prefixes, before
coordinate-viability pruning.

We implemented a stronger finder, Family1NearPair. It recovers all 20
certified Family 1 winners through m=7 within one of their exact lengths,
with no misses; 18 returned lengths match the reference exactly. It also
recovers every saved six-state near-top case exactly.

That passes the winner calibration, but it does not make the finder generally
reliable. The broader seven-state check still contains a returned length 43
for a graph already known to have H≤32, disproving a general within-two
claim. The eight-state development check returns 52 against an existing verified
upper of 50; its true H remains unknown.

## The implemented strategy

The new [native pipeline](../Family1NearPair.h) uses the following fixed policy:

1. **Try complete exact word layers first, k=N/A.** The fixed limits are
   depth 24, at most 16,777,216 words in a layer, and 256 MiB of planned array
   payload. There is no clock limit. A collision proves the shortest length;
   a completed collision-free layer supplies a lower bound. A memory limit
   returns UNKNOWN with only the lower bound actually established.
2. **Choose better graph-derived starting pairs.** Enumerate complete binary
   word layers through depth 20, with a 1,048,576-word layer limit. Build a
   bounded, deterministic catalogue of 16,384 pairs that agree on the selected
   permutation coordinates. Evaluate every catalogue pair on the full family.
   Rank by D within each (length, actual common-prefix length) channel and
   distribute 512 starts across those channels. No reference pair is supplied.
3. **Run full joint search, k=4, beam 16.** Each start gets complete 4^4 windows
   over all four paired symbols, permutation-first then total-D ranking,
   maximum length 80 and 2,000,000 expansions per attempt. The search advances
   the whole selected block and checks every intermediate depth for success.
   It retains every previously verified shorter pair. If no pair is found,
   retry with the compact catalogue: 4,096 candidates per prefix layer and
   the same 512 starts, k=4 and beam 16.
4. **Rerank the original catalogue by common-input merge distance.** For
   each static-mask DFA, precompute shortest same-input coalescence distance
   on its ordered state pairs. Rank seeds within the same channels by
   (number of infinite distances, maximum finite distance, sum of finite
   distances, D, first word, second word). Select 512 starts and repeat
   joint k=4, beam 16, retaining the best earlier verified upper. The
   catalogue word layers are reused; rescoring and all joint work are charged.

The common-input score chooses starts only. Infinite common-input distance
does not rule out a joint extension, prune a branch or establish a lower
bound. The default selects up to 1,024 starts, or 1,536 with the compact
retry, counting possible overlaps. No answer-dependent trigger is used.

The seed catalogues are bounded heuristics, not all compatible word pairs in
those word layers. The compact path packs permutation profiles and uses a
per-layer pair cap; its wide-profile fallback uses the older global cap.
The actual catalogue rule, caps, retry, winning seed and work are exported.

D still counts unequal endpoints on every original static-mask DFA, including
duplicate realizations at coincident ports. Identical words are rejected.
The joint search retains all coordinates because 01 or 10 can break an
agreement. Permutation priority changes ranking, not the allowed alphabet.

The important change is seed selection. Canonical compatible pairs often
start the greedy search in poor regions. Full-family D and common-input
distance provide complementary seed rankings, separated by length and
first-difference age. The deeper exact phase removes an avoidable source
of error at m≤6.

## Why the exact budget matters

With an exact fallback only through depth 16, the new joint k=4 seed strategy
passes all 20 winner cases, but one six-state nonwinner returns 33 against
exact H=21. More beam and seed variants do not reliably fix that outlier.

The fixed depth-24/256-MiB exact budget instead solves **all 69** preserved
m=6 cases with H=21..23 exactly, at **k=N/A**. There are no heuristic seed
attempts. The run evaluates 266,328,512 words in total and independently
replays every final pair. Observed four-process wall time is about 4.63
seconds; this is a local measurement, not a controlled speed claim.

This is a general budget choice, not a branch on a known answer or graph key.
The certified global maximum through m=6 is 23. Six-state full profiles need
at most three 64-bit planes, and the exact engine's first-collision layer
through length 23 fits this payload budget. Thus the preserved exhaustive
findings and memory planner explain why the budget suffices through m=6,
without rerunning all 192,181 six-state classes in this experiment.

On all 47 bounded m=7 nonwinners, the same exact budget safely returns
UNKNOWN with H≥24. It stops at the memory limit after completing length 23.
Median native time is about 1.85 seconds, with peak planned payload about
224 MiB. These lower bounds help interpret the result; they do not establish
the shortest seven-state pair.

## Strategies tested

The main calibration includes every exhaustive winner tie through m=7.
Reference scores and reference words are excluded from native query inputs;
labels are attached after the outputs are sealed.
The 20 winners, the selected m=7 failure and the m=8 leader were used for
method development. The broader saved frontier overlaps those development
cases; it is a stress test, not an independent generalization guarantee.

| Strategy | Window and main settings | Found / 20 | L=H / 20 | L≤H+2 / 20 | Largest positive gap |
|---|---|---:|---:|---:|---:|
| Canonical compatible starts | Joint k=4, B=1, 128 starts | 20 | 7 | 8 | 10 |
| More beam and starts | Joint k=4, B=4, 1,024 starts | 20 | 11 | 17 | 5 |
| Wider beam | Joint k=4, B=64, 128 starts | 20 | 12 | 18 | 4 |
| Full-D scored starts, short exact fallback | Joint k=4, B=16, 512 starts; exact depth16, k=N/A | 20 | 14 | 20 | 2 |
| Full-D baseline | Joint k=4, B=16; exact depth24, k=N/A | 20 | 16 | 20 | 2 |
| **New default: full-D + common-distance starts** | **Joint k=4, B=16; exact depth24, k=N/A** | **20** | **18** | **20** | **1** |
| Deeper joint window | Joint k=6, B=4; full-D starts and exact depth24 | 20 | 16 | 18 | 4 |
| Deeper joint window | Joint k=8, B=1; full-D starts and exact depth24 | 20 | 13 | 19 | 3 |

All evaluated joint windows are complete. The new default's calibration
uses 127,612,864 joint node expansions, with exact and prefix word work
reported separately. Its first 12 winner cases, m≤6, carry native minimum
proofs. The six seven-state matches to H=34 are verified against the
separate exhaustive reference; the finder itself reports only its proved
lower bound and found upper.

We also tested:

* **Receding-horizon search:** inspect k joint steps, commit one symbol,
  retain wider beams and optionally avoid expanded states. Joint k=4 with
  beam 256 finds all 20, but only 18 within two. Scored-start rolling matches
  the full-D baseline's seven-state lengths at greater cost.
* **Different metrics:** exact individual pair distances on the underlying
  m²-state product, maximum/sum distance objectives, and alternate lookahead
  ties. These underlying-graph metrics do not improve the winner results.
  Mask-specific common-input seed distances do: both maximum-first and
  sum-first rankings find 18 optimal winners and all 20 within one at
  joint k=4, B=16. The default retains maximum-first alongside full-D.
* **Complete local rewrites:** deletion/substitution spheres (k=N/A),
  binary-prefix replacement at k=12/16, and common-tail replacement at
  common k=16/18. These improve some weaker
  initial pairs but none of the closer 20-case portfolio. The tested complete
  edit sphere evaluates 2,491,739 words; common-tail replacement at common
  k=18 evaluates 65,120,999 continuations without a gain on that portfolio.
* **SAT/CEGAR and profile-cycle searches, k=N/A:** fixed work budgets, exact
  profiles and no randomized choices. The SAT build removes RNG code.
  Neither route finds the hard m=6,7 cases within its declared budgets.
* **Auxiliary common suffixes:** fixed common k=8 and k=12 after distinct
  graph-derived prefixes. These are valid certificate searches with narrower
  coverage, and do not replace the four-symbol joint phase. They do not
  improve the strongest winner calibration or the prior m=8 certificate.

Increasing k, beam width or catalogue size is not monotone. Every portfolio
therefore keeps the minimum verified upper and charges all attempted work.
The [comparison table](../results/family1-finder-strategies-20261026/near/strategy-comparison.csv)
and per-strategy directories retain the unfavorable outcomes too.

## Broader validation and the remaining failure

The final frozen binary tests all **343** preserved frontier graphs:
219 m≤5 cases, all 69 hard m=6 cases, and 55 m=7 cases. It returns a valid
pair for every graph, using the compact retry for two seven-state misses.
All 288 m≤6 rows are natively proved exact.

The eight m=7 winners return, in canonical key order:

| Key | Reference H, k=N/A | Found L, joint k=4 |
|---|---:|---:|
| 0001020302030405000604060105 | 34 | 35 |
| 0001020304050406050600010203 | 34 | 34 |
| 0102000301040204050600030506 | 34 | 34 |
| 0102000304050106000304050206 | 34 | 35 |
| 0102010203040005030604060005 | 34 | 34 |
| 0102010203040005050600060304 | 34 | 34 |
| 0102020304050006000604050103 | 34 | 34 |
| 0102030405060001000203040506 | 34 | 34 |

For the 47 m=7 nonwinners, exact H is generally unavailable. We can still
check known upper certificates. The new default certifies 29 of them weaker
than the maximum by finding L≤33; 18 retain false-compatible uppers.
The graph 0102000304050203000604050003 returns 43 despite its existing
H≤32 certificate. That proves an error of **at least 11**. The full-D
baseline returns 45 at joint k=4, beam 16; its k=6, beam 4 trial returns
44 and its k=8 trial returns 45. Larger windows do not fix this case.
The historical 32-pair is independently replayed; its producing k is not
established here.

At joint k=4, the finite top band within two of the largest upper contains
only two graphs, with returned lengths 43 and 41. Both are known nonwinners;
all eight true winners lie outside that band. Rarity alone would again make
the wrong ranking look plausible.

The m=8 development check returns 52 at joint k=4, beam 16. Its old length-50
pair is independently replayed and remains the stronger certificate.
The historical producing common-suffix k for that old pair is unknown;
its completed refinement k does not identify the producer. No new m=8
minimum or improved leader is claimed.

Consequently, the winner gate passes while the broader within-two gate
fails. We should use this implementation as the stronger measured baseline,
and keep m=7 nonwinner outliers and the m=8 case in the mandatory quality
suite. The current evidence does not support moving to m=9 with reliable
near-shortest rankings.

## Code and reproduction

The [CLI guide](family1-near-cli.md) documents every default and artifact.
The [reproducible runner](../scripts/family1_near_benchmark.py) freezes inputs,
checks all native settings and journal hashes, replays every positive,
and checks both lower and upper claims against reference H.

    cmake -S . -B out/build/near -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build out/build/near -j 6
    ctest --test-dir out/build/near --output-on-failure
    python3 scripts/family1_near_benchmark.py \
      --exe out/build/near/Family1NearPair --out out/near-calibration

For the broader saved frontier, supply the complete file, not a ranked prefix:

    python3 scripts/family1_near_benchmark.py \
      --exe out/build/near/Family1NearPair \
      --pool results/family1-neighbor-seeds/near-top.jsonl \
      --exact results/family1-neighbor-seeds/near-top.jsonl \
      --out out/near-frontier

The [21 paired-word figures](../output/figures/family1-near-calibration/README.md)
record actual words, producing k and every D value beside each graph.
The [artifact index](../results/family1-finder-strategies-20261026/README.md)
includes the full tables, parameter/source/binary pins and negative trials.
All twelve semantic CTests pass. Separately, the selector is checked against
1,888,160 independently enumerated compatible pairs on every m≤4 graph
and additional m=8 cases. Independent forward BFS also checks 226,922
mask-specific common-input pair distances on 745 graphs and 4,470 full-mask
score aggregates. Passing those correctness checks does not erase
the quality failures above.
