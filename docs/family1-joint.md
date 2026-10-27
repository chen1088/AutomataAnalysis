# Joint word-pair lookahead

The [heuristics reference](shortest-hard-pair-heuristics.md) explains the
objective, seed portfolio, block/rolling distinction and measured limits.
This guide describes the Family1Joint executable and its controls.

`Family1Joint` implements the four-symbol search requested for the m=8
recheck. A step appends one of `00,01,10,11` to an ordered pair of words.
The search starts with two empty words and accepts only distinct words.

## Metric and first difference

For a family of N rooted DFAs, the progress metric is

`D(u,v) = number of DFAs A with delta_A(root_A,u) != delta_A(root_A,v)`.

The synchronized count is `N-D`, so `D(empty,empty)=0`: all endpoint pairs
agree. Identical words always have D=0 and are never accepted as a witness.
Once the words differ, D=0 is success. It can happen immediately at the first
different symbol; the algorithm does not require D to become positive first.
All endpoint states are retained because later unequal inputs can lose an
agreement. A small D is a progress signal, not a remaining-length bound.

The explicit divergence mode follows this startup policy:

1. Enumerate every common binary prefix x of lengths zero through c.
2. Start independent attempts from `(x0,x1)` and `(x1,x0)`.
3. Inspect that initial pair for a positive certificate. Otherwise enumerate
   k full joint steps after the first difference before ranking endpoints.
4. Greedily commit the full best k-symbol extension and repeat. All
   intermediate depths are also checked for positive pairs.

There are exactly `2*(2^(c+1)-1)` configured starts: c=2 gives 14 and c=7
gives 510. They are enumerated completely in length/lexical order, never
sampled or ranked against one another using their trivial initial D=0.
Only found lengths select the final best pair across attempts. A known
positive can safely exclude later starts longer than the improvement cap.
The remaining common-prefix depth limit is still a heuristic coverage limit.

Enable this mode with `--startup divergence --common-depth 2`. The default
`--startup legacy` preserves the earlier empty-root and optional prefix-pair
experiments; it does not implement this first-difference-aligned startup.

For the two-state Family 1 closure, joint k=2, c=0, beam one finds
`u=000`, `v=110`, with D at prefix lengths zero through three equal to
`[0,4,2,0]`. The separate distinct-word flag rejects the first zero and
accepts the final zero. The [example figure](../output/figures/hard-pair-joint-startup-example/witness.svg)
records both words, every prefix score, and producing parameters.

Here **k counts joint-symbol steps**. Each complete lookahead window has
`4^k` leaves and `4+4^2+...+4^k` edges. A shorter final window records its
actual span explicitly. An insufficient expansion budget refuses a window
before starting it. Every window that is evaluated is complete.

Both complete endpoint profiles are retained over the static-mask family.
Agreement can increase or decrease when the next two input symbols differ.
The common-suffix scorer's discarded coordinates, monotonicity assumption,
and permutation-mismatch pruning are not used here.

With `--beam 1 --diagonal-beam 0`, the finder greedily retains the distinct
pair with the fewest disagreeing masks after each full window, breaking ties
lexicographically. It advances the selected whole k-symbol block and checks
positives at every visited intermediate depth. This is block lookahead rather
than recomputing the window after only its first pair symbol.
Optional wider beams retain several distinct complete endpoint pairs;
`--diagonal-beam` separately retains identical-word paths that may diverge
later. Equivalent full states at the same depth share their lexical first
representative. No random sampling or seeded tie ordering is used.

Two optional controls retain deterministic search diversity. `--unequal-beam N`
keeps an additional quota of endpoints whose current window contained `01`
or `10`; this permits temporary losses of agreement. `--prefix-pairs N`
adds graph-derived distinct starting prefixes after the mandatory empty-root
attempt. Their complete word layers use `--prefix-depth`, `--prefix-words`,
and `--common-prefix-depth`; selection is finite and deterministic. Every
subsequent window still enumerates all four joint symbols. Prefix generation
does not freeze where later words may differ.

The default `--score total` orders leaves by `(D, first word, second word)`.
The experimental `--score permutation` orders by `(P,D,first word,second word)`,
where P counts disagreeing coordinates in which both input maps are
permutations. Common continuations cannot merge an unequal pair in such a
coordinate. The priority rule can choose a larger total D to reduce P;
it never declares a joint branch impossible and never prunes a joint symbol.
Success still requires total D=0 and different words. This rule is optional
because the benchmark shows large length errors despite better hit rates.

