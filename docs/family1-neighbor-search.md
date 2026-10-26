# Root-aware searches near earlier leaders

`scripts/family1_neighbor_search.py` runs a bounded, resumable candidate search
at every exact reachable size from 8 through 20. It imports the complete certified
maximizing collections through seven states. Optional seed files can add exact
near-top graphs or unresolved challengers; the original seed records and their
proof metadata remain attached to the observations. An upper bound near the
maximum does **not** establish that the graph's actual score is near the maximum.

The global graph model still allows arbitrary indegrees, loops, coincident ports,
and graphs which are not strongly connected. Every seed is scored separately.

## Candidate generation

The unit edits are those in [the graph-edit definition](family1-graph-edits.md):
retarget one outgoing port, insert or smooth a routing vertex in two distinct
edge occurrences, and subdivide or smooth one edge with a loop at the inserted
vertex. Independent port swaps and root-preserving vertex relabelings are free.

Radius two requests the operator patterns `G`, `GR`, and `RG`, where `G` is
growth and `R` is retargeting. Radius three additionally requests `GRR`, `RGR`,
`RRG`, `GGS`, `GSG`, and `SGG`, where `S` is smoothing. These are all possible
size-change patterns of at most three unit edits ending one state larger.
The generator rotates patterns across parent graphs to offer both orders of
growth and retargeting early. A budget may interrupt any pattern; the saved paths
show exactly which ones were visited.

`--candidate-shapes` bounds the number of generated ordinary shapes, and
`--path-budget` bounds primitive edges examined in these paths. Stopping at either
budget explicitly marks generation incomplete. All generated paths and shapes
remain saved, including those not selected for scoring. A saved edit-path length
is an **upper bound from the specified parent root before changing the root**;
it is not an exact distance and does not include a later change of starting state.

The parent order uses the largest certified lower bound first. Its secondary
rank counts vertex roots whose certified lower bound is at least the preceding
size's incumbent lower bound minus two. Both vertex-root count and distinct
rooted-class count are reported. Unknown scores and large upper bounds do not
count as lower-bound evidence. Indegree-profile diversity helps select edited
shapes. These choices prioritize limited work; they are not mathematical
exclusions of other graphs.

## Starting vertices and constructive bounds

`--shapes-per-size` selects that many edited ordinary shapes. A constructive
baseline shape is additional. The selection unit is a whole ordinary shape:
**every accessible starting vertex is accounted for**, and every distinct rooted
class arising from those vertices is queued. Vertex roots yielding the same
rooted class share one query, with their multiplicity recorded. A vertex which
cannot reach the whole graph is listed with its smaller reachable-state count;
it is not mislabeled as an exact-size seed.

Repeatable `--shape-seeds FILE` additionally queues every explicitly supplied
same-size ordinary shape, regardless of the edited-shape breadth. It imports
only the supplied certified score interval; a conjectured asymptotic formula
never supplies a numerical bound. For example, the user's circulant family
`tau0(i)=i+1 mod m`, `tau1(i)=i+floor(m/3) mod m` can be queued at every size.
Translations make its vertex roots equivalent, so one native query covers all
of them and the root profile records the full vertex multiplicity.

The baseline comes from `results/family1-atlas-current/champions.jsonl`. Its table,
projection, port adjustments, and bound must match the checked `extension(m)`
construction, with lower bound exactly 34 and no asserted upper bound. The
construction projects onto a certified seven-state graph of score 34. For every
new root mapping to the base root, the same static-mask lift proves `H >= 34`.
This gives 104 distinct certified rooted baseline examples across sizes 8–20.
Other roots receive no automatic score of 34.

## Native threshold queries and proof records

The alternative `--query-method metric` uses native `Family1Sample` in guided
mode. Its `--threshold` is a length cap; a verified pair may be shorter. Search
uses `--samples` prefix seeds, `--beam-width`, and `--lookahead` to increase the
number of mask coordinates with equal endpoints along a common suffix. Neutral
moves are retained to cross plateaus. `--full-agreement` records exact all-mask
agreement along the best trace. Every reported collision is separately replayed
on every static mask. Agreement counts and sampling misses never supply lower
bounds. Actual witness length supplies only an upper bound.

Use `--full-guidance` to evaluate the beam objective over all `2^m` masks, while
sampling only word pairs. The packed pair state needs roughly 5 MiB at m=20,
and updates skip blocks whose coordinates have all merged. This avoids mistaking perfect
agreement on a small mask subset for agreement across the complete Family 1.

An all-size metric pilot can be reproduced in a fresh directory:

```powershell
uv run --no-project python scripts/family1_neighbor_search.py `
  --out out/family1-neighbor-metric-new --query-method metric `
  --seeds results/family1-neighbor-seeds/near-top.jsonl `
  --shape-seeds results/family1-circulant-family/champions.jsonl `
  --shapes-per-size 1 --candidate-shapes 16 --path-budget 512 `
  --radius 2 --jobs 4 --threshold 96 --samples 8 `
  --beam-width 4 --lookahead 1 --projection-masks 64 --full-guidance
```

The reusable window/beam/exact-tail finder is also available. It uses every
static mask for its metric, constructs permutation-compatible prefix pairs,
and rejects proven unmergeable branches. Its exact tail is shortest only from
the recorded intermediate pair. This command queues all accessible roots of
one edited shape, the projection baseline, and the literal circulant at every
size 8 through 20:

