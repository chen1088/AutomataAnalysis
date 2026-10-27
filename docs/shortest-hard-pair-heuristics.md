# Heuristics for shortest hard word pairs

This reference describes the deterministic word-pair algorithms used for
Family 1, their work budgets, and the evidence for their accuracy. The target
is the **shortest pair of distinct, equal-length binary words** that agrees
on every automaton in a family. A verified pair supplies an upper bound;
bounded seed selection and beam search do not generally prove shortestness.
The production entry point is [Family1NearPair](family1-near-cli.md).
The [strategy report](family1-finder-strategies-report.md) and
[adaptive-window report](family1-adaptive-window-report.md) contain the
individual experiments and unfavorable results as well as successful ones.

## Objective, state, and certificates

A Family 1 input is a root-accessible directed graph with vertices
`0,...,m-1`, root 0, and two outgoing port occurrences per vertex. Loops,
coincident ports, and arbitrary indegrees are allowed. Each original static
mask `sigma` defines a DFA: at state `q`, binary input `x` follows port
`x XOR sigma[q]`. The same mask applies on every revisit. There are
`N=2^m` mask coordinates.

Let `E(w)` be the ordered vector of endpoints reached by word `w` from the
root in every mask. Then

```text
H(G) = min { n >= 1 : u,v in {0,1}^n, u != v, E(u)=E(v) }
D(u,v) = #{ sigma : E(u)[sigma] != E(v)[sigma] }.
```

The synchronized count is `N-D`. In particular, `D(empty,empty)=0`, and
identical words always have D=0. Success requires **both** `u!=v` and D=0.
There is no requirement that D first become positive: a first unequal input
can already give a valid pair. Distinctness is part of the search state,
separate from the endpoint vectors.

One joint step appends one ordered symbol from **00,01,10,11**. All four
remain available after every prefix. Agreement is not monotone: 01 or 10
can separate two currently equal endpoints. Consequently the joint state
retains both complete endpoint profiles, including coordinates already in
agreement. D is a ranking signal, not an admissible estimate of remaining
length. For example, the two-state closure has the joint k=2 witness
`u=000`, `v=110`, with prefix trace `[0,4,2,0]`. The
[paired-word figure](../output/figures/hard-pair-joint-startup-example/witness.svg)
shows the graph, words, trace, and producing settings.

All-mask scores and scalar verification count every original mask, retaining
the multiplicity of identical DFA realizations caused by coincident ports.
An internal exact representation may eliminate irrelevant mask bits only
when its equivalence preserves endpoint equality; the reported D objective
still uses original-mask weights. Every accepted positive is independently
replayed with scalar DFA transitions. A length-L positive proves `H(G)<=L`.
A miss supplies no lower bound.

Complete exact binary word layers are a separate oracle, with **k=N/A**.
The first layer containing two distinct words with equal full profiles gives
H exactly. A completed collision-free depth-d layer proves `H>=d+1`:
any shorter collision would extend to that layer with a common suffix.
An incomplete layer supplies no additional lower bound. Full states decide
equality; hashes alone cannot establish a collision.

## Graph-only starts and the default portfolio

The [native pipeline](../Family1NearPair.h) first attempts exact layers
through depth 24, with a 16,777,216-word layer limit and 256 MiB of planned
array payload. These are work and storage limits, with no clock cutoff.
An exact positive returns immediately; a refused layer preserves only the
lower bound already proved. This phase must remain visible when evaluating
the heuristic: an exact recovery at k=N/A is different evidence from a
joint-search recovery at numeric k.

The heuristic constructs starts from the graph, without reference words or
H labels. Complete binary layers extend through depth 20, subject to
1,048,576 words per layer. Words are grouped by their endpoint profiles on
up to 64 selected permutation coordinates. Canonically ordered compatible
pairs form a bounded catalogue, normally capped at 16,384 pairs. These
complete word layers do **not** imply enumeration of all compatible pairs.
The catalogue cap is an explicit heuristic restriction.

Every collected pair receives its full-family D score. Selection uses
channels `(word length, actual longest common prefix length)`; each channel
is sorted by `(D,u,v)`, and deterministic round-robin selection distributes
512 starts among channels. This preserves several lengths and ages of the
first difference. Ranking every identical common-prefix state by its initial
D=0 would provide no useful discrimination. See
[Family1ScoredSeeds.h](../Family1ScoredSeeds.h) and
[Family1JointSeeds.h](../Family1JointSeeds.h) for the actual catalogue rules.

