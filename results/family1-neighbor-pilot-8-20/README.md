# Root-aware edit-neighborhood pilot, sizes 8 through 20

The completed v3 pilot evaluated all 377 selected rooted classes across 39
ordinary shapes, covering 546 vertex choices of root. At each size it selected
one edited shape, the projection baseline, and the user's literal circulant
shape. Each whole-graph-accessible root was included, modulo exact rooted
isomorphism; none was dropped to meet the shape budget.

All 377 native length-34 queries returned UNKNOWN at the small 500 ms budget.
No improved lower bound or global upper bound is claimed. Existing exact scores
and structural lower certificates remain intact: there are 104 rooted lift
examples with H>=34 across exact sizes 8 through 20, and the literal circulant
at size eight retains its independently exact score 18.

`summary.json` has an explicit entry for every size 1 through 20. The complete
small-case optimum proofs through seven are inherited, rather than recomputed
by this local search. All larger graph-class coverage remains nonexhaustive.

- `records.jsonl` retains all imported and generated graph classes, tables,
  intervals, provenance and observations, including unselected and unresolved
  classes.
- `incumbents.jsonl` retains every largest-certified-lower-bound tie. It is not
  a complete global maximizing collection above seven states.
- `potential-competitive.jsonl` retains every observed graph whose upper bound
  does not exclude a tie or improvement. UNKNOWN never excludes a graph.
- `root-profiles.jsonl` reports every selected starting vertex and root orbit.
- `audit.json` records all native replay, plan-integrity and root-coverage checks.
- `complete-pilot-evidence.zip` contains the full original run, including all
  377 native results and mask traces, generation paths, candidate shapes, pinned
  implementation, and resumable journals. `artifact-manifest.json` pins exports.

The source run is preserved at `out/family1-neighbor-pilot-8-20-v3/`. Its no-op
resume passed. Two earlier pilot versions remain preserved separately.

Reproduce in a fresh directory from the repository root:

```powershell
uv run --no-project python scripts/family1_neighbor_search.py `
  --out out/family1-neighbor-pilot-new `
  --seeds results/family1-neighbor-seeds/near-top.jsonl `
  --shape-seeds results/family1-circulant-family/champions.jsonl `
  --shapes-per-size 1 --candidate-shapes 16 --path-budget 512 `
  --radius 2 --jobs 8 --threshold 34 `
  --timeout-ms 500 --solve-timeout-ms 250 --projection-masks 8
```

Append `--resume` with the same settings. Changing proof budgets, seed inputs,
or program versions requires a fresh directory. Details and larger-search
commands are in [the search documentation](../../docs/family1-neighbor-search.md).
