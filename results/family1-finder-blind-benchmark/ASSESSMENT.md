# Benchmark assessment

The predeclared 24-graph, 128-automatic-seed grid completed all 72 runs. Every
accepted pair passed independent scalar replay over every static mask. No
saved witness or witness-derived prefix was supplied.

| Exact-tail threshold | Hits /24 | Misses | Matches known H | Mean L/H among hits | Maximum L/H | Native seconds, all24 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 17 | 7 | 9 | 1.2068 | 2.2222 | 0.0800 |
| 2 | 17 | 7 | 9 | 1.2050 | 2.2222 | 0.0847 |
| 8 | 17 | 7 | 10 | 1.2034 | 2.3889 | 0.4012 |

The seven misses are seven of the eight seven-state maximizers. All 128
attempted prefix pairs in each of these runs failed the exact permutation
gate, and no suffix nodes were expanded. The immediate bottleneck is the
automatic prefix list, rather than suffix completion. A miss does not rule
out a graph or contradict its certified H=34.

Exact tails help some cases and hurt others under the fixed heuristic budget:

- Five-state maximizer 1511: threshold8 finds length15, matching H, versus17
  with tails disabled.
- Seven-state maximizer 539749: thresholds2 and8 find39 versus40, while H=34.
- Literal seven-state circulant: threshold8 finds24 versus25, while H=14.
- Manuscript-reference seven-state circulant: threshold8 finds23 versus24,
  while H=13.
- Six-state maximizer117031: threshold8 finds28 versus26, while H=23.
- Literal eight-state circulant: threshold8 finds43 versus40, while H=18.

These are engineering parameter comparisons, not a statistical claim that
one threshold generally dominates. Best-of-seeds also tightens its length cap
adaptively, so identical generator seeds and budgets need not produce the
same later prefix pairs across settings. Conditional exact completion does
not optimize the earlier heuristic choices.

`analysis.json` includes every run's gate count, tail calls/states, lengths,
gaps, ratios and native runtime. `runs.csv` and `runs.jsonl` retain the full
predeclared grid. The initial word-length cap was 2H+8 for every setting;
the known H was used for this budget and quality comparison only.