```powershell
uv run --no-project python scripts/family1_neighbor_search.py `
  --out out/family1-neighbor-finder-new --query-method finder `
  --seeds results/family1-neighbor-seeds/near-top.jsonl `
  --shape-seeds results/family1-circulant-family/champions.jsonl `
  --shapes-per-size 1 --candidate-shapes 16 --path-budget 512 `
  --radius 2 --jobs 4 --threshold 96 --samples 8 `
  --beam-width 4 --window-k 2 --tail-threshold 4 --tail-max-states 100000
```

Here `--threshold` is the maximum whole-word length and `--samples` is the
number of outer prefix attempts. Prefix profile construction has its own
additional native budget. See [the generic finder](hard-pair-finder.md) for
distribution diagnostics, individual-pair obstructions, and benchmarks.

For comparison, the threshold backend asks an exhaustive logical question at
one length, subject to a solver budget:

`Family1Threshold` asks whether a collision exists at one specified length `L`:

| Native result | Certified information |
|---|---|
| `no_collision` | `H >= L+1` |
| `collision` | `H <= L`, with two distinct equal-length words replayed over all masks |
| `unknown` | No additional score bound |

A collision at an earlier length extends to the same length `L` by appending
the same suffix to both words. Thus a certified absence at `L` excludes all
earlier collisions. The threshold result is combined only with observations
having the same complete canonical table. Contradictory intervals stop the run.
An unknown result preserves every inherited bound. A graph can be excluded from
beating the incumbent only when a certified upper bound is smaller than the
incumbent's lower bound. Pending and unresolved graphs remain exported.

Resume pins input files, the native executable, and the Python implementation
and dependencies. It checks hashes of cached plans, generated paths and candidate
files. Each journal observation is reconstructed from the hashed native JSON;
changed journal keys, bounds or witnesses are rejected. Changing proof budgets
or executable versions requires a new output directory. A partial final journal
line can be recovered without losing completed observations.

`--limit-graphs` bounds new native queries in one invocation. If it stops within
a selected shape, every remaining root stays queued and the summary explicitly
reports incomplete root coverage. `--generate-only` freezes the planned pools
without querying them; resume honors those pools rather than silently regenerating
them from different bounds. New discoveries can guide a separate broader run.

## Reproduce

The small all-size pilot selects one edited shape plus the baseline at each size:

```powershell
uv run --no-project python scripts/family1_neighbor_search.py `
  --out out/family1-neighbor-threshold-new `
  --seeds results/family1-neighbor-seeds/near-top.jsonl `
  --shape-seeds results/family1-circulant-family/champions.jsonl `
  --shapes-per-size 1 --candidate-shapes 16 --path-budget 512 `
  --radius 2 --jobs 8 --threshold 34 `
  --timeout-ms 500 --solve-timeout-ms 250 --projection-masks 8
```

Append `--resume` to continue it with exactly the same settings and source
versions. Earlier pilots are preserved at `out/family1-neighbor-pilot-8-20` and
`out/family1-neighbor-pilot-8-20-v2`, including the exact Python files used. They
are separate runs and are not silently replaced.

For a larger run, choose a fresh output directory and increase shape breadth,
path budget, and SAT time. Optional `--seeds` can be repeated. All eight certified
seven-state maximizers are included independently of optional seeds.

```powershell
uv run --no-project python scripts/family1_neighbor_search.py `
  --out out/family1-neighbor-broader-8-20 `
  --seeds results/family1-neighbor-seeds/near-top.jsonl `
  --shapes-per-size 4 --candidate-shapes 128 --path-budget 8192 `
  --radius 3 --jobs 4 --threshold 34 `
  --timeout-ms 10000 --solve-timeout-ms 2000 --projection-masks 16

uv run --no-project python tests/family1_neighbor_search_test.py
```

Main outputs are `summary.json`, all merged `records.jsonl`, every incumbent tie
in `incumbents.jsonl`, every still-competitive observed graph in
`potential-competitive.jsonl`, and the complete selected `root-profiles.jsonl`.
Per-size `plans/` retain parent rankings, all generated candidates and paths,
including unselected shapes. `queries/` retains native evidence and
`query-results.jsonl` is the resumable observation journal.

The inherited global maximum proofs through seven states are explicitly
separated from this run's nonexhaustive local records. No result of this bounded
search certifies a global maximum or the complete maximizing collection at
sizes 8–20.

## Completed bounded pilots

The [full-metric guided pilot](../results/family1-neighbor-full-metric-8-20/README.md)
and [window/exact-tail finder pilot](../results/family1-neighbor-finder-8-20/README.md)
each queried 377 rooted classes across 39 selected ordinary shapes, three at
every size 8 through 20. All accessible roots of those selected shapes were
covered. Both used an eight-attempt outer prefix budget and length cap 96.
The former found 61 all-mask verified upper witnesses; the latter found 27.
The newer pilot has 350 unresolved queries, including every selected query at
sizes 16 through 20. Neither pilot increased the certified lower bound of 34
at any larger size.

These are limited engineering pilots, not a controlled head-to-head quality
test: only 203 queried rooted classes are shared. On that shared set, the
guided pilot found 18 witnesses and the finder found 12. The fixed 24-case,
128-attempt benchmark in the [finder documentation](hard-pair-finder.md) is a
separate experiment. Prefix matching and safe pruning do not guarantee better
finite-budget witness quality for every family.

Both publications preserve every observed graph, inherited lower-bound tie,
upper witness and potential challenger, plus a checked archive of the entire
raw run. Their audits validate graph/query coverage, artifact hashes, native
JSON and scalar-verification counts; they do not repeat all scalar endpoint
computations. A no-op resume of the completed finder pilot also passed.
Earlier results remain available and should be supplied as additional seed
observations when starting a broader run; a new heuristic miss does not erase
a previously certified upper bound.
