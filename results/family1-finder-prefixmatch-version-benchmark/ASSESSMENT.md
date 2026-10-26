# New-version assessment

All72 predeclared runs completed and produced independently verified witnesses.
The new version hits **all24 graphs**, including all eight seven-state maximizers;
the frozen first version hit17 and missed seven of those eight maximizers.

| Tail threshold | Hits /24 | Matches known H | Mean L/H, all24 | Maximum L/H | Native seconds, all24 |
|---:|---:|---:|---:|---:|---:|
| 0 | 24 | 8 | 1.1843 | 2.3333 | 1.0187 |
| 2 | 24 | 8 | 1.1855 | 2.3333 | 1.0349 |
| 8 | 24 | 9 | 1.1721 | 2.3333 | 1.3621 |

The first version's exact-H counts were9,9,10. Its mean ratios excluded seven
misses, whereas these means include all24 cases. These are not equal-population
means and should not be presented as a clean numerical improvement in closeness.

Among the17 cases hit by both versions, threshold0 gives two shorter,13 equal,
and two longer pairs; threshold2 gives the same counts. Threshold8 gives four
shorter,10 equal, and three longer pairs. Each setting additionally removes all
seven previous misses. No result or regression has been omitted.

For the eight certified seven-state rooted maximizers, H=34 throughout:

| Child ordinal | T0 length (gap) | T2 length (gap) | T8 length (gap) |
|---:|---:|---:|---:|
| 539749 | 36 (+2) | 37 (+3) | 38 (+4) |
| 679758 | 38 (+4) | 38 (+4) | 38 (+4) |
| 1783759 | 38 (+4) | 38 (+4) | 37 (+3) |
| 2221624 | 41 (+7) | 41 (+7) | 41 (+7) |
| 2470130 | 37 (+3) | 37 (+3) | 36 (+2) |
| 2471796 | 38 (+4) | 39 (+5) | 36 (+2) |
| 3411148 | 38 (+4) | 38 (+4) | 38 (+4) |
| 4099217 | 41 (+7) | 40 (+6) | 39 (+5) |

No setting yet recovers a length34 pair in this blind128-seed benchmark. The
literal eight-state circulant remains a weak result: found length42 versus
its known H=18. Coverage improvement is therefore substantial, while closeness
to the shortest pair remains uneven.

## What the prefix preprocessing certifies

The selected constraints are the permutation realizations of the same seed,
with duplicate DFAs removed only for preprocessing. Full-family mask
multiplicities remain in the objective and final verification.

All words are enumerated separately at each length through16, subject to the
per-layer65,536-word budget. Hash matches compare complete endpoint profiles.
Longer lengths20,24,28,32 use16,384 distinct deterministic sampled word IDs each,
when within the allowed pair-length cap. Those layers explicitly have
`sampled=true,complete_enumeration=false`; they do not prove exhaustive prefix
coverage. The final128 pair budget is spread across colliding depths and
profile buckets. A128-seed outer run uses learned pairs alongside unfiltered
templates and common-prefix variants; it does not try every compatible pair.

For example, seven-state ordinal679758 evaluates196,606 word profiles:
131,070 from complete layers1–16 and65,536 from four sampled longer layers.
Its first selected-subfamily collision at length9 is proved minimal for that
selected subfamily, not for the full Family1 graph whose H is34. Prefix matching
certifies compatibility with those selected constraints only.

Prefix preprocessing is additional work beyond the128 outer attempts. The
reported native runtimes include that work. This is a comparison of complete
algorithm versions—prefix matching plus proven viability—not a causal
prefix-only timing experiment.

## Exact tails and viability

Every reported whole pair was independently replayed over all static masks.
A shortest BFS suffix is conditional on its recorded starting pair; it does
not certify the earlier heuristic choices or global H. State/depth limits and
failed searches do not yield new graph-score bounds.

The optional viability gate checks a deterministic first-eight subset of
currently unmerged mask coordinates. It prunes only after a complete per-DFA
pair analysis proves nonmergeability. All exported closed-set proof examples
were independently checked. Cache hits consume the same coordinate budget as
misses, and cold-resume branch decisions matched warm uninterrupted runs.

The separate [T2-only ablation](../family1-finder-prefixmatch-viability0-ablation/README.md)
disables this optional check. It still hits all24 graphs;23 lengths are identical,
while the literal eight-state length improves from42 to40. Safe pruning does
not imply dominance for a finite heuristic search.

All72 primary rows remain in `runs.jsonl`/`runs.csv`; every per-run configuration,
prefix layer summary, tail count/state count, viability counter and native result
hash is retained. `analysis.json` records the paired comparisons and ablation.
