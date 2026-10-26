# Rooted graph edit distance

We compare accessible rooted directed multigraphs with exactly two outgoing
edge occurrences at every vertex. Loops and coincident ports are allowed;
indegrees are unrestricted. The root remains fixed throughout an edit sequence.
The Family 1 score is a separate function on this space.

## Free identifications

Root-preserving vertex relabelings and independent swaps of the two outgoing
ports have cost zero. Thus the objects being compared are rooted isomorphism
classes, with the same equivalence relation as the exhaustive search.

The minimum below is over all such relabelings, rather than over the displayed
vertex numbers. Changing the root is not a free identification or an allowed
edit. An ordinary, unrooted comparison would be a different distance.

## Unit edits

Every intermediate graph must remain root-accessible and have two outgoing
ports at every vertex. The following operations and their inverses cost one.

1. **Retarget one port.** Replace one occurrence `a -> b` by `a -> c`.
   Other outgoing ports are unchanged. This allows arbitrary indegrees.
2. **Insert a routing vertex into two edges.** Choose two distinct edge
   occurrences `a -> b` and `c -> d`, add a new nonroot vertex `v`, and replace
   them by

   ```text
   a -> v,  c -> v,  v -> b,  v -> d.
   ```

   Sources or targets may coincide, and either chosen occurrence may be a loop.
   Distinct occurrences are required even when the original edges coincide.
   Its inverse deletes a nonroot vertex with no self-loop and exactly two
   incoming occurrences, matching them to its two outgoing occurrences in
   either bijection.
3. **Insert a routing vertex with a loop.** Replace one occurrence `a -> b` by

   ```text
   a -> v,  v -> v,  v -> b.
   ```

   Its inverse deletes a nonroot vertex with one loop and one external incoming
   occurrence, joining that incoming occurrence to its external outgoing target.

In inverse operations, inaccessible results are discarded. Insertions always
preserve accessibility: each former edge can still be followed, through the
new vertex. No operation removes the root or silently removes other vertices.

The two routing edits preserve every old vertex's indegree and give the new
vertex indegree two. Starting from a balanced graph, routing edits alone stay
balanced. This is a property of these edits, not a restriction on the graph
universe or on the exhaustive Family 1 search.

These routing edits are **macro operations of unit cost**. If cost instead
meant “one vertex insertion plus one unit per changed target,” a two-edge
insertion would have a different price. The convention must be stated before
comparing numerical distances. An edge switch that exchanges two targets is
two retargeting edits here; it is not an additional unit move.

## Definition and metric property

Write `d(G,J)` for the minimum number of unit edits in a sequence from the
rooted class of `G` to the rooted class of `J`. Relabelings and port swaps can
be applied freely between successive edits. There is no imposed size budget
on intermediate graphs.

This is a finite, integer-valued metric on all finite accessible rooted
two-out graphs:

- An empty edit sequence gives distance zero precisely for the same rooted
  class. Distinct classes require at least one positive-cost edit.
- Every permitted edit has a permitted inverse between the same two accessible
  graphs, giving symmetry.
- Concatenating sequences gives the triangle inequality.
- The edit graph is connected, as shown below, so the minimum is finite.

For connectivity at a fixed size `m`, retain any rooted depth-first spanning
tree and list vertices in its preorder. Each nonleaf vertex is followed in
preorder by its first child, so that successor edge already exists. If a leaf
has a successor in preorder, retarget one of its outgoing ports to that
successor. A tree leaf has no tree edges among its outgoing ports; consequently
these edits retain the whole spanning tree and preserve accessibility. The
result contains a directed Hamilton path starting at the root.

Keep the path edges and retarget all other outgoing ports so that both ports
of every nonfinal vertex go to the next vertex, and both ports of the final
vertex are loops. The retained path preserves accessibility during every
retargeting. Up to a free relabeling, this is one canonical graph `P_m`.

