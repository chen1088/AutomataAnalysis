# Accuracy-oriented Family 1 pair CLI

For the algorithms and their accuracy limits, see the
[heuristics reference](shortest-hard-pair-heuristics.md).

Family1NearPair is an experimental deterministic finder for distinct,
equal-length binary word pairs. Its joint phase uses the complete alphabet
00,01,10,11. A verified pair is an upper certificate; its shortest length
remains unproved unless it meets an independently established lower bound.

Build the dependency-free executable:

    cmake -S . -B out/build/near -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build out/build/near --target Family1NearPair -j 4

For example, search the supplied eight-state graph:

    out/build/near/Family1NearPair \
      --m 8 --graph 01020003040501060003020705060407 \
      --k 4 --beam 16 --out out/near-example

The default joint lookahead is **k=4**, beam 16, permutation-first ranking,
maximum word length 80 and 2,000,000 node expansions per selected-seed attempt.
Every evaluated window covers all 4^k leaves and advances the whole chosen
block. A window is refused before it starts if the remaining work budget
cannot cover it completely.

Before that phase, complete word layers through depth 24 are attempted with
a 16,777,216-full-word layer budget and 256 MiB array-payload budget. This exact
phase has **k=N/A**. A successful exact result returns immediately. Otherwise,
the graph-derived prefix catalogue uses complete word layers through depth 20
with at most 1,048,576 words per layer, a bounded catalogue of 16,384 compatible
seed pairs and 512 selected starts. Full-family D ranks candidates within
(length, common-prefix-length) channels. These are finite deterministic
catalogues, not every possible compatible word pair.

If that search misses, the default retries with the compact catalogue at
the same joint k and beam, using at most 4,096 collected pairs per prefix
layer and the same 512 selected starts. The exact phase is reused. This
retry is driven by the absence of a pair, never by a reference answer.
The winning catalogue and total work across all stages are recorded.
Use --fallback-compact off to disable it.

The default --seed-ranking portfolio then reranks the SAME original
catalogue with mask-specific common-input merge distances. Its tuple is
(number of infinite distances, largest finite distance, sum of finite
distances, D, first word, second word). It selects another 512 starts across
the same channels and runs the same full four-symbol joint k=4 search.
Infinite common-input distance is a seed preference only: it neither prunes
a joint branch nor supplies a lower bound for independent future words.

Every earlier verified upper remains available. Catalogue word generation
is reused; score evaluations and joint work from all stages are charged.
--starts means per ranking stage: the default may select 1,024 starts,
or 1,536 when the compact retry also runs, with possible overlaps.
seed_candidates_selected reports that aggregate. Other --seed-ranking
choices are full, common-max and common-sum for controlled comparisons.

Use --exact-depth 0 to disable the exact phase, --seed-mode compact for the
alternate catalogue rule, or --help to inspect all work-budget flags. There
are no seed, random-sampling or clock-limit flags.

## Artifacts and interpretation

The output directory must be fresh and empty:

* run.json pins the executable, compile-time source fingerprint when supplied
  by the build, all parameters and every unique canonical input key.
* witnesses.jsonl immediately records every verified length improvement,
  including the actual two words, winning seed, first difference and greedy
  window position, producing k, bounds, and full D and synchronized-count
  traces over every original static mask.
* records.jsonl retains every completed graph, including misses, exact-phase
  status and lower bounds, candidate-selection caps, work and window counts.
* summary.json reports whether every supplied graph was tested and pins both
  result journals. A terminated run has no completed summary.

Producing k is null for an exact-word-layer witness and numeric for a joint
seed witness. configured_joint_k always records the requested joint setting,
including when the exact phase solves the graph first. Minimality can also
be certified if a joint witness meets the exact phase's lower bound; its
producer and numeric joint k remain unchanged.

Every accepted pair is independently replayed on every original static-mask
DFA, including coincident-port multiplicities. A miss does not imply a large
H; only the complete exact layers can supply its reported lower bound.
Finite catalogue and beam restrictions remain heuristic, and no universal
near-shortest error bound is claimed.

The fixed exact budget is sufficient for the certified maximum through m=6
(H≤23 and at most three 64-bit profile planes). All 69 preserved hard m=6
cases were independently recovered exactly with these budgets, k=N/A.
The joint heuristic remains necessary at m=7; its broader quality limits
are reported separately from the successful winner calibration.

Repeat --graph to test a complete supplied candidate pool. Equivalent inputs
are canonicalized and deduplicated, with the original argument count retained.
The caller must separately establish that candidate generation covered its
entire declared edit neighborhood.

The separate [adaptive-window experiment](family1-adaptive-window-report.md)
tests population-variance rules with the exact oracle disabled, complete joint
k=2..5 or k=4..6 windows and one-symbol advancement. It is an experimental
benchmark target; it does not change this CLI's fixed joint k=4 default.