The default then runs joint **k=4, beam B=16**, with maximum total length 80
and 2,000,000 node expansions per selected-seed attempt. It commits full
blocks. If no positive is found, a deterministic compact-catalogue retry
collects at most 4,096 pairs per prefix layer and selects another 512 starts.
Its wide-profile fallback uses the global-catalogue rule. The retry depends
on a miss, never on a known answer.

The portfolio also reranks the original catalogue by mask-specific
**common-input** merge distances. For each coordinate, reverse BFS on ordered
state pairs gives the shortest common suffix that merges its current states,
or infinity. The maximum-first seed tuple is

```text
(number of infinities, largest finite distance, sum of finite distances,
 D, u, v).
```

The same channels select another 512 starts for the same joint k=4 search.
The original word catalogue is reused; rescoring and joint work are charged.
Thus 512 means per ranking stage: the portfolio may select 1,024 starts,
or 1,536 with the compact retry, including overlaps. Every stage retains
the shortest previously verified upper.

An infinite common-input distance is only a seed preference here. Different
future inputs can merge states that no common suffix can merge. Neither
that distance nor permutation incompatibility can safely reject a branch
of unrestricted four-symbol joint search.

A separate, simpler startup enumerates every common binary prefix x through
depth c and independently tries `(x0,x1)` and `(x1,x0)`. Its declared set has
`2*(2^(c+1)-1)` starts, all traversed in length/lexical order. It provides
explicit bounded first-difference coverage, rather than the scored catalogue's
selection policy; see [joint startup](family1-joint.md).

## Fixed lookahead: block and rolling advancement

Joint k always counts paired-symbol steps. A complete depth-k window has
`4^k` leaves and

```text
W(k) = sum(j=1..k) 4^j = (4^(k+1)-4)/3
```

transition edges. At k=4 these are 256 leaves and 340 expansions per parent.
All intermediate depths are checked for distinct D=0 pairs, so a shorter
positive inside a window is retained. The whole evaluated population still
finishes. Final windows clipped by a length cap record their actual span.

[Block search](../HardPairJointFinder.h) ranks full-depth leaves by
`(P,D,u,v)` when permutation priority is enabled, or `(D,u,v)` otherwise.
Here P counts disagreeing coordinates whose two input maps are permutations.
A common continuation cannot merge their unequal endpoints; independent
inputs may. P therefore changes priority without removing joint symbols.
Beam one is greedy block lookahead. A wider beam retains several full
endpoints and advances each by the entire selected k-symbol block.

[Rolling search](../HardPairJointRolling.h) evaluates the same full window
but groups leaves by their first action. Each immediate child inherits the
best future `(P,D)` rank among its `4^(k-1)` completions. The beam retains
one-symbol children by future rank, then immediate `(P,D)` and lexical words,
and recomputes lookahead next round. It does not commit the rest of the
previously favored suffix. Optional tie, diversity, and cycle controls are
separate configurations; they must be identified in comparisons.

```text
for each deterministically selected distinct seed (u,v):
    beam = {complete_state(u,v)}
    inspect seed for success
    while beam can advance within the length limit:
        candidates = empty
        for each retained parent in deterministic order:
            s = min(k, remaining length)
            require enough remaining node budget for W(s)
            enumerate every 00/01/10/11 extension through s
            inspect every intermediate state for distinct D=0
            if block: add depth-s endpoints with their (P,D,words) rank
            if rolling: add first children with best conditional future rank
        preserve shortest verified positive across all parents
        stop this attempt after success or budget refusal
        otherwise deduplicate complete states at this depth and retain beam
return shortest scalar-verified positive across all attempts
```

Atomic budget checks prevent a nominal k window from becoming a sampled or
partially explored comparison. A started fixed window finishes. The block
finder's cooperative interrupts are checked between windows; a forcibly
terminated benchmark has no completed summary. A refusal and length exhaustion have
different recorded statuses, and neither means that no pair exists.