`--target-upper 50` stops a graph only after full scalar verification of a
pair with length at most 50. This is useful for excluding that graph from an
`H>50` search, and every supplied graph is still tested. Leave the target at
zero when refining a graph's shortest found pair. Per-attempt expansion
budgets, prefix caps, attempts and truncated diagnostics remain explicit.

The finder independently replays every positive pair on all original `2^m`
static masks. A returned length L establishes `H(G)<=L`. Beam pruning can
miss shorter pairs, and a miss gives no lower bound. An expected error of
one or two is a working hypothesis requiring calibration, not a guarantee.

The older `Family1Offline` word finder chooses distinct prefixes and then
appends a **common** suffix. Its k-step windows have `2^k` leaves and use
only `00,11` after the prefixes. Those are legitimate word pairs, so verified
positive certificates remain valid. Their coverage and k values must be
distinguished from joint search.

## Build and run

The dependency-free build includes both executables:

```bash
cmake -S . -B out/build/joint -DCMAKE_BUILD_TYPE=Release -DFAMILY1_OFFLINE_ONLY=ON
cmake --build out/build/joint -j 6
ctest --test-dir out/build/joint --output-on-failure
out/build/joint/Family1Joint --m 8 --graph 01020003040501060003020705060407 --k 8 --beam 1 --diagonal-beam 0 --max-length 80 --expansions 2000000 --out out/joint-k8-one
```

Outputs include immutable `run.json`, all supplied graphs in `records.jsonl`,
and `summary.json`. Every record includes k, alphabet, complete-window counts,
work limits, and the pair when found. No shortest-length certificate is
claimed by the bounded finder.

Every accepted improvement is also immediately flushed to `witnesses.jsonl`.
It includes both words, the producing parameters and winning startup, the
first-difference position, D at every prefix, and synchronized counts `N-D`.
The final record contains diagnostic greedy-round scores for the winning
attempt, or the last attempt after a miss. `--trace-records` bounds those
diagnostics without changing search choices. Use the
[witness figure renderer](hard-pair-figures.md) to display that pair and trace
beside the graph. Family 1 counts every original mask, including duplicate
realizations at coincident ports; generic saved families declare their own
deduplication/counting policy.

For a complete, already enumerated candidate set, the campaign driver tests
every supplied row and records the input/executable hashes. It retains all
misses and refuses incompatible resumes:

```bash
python3 scripts/family1_joint_campaign.py --candidates candidates.jsonl --exe out/build/joint/Family1Joint --out out/joint-k8-all --k 8 --beam 1 --diagonal-beam 0 --max-length 80 --expansions 2000000 --jobs 16
```

Each candidate row supplies `m`, its canonical `key`, and `canonical_table`.
Candidate generation must separately cover the entire declared neighborhood;
a completed campaign does not make a capped generation complete.

## Independent checks

The CLI test independently enumerates all 64 rooted accessible graph classes
through m=3, computes their shortest collisions using single-word layers,
and compares those answers with exhaustive four-symbol pair traversal.
It exercises the native finder at joint k=1 with sufficiently wide beams
to retain the complete small frontier, and checks all 16 leaves at joint k=2.
It also checks that agreement may be gained and lost, identical words are
excluded, insufficient budgets give no bound, and repeat runs agree.

The [generic quality benchmark](../results/hard-pair-joint-benchmark-20261026/README.md)
adds saved arbitrary DFA families, complete unions of their Family 1 closures,
all certified winners through m=7, and the held-out m=8 example. Joint
k=2,4,6,8 are explicit in every result. Randomness generates saved fixtures
only; search remains deterministic. An independent exact reference supplies
shortest lengths for small cases, and every returned pair is scalar-replayed.
The present heuristics still miss hard examples or return much longer pairs.
They do not justify a one-or-two-step error bound or reliable m=8 rankings.

The [adaptiveness report](family1-adaptiveness-report.md) separates candidate
coverage from finder error against complete exhaustive findings. Generation
uses k=N/A; fixed-pool tests use joint k=2,4,6,8. It also tests complete m=6,7
edit pools and the historical crowding gate, retaining every miss and pair.

For the stronger Family 1 workflow, use
[Family1NearPair](family1-near-cli.md): exact word layers have k=N/A, followed
by full-D scored prefix starts and joint k=4/beam16 by default. Its
[strategy benchmark](family1-finder-strategies-report.md) separates the
successful winner calibration from remaining seven-state nonwinner failures.
