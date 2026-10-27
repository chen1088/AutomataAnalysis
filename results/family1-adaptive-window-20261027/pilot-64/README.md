# Deterministic adaptive joint-window benchmark

This sealed run contains 20 graphs and 11 configurations. Each configuration uses 64 starts per seed ranking. The exact oracle is disabled (`exact_depth=0`); every returned distinct word pair was independently replayed on every original static mask before reference values were loaded.

All joint lookaheads use the complete alphabet `00,01,10,11`. A complete depth-k window contains all `4^k` leaves, including identical word pairs for its moments. Only distinct word pairs can supply positive certificates. The empty pair has D=0; D counts unequal endpoints and the synchronized count is N−D, where N=2^m.

For n=4^k, the normalized total variance is `(n sum(D^2) − sum(D)^2)/(n^2 N^2)`. The normalized action variance is `(4 sum_a(sum_a D)^2 − sum(D)^2)/(n^2 N^2)`: the population variance of the four conditional **mean** D values, not their minima. Thresholds use parts per million and comparisons use exact integer arithmetic. Growing k reuses the completed layers; work is `sum_k 4^k * completed_layers[k]`.

| Configuration | Policy | Joint k | Threshold ppm | Found | L=H | L≤H+1 | L≤H+2 | m=6,7 L=H | Joint expansions | Capped attempts |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| block4 | fixed-block | 4 | 0 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 22,713,788 | 0 |
| rolling4 | fixed-roll | 4 | 0 | 20/20 | 15/20 | 19/20 | 20/20 | 5/10 | 93,843,612 | 0 |
| rolling2 | fixed-roll | 2 | 0 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 6,658,524 | 0 |
| rolling5 | fixed-roll | 5 | 0 | 20/20 | 15/20 | 19/20 | 20/20 | 5/10 | 338,848,700 | 0 |
| variance-low | total-roll | 2..5 | 1000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 6,664,668 | 0 |
| variance-mid | total-roll | 2..5 | 10000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 31,684,444 | 0 |
| variance-high | total-roll | 2..5 | 40000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 69,829,724 | 0 |
| action-low | action-roll | 2..5 | 1000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 34,619,452 | 0 |
| action-mid | action-roll | 2..5 | 10000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 76,274,556 | 0 |
| variance-deeper | total-roll | 4..6 | 10000 | 20/20 | 15/20 | 19/20 | 20/20 | 5/10 | 175,090,844 | 0 |
| variance-progress | progress-roll | 2..6 | 10000 | 20/20 | 14/20 | 19/20 | 20/20 | 4/10 | 104,842,708 | 5 |

Known-H columns include every exact-reference graph in their denominators; misses do not count as within any gap. Unknown-H results remain upper-bound certificates. Historical verified upper bounds are stored separately from each new finder result and receive no new-finder success credit.

The seed catalogue and rankings are shared across compared configurations for each graph. Per-policy joint work includes all attempts, including failed or capped ones. Seed preprocessing is reported both once per graph and as the cost each policy would incur alone; selecting the shortest display pair does not define a costed portfolio.

Detailed moments cover **winning-attempt ancestry only**. Aggregate k histograms cover all attempts. Selected-k histograms may include provisional horizons from aborted decisions; actual winning sequences are recorded separately. A refused growth layer ends that attempt without committing a last-eligible-k fallback. A bounded failure supplies no negative proof.

Actual words, D traces, configured k ranges and producing k sequences are retained in every case/configuration CSV row. A bounded seed collision has producing k=N/A; its empty sequence does not indicate a missing parameter. The default figure display chooses one shortest new result per graph with a lexical configuration tie break, explicitly as post-hoc display selection.

The variance criterion is not a global quality certificate. Even an eligible adequate window need not lower D at the next committed symbol, and permutation-first progress can improve its primary objective while increasing D. Local search results never certify a universal approximation error.

Files:

- [Summary and subgroup metrics](summary.json)
- [Independent validation](validation.json)
- [Frozen run parameters](run.json)
- [Query seals](query-audit.json)
- [Actual pair results: cases.csv](cases.csv)
- [Winning ancestry moments: winning-window-moments-000.csv](winning-window-moments-000.csv)
- [Winning ancestry moments: winning-window-moments-001.csv](winning-window-moments-001.csv)
- [Winning ancestry moments: winning-window-moments-002.csv](winning-window-moments-002.csv)
- [Winning ancestry moments: winning-window-moments-003.csv](winning-window-moments-003.csv)