Safe same-depth deduplication requires the complete ordered profiles and
distinctness flag. D, P, a histogram, or a hash without full equality is
insufficient. Equal future states can share a deterministic representative;
adaptive deduplication retains the better available forecast before lexical ties.
beam truncation still discards other future states heuristically. Reducing
the remaining length cap to `best_upper-1` safely skips attempts that cannot
improve an existing positive. No other bound follows from a small D.

For S starts, B retained parents, and R rounds, full-window transition work
is at most `S*R*B*W(k)` before the per-attempt expansion cap. Block search
uses roughly `ceil((L-seed_length)/k)` rounds; rolling can use
`L-seed_length` rounds. Each transition also pays the packed-profile update
and score cost. Retention, equality checks, and word storage add overhead;
the bound describes node work rather than elapsed time. Prefix generation,
seed scoring, exact layers, and common-distance preprocessing are separate
costs, not free work hidden inside k.

## Common-suffix search has narrower coverage

After **distinct** equal-length prefixes, appending a shared suffix preserves
distinctness and produces legitimate certificates. Its alphabet is only
00,11, with `2^k` leaves and `2^(k+1)-2` edges for a complete common-k window.
Agreement is then monotone, so agreeing coordinates can be dropped from
the residual objective. Proven unmergeability in an individual coordinate
can reject that fixed common-suffix branch. Its individual merge distance
can also bound the required common-suffix length.

These deductions apply to the restricted continuation problem. They do not
prove global H or permit the same coordinate deletion and pruning in joint
search. Starting a common-suffix search from two empty words would keep the
words identical forever. Reports must label **common k** separately from
**joint k**; see the [common-suffix method](family1-heuristic-method.md).

## Variance-adaptive rolling horizons

[HardPairJointAdaptive.h](../HardPairJointAdaptive.h) grows a complete
frontier from minimum k to maximum k, reusing earlier levels. For leaf scores
`d_i`, population size `M=4^k`, and original family size N, normalized total
population variance is

```text
V = (M*sum(d_i^2) - sum(d_i)^2) / (M^2*N^2).
```

The normalized decrease `(D(parent)-d_i)/N` has the same variance, as does
the normalized synchronized count. These are population moments over every
leaf, not sample estimates. Identical-word leaves remain in the population;
the success test still excludes them.

At each eligible complete horizon, select k when V meets the declared
threshold; otherwise deepen through maximum k. Thresholds are integer parts
per million. Exact portable 128-bit comparisons select the horizon without
floating-point decisions. The first-action-mean variant substitutes

```text
V_action = (4*sum_a(s_a^2) - sum(d_i)^2) / (M^2*N^2),
s_a = sum of d_i among leaves beginning with action a.
```

This measures variance of the four conditional means D/N. It differs from
variance of conditional minima. The progress variant additionally requires
a strictly better numeric `(P,D)` endpoint somewhere in the window; the
committed immediate child need not improve D.

The selected horizon ranks first actions as in rolling search and commits
one symbol. Adaptive block advancement is rejected because different
horizons would put different word lengths into one beam. Minimum-window
work is checked before expansion; each additional complete layer costs
`4^j` more nodes. If growth cannot fit, the completed statistics remain
recorded, but the provisional horizon is not committed as a fallback. The
attempt finishes other affordable parents in that round, preserves positives,
and ends with an explicit refusal. Partial populations never choose k.
Frontier storage grows as `4^k`; adaptive work through selected k is W(k),
with additional probes charged even when their paths lose.

```text
adaptive_probe(parent, k_min, k_max, threshold):
    preflight the complete minimum window; refuse atomically if it cannot fit
    frontier = {parent}
    for j = 1,...,min(k_max, remaining length):
        require budget for every one of the next 4^j transitions
        frontier = all four children of every previous frontier state
        record complete moments and inspect distinct D=0 pairs
        if j < min(k_min, remaining length): continue
        if a positive was found: return the complete positive window
        if variance meets threshold and the optional progress gate passes:
            return this horizon and its first-action forecasts
    return the final complete horizon, or an explicit budget refusal
```

An incremental refusal ends the attempt after the affordable parents in that
round are finished. It does not commit a smaller fallback horizon. Reaching
maximum k without meeting the threshold is an explicitly capped decision,
not evidence that the variance criterion succeeded.

