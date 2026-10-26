# New-version blind quality benchmark

This is the second predeclared24-graph threshold grid. The first72-row report remains unchanged. The new version includes both full-profile prefix matching and a proven pair-viability gate. It is not a causal prefix-only comparison. No saved witness or witness-derived prefix is supplied.

The same outer budget128, k2, beam4, thresholds0/2/8, pair cap2H+8 and exact-tail state cap100,000 are used. Prefix preprocessing is additional work: complete layers through16 and16,384 deterministic sampled words at each configured longer depth20/24/28/32 when within the length cap. Every run.json configuration and preprocessing statistic is retained.

| Graph | H | First T0/T2/T8 | New T0/T2/T8 |
|---|---:|---|---|
| max-m1-0 | 1 | 1 / 1 / 1 | 1 / 1 / 1 |
| max-m2-1 | 3 | 3 / 3 / 3 | 3 / 3 / 3 |
| max-m3-7 | 6 | 6 / 6 / 6 | 6 / 6 / 6 |
| max-m3-45 | 6 | 6 / 6 / 6 | 6 / 6 / 6 |
| max-m4-443 | 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| max-m5-1391 | 15 | 15 / 15 / 15 | 15 / 15 / 15 |
| max-m5-1511 | 15 | 17 / 17 / 15 | 17 / 17 / 16 |
| max-m5-5982 | 15 | 16 / 16 / 16 | 16 / 16 / 17 |
| max-m5-6241 | 15 | 15 / 15 / 15 | 15 / 15 / 15 |
| max-m5-6811 | 15 | 15 / 15 / 15 | 15 / 15 / 15 |
| max-m6-33343 | 23 | 23 / 23 / 23 | 25 / 25 / 23 |
| max-m6-117031 | 23 | 26 / 26 / 28 | 26 / 26 / 24 |
| max-m7-539749 | 34 | 40 / 39 / 39 | 36 / 37 / 38 |
| max-m7-679758 | 34 | miss / miss / miss | 38 / 38 / 38 |
| max-m7-1783759 | 34 | miss / miss / miss | 38 / 38 / 37 |
| max-m7-2221624 | 34 | miss / miss / miss | 41 / 41 / 41 |
| max-m7-2470130 | 34 | miss / miss / miss | 37 / 37 / 36 |
| max-m7-2471796 | 34 | miss / miss / miss | 38 / 39 / 36 |
| max-m7-3411148 | 34 | miss / miss / miss | 38 / 38 / 38 |
| max-m7-4099217 | 34 | miss / miss / miss | 41 / 40 / 39 |
| literal-m7 | 14 | 25 / 25 / 24 | 23 / 23 / 23 |
| literal-m8 | 18 | 40 / 40 / 43 | 42 / 42 / 42 |
| manuscript-reference-m7 | 13 | 24 / 24 / 23 | 24 / 24 / 24 |
| manuscript-reference-m8 | 13 | 15 / 15 / 15 | 15 / 15 / 15 |

All new-version outcomes, including misses and regressions, remain in runs.jsonl/runs.csv. Every positive pair is independently replayed over every static mask. A shortest conditional suffix certificate is not a global shortest-pair proof.
