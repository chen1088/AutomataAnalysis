# Constructed length-34 pair transfer

6 distinct pairs from 27 newly constructed native results were replayed on all eight seven-state maximizing rooted classes. Each replay independently simulates all 128 static masks and retains both complete endpoint vectors.

| Graph ordinal | Direct new length-34 result in pool | Original-pair reuse succeeds | Any listed variant succeeds |
|---:|:---:|:---:|:---:|
| 539749 | yes | yes | yes |
| 679758 | no | no | no |
| 1783759 | yes | yes | yes |
| 2221624 | no | no | no |
| 2470130 | yes | yes | yes |
| 2471796 | no | no | no |
| 3411148 | yes | yes | yes |
| 4099217 | yes | yes | yes |

Original-pair reuse found no additional graph classes. Global complements have the same success sets, as expected: complementing every input letter is exactly replacing each mask by its bitwise complement. Reverse and reverse-complement words were tested as new candidates; neither transformation produced a successful pair on any of these eight graphs.

The uncovered classes are 679758, 2221624, 2471796. This is a finite candidate-pool transfer experiment, not an independent automatic search and not evidence that no other length-34 pair exists. Successful length-34 pairs are globally shortest only because H=34 was separately certified for these graphs.

Inputs are controlled v1/v2 lookahead results, the k6/W16 target34 results, and completed k8/k16/distance target34 native attempts. The script never opens the original saved-witness/maximizer datasets. Each collected pair records the native JSON SHA-256 and its run/attempt provenance. Graph transition tables are reconstructed from the keys in the controlled rows.

Files: `constructed-pairs.jsonl` contains the source pairs and provenance; `variants.jsonl` lists all tested transformations and successful classes; `replays.jsonl` retains every full product-state comparison; `source-inventory.json` pins all examined native outputs and row containers; `summary.json` gives counts and claim boundaries.

Reproduce from the repository root (using the actual Python 3.11 executable on this machine):

```powershell
& C:\Users\chenxu\.local\bin\python3.11.exe scripts/family1_constructed_pair_transfer.py
```
