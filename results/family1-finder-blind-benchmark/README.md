# Blind automatic-seed finder benchmark

All20 certified maximizing rooted classes through size7 and four separately labeled circulants are included in the full run. Saved witnesses and witness-derived prefixes are never passed to the finder. The known exact H supplies the reporting baseline and the common pair-length cap 2H+8.

The predeclared threshold grid is 0,2,8 for every graph, with the same128 automatic-seed budget, k=2, beam4, and tail-state cap100,000. All settings are reported; the table does not select only a favorable setting.

| Graph | H | T=0 L | T=2 L | T=8 L |
|---|---:|---:|---:|---:|
| max-m1-0 | 1 | 1 | 1 | 1 |
| max-m2-1 | 3 | 3 | 3 | 3 |
| max-m3-7 | 6 | 6 | 6 | 6 |
| max-m3-45 | 6 | 6 | 6 | 6 |
| max-m4-443 | 10 | 10 | 10 | 10 |
| max-m5-1391 | 15 | 15 | 15 | 15 |
| max-m5-1511 | 15 | 17 | 17 | 15 |
| max-m5-5982 | 15 | 16 | 16 | 16 |
| max-m5-6241 | 15 | 15 | 15 | 15 |
| max-m5-6811 | 15 | 15 | 15 | 15 |
| max-m6-33343 | 23 | 23 | 23 | 23 |
| max-m6-117031 | 23 | 26 | 26 | 28 |
| max-m7-539749 | 34 | 40 | 39 | 39 |
| max-m7-679758 | 34 | miss | miss | miss |
| max-m7-1783759 | 34 | miss | miss | miss |
| max-m7-2221624 | 34 | miss | miss | miss |
| max-m7-2470130 | 34 | miss | miss | miss |
| max-m7-2471796 | 34 | miss | miss | miss |
| max-m7-3411148 | 34 | miss | miss | miss |
| max-m7-4099217 | 34 | miss | miss | miss |
| literal-m7 | 14 | 25 | 25 | 24 |
| literal-m8 | 18 | 40 | 40 | 43 |
| manuscript-reference-m7 | 13 | 24 | 24 | 23 |
| manuscript-reference-m8 | 13 | 15 | 15 | 15 |

Each accepted pair is independently replayed over every static mask. `runs.jsonl` and `runs.csv` retain every setting's gap, ratio, runtime, module statistics, exact-tail status/state counts, native result hashes, and commands. A tail BFS proves a shortest common suffix from its particular starting pair only. It does not prove that the resulting whole word pair is globally shortest, or that all shortest pairs were collected. Misses retain no new score bound.
