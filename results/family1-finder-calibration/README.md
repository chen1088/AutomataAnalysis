# Seven-state finder calibration

A **single fresh automatic two-stage portfolio recovered34 on all eight** in 13 native invocations and 87.273 seconds wall time. Stage1 runs k6 on all eight; only its five nonhits proceed to the fixed k16 second stage. Selection uses verified hits, not graph identity or saved word pairs. This is a calibrated portfolio, distinct from one uniform k16 configuration. Both uniform k16 experiments recovered seven classes and timed out on ordinal539749 after180 seconds.

The fresh portfolio is published in [the compact report and full raw-evidence archive](../family1-finder-calibrated-portfolio/README.md). Its thirteen stage cases are included below and every new length34 pair is replayed again by this aggregate.

The direct finder outputs rediscover length34 on **8 of all eight** certified maximizing seven-state rooted graph classes. Every one of the 49 collected length-34 native results was independently replayed by this script over all128 static masks; both full endpoint vectors and full agreement traces are retained. No original saved optimal witness file is read.

These recovered pairs are globally shortest because the earlier exhaustive graph scoring already certified H=34. A heuristic hit alone supplies an upper bound; a failed bounded run supplies no new graph lower bound. Conditional suffix BFS supplies its stated conditional shortestness only.

| Ordinal | Smallest tested successful k | Beam | Tail threshold | Prefix pairs / outer attempts | Prefix depth / words per layer | Distance coordinates | Common-prefix depth | Native seconds | Native / executable SHA prefixes | Source batch |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 539749 | 6 | 16 | 8 | 1024 / 1024 | 16 / 65536 | 0 | 0 | 0.657 | 85aec921761e / 5e641b5d1e36 | family1-finder-calibrated-portfolio/stage1-k6 |
| 679758 | 16 | 16 | 8 | 65536 / 65536 | 21 / 2097152 | 128 | 8 | 43.909 | f0b39c78ee55 / 5e641b5d1e36 | family1-target34-uniform-k16-budget50000 |
| 1783759 | 8 | 16 | 8 | 8192 / 8192 | 20 / 1048576 | 0 | 0 | 1.350 | b37083d2c815 / 9389863194cc | family1-target34-k8-complete-prefix20 |
| 2221624 | 16 | 16 | 8 | 65536 / 65536 | 21 / 2097152 | 128 | 8 | 83.729 | 7cbdba6b1051 / 5e641b5d1e36 | family1-finder-calibrated-portfolio/stage2-k16 |
| 2470130 | 4 | 4 | 8 | 128 / 128 | 16 / 65536 | 0 | 0 | 0.087 | 029e6ba773de / 9389863194cc | family1-finder-lookahead-grid-v2 |
| 2471796 | 16 | 16 | 8 | 65536 / 65536 | 21 / 2097152 | 128 | 8 | 62.682 | 25a8a2403353 / 5e641b5d1e36 | family1-finder-calibrated-portfolio/stage2-k16 |
| 3411148 | 6 | 16 | 8 | 1024 / 1024 | 16 / 65536 | 0 | 0 | 1.169 | bb7ebf6dfc19 / 5e641b5d1e36 | family1-finder-calibrated-portfolio/stage1-k6 |
| 4099217 | 16 | 16 | 8 | 8192 / 8192 | 20 / 1048576 | 128 | 0 | 2.153 | 7a68bba6c42a / 21b0191f43b3 | family1-target34-distance-k8-16-prefix20 |

The table uses SHA-256 prefixes for readability; `smallest-tested-successful-k.jsonl` contains the complete hashes, exact commands, complete native settings and witness provenance. The smallest successful tested k is tied to the complete configuration shown and is not a proof that smaller k cannot work. The controlled v1 and v2 grids keep their own fixed settings; the adaptive recovery runs also increase prefix coverage, seed budget, common-prefix diversity and/or distance pruning. Their outcomes must not be attributed to k alone. This is retrospective calibration on known seven-state maximizers, not a held-out estimate of success on other graphs or state sizes.

| Batch | Cases | Length34 results | Longer collisions | Unknown / other incomplete | Time capped incomplete | Distinct graph classes with34 | Native seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| family1-finder-calibrated-portfolio/stage1-k6 | 8 | 3 | 0 | 5 | 0 | 3 | 9.575 |
| family1-finder-calibrated-portfolio/stage2-k16 | 5 | 5 | 0 | 0 | 0 | 5 | 201.417 |
| family1-finder-lookahead-grid-v1 | 144 | 7 | 137 | 0 | 0 | 1 | 15.375 |
| family1-finder-lookahead-grid-v2 | 64 | 6 | 58 | 0 | 0 | 1 | 74.164 |
| family1-finder-target34-k6-w16 | 8 | 3 | 0 | 5 | 0 | 3 | 11.763 |
| family1-target34-common8-prefix21 | 6 | 0 | 0 | 6 | 0 | 0 | 119.587 |
| family1-target34-common8-wide65536 | 3 | 3 | 0 | 0 | 0 | 3 | 197.686 |
| family1-target34-distance-k8-16-prefix20 | 13 | 4 | 0 | 9 | 0 | 4 | 456.111 |
| family1-target34-k16-complete-prefix20 | 8 | 4 | 0 | 4 | 0 | 4 | 1943.437 |
| family1-target34-k8-complete-prefix20 | 8 | 3 | 0 | 5 | 0 | 3 | 148.061 |
| family1-target34-uniform-k16-budget50000 | 8 | 7 | 0 | 0 | 1 | 7 | 208.814 |
| family1-target34-uniform-k16-other5 | 5 | 4 | 0 | 0 | 1 | 4 | 20.583 |

No single complete configuration has yet been observed recovering34 on all eight classes in this snapshot. Direct union coverage across configurations must be distinguished from uniform-configuration coverage.

`cases.jsonl` preserves every completed controlled/adaptive native answer, its complete run configuration, all cap fields, and hashes of native output, native configuration, executable, and container/attempt metadata. Process attempts without a completed native result are retained separately. A timed-out invocation is `time_capped_incomplete`, with its wall time and configuration retained; it is not an algorithmic failure or a graph lower-bound certificate. Native-seconds totals sum completed native answers and exclude timed-out wall time. Prefix/depth/pair caps and exact-tail caps remain explicit; none is promoted to an exhaustive graph score.

`verified-minimum34.jsonl` retains each independently replayed pair, both complete128-state vectors and scalar common-suffix score traces. `smallest-tested-successful-k.jsonl` contains the fully provenanced selected table rows. `configuration-groups.json` groups only identical executable hashes and complete nongraph run settings. `summary.json` lists whole-experiment counts and input hashes. No transfer/subsequence reduction result is counted as a direct finder hit.

Rebuild this aggregate after additional completed target attempts:

```powershell
uv run --no-project python scripts/family1_finder_calibration.py
```
