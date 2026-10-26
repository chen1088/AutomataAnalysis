# Complete Family 1 results through six reachable states

Native MSVC/vcpkg Release run completed on 2026-10-25, starting from repository
base `3dfe58a3863dfec00da4caa9745f8443a4daef84` with the accompanying search
implementation. Each graph was scored separately over all static masks.

| Exactly reachable states | Rooted classes evaluated | Maximum H | All maximizing classes |
|---|---:|---:|---:|
| 1 | 1 | 1 | 1 |
| 2 | 6 | 3 | 1 |
| 3 | 57 | 6 | 2 |
| 4 | 678 | 10 | 1 |
| 5 | 10,398 | 15 | 5 |
| 6 | 192,181 | 23 | 2 |

All 203,321 results are exact, with no depth-capped or incomplete scores.
The cumulative budget of one through six has maximum 23, attained by both
six-vertex classes. This cumulative maximum is taken over independent seed
scores; it is not the score of a product across different graphs.

- [maximizers.jsonl](maximizers.jsonl): all 12 per-size maximizing classes,
  canonical tables and witness pairs.
- [summary.json](summary.json): exact-size and cumulative coverage and maxima.
- [score-distributions.json](score-distributions.json): every score frequency.
- [cumulative_maximizers.jsonl](cumulative_maximizers.jsonl): both global ties.
- [dot/](dot/): all 12 maximizing graphs, including loops and both port edges.
- [validation.json](validation.json): compiler, commands, evidence, hashes,
  passed checks, and remaining verification limits.

The complete evaluated-graph export is `out/family1-m1-m6/graphs.jsonl` (48 MB);
`checkpoint.jsonl` beside it records every evaluation and supports resume. These
generated files are local and ignored by Git. Their SHA-256 hashes are retained
in `validation.json`. The files in this directory preserve the small result
collection with the source.

The two six-vertex canonical tables are:

```text
[[0,1],[2,3],[3,4],[2,5],[0,1],[4,5]]
[[1,2],[0,3],[4,5],[2,3],[0,1],[4,5]]
```

Every saved witness pair was independently verified by direct simulation over
every static mask. Independent complete class enumeration was checked through
four vertices; independent shortest-length scoring was checked through three.
For larger sizes, exactness comes from the C++ fresh-layer search. See the
[search documentation](../../docs/family1-search.md) for build, search, resume,
export, verification commands, and the unreachable-vertex reduction.
