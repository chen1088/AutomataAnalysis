# Global certificates and the study from one to twenty states

The completion criterion is a global upper bound matching an attained score,
followed by a complete collection of maximizing rooted classes. Finding a few
rare candidates does not exclude an even rarer stronger graph.

## Scope of the graph formula

`Family1GlobalCheck` introduces variables for both outgoing targets at every
vertex. Targets range over `0,...,m-1`; ports in each row are sorted. Loops and
coincident targets remain permitted, and no indegree or strong-connectivity
condition is imposed.

Every nonroot vertex must have an incoming edge from an earlier vertex.
This implies accessibility by induction. Conversely, every rooted accessible
graph admits such a labeling by a rooted spanning tree or breadth-first
discovery. Therefore the formula covers every required rooted graph class,
although it may encode a class more than once.

The optional `--discovery-labels` mode uses encoder v2 and additionally orders
first occurrences in the flattened sorted transition table. A target `q>=2`
must have an earlier occurrence of `q-1`. Every accessible rooted graph admits
these labels by breadth-first discovery: already discovered targets have
smaller labels than newly discovered targets, and two new successors in one
row can be assigned their two next labels in either order. Thus sorting rows
does not remove any class. The only ambiguity is which of two new successors
gets the next label, giving at most `2^floor((m-1)/2)` admitted tables per class.
An independent test checks this coverage on all ordered accessible tables
through four states. Default encoder v1 remains unchanged.

## Excluding all stronger graphs

Fix a threshold `L`. If `H(G)>L`, every two distinct equal-length words of length
at most `L` must be separated by some static mask. For each learned word pair,
the graph formula requires one such separating mask. A mask is shared across
both word trajectories and all revisits to a vertex; different word pairs may
use different masks.

A candidate graph is scored. A certified lower bound above `L` establishes a
stronger graph. A universally colliding pair of length at most `L` becomes a
new necessary separation constraint. An unresolved candidate may be postponed
by a guarded clause activated only through a SAT assumption, allowing the
learner to inspect other graphs. Such a block is a scheduling device and is
not a mathematical rejection. If the temporarily restricted space becomes
UNSAT, the solver removes **all** postponement assumptions and checks the
whole graph formula again. Only UNSAT on that bare formula proves a global
bound; SAT or UNKNOWN leaves the result `unknown`. Canonical postponed graph
tables, their certified bounds, and reasons remain in the run record.

If the graph formula becomes **UNSAT**, no rooted accessible graph has `H>L`.
This proves the global bound `H<=L` without enumerating all graph classes.
The argument does not depend on which pairs were learned: every valid pair
of the stated lengths supplies a necessary condition on a stronger graph.

## Reproducible artifacts

Each run writes `result.json`, including the encoder version and learned word
pairs. A certified UNSAT run also writes the complete `graph-space.cnf` in
standard DIMACS format. Replaying reconstructs and solves the graph formula,
and requires its CNF to agree byte for byte with the saved artifact.
Certificate export reconstructs the base graph and learned-pair formula from
scratch whenever scheduling guards were used, so no temporary block or
selector variable enters the portable artifact. `sat_variables` and
`sat_clauses` describe that artifact on a certified run; the separate
`search_sat_variables` and `search_sat_clauses` retain search statistics.

```powershell
.\out\build\msvc-vcpkg\Release\Family1GlobalCheck.exe --states 4 --threshold 10 --out out\global-four --timeout-ms 60000 --solve-timeout-ms 60000
.\out\build\msvc-vcpkg\Release\Family1GlobalCheck.exe --replay out\global-four --out out\global-four-replay --timeout-ms 60000 --solve-timeout-ms 60000
```

To continue a partial search with saved separation constraints, use `--resume`
and a new output directory. Raising a timeout is not evidence of completion;
only the reported SAT/UNSAT outcome establishes the corresponding conclusion.
Use repeatable `--seed-pairs RUNDIR` options to import necessary separation
conditions from other sizes. Such pairs are still necessary for every graph
with `H>L`, independently of the size that produced them. Pairs longer than
the new threshold are skipped; import, duplicate, and skipped counts are
saved in `seed_pair_sources`. Seeds cannot modify a certificate replay.
`--max-postponed-models` limits temporary exclusions. Candidate full-product
scoring can be bounded by `--candidate-max-layer-states` and
`--candidate-max-working-mib`; reaching either cap never supplies an exact
score. The full-mask packed backend scores seven/eight-state candidates and
larger graphs with at most eight noncoincident rows. Other candidates use the
static-mask symbolic verifier.

The CNF can also be checked by an independent SAT solver. The small certificates
through three states were checked using both Z3 and PicoSAT, together with
direct simulation over every ordered labeled accessible graph. These are
finite computational UNSAT certificates, not externally checked DRAT/LRAT
traces. The encoder's completeness and implication are established above and
covered by independent small-case tests.

## Maximum value versus every maximizing class

A global upper bound `L` and an individual certified lower bound `L` establish
the optimum value. They do not enumerate every class attaining it. The unified
study keeps `maximum_value_certified` separate from
`maximizing_collection_complete`; the latter requires complete class coverage.
All unresolved challengers remain recorded rather than silently discarded.

## Current status

The original exhaustive runs certify both optimum values and all maximizing
classes for `m=1,...,6`. The symbolic whole-graph method independently proved
upper bounds for `m=1,2,3,4`, using 1, 3, 17, and 95 rejected candidates.

A formal attempt was recorded at every size from 1 through 20. The newer solver
attempts for sizes 5 through 20 returned `unknown` under their budgets. For 5
and 6 the previous exhaustive proofs remain valid. A subsequent independent
[exhaustive seven-state certificate](family1-seven-state-search.md) establishes
the absolute maximum 34 and all eight rooted maximizers. Sizes 8 through 20
remain **unresolved**. The current atlas includes constructive `H>=34`
examples at each of these exact sizes, with no global upper bound or claimed
complete winner collection. The earlier twenty-state `H>=27` observation
remains in the historical study; its smaller lower bound does not exclude it.

`scripts/family1_study.py` aggregates all twenty sizes, retains all tied
observations, and replays imported global upper-bound certificates before
using them. `study.csv` and `summary.json` expose the per-size proof status,
unresolved challenger counts, exact observations, and certified bounds.

Resume and replay derive the discovery mode from the saved encoder version.
To move necessary pair constraints between versions, import them as seeds
into a fresh run instead of changing an existing certificate's formula:

```powershell
.\out\build\msvc-vcpkg\Release\Family1GlobalCheck.exe --states 7 --threshold 29 --discovery-labels --seed-pairs out\global-resume-audit\v2-m7-28 --out out\global-seven-discovery --timeout-ms 120000 --solve-timeout-ms 30000 --candidate-timeout-ms 30000 --candidate-max-working-mib 16384 --candidate-max-layer-states 536870912 --max-candidates 10000
```
