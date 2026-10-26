# Family 1 heuristic search

This document describes the graph-candidate and hard-word-pair heuristics used
by the native offline runner. The [command reference](family1-offline.md)
explains how to run it. The earlier Python controllers remain available for
their historical experiments; the offline executable runs its own native
bounded search and does not launch those controllers.

## Objective and certificates

A seed is a directed graph with vertices `0,...,m-1`, root `0`, and two outgoing
ports per vertex. Loops, coincident ports and arbitrary indegrees are allowed.
Every vertex must be reachable from the root; strong connectivity is not
required. For a fixed mask `sigma`, input `x` uses port `x XOR sigma[s]` at
state `s`. The mask remains fixed on every revisit.

For a word `w`, let `P_G(w)` be its vector of endpoints over all `2^m` masks.
The score `H(G)` is the least positive `n` such that two distinct words
`u,v` of length `n` satisfy `P_G(u)=P_G(v)`. Each graph is scored separately.
Neither a repeated state at a different length nor a product across several
seed graphs defines this score.

A verified pair of length `L` proves **`H(G) <= L`**. A complete collision-free
length-`d` layer proves **`H(G) >= d+1`**, since a shorter collision would extend
to length `d` by appending the same suffix. Together these bounds can certify
an exact score. Hashes accelerate lookup; full product states decide equality.
Masks at coincident-port vertices can be omitted internally because those
bits never affect any transition.

The heuristic working estimate is `L-1`, with a rough range `[L-2,L]` clipped
to any independently certified bounds. This is a ranking convention, not an
error guarantee or a confidence interval. A search miss supplies no new lower
bound. In particular, a longer found pair does not prove a harder graph.

## Candidate graphs

Canonicalization identifies root-preserving vertex relabelings and independent
port swaps. Moving the root can give a different rooted class. Every accessible
root of a selected underlying graph is considered separately; isomorphic
rooted copies are deduplicated without collapsing different classes.

The editable neighborhood uses five primitive operations:

1. Retarget one outgoing port, retaining accessibility.
2. Insert a routing vertex into two edge occurrences, with its outgoing ports
   leading to the former targets.
3. Insert a routing vertex into one edge occurrence, with one outgoing port
   leading to the former target and the other a self-loop.
4. Apply the exact inverse of operation 2.
5. Apply the exact inverse of operation 3.

Every intermediate graph remains accessible and within the supported sizes
`1..20`. The root stays fixed during edits. Considering other accessible roots
afterward is an additional candidate-generation operation, not a zero-cost
rooted edit. See [the full edit definition](family1-graph-edits.md).

The radius limits the number of primitive edits. Path and candidate budgets
bound the generated neighborhood. Parents, edit types and depth layers share
work, rather than requiring an explosive shallow layer to finish before any
deeper layer can be visited. Deterministic seeds and canonical-key ordering
make a fixed bounded plan reproducible, subject to clock-based stopping.

The executable embeds only graph tables: all 20 certified rooted maximizing
classes through size seven, and two eight-state experimental graphs. It does
not embed their word witnesses or score labels as answers. Default searches
use this catalogue to bootstrap parents and target-size seeds, plus the
circulant baseline `i -> i+1 (mod m)` and `i -> i+floor(m/3) (mod m)`.
When a preceding size is absent from the catalogue, root stems provide
accessible extensions of smaller seeds. These are starting points, not
claimed maximizing constructions. Explicit parent keys allow a later run to
explore a newly found graph's neighborhood.

This catalogue makes the default search a warm start. Benchmarks claiming to
discover a graph without prior knowledge must supply an appropriate parent
set instead. The known child graph must not secretly be used as a seed in
such a benchmark.

## Prefix pairs and permutation constraints

A trial starts with distinct equal-length prefixes `u,v`. Each mask gives a
pair of current states. In some masks both input transitions are permutations;
such a coordinate can never merge two different states under a common suffix.
Therefore the prefixes must already agree on every such coordinate. This is
a necessary condition, not a restriction to permutation seed graphs.

For prefix generation the runner selects at most 64 permutation coordinates,
groups words by their complete endpoint vectors on that selected set, and
selects distinct words from matching buckets. This is a prefix-generation
optimization: a subsequent gate checks every permutation coordinate, and the
suffix objective and positive replay use all masks. An incompatible prefix
cannot become a positive finding merely by passing the selected coordinates.
If there are no permutation masks, this necessary constraint is empty. Complete short
prefix layers and sampled longer layers have explicit word, pair and sample
budgets. Common-prefix strata can retain pairs with different initial shared
prefix lengths. Prefix breadth matters independently of the lookahead window.

## Agreement metric and lookahead

For a retained prefix pair, define

`D(u,v) = #{ sigma : delta_sigma(0,u) != delta_sigma(0,v) }`.

The complete static-mask product is used for this metric. Bitsets pack the
coordinates for speed; the objective is not a count over randomly selected
DFAs. Appending the same symbol to both words cannot destroy an agreement,
so `D` is nonincreasing along a common suffix.

