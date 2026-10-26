# Generic hard-pair finder

`HardPairFinder.h` is a reusable header for finite families of binary DFAs.
It has no Family 1 dependency. Coordinates may have different state counts,
different roots, and unrelated transitions. The Family 1 command-line adapter
is one use of this module.

For a fixed distinct equal-length pair `u,v`, the module searches for a common
suffix. Its metric is the number `R` of family coordinates whose endpoints
still differ. Equal coordinates remain equal after every common letter, so
`R` cannot increase.

## State adapter

A family-state adapter supplies:

```cpp
std::uint64_t remaining_count() const;
std::uint64_t mask_count() const;
State append_common(bool letter) const;
```

`mask_count()` is the total number of DFA coordinates. Its historical name
does not require the family to consist of masks. An adapter may instead expose
`merged_count()` with `mask_count()`. It may also expose
`permutation_mismatch_count()` for a proven common-suffix obstruction; without
that method the generic module assumes no such shortcut. The optional
`has_proven_obstruction()` hook permits other independently certified
impossibility checks. Heuristic pessimism must never return `true` here.
An optional `minimum_completion_length()` supplies an admissible lower bound
on the required common suffix. Unknown analyses contribute zero. A branch is
safely excluded when this bound exceeds its remaining length budget.

The state must represent the complete coordinate information needed to append
a letter. Its counts remain exact. Sampling can be a separate heuristic, but
must not be presented as the full metric through this adapter.

`find_hard_pair_suffix(initial, options, exact_tail_callback)` returns its
chosen suffix and full metric trace. Options include `window_k`, `beam_width`,
`max_suffix`, `tail_threshold`, expansion limits, and exact-tail state/depth
limits. It retains multiple candidates, including neutral moves, rather than
requiring a strict drop at each step. A finite beam is still a heuristic.

## Binary windows and distributions

At a window boundary, all length-`k` binary extensions can be compared by

```text
drop(w) = R_before - R_after(w),    w in {0,1}^k.
```

The implementation shares prefix work and retains candidates by actual drop,
remaining count, and deterministic tie/diversity rules. Flat layers retain
representatives instead of discarding zero-gain paths.

The standalone `enumerate_window_distribution(state,k,limits)` evaluates every
window unless capped or interrupted. Its histogram and population moments
describe the full set of `2^k` windows only when `complete=true`. A finder may
stop a window early after a verified success or an exact-tail result; that
partial window report is explicitly incomplete.

Normalized drop divides by `R_before`, the number of coordinates still
unequal. It does not divide by the original family size. When `R_before=0`,
normalization is undefined and the output flags that case. No independence
or generic concentration assumption is used. The
[scalar reference distributions](../results/family1-window-distributions/README.md)
show why the distribution can change substantially as the same pair approaches
completion.

The distribution is a property of the family **and the current pair**, not just
the window length or number of coordinates. Window size, beam width, seed
budget, and exact-tail threshold are configurable. The implementation does not
assume that a rich family has concentrated gains, that coordinates behave
independently, or that the largest immediate gain gives the shortest final
pair. Complete histograms, zero-gain fractions, spread, and normalized gains
can guide later parameter experiments. No adaptive-parameter advantage has
been established yet.

The native window limit is now 16. Work is separately bounded by
`--max-expansions` (default 10,000 per starting pair). A complete binary window
needs `2^(k+1)-2` transition extensions before pruning; k=16 needs 131,070.
Increasing k while retaining a small node budget can leave the window incomplete.
`--beam-ranking remaining` compares final unresolved-coordinate counts across
parents; the historical `drop` ordering remains the default.

## Prefix construction and safe pruning

`HardPairPrefixSeeds.h` constructs distinct equal-length prefix pairs whose
complete endpoint vectors agree on a selected subfamily. It supports arbitrary
binary DFAs and roots, full short layers, deterministic sampled longer layers,
and candidates spread across lengths. Hash matches are compared with the full
endpoint vectors. A selected-subfamily collision is a starting pair, not a
collision certificate for the full family. Sampled layers provide no shortestness
claim.

Opt-in `--prefix-common-depth 8` also stratifies candidates by their actual
longest common prefix, including different prefixes of the same length. It
uses complete endpoint-profile equality and bounded deterministic reservoirs.
The default zero preserves the earlier candidate sequence. Explicit prefix
word/sample budgets can be increased through `2^22`; complete depth21 uses
2,097,152 words at that layer and can require substantial memory.

The Family 1 adapter selects every distinct realization in which both letters
are permutations. Any surviving unequal pair in such a realization can never
merge under a common suffix. Matching these coordinates first avoids wasting
the entire prefix budget on impossible starts. Other templates and actual
common-prefix variants are retained as well.

