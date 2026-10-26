# Incumbent-cutoff elimination benchmark

On 5,992 unique graphs selected from sealed edit and random prefixes, 5,905 were independently certified weaker than the same-size incumbent; 87 remain unresolved. No maximizing graph was eliminated. All native invocations completed; no timeout/error is hidden.

This is a retrospective operating-point test: every m-state graph is queried at the common capF_m−1, where F_m is the previously certified global maximum for that size. Per-graph H, truth labels and saved words never enter the native scorer. Stage1 is fixed at k6, beam4,128 outer samples/prefix pairs, prefix depth16/65536 words,10000 expansions and tail threshold8. All hits are replayed independently on the entire static-mask family. A miss remains lower bound1 with no upper bound.

| m | Unique queries | Certified weaker | Unresolved true winners | Unresolved nonwinners |
|---:|---:|---:|---:|---:|
| 2 | 6 | 5 | 1 | 0 |
| 3 | 57 | 55 | 2 | 0 |
| 4 | 486 | 484 | 1 | 1 |
| 5 | 1163 | 1156 | 3 | 4 |
| 6 | 2083 | 2063 | 0 | 20 |
| 7 | 2197 | 2142 | 1 | 54 |

Scoring budgets are32 and128 candidates per cohort, with whole-root-shape blocks retained and overshoot recorded. Repeated graphs across cohorts share one deterministic cached query. Candidate generation recall is reported separately: surviving a bounded elimination query does not certify a maximizer, and winning classes absent from a selected prefix cannot be recovered by its scorer. Unscored candidates remain outside the scoring-budget population, rather than being silently discarded.

`observations.jsonl` retains each cohort's nonwinner elimination fraction, survivor precision/global winner recall and exact witness-gap histogram where H is known (m≤6). `scores.jsonl` preserves every attempt, observation and provenance. `analysis.json` aggregates per-size results. The source helper/executable and generation seal are pinned in `query-plan.json` and the work directory snapshots. This finite candidate test supplies no global exclusion certificate for sizes8–20.

```powershell
uv run --no-project python tests/family1_edit_elimination_benchmark.py
```
