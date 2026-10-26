# Edit neighborhoods and search priority

Searching edits of previous winners and near-winners is a useful way to find
strong candidates. The certified small cases support this priority, but they
do not justify discarding the remaining graph classes. Root robustness is
another priority signal, rather than a certificate of optimality.

The [validation data](../results/family1-edit-priority/validation.json) records
the checks below and pins their source files. The
[edit metric](family1-graph-edits.md) keeps the root fixed, allows arbitrary
indegrees, and permits only accessible intermediate graphs.

## What previous near-winners cover

For each winning child, the ancestry audit finds the highest-scoring accessible
parent obtained by one permitted routing-vertex deletion. All ties and both
edge-occurrence reconnection bijections are retained.

| Step | Previous maximum | Best parent scores of every winning child |
|---|---:|---|
| 1 to 2 | 1 | 1 |
| 2 to 3 | 3 | no permitted parent; 1 |
| 3 to 4 | 6 | 5 |
| 4 to 5 | 10 | 9, 9, 9, 9, 8 |
| 5 to 6 | 15 | 15, 14 |
| 6 to 7 | 23 | 21, 22, 21, 23, 22, 22, 22, 22 |

Thus parents within two of the previous maximum cover all winners in the
observed steps from 3 to 4 through 6 to 7. One three-state winning class has
no permitted routing parent at all. A proof that a fixed parent-score window
or edit radius covers every future maximizer is not available.

The broader unit edit metric gives exact distances at most three from every
certified winner through seven states to the complete previous winning set.
This is a finite observed result, not a size-independent theorem.

## Scores need not be close in an edit neighborhood

Each of the eight seven-state maximizers has an accessible neighbor of score
one, obtained by making its two root ports coincide with one retargeting.
The validation file retains twelve such operations, with full tables. For
example, change the first row of

```json
[[0,1],[2,3],[2,3],[4,5],[0,6],[4,6],[1,5]]
```

to `[1,1]`. The original graph has certified `H=34`; the modified graph is
accessible and has `H=1`, witnessed by the distinct words `0` and `1`.
This verifies a score change of 33 across a single edit. A low-scoring graph
can therefore be adjacent to a global maximizer.

There is also a general obstruction to a universal constant Lipschitz bound.
For an integer `L>=1`, take a root with one loop and one edge to a full binary
tree of depth `L-1`. Both outgoing ports of a leaf are loops at that leaf.
There are `m=2^L` vertices. In the all-zero static mask, every word of each
fixed length `n<=L` reaches a distinct state: `0^n` stays at the root, while
`0^k 1 u` reaches the tree vertex named by `u`. At a fixed word length, that
vertex also determines `k`. Consequently `H>=L+1` for the full Family 1
product. Retarget the root loop to its other target. The graph stays accessible
and now has `H=1`. One edit can change `H` by at least `L`, for unbounded `L`.
The finite checks in the report verify instances `L=1,...,6`; the argument
proves the assertion for every `L`.

More strongly, the set of score-one graphs is within two retargetings of
every graph at the same size. Keep a rooted DFS spanning tree. If the root
has one tree child, retarget its other port to that child. If it has two
tree children `A,B`, choose a tree leaf in the `A` subtree, retarget one
of that leaf's nontree ports to `B`, and then retarget the root's edge to
`B` into an edge to `A`. The first edit preserves the entire spanning tree.
After the second, the `B` subtree remains reachable through `A`, its chosen
leaf, and the new edge. The root ports now coincide, giving `H=1`.

This construction was checked on all 64 rooted classes through size three
and all eight seven-state maximizers. Among those 64 classes, 22 already
have score one, 28 use one retargeting in this construction, and 14 use two.
These counts describe the construction, not minimum distances for every class.

If a proposed same-size one-retarget inequality were
`abs(H(G)-H(J))<=B(m)` for every neighboring pair, this construction would
already imply the global bound `F(m)<=1+2B(m)`. Obtaining a tight universal
edit inequality can therefore be as hard as the desired global score bound.
A bound only for routing insertions is a different statement and also needs
a coverage theorem before it yields an induction for all graphs.

## Root robustness

Every accessible choice of root should be scored separately and canonicalized
under root-preserving isomorphism. Ordinary graph automorphisms may identify
several vertex choices, so the number of winning vertices can differ from
the number of winning rooted classes.

For the certified ordinary winning shapes, the counts of vertices at the
global maximum are:

| Size | Winning-root vertex counts, one entry per ordinary winning shape |
|---:|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 2 |
| 4 | 1 |
| 5 | 2, 1, 1, 1 |
| 6 | 2 |
| 7 | 1, 1, 1, 5 |

