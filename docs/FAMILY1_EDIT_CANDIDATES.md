# Edit-based graph candidates

`Family1Edit.exe` generates graph candidates in native C++. The separate
ranker orders a frozen pool, and the general hard-pair module screens its
graphs. Graph generation does not inspect current-size scores or saved word
pairs. Every graph class, root, edit path, tie and unresolved observation is
retained in the corresponding exports.

## Graph space and edits

The graph has exactly two outgoing ports at each vertex. Indegrees are
unrestricted; loops, coincident ports and accessible graphs that are not
strongly connected remain allowed. Root-preserving relabelings and independent
port swaps identify the same rooted class. The five primitive operations are
retargeting, two-edge routing insertion, loop routing insertion, and the two
inverse smoothings. See the [edit metric](family1-graph-edits.md).

The native search shares work across parents, edit kinds, frontier vertices
and depth layers. Radius is limited to three, with explicit path and candidate
budgets. `--max-paths` counts accepted nonempty primitive paths;
`--max-candidates` counts distinct target endpoints before root closure. A cap
limits the search and never proves that an unvisited graph is irrelevant.
The implementation supports intermediate sizes through20. A path that could
leave this representation is explicitly marked by `representation_capped`.

`--root-closure` additionally records every accessible root of each observed
ordinary shape. This may emit more rows than the endpoint budget. Rerooting is
not a free edit: a candidate receives a rooted-distance upper bound only when
an actual root-fixed path reaches its canonical rooted class. Other root rows
have a null bound and retain their separate origin metadata. Vertices that
cannot reach the whole graph do not become exact-size roots.

The native CLI writes canonical tables, `paths.jsonl`, `candidates.jsonl`,
`run.json`, `summary.json` and checksum sidecars. A completed bounded plan can
be reused with identical arguments plus `--resume`. An interrupted generation
is preserved; it does not pretend to serialize the entire live frontier.
The scoring pipeline has independent per-attempt resume and integrity checks.

## Generation, priority and scoring

Previous-size winners alone are an insufficient source pool. The implemented
near-top policy uses all previous-size classes with a sufficiently high
certified score, rather than choosing one representative. Where an interval
is unresolved, it is explicitly a possible near-top parent, not a certified
one. This priority has no claimed coverage theorem for future sizes.

`scripts/family1_rank_edit_candidates.py` supports:

- `discovery`: keep the original whole-shape appearance order.
- `structural`: prefer more accessible roots with distinct ports, then more
  accessible roots and indegrees nearer two, with seeded ties.
- `parent-strata`: round-robin across certified previous-parent score levels,
  using structural priority within levels.

These rules reorder all rows without filtering any graph. They do not read
candidate scores, upper bounds, or witnesses. Unbalanced and nonstrongly
connected graphs remain in the pool. Each ordinary shape's observed roots
stay together, so a nominal budget can overshoot by a few rows. See the
[ranking module](FAMILY1_CANDIDATE_RANKING.md).

For a maximization search with an incumbent lower bound L, the scorer searches
for a collision of length at most L-1. A verified witness proves H(G)<L and
excludes that graph. A miss or timeout supplies no lower bound. Surviving
graphs remain unresolved; a long heuristic pair is not evidence of a large H.
All accepted pairs receive independent replay over every static mask. See
[general scoring and resume](FAMILY1_GRAPH_CANDIDATE_SEARCH.md).

## Benchmark

The generation benchmark covers exact sizes 1 through 7, all previous winners
and previous parents within two of their maximum, radii 1/2/3, three fixed
seeds and budgets 32/128/512/2048. It includes 222 native generation runs,
895 raw-order measurements, and 666 same-pool ranking comparisons. All pools
and rankings are sealed before their child-size truth is used for evaluation.
This is retrospective calibration on known small cases, not a held-out
generalization claim. Random accessible graph baselines use matched accepted
candidate counts, with their draw counts and whole-shape overshoots reported;
they are not claimed uniform over isomorphism classes.

