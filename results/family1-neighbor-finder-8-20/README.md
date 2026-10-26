# Audited bounded neighborhood run

All 377 selected rooted classes across 39 shapes were queried. The audit preserves every record, lower-bound tie, and unresolved potential challenger. This is bounded graph coverage; global maxima and complete maximizing collections remain unresolved at these larger sizes.

| m | Selected shapes | Rooted classes | Upper witnesses | UNKNOWN | Best inherited lower bound |
|---:|---:|---:|---:|---:|---:|
| 8 | 3 | 17 | 3 | 14 | 34 |
| 9 | 3 | 19 | 11 | 8 | 34 |
| 10 | 3 | 21 | 4 | 17 | 34 |
| 11 | 3 | 23 | 2 | 21 | 34 |
| 12 | 3 | 25 | 2 | 23 | 34 |
| 13 | 3 | 27 | 2 | 25 | 34 |
| 14 | 3 | 29 | 2 | 27 | 34 |
| 15 | 3 | 31 | 1 | 30 | 34 |
| 16 | 3 | 33 | 0 | 33 | 34 |
| 17 | 3 | 35 | 0 | 35 | 34 |
| 18 | 3 | 37 | 0 | 37 | 34 |
| 19 | 3 | 39 | 0 | 39 | 34 |
| 20 | 3 | 41 | 0 | 41 | 34 |

Upper witnesses certify individual graph upper bounds. UNKNOWN adds no lower bound. The inherited bounds remain identified in record provenance. Native witness metadata confirms independent scalar checks over all 2^m masks; this publication audit checked hashes, contents, witness lengths and counts, and did not repeat that scalar computation.

`complete-evidence.zip` contains every raw run file, including its saved used executable and Python driver, with no exclusions. `manifest.json` pins all original and archived file bytes; `audit.json` records coverage and consistency checks. The seven compact exports are unchanged copies.

Reproduce publication to a new empty directory:

```powershell
uv run --no-project python scripts/family1_publish_neighbor_run.py --run out/family1-neighbor-finder-8-20-v1 --out results/neighbor-publication-new
```