To pass from `P_m` to `P_(m+1)`, insert a loop-routing vertex into one loop at
the final vertex. Retarget the old final vertex's other loop to the new vertex,
and retarget the new vertex's edge back to its predecessor into a loop. These
three edits preserve accessibility. Thus all the `P_m` are connected, proving
connectivity across sizes as well. This argument works for arbitrary finite
sizes; the current implementation and saved experiments support sizes 1–20.

Since a unit edit changes vertex count by at most one,

```text
d(G,J) >= abs(number_of_vertices(G) - number_of_vertices(J)).
```

## Measured distances between consecutive maximizers

Let `W_m` be the complete set of rooted Family 1 global maximizers at exactly
`m` reachable vertices, and define

```text
d(W_m,J) = min { d(G,J) : G in W_m }.
```

This minimum is not taken over one arbitrarily selected winning representative.
The full certified collections are used, including different roots of the same
ordinary shape.

The [exact distance report](../results/family1-edit-distance-through7/README.md)
contains every winning child at every step from 1 to 7. Lists below follow
increasing rooted canonical keys within the child size.

| Step | Shortest distances to the previous winning set |
|---|---|
| 1 to 2 | 1 |
| 2 to 3 | 2, 2 |
| 3 to 4 | 2 |
| 4 to 5 | 3, 3, 3, 2, 2 |
| 5 to 6 | 1, 2 |
| 6 to 7 | 3, 3, 3, 1, 3, 3, 3, 3 |

These are exact distances under the stated edit costs. The computation
enumerates complete unit neighborhoods of all source winners and each target
winner. A direct edge proves distance one. If no direct edge exists, a common
neighbor proves distance two. Disjoint source radius-one and target unit
neighborhoods exclude all paths of length at most two; saved three-edit paths
then establish distance three. Finding those paths needs only part of the
next layer and makes no exhaustive radius-two enumeration claim.

Every path in `paths.jsonl` includes full ordered transition tables, primitive
edits, and explicit root-preserving isomorphisms with port swaps. All steps
are rebuilt and checked. No Family 1 score is recomputed by this distance
program: endpoint scores and complete winner collections come from the
certified search outputs, pinned by SHA-256 in the report.

## The six-state to seven-state example

The winning six-state table

```json
[[1,2],[0,3],[4,5],[2,3],[0,1],[4,5]]
```

has `H=23`. Insert vertex 6 into the edge occurrences `0 -> 1` and `1 -> 0`,
giving vertex 6 outgoing targets `[0,1]`. This gives

```json
[[6,2],[6,3],[4,5],[2,3],[0,1],[4,5],[0,1]]
```

whose rooted canonical key is `0102000304050106000304050206` and whose certified
score is `H=34`. Its edit distance to `W_6` is one, while its score gain is 11.
These are different quantities; the metric does not assert any bound on the
change of `H`.

Only this one of the eight rooted seven-state winners has distance one from
`W_6`. All other seven-state winners have distance three. Independently, the
one-insertion ancestry audit lists every permitted smoothing operation: the
best predecessor scores are `21,22,21,23,22,22,22,22`. A predecessor's lower
score does not prevent its child from being globally optimal.

For this particular step, the exclusion of distance two also has a simple
structural proof. Both endpoint collections are balanced. Two edits with net
size change plus one would consist of one routing insertion and one
retargeting. Routing preserves indegree deficits; a nontrivial retargeting
creates two nonzero deficits. It cannot leave a balanced endpoint. This
argument is not applied to steps with unbalanced winning endpoints.

The [ancestry report through seven states](../results/family1-ancestry-through7/README.md)
addresses the more restrictive one-insertion relationship at every previous
step, including 5 to 6. The distance report allows rewiring and intermediate
growth or smoothing, and answers a broader question.

## Reproduce

```powershell
uv run --no-project python scripts/family1_edit_distance.py
uv run --no-project python tests/family1_edit_distance_test.py
```

All files are kept in `AutomataAnalysis`; dissertation sources are untouched.
