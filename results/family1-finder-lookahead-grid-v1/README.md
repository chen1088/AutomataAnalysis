# Controlled lookahead sweep: all eight m=7 maximizers

All144 predeclared runs completed: k=1,...,6, beam4, tail thresholds0/2/8,128 automatic seeds, fixed total pair-length cap76, the same prefix preprocessing and viability settings, and no saved witness or witness-derived prefix hints. The native executable and DLLs were snapshotted before the sweep. Every returned pair was independently replayed on all128 static masks.

**Length34 was recovered for ordinal2470130:** k4/T8, and every tested tail threshold at k5 and k6. These seven successful settings concern one rooted graph class. None of the other seven classes reached34 in this grid.

All entries below are found total pair lengths; the independently certified minimum is34 in every row. Increasing k is not monotone for this bounded heuristic.

## Tail threshold 0

| Rooted class ordinal | k1 | k2 | k3 | k4 | k5 | k6 |
|---:|---:|---:|---:|---:|---:|---:|
| 539749 | 39 | 36 | 41 | 40 | 36 | 35 |
| 679758 | 36 | 38 | 38 | 37 | 37 | 37 |
| 1783759 | 40 | 38 | 36 | 38 | 36 | 38 |
| 2221624 | 45 | 41 | 44 | 39 | 39 | 41 |
| 2470130 | 38 | 37 | 37 | 37 | 34 | 34 |
| 2471796 | 38 | 38 | 36 | 36 | 36 | 37 |
| 3411148 | 42 | 38 | 39 | 40 | 39 | 40 |
| 4099217 | 41 | 41 | 41 | 40 | 39 | 39 |

## Tail threshold 2

| Rooted class ordinal | k1 | k2 | k3 | k4 | k5 | k6 |
|---:|---:|---:|---:|---:|---:|---:|
| 539749 | 36 | 37 | 41 | 40 | 36 | 35 |
| 679758 | 36 | 38 | 38 | 37 | 37 | 37 |
| 1783759 | 40 | 38 | 36 | 38 | 36 | 38 |
| 2221624 | 45 | 41 | 42 | 39 | 39 | 40 |
| 2470130 | 38 | 37 | 37 | 37 | 34 | 34 |
| 2471796 | 38 | 39 | 36 | 36 | 36 | 37 |
| 3411148 | 41 | 38 | 39 | 39 | 39 | 39 |
| 4099217 | 40 | 40 | 41 | 40 | 39 | 39 |

## Tail threshold 8

| Rooted class ordinal | k1 | k2 | k3 | k4 | k5 | k6 |
|---:|---:|---:|---:|---:|---:|---:|
| 539749 | 36 | 38 | 40 | 37 | 36 | 35 |
| 679758 | 38 | 38 | 38 | 37 | 37 | 37 |
| 1783759 | 35 | 37 | 36 | 37 | 36 | 38 |
| 2221624 | 42 | 41 | 42 | 39 | 39 | 39 |
| 2470130 | 36 | 36 | 37 | 34 | 34 | 34 |
| 2471796 | 38 | 36 | 36 | 36 | 36 | 37 |
| 3411148 | 38 | 38 | 38 | 39 | 39 | 39 |
| 4099217 | 40 | 39 | 40 | 40 | 39 | 39 |

Across the full tested grid, best lengths in ordinal order are35,36,35,39,34,36,38,39. This minimum-over-settings summary does not hide the individual outcomes above.

The default10,000-node expansion budget produced 0 recorded expansion-limit events. Full module/tail/prefix statistics, runtime and actual witnesses remain in runs.jsonl and runs.csv; complete native results are referenced by SHA-256. A conditional BFS flag alone does not prove global shortestness. A found34 pair matches the independently certified H for its graph.

The driver supports further grids and an explicit length cap without injecting witness hints:

```powershell
uv run --no-project python tests/family1_finder_lookahead_benchmark.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe --window-grid 1 2 3 4 5 6 --beam-grid 4 --tail-grid 0 2 8 --samples 128 --length-cap 76 --jobs 4
```

Appending k/beam/random-seed values is allowed with unchanged fixed settings. A different executable, length cap, seed budget or preprocessing budget requires a new output/work directory. Snapshotted binaries allow old runs to be resumed after a newer project build.