At a beam node, enumerate the binary common suffixes of the next `k` symbols.
For a window `z`, its drop is `D(u,v)-D(uz,vz)`. A complete window has `2^k`
leaves and `2^(k+1)-2` transition edges. With multiple retained parents,
multiple rounds and multiple prefix pairs, the work is substantially larger
than `2^k` for the entire search.

Retain several promising leaves by remaining disagreement, using deterministic
tie breaking, and continue from them. A beam preserves alternatives that a
single greedy choice would discard. Window reports include drop distributions:
minimum, maximum, mean, spread and histogram. A complete distribution describes
all leaves of that particular window, not all word pairs at that total length.
Budget truncation, an early positive hit or branch pruning can leave a window
incomplete. Its histogram then describes the visited leaves only. Diagnostic
retention is bounded independently of the search, with omitted-report counts.

Near a small disagreement threshold, perform breadth-first search for a common
suffix, storing complete residual pair states. This can find a shortest suffix
for that fixed prefix pair or beam node. It does not prove that the resulting
whole word pair is globally shortest: a different prefix pair may be better.
Depth, state and call budgets can also leave the tail search unresolved.

A further pruning rule examines individual residual DFA coordinates. Complete
reverse breadth-first search on that DFA's ordered state pairs determines
which pairs can ever reach a diagonal. If one current coordinate is proved
unmergeable, that particular prefix/suffix branch is impossible and is pruned.
For mergeable coordinates, the maximum of their individual shortest merge
distances is a lower bound on the common suffix length. It can prune a branch
that cannot finish within the remaining length budget. Coordinate checks and
their table cache are bounded; unexamined or incomplete tables supply no
negative proof. These are conditional branch deductions, not lower bounds on
the graph's global `H(G)`.

Every accepted pair is replayed over all static masks before updating a bound.
Each shorter verified positive is journaled before the next prefix trial, and all
retained graph classes remain in the journal when the estimated leader changes.

## Refinement and rarity

For each graph, retain the shortest verified pair found so far. Larger windows,
more prefix pairs or words, a wider beam and a larger exact-tail budget can all
improve it. Their effects differ: increasing `k` does not repair inadequate
prefix coverage. Expansion budgets must grow with window size; a nominal
`k=16` setting cannot explore a full window with only a few thousand expansions.

A crowded band near the largest observed pair lengths triggers further word
refinement, up to the configured maximum window. Recompute the leader and
retain every tied rooted class after improvements. Increasing the edit radius
in a subsequent run explores farther graphs. The offline runner exposes these
controls explicitly; it does not imply that a bounded native run reproduces
every scheduling decision of the earlier Python experiments.

Rarity is a useful search preference, not a pruning theorem. A small estimated
top tier does not certify optimality. Conversely, a crowded tier can signal a
weak word finder rather than many truly extremal graphs. Certified lower bounds,
verified upper witnesses, heuristic estimates and unresolved cases must remain
separate in every report.

## Calibration and limits

The earlier graph-only seven-state calibration had eight known score-34
classes. Its bounded initial lengths were `34,34,34,35,36,36,38,38`; broader
prefix work improved them to `34,34,34,34,34,35,36,38`. The rough two-step range
covered seven of eight classes in that experiment. This directly rules out
treating `L-1` or `[L-2,L]` as certified accuracy guarantees. See the committed
adaptive-search and calibration reports for the historical settings.

The offline runner's small exact-mode results and heuristic witnesses are
checked independently by its integration tests. Native offline runs are new
experiments; previously verified scores are not automatically attached to
the embedded seeds. Timeouts, graph caps, memory limits, pending roots and
depth caps remain visible in the outputs.

The first packaged runner matched every exact score for all 742 classes through
size four against an independent exhaustive scalar implementation. It also
reproduced all 10,398 five-state scores from the complete earlier journal and
all five maximizing classes, with 332,736 independent graph/mask witness replays.
Both full-project Windows configurations passed 36 tests, and both standalone
configurations passed their two CTests, including the independent CLI suite.

A new graph-only seven-state run used `k=8`, beam 16, 1,024 prefix pairs,
prefix depth 18, 262,144 complete words per layer, 32,768 samples per sampled
depth, and five seconds per graph. In canonical-key order its returned lengths
were **35,36,34,38,34,36,34,38**, against true score 34 for every graph. All pairs
were verified; the two-step rough range covered six of eight cases. This short
run recovered three actual shortest lengths and left two errors of four.
The longer historical calibration above used different budgets and scheduling.

For the eight-state working candidate
`01020003040501060003020705060407`, the native runner reconstructed a verified
length-50 pair from the graph alone, using the same prefix/beam settings,
maximum total length 80 and a ten-second budget. It completed 1,024 prefix
trials in approximately 7.34 seconds on this machine. All 256 masks passed
scalar replay. The resulting estimate is 49; no exact score or global maximum
follows. Clock-limited results can vary with hardware and concurrent load.

Both exact scoring and the heuristic all-mask objective can become expensive:
there are `2^m` mask coordinates, `2^n` words at an exact layer, and rapidly
growing graph neighborhoods. Supporting an input size through 20 does not
guarantee an exact answer, a witness, or a global certificate within a given
budget. The conjectured growth of the maxima is not used as a proven bound.
