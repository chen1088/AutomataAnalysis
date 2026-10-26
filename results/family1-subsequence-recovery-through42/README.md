# Subsequence reduction of constructed near-pairs

The inputs are newly constructed near-pairs from the controlled v1/v2 lookahead grids. For each of the three remaining seven-state classes, take every distinct eligible pair, form the union of distinct length-34 subsequences of all its words, and compare complete endpoint vectors over all 128 static masks. Saved optimal witnesses are not read. Selection mode: `upto`; maximum source length 42. Words are processed by increasing length, then lexicographically.

| Ordinal | Source length range | Source pairs | Source words | Distinct subsequences | Recovered length34 | Complete within this pool | Native seconds |
|---:|---:|---:|---:|---:|:---:|:---:|---:|
| 679758 | 36–38 | 13 | 26 | 51361 | no | yes | 0.094776 |
| 2221624 | 38–42 | 12 | 24 | 1000000 | no | no | 1.814200 |
| 2471796 | 36–39 | 7 | 14 | 123603 | no | yes | 0.210030 |

Each negative result excludes a collision only inside the explicitly described subsequence pool. It supplies no graph score lower bound and does not rule out other length-34 pairs. Equal hashes are always checked against complete product-state vectors, and identical words are excluded even when they occur in several source pools.

The standalone MSVC/O2 implementation generates each distinct subsequence once per source word by choosing the earliest available occurrence of its next letter; a later equal occurrence can only remove possible suffixes. It shares endpoint computations along this enumeration tree. Cross-input duplicates are deduplicated as actual words. All retained words from all inputs share one complete-profile table, so cross-input and within-input collisions are both detected.

The native self-test compares all 1,538 binary-word/target-length spaces through source length7 against a separate positional-subset implementation, replays cached profiles, forces all hashes equal, checks loops/coincident ports, and checks resource-cap labeling. The Python runner independently checks each source pair over128 masks, checks each per-input subsequence count by a distinct-subsequence dynamic program, and replays every reported hit independently.

Limits: 100,000,000 enumeration nodes; 1,000,000 distinct complete profiles; 1,000,000 distinct words. A resource cap marks the entire union incomplete; per-input flags identify fully enumerated inputs. Incomplete counts are compared with upper totals from the independent counting DP. No negative result from a capped pool is treated as exhaustive.

Per-graph JSON pins the native result, source rows, newly constructed source pairs, full product states of any accepted hits, and reproduction command. No CMake or existing experiment files were changed.

```powershell
cmd.exe /c out\family1-subsequence-recovery\build.cmd
& C:\Users\chenxu\.local\bin\python3.11.exe scripts/family1_subsequence_recovery.py
```
