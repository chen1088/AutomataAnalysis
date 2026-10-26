# Subsequence reduction of constructed near-pairs

The inputs are newly constructed near-pairs from the controlled v1/v2 lookahead grids. For each of the three remaining seven-state classes, take every distinct pair of the shortest found length, form the union of all distinct length-34 subsequences of all its words, and compare complete endpoint vectors over all 128 static masks. Saved optimal witnesses are not read.

| Ordinal | Near length | Source pairs | Source words | Distinct subsequences | Recovered length34 | Complete within this pool | Native seconds |
|---:|---:|---:|---:|---:|:---:|:---:|---:|
| 679758 | 36 | 3 | 6 | 1017 | no | yes | 0.002089 |
| 2221624 | 38 | 1 | 2 | 6830 | no | yes | 0.010945 |
| 2471796 | 36 | 2 | 4 | 600 | no | yes | 0.001274 |

Each negative result excludes a collision only inside the explicitly described subsequence pool. It supplies no graph score lower bound and does not rule out other length-34 pairs. Equal hashes are always checked against complete product-state vectors, and identical words are excluded even when they occur in several source pools.

The standalone MSVC/O2 implementation generates each distinct subsequence once per source word by choosing the earliest available occurrence of its next letter; a later equal occurrence can only remove possible suffixes. It shares endpoint computations along this enumeration tree. Cross-input duplicates are deduplicated as actual words. All retained words from all inputs share one complete-profile table, so cross-input and within-input collisions are both detected.

The native self-test compares all 1,538 binary-word/target-length spaces through source length7 against a separate positional-subset implementation, replays cached profiles, forces all hashes equal, checks loops/coincident ports, and checks resource-cap labeling. The Python runner independently checks each source pair over128 masks, checks each per-input subsequence count by a distinct-subsequence dynamic program, and replays every reported hit independently.

Per-graph JSON pins the native result, source rows, newly constructed source pairs, full product states of any accepted hits, and reproduction command. No CMake or existing experiment files were changed.

```powershell
cmd.exe /c out\family1-subsequence-recovery\build.cmd
& C:\Users\chenxu\.local\bin\python3.11.exe scripts/family1_subsequence_recovery.py
```