Complete one-insertion pools from near-top parents contain every known
maximizing rooted class through seven states. At seven states, all 69 parents
have exact scores 21 through 23. They generate 3,581 direct rooted endpoints;
all accessible roots expand this to 13,329 classes across 1,926 shapes. Both
sets contain all eight maximizers. Full seven-state enumeration contains
4,166,855 classes. Winner-only one-insertion generation contains just one
maximizing rooted class, or three after considering all roots.

The recommended measured configuration is the **budgeted** near-top,
radius-one, all-roots pool with parent-strata priority:

| Seed | Actual candidate roots at nominal 2048 | Known winners retained | Certified weaker at cap 33 | Unresolved |
|---:|---:|---:|---:|---:|
| 1088 | 2051 | 8/8 | 1890 | 161 |
| 2027 | 2050 | 8/8 | 1887 | 163 |
| 65537 | 2048 | 8/8 | 1886 | 162 |

The unresolved sets include 153 through 155 nonwinners. They are candidate
shortlists, not certified maximizing collections. Raw canonical ordering
found none of the winners in those prefixes. Conversely, ranking the larger
complete 13,329-class pool puts only three winners in its first 2048 rows.
Increasing radius or pool size under a fixed budget can reduce recall. Every
negative outcome remains in the reports.

Screening the entire 13,329-class pool with the same cheap query certifies
12,691 weaker graphs and retains 638 unresolved: all eight winners and 630
nonwinners. All 13,329 native invocations completed, with zero false exclusions.
The query cutoff 33 is a shared retrospective operating point using the
already-certified seven-state incumbent, not a graph-specific score hint.

- [Generation, random baselines and independent audits](../results/family1-edit-candidate-benchmark/README.md)
- [All same-pool ranking measurements](../results/family1-edit-ranked-candidate-benchmark/README.md)
- [Full seven-state screening and every survivor](../results/family1-edit-elimination-complete-m7/README.md)
- [Native Windows build/test pins](../results/family1-edit-candidate-validation/README.md)
- [Benchmark plots and editable SVGs](../output/figures/family1-edit-candidates/README.md)

## Reproduction

Build both native configurations with the existing MSVC/vcpkg setup:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-windows-vcpkg.ps1 -Configuration Release
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-windows-vcpkg.ps1 -Configuration Debug
```

Generate and benchmark the small cases, then rank and screen the sealed pools:

```powershell
uv run --no-project python tests/family1_edit_candidate_benchmark.py
uv run --no-project python tests/family1_edit_ranked_candidate_benchmark.py
uv run --no-project python tests/family1_edit_elimination_benchmark.py
```

The bounded 8-through-20 pilot integrates native edits, parent-strata ranking
and all-root screening at each size:

```powershell
uv run --no-project python scripts/family1_edit_candidate_pilot.py `
  --out out/edit-candidate-pilot-new --min-m 8 --max-m 20 `
  --radius 3 --max-paths 4096 --max-candidates 256 `
  --score-shapes 2 --samples 128 --native-timeout 2 --jobs 4
```

Append `--resume` with identical inputs, sources, executable and settings to
reuse a completed run. Change budgets in a fresh directory. The recorded pilot
generated 43,888 classes, processed 364 selected roots, and retained all unselected
graphs and 104 imported construction lower bounds. Its 122 completed misses
and 242 timeouts exclude no selected graph. No larger maximum or stronger
lower bound was proved. Its small frontier and two-second budgets are explicit;
it does not claim exhaustive candidate or score coverage.

The [complete pilot export and audited evidence](../results/family1-edit-candidate-pilot-8-20/README.md)
retain every canonical table, edit path, ranking and query outcome.

Use radius 1 and broader candidate budgets for the measured small-edit
strategy, or radius 2/3 for additional exploration. For heavier screening use
the general module's `--enable-stage2` and explicit memory/time settings.
Unselected, timed-out and unresolved graphs must remain available for later
refinement.
