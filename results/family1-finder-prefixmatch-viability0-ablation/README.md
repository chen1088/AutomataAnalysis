# T=2 viability ablation: 24 graphs

This report contains **24 runs at exact-tail threshold T=2 only**, with the optional general pair-viability check disabled (`--viability-checks 0`). It compares those lengths against the T=2 subset of the separate new-version72-run report, where8 residual coordinates may be checked at each state. It contains no T=0 or T=8 ablation runs.

Both use the same prefix matcher,128 automatic seeds, k=2, beam4, initial pair-length cap2H+8, tail-state cap100,000 and fixed seed1088. The permutation gate remains enabled in both. No saved witness or witness-derived prefix is supplied.

**All24 graphs were hit in both configurations. Lengths agree on23 graphs.** The literal eight-state circulant improves from42 with checks8 to40 with checks0 (known H=18). No other pair length changes. This does not invalidate the sound viability proofs: finite beam and adaptive prefix scheduling do not guarantee quality dominance after pruning.

| Graph | H | L checks8 | L checks0 |
|---|---:|---:|---:|
| max-m1-0 | 1 | 1 | 1 |
| max-m2-1 | 3 | 3 | 3 |
| max-m3-7 | 6 | 6 | 6 |
| max-m3-45 | 6 | 6 | 6 |
| max-m4-443 | 10 | 10 | 10 |
| max-m5-1391 | 15 | 15 | 15 |
| max-m5-1511 | 15 | 17 | 17 |
| max-m5-5982 | 15 | 16 | 16 |
| max-m5-6241 | 15 | 15 | 15 |
| max-m5-6811 | 15 | 15 | 15 |
| max-m6-33343 | 23 | 25 | 25 |
| max-m6-117031 | 23 | 26 | 26 |
| max-m7-539749 | 34 | 37 | 37 |
| max-m7-679758 | 34 | 38 | 38 |
| max-m7-1783759 | 34 | 38 | 38 |
| max-m7-2221624 | 34 | 41 | 41 |
| max-m7-2470130 | 34 | 37 | 37 |
| max-m7-2471796 | 34 | 39 | 39 |
| max-m7-3411148 | 34 | 38 | 38 |
| max-m7-4099217 | 34 | 40 | 40 |
| literal-m7 | 14 | 23 | 23 |
| literal-m8 | 18 | 42 | 40 |
| manuscript-reference-m7 | 13 | 24 | 24 |
| manuscript-reference-m8 | 13 | 15 | 15 |

The24 ablation rows are retained in `runs.jsonl`/`runs.csv`; every accepted pair was independently replayed over every static mask. `summary.json` pins the executable, headers, driver and full native configurations. Conditional BFS flags never substitute for global shortest-pair proofs.