`HardPairViability.h` independently solves the two-state mergeability problem
inside one DFA by complete reverse BFS from its diagonal. If even one remaining
coordinate cannot merge individually, the whole pair cannot merge. The Family 1
adapter checks eight remaining coordinates by default and exports examples of
closed negative certificates. A positive individual check does not prove joint
mergeability. Caps or interruption return unknown and never prune. Fixed check
counts include cache hits, preserving deterministic decisions after resume.

`--distance-coordinates N` reuses the complete single-DFA tables as a safe
lower bound: at least the largest individual shortest merge distance is
required to finish the pair. The bound is checked against the current suffix
budget. Its default zero disables this extra pruning; unknown tables never
exclude a branch. This proves only that a particular branch cannot meet its
budget, not a lower bound on the seed graph's H.

This check matters even with a nearly perfect metric: one twenty-state trial
had only 501 of 1,048,576 coordinates remaining, but 496 of those pairs were
individually unmergeable. See the
[independent residual diagnosis](../results/family1-residual-pair-diagnostic/README.md).

## Exact tail search

When only a few coordinates remain, a callback can call

```cpp
hardpair::exact_suffix_bfs(coordinate_pairs, transition, limits);
```

Each `CoordinatePair` contains a DFA coordinate ID and its two current states.
The callback `transition(id,state,letter)` handles that coordinate's own DFA;
there is no common state-count assumption. Merged pairs use an absorbing
marker. Unordered unequal pairs are sufficient because both members receive
the same letter.

This is ordinary shortest-path BFS from a fixed pair product to its diagonal.
Global visited states are valid here: returning to an identical complete pair
vector at another depth cannot improve its shortest future completion.
This differs from computing `H(G)` by detecting collisions among root words,
where witnesses must have equal length and cross-length state visits are
insufficient.

Hashes only select buckets. Every matching hash is compared against the
complete pair vector. For remaining coordinate state counts `n_1,...,n_r`,
a coarse state-space bound is

```text
product_i (1 + choose(n_i,2)).
```

The extra state per coordinate is the merged marker. This explains why a
threshold such as two or four remaining coordinates can make exact search
useful even when the original family contains many realizations.

An exhausted uncapped BFS either returns a shortest common suffix for that
starting pair or proves that no common suffix exists from it. A state cap,
depth cap, or interruption makes a negative result incomplete. Such a result
does not prove a new lower bound on the original graph's `H`.

## Conditional shortestness

`shortest_conditional` certifies the BFS suffix from the recorded intermediate
pair. If heuristic windows preceded the BFS, it does not certify those earlier
choices. `shortest_for_initial_pair` additionally means that BFS started at
the supplied initial pair. Neither flag, by itself, proves that the whole
word pair is globally shortest among all choices of initial words.

The independent heterogeneous example has three DFAs with state counts
2,3,5 and roots 1,0,0. From the pair `0 / 1`, its shortest common suffix is
`0000`, producing a pair of total length five. The family already has a
length-two merge `01 / 10`. Thus exact conditional tail search and exact
global merge-length computation answer different questions.

A common prefix also cannot generally be canceled. In the DFA

```text
root0: 0->1, 1->2
state1: both letters->1
state2: both letters->2
```

`0 / 1` cannot be completed by any common suffix, but `00 / 01` already
merge. The common prefix `0` changed the relevant starting state. The Family 1
adapter therefore schedules actual common-prefix variants, rather than
testing a root pair and canceling the prefix.

## Independent validation

`tests/HardPairFinderIndependent.cpp` defines its own explicit-family adapter
and an ordered-set scalar BFS. It shares no Family 1 production transition,
canonicalization, or state implementation. Native MSVC Release and Debug
passed:

- All 64 rooted accessible seed classes through size three, with 1,263
  conditional pair-BFS comparisons and 48 forced-hash cases.
- 128 complete window distributions, including all windows, population
  variance, normalized drops, and flat neutral distributions.
- Heterogeneous state counts, nonzero roots, state/depth caps, interruption,
  repeated states, and the common-prefix counterexample.
- A controlled ten-state DFA where a two-letter window with beam one misses
  within its budget, while exact tail search returns the shortest conditional
  suffix of length three. This is an example, not a universal dominance claim.

`tests/family1_finder_cli_test.py` independently checks the Family 1 adapter:
full score traces, all-mask witness replay, conditional suffix proofs against
scalar BFS, capped results, and partial best-of-seeds continuation. Release and
Debug passed all 64 tiny classes; the 16-seed test found a valid pair in each class
and independently checked 30 conditional-tail certificates in the current version.
Both complete configurations passed all 28 registered CTests; see the
[pinned validation record](../results/family1-hard-pair-finder-validation/README.md).
The expanded k<=16, common-prefix stratification, admissible-distance and
ranking tests also passed in both complete 28-test configurations; their
[current source and executable pins](../results/family1-finder-lookahead-validation/README.md)
are retained separately from the earlier version.

## Blind quality benchmark