The two vertices at size two give only one rooted class. At size seven all
four ordinary shapes have trivial vertex automorphism groups, so their winning
vertex and rooted-class counts agree. The other roots at size seven have
certified upper bound 33; their exact scores are not supplied by this report.

Root robustness is neither necessary nor sufficient for global optimality.
Some certified winning shapes have only one winning root. Conversely, a
directed cycle with coincident ports at every vertex has `H=1` at every root;
it is not globally optimal for any size at least two. Equal scores at all
roots alone do not establish that the common score is large.

Even robustness above a substantial fixed threshold can be amplified by a
construction. In the atlas's seven-state loop-chain extensions, the projection
to the certified base maps the original root and all `m-7` new chain vertices
to base root zero. Every one of these `m-6` roots inherits `H>=34`.
The extensions are strongly connected: the old base is strongly connected,
the replacement chain preserves every old route, every new vertex returns
to the old graph, and the root reaches the entire chain. Thus all these
rerootings retain exactly `m` accessible vertices.

The report checks every projection for every size 8 through 20 and every
root in that fiber, including all 128 base masks and both input symbols.
It exports **104 distinct rooted classes** in
[root-lift-candidates.jsonl](../results/family1-edit-priority/root-lift-candidates.jsonl):
there are respectively 2 through 14 certified roots at sizes 8 through 20.
All have lower bound 34; their exact scores and global optimality remain
unknown. The other six roots of each extension remain legitimate search
candidates as well; this lower-bound export does not score or exclude them.

## Rigorous lower bounds and exact sizes

Suppose a root-preserving projection `pi:J->G` satisfies, for each state and
port, the transition identity

```text
pi(tau_J[s][p]) = tau_G[pi(s)][p XOR e(s)].
```

Here `e(s)` accounts for a possible local port swap. Lift each base static mask
by `sigma_J(s)=sigma_G(pi(s)) XOR e(s)`. The bits stay fixed on every revisit.
Induction on a word gives

```text
pi(delta_J,sigma_J(root_J,w)) = delta_G,sigma_G(root_G,w).
```

Any collision across all masks of `J` would therefore be a collision across
all masks of `G`. Hence `H(J)>=H(G)`. This is a lower-bound transfer and does
not give an upper bound on `H(J)`. Every graph projects to the one-state
loop graph, whose score is one, illustrating why the reverse inequality fails.

There is a general exact-size extension for any accessible seed. Retain a
rooted spanning tree and choose a port occurrence `a->v` outside that tree.
Such an occurrence exists, since the graph has `2m` edges and the tree only
`m-1`. Add a new nonroot copy `v'` of `v`, with its two outgoing targets copied
before changing any edges, and redirect the chosen occurrence to `v'`.
The original tree preserves access to all old vertices and the redirected
edge reaches the new one. Mapping `v'` to `v` and fixing old vertices is a
port-preserving projection. Therefore this exact `(m+1)`-state graph has
score at least the original score. Repeating the construction proves
`F(m+1)>=F(m)` and propagates a certified lower bound to every larger exact
size. This cloning construction is not an additional unit move in the edit
metric defined earlier.

In particular, the certified seven-state result supplies a rigorous
`F(m)>=34` for every exact size 8 through 20. It does not certify that 34
is optimal or that the exported graphs attain the unknown optima. Combining
different seeds into one product is not used in this argument.

## Safe pruning and useful priority

A verified equal-length witness pair is an admissible upper bound for its
graph. If its length is strictly below the incumbent certified lower bound,
that graph cannot attain the maximum and can be pruned from contention.
An upper bound equal to the incumbent must be retained until a potential tie
is resolved; every maximizing class is required.

An old witness transfers unchanged across edits that avoid every edge
occurrence traversed by either witness word under every static mask. An
induction on the two paths proves that all their endpoint vectors remain
unchanged; new mask bits are irrelevant when new vertices are unvisited.
This can certify an upper bound for an entire explicitly constrained edit
region. If a changed edge is used, directly verifying the old pair on the
new graph is a safe and often cheap upper-bound test. A failed pair gives
no lower bound.

More generally, a region can be pruned if a formally verified certificate
shows that every graph in it has an upper witness shorter than the incumbent.
This needs a proof over the whole region, including all graph choices and
all static masks. A score of the parent, a short edit distance, or a large
number of high-scoring roots does not supply such a proof.

A practical ordering is to expand previous winners and near-winners first,
try their known witness pairs on new candidates, reroot every new ordinary
shape, deduplicate rooted classes, and deepen only unresolved challengers.
Root-wise certified lower bounds can prioritize robust shapes. Classes
outside the explored edit neighborhoods remain unresolved until a coverage
or upper-bound certificate handles them. A completed local search certifies
its explored region; it is not a formal global certificate for sizes 8–20.