Variance is not confidence that the next action is good. At joint k=2,
the saved graph `000100020202` has normalized total variance `13/256` but
all four conditional minimum D values equal 4. Graph `000100020002` has
four equal conditional means 5, yet minima `4,3,4,4`. The
[complete scalar counterexamples](../results/family1-adaptive-window-20261027/variance-counterexamples.json)
show both failures of that interpretation.

## Measured accuracy and limits

The oracle-off strong calibration uses all 20 certified winners through
m=7, 512 starts per ranking, B=16, length 80, and 2,000,000 expansions per
attempt. Fixed block **joint k=4** and fixed rolling **joint k=4** each find
16 exact reference lengths and all 20 within one. Both six-state winners
return 24 against H=23. The hybrid production calibration instead includes
exact depth24, **k=N/A**, alongside joint k=4 and reaches 18 exact matches.
Its exact phase accounts for its minimum proofs through m=6; these are not
oracle-off heuristic successes.

The broader oracle-off stress test uses every one of 343 saved graphs,
64 starts per ranking, B=16, and the same length/expansion limits. Exact H
is known for 296 rows. Missing pairs remain in denominators:

| Policy | Joint k | Found /343 | L=H /296 | Largest finite known-H gap |
|---|---|---:|---:|---:|
| Fixed block | 4 | 338 | 237 | 10 |
| Fixed rolling | 4 | 340 | 264 | 10 |
| Total variance, 1,000 ppm | 2..5 | 339 | 236 | 13 |

Rolling k=4 uses about 3.8 times the block transition work in that test.
Low-threshold variance returns **exactly the same word pairs and misses**
as fixed rolling k=2 on both this frontier and the strong 20-winner suite,
with slightly more work: 31,104 and 34,240 extra nodes respectively.
At 512 starts per ranking, adaptive **joint k=4..6**, 10,000 ppm also
gets 16 exact and all 20 within one, using 1,254,092,004 joint nodes versus
599,764,196 for fixed rolling k=4. The observed extra adaptation work does
not improve those lengths.

Among 47 seven-state nonwinners, block k=4, rolling k=4, and adaptive
k=2..5 each miss three graphs, including one with a separately verified
length-32 certificate. The hybrid exact-plus-joint-k=4 pipeline returns
43 for that graph, already proving an error of at least 11. Historical
certificates remain separate from new finder results; an unknown historical
producing k stays unknown. A narrow or rare band of large returned uppers
therefore cannot certify good graph rankings.

These winner cases were used for development, and the saved frontier
overlaps them. Neither set is all seven-state graphs or independent evidence
of a universal near-shortest error bound. The
[adaptive evidence index](../results/family1-adaptive-window-20261027/README.md)
links complete pair tables, moment records, k sequences, and figures.

## Reproducible reporting and candidate coverage

No random choices, random sampling, random tie ordering, or clock-driven
selection belong in this workflow. Candidate graphs, prefix catalogues,
beam ties, and attempt order are deterministic. Graph generation and word
finding have separate coverage claims: an experiment declaring an edit
neighborhood must enumerate and test **every member**, with all tied rooted
classes retained. A capped generation or a ranked prefix of the candidate
file cannot be called that complete neighborhood. The
[edit definition](family1-graph-edits.md) specifies retargeting and routing
insertions/inverses, root handling, and accessibility.

Every experimental report must state joint k or its configured adaptive
range, common k where applicable, and k=N/A for exact or non-window work.
Record B, starts per ranking, catalogue/layer caps, length limits, expansion
limits, actual node work, misses, and refusal reasons. A seed-catalogue
positive has producing k=N/A without implying an exact-oracle proof.
Adaptive witnesses need the actual producing-k sequence, including clipped
final spans, as well as configured bounds. Winning-path moments describe
that ancestry; all-attempt work and k histograms account for losing probes.

Retain actual u and v, full prefix D and `N-D` traces, original-mask count,
winning seed, producer, and source/configuration pins in the machine-readable
record. Put the actual pair and trace beside its graph in figures, using the
[witness renderer](hard-pair-figures.md). Keep reference labels outside native
queries and attach them only after outputs are sealed. The saved adaptive
validation reports 13 passing semantic CTests and independently reconstructs
1,545 complete windows from scalar transitions, including conditional moments,
atomic budget refusal, and winning ancestry. These checks establish algorithm
and artifact consistency; measured gaps and misses still determine accuracy.