The quality benchmark uses all 20 certified rooted maximizers through seven
states, plus the separately labeled literal and manuscript-reference circulants
at seven and eight states. It passes no saved witness or witness-derived prefix
to the finder. The known exact score is used to report the gap and ratio and
to set the common length budget `2H+8`.

```powershell
uv run --no-project python tests/family1_finder_benchmark.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

Default runs compare a two-letter window with beam four, 128 automatic seeds,
and threshold-two exact tails against the same window search with tails disabled.
Every accepted pair is independently replayed over every static mask. The report
retains misses, pair length, gap, ratio, runtime, exact-tail state counts, caps,
and conditional-proof metadata. Matching a previously certified `H` is distinct
from deriving that `H` from the finder alone.
These known cases are engineering checks, not a held-out generalization test.

The [first version](../results/family1-finder-blind-benchmark/ASSESSMENT.md)
found pairs for 17/24 graphs at each tested tail threshold. The
[updated version](../results/family1-finder-prefixmatch-version-benchmark/README.md),
with profile matching and proven viability pruning, found pairs for all 24.
For the eight seven-state maximizers, threshold-eight lengths were
38,38,37,41,36,36,38,39, compared with exact H=34. This improves coverage but
does not uniformly improve length: some circulants remain poor cases, and
shortest-length matches across all 24 dropped from ten to nine for this setting.
These are version comparisons; prefix preprocessing adds work outside the
128 outer attempts. They do not isolate either optimization's causal effect.
The separate threshold-two viability ablation still hits all 24 graphs with
the general viability check disabled: 23 lengths are unchanged and one
circulant improves from 42 to 40. Sound pruning can change finite-beam choices;
it does not guarantee a shorter heuristic result. The
[ablation report](../results/family1-finder-prefixmatch-viability0-ablation/README.md)
retains all outcomes.

## Seven-state lookahead calibration

The [controlled larger-window sweep](../results/family1-finder-lookahead-grid-v2/README.md)
keeps the older 128-attempt, beam-four prefix budget fixed and tests
k=2,4,6,8,10,12,14,16 with a million-node budget. Only one of eight graphs
reaches 34; its minimum successful tested k is four. Increasing k is not
monotone for the finite beam and first-hit procedure.

The [broader calibration](../results/family1-finder-calibration/README.md)
independently rediscovered length34 pairs for all eight graphs. This required
larger prefix pools as well as deeper lookahead. The last three recoveries
used k16, beam16, complete prefix layers through21, actual-common-prefix
stratification through8, up to65,536 prefix attempts, all128-coordinate distance
bounds and remaining-count ranking. No saved optimal word or witness-derived
prefix was supplied. All accepted pairs were independently replayed over128
static masks; the existing H=34 certificates establish that these lengths
match the minimum. The target cap34 is supplied from that prior certificate.
This is calibration on known cases, not a new global-optimality proof or a
guarantee for an unknown graph.

The [fresh two-stage regression](../results/family1-finder-calibrated-portfolio/README.md)
then reproduced all eight in one automatic run: k6 found three graphs and k16
found the remaining five, in 87.27 seconds wall time on the native Release
build. Every accepted pair passed independent all128-mask replay. Uniform k16
by itself recovered seven within its time limit, so the two-stage result is
kept distinct from a single-window claim.

```powershell
uv run --no-project python scripts/family1_finder_calibrated_portfolio.py `
  --out out/m7-target-calibration-new --jobs 4 --timeout 180
```

This calibrated command uses k6 with 1,024 prefix attempts first, then sends
only its nonhits to k16 with 65,536 attempts. Both stages use beam16 and the
known target34; the second uses the broader prefix and distance settings above,
with a 50,000-node budget per prefix. Every attempt is preserved. It is a
two-stage portfolio, not a claim that a single fixed k succeeds universally.

## Native commands

```powershell
# Historical inexpensive baseline; use the calibrated portfolio above for m7.
.\out\build\msvc-vcpkg\Release\Family1Sample.exe `
  --graph 0001020302030405000604060105 --out out/finder-example `
  --mode finder --length 76 --samples 128 --window-k 2 --beam-width 4 `
  --tail-threshold 8 --tail-max-states 100000 --best-of-seeds

# Full gain distribution for all sixteen common four-letter windows.
.\out\build\msvc-vcpkg\Release\Family1Sample.exe `
  --graph 0001020302030405000604060105 --out out/distribution-example `
  --mode distribution --window-k 4 --first-prefix 001010 --second-prefix 110101

uv run --no-project python tests/family1_finder_prefixmatch_benchmark.py `
  --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

Use a fresh output directory for a changed configuration. Append `--resume`
with identical settings to continue a saved run. The native adapter pins prefix
construction, viability and search budgets in `run.json`; every hit is replayed
by scalar transitions over all masks. Misses leave the score unresolved.
