# Audited bounded neighborhood run

All 377 selected rooted classes across 39 shapes were queried. The audit preserves every record, lower-bound tie, and unresolved potential challenger. This is bounded graph coverage; global maxima and complete maximizing collections remain unresolved at these larger sizes.

| m | Selected shapes | Rooted classes | Upper witnesses | UNKNOWN | Best inherited lower bound |
|---:|---:|---:|---:|---:|---:|
| 8 | 3 | 17 | 2 | 15 | 34 |
| 9 | 3 | 19 | 11 | 8 | 34 |
| 10 | 3 | 21 | 12 | 9 | 34 |
| 11 | 3 | 23 | 8 | 15 | 34 |
| 12 | 3 | 25 | 4 | 21 | 34 |
| 13 | 3 | 27 | 3 | 24 | 34 |
| 14 | 3 | 29 | 3 | 26 | 34 |
| 15 | 3 | 31 | 3 | 28 | 34 |
| 16 | 3 | 33 | 3 | 30 | 34 |
| 17 | 3 | 35 | 3 | 32 | 34 |
| 18 | 3 | 37 | 3 | 34 | 34 |
| 19 | 3 | 39 | 3 | 36 | 34 |
| 20 | 3 | 41 | 3 | 38 | 34 |

Upper witnesses certify individual graph upper bounds. UNKNOWN adds no lower bound. The inherited bounds remain identified in record provenance. Native witness metadata confirms independent scalar checks over all 2^m masks; this publication audit checked hashes, contents, witness lengths and counts, and did not repeat that scalar computation.

`complete-evidence.zip` contains every raw run file, including its saved used executable and Python driver, with no exclusions. `manifest.json` pins all original and archived file bytes; `audit.json` records coverage and consistency checks. The seven compact exports are unchanged copies.

Reproduce publication to a new empty directory:

```powershell
uv run --no-project python scripts/family1_publish_neighbor_run.py --run out/family1-neighbor-full-metric-8-20-v1 --out results/neighbor-publication-new
```
