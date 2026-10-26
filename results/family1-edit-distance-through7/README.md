# Rooted edit distances between consecutive maximizers

Each distance is to the complete set of rooted maximizers at the previous exact size. Root-preserving relabeling and independent port swaps are free. Unit moves are one-port retargeting, two-edge routing-vertex insertion/smoothing, and one-edge subdivision with a loop at the new vertex (or its inverse). Every intermediate graph remains root-accessible.

The distance is a structural quantity. The change in Family 1 merge length is recorded separately and is not a graph-edit cost.

| Previous size | Child size | Child ordinal | Shortest edit distance | Previous maximum H | Child H |
|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 1 | 1 | 1 | 3 |
| 2 | 3 | 7 | 2 | 3 | 6 |
| 2 | 3 | 45 | 2 | 3 | 6 |
| 3 | 4 | 443 | 2 | 6 | 10 |
| 4 | 5 | 1391 | 3 | 10 | 15 |
| 4 | 5 | 1511 | 3 | 10 | 15 |
| 4 | 5 | 5982 | 3 | 10 | 15 |
| 4 | 5 | 6241 | 2 | 10 | 15 |
| 4 | 5 | 6811 | 2 | 10 | 15 |
| 5 | 6 | 33343 | 1 | 15 | 23 |
| 5 | 6 | 117031 | 2 | 15 | 23 |
| 6 | 7 | 539749 | 3 | 23 | 34 |
| 6 | 7 | 679758 | 3 | 23 | 34 |
| 6 | 7 | 1783759 | 3 | 23 | 34 |
| 6 | 7 | 2221624 | 1 | 23 | 34 |
| 6 | 7 | 2470130 | 3 | 23 | 34 |
| 6 | 7 | 2471796 | 3 | 23 | 34 |
| 6 | 7 | 3411148 | 3 | 23 | 34 |
| 6 | 7 | 4099217 | 3 | 23 | 34 |

`paths.jsonl` stores every complete ordered transition table along a shortest path, every primitive edit, and the free rooted isomorphism after that edit. Lower bounds use complete bidirectional unit neighborhoods; an exhaustive radius-two search is not claimed or needed.

```powershell
uv run --no-project python scripts/family1_edit_distance.py
uv run --no-project python tests/family1_edit_distance_test.py
```

See [the mathematical definition and metric proof](../../docs/family1-graph-edits.md) and [the one-insertion ancestry audit](../family1-ancestry-through7/README.md).
