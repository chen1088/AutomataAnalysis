# Subsequence and substitution recovery experiments

These experiments did not recover any new length-34 pair. They use only pairs newly constructed by the controlled lookahead grids. No original saved optimal witnesses are read. A negative result applies only to the stated candidate pool; a resource-capped pool remains incomplete.

The native implementation enumerates distinct subsequences, rather than positional deletion combinations. All candidate words from all selected sources for one graph share a table of complete 128-coordinate endpoint vectors. Hash equality is checked against the complete vector, identical words are excluded, and both within-source and cross-source pairs are checked. Any reported pair would be independently replayed over every mask by the Python driver.

| Candidate pool | Ordinal | Distinct length-34 words evaluated | Complete pool | Recovered 34 | Native seconds |
|---|---:|---:|:---:|:---:|---:|
| Minimum-length constructed pairs | 679758 | 1,017 | yes | no | 0.0021 |
| Minimum-length constructed pairs | 2221624 | 6,830 | yes | no | 0.0109 |
| Minimum-length constructed pairs | 2471796 | 600 | yes | no | 0.0013 |
| Every constructed pair of length at most42 | 679758 | 51,361 | yes | no | 0.0948 |
| Every constructed pair of length at most42 | 2221624 | 1,000,000 | no | no | 1.8142 |
| Every constructed pair of length at most42 | 2471796 | 123,603 | yes | no | 0.2100 |
| Minimum pairs, then at most one bit substitution per word | 679758 | 30,114 | yes | no | 0.0727 |
| Minimum pairs, then at most one bit substitution per word | 2221624 | 168,562 | yes | no | 0.4260 |
| Minimum pairs, then at most one bit substitution per word | 2471796 | 17,782 | yes | no | 0.0444 |
| Constructed pairs up to42, then one bit substitution | 679758 | 1,000,000 | no | no | 2.7651 |
| Constructed pairs up to42, then one bit substitution | 2221624 | 1,000,000 | no | no | 2.6120 |
| Constructed pairs up to42, then one bit substitution | 2471796 | 1,000,000 | no | no | 2.6303 |
| Every constructed pair of length at most45 | 2221624 | 10,000,000 | no | no | 20.2633 |

The 10-million-word run includes all 15 distinct constructed pairs for class2221624, with30 source words of lengths38–45. It finishes26 entire source-word pools before reaching the word cap. The full-profile count is also10,000,000: no two distinct evaluated words share a product state. This is an incomplete restricted search, not a lower bound on the graph's shortest merge length.

The current automatically rediscovered length-34 coverage stays at five of eight certified maximizing classes. Pool transfer and reversal/complement tests in [the transfer report](../family1-constructed-pair-transfer/README.md) add no classes. The missing classes remain679758,2221624,2471796. Their separately certified score remains34.

The native self-test passed all1,538 binary-word/target-length spaces through source length7 against a separate positional-subset reference. It checks every cached profile against scalar simulation and includes forced hash collisions, loops, coincident ports and cap labeling. The Python driver independently verifies all constructed source pairs over128 masks and checks each completed source's distinct-subsequence count by a separate dynamic program. Incomplete source counts are checked against that program's upper total.

All raw provenance, commands, caps and per-input completion flags are retained in these reports:

- [Minimum pools](../family1-subsequence-recovery/README.md)
- [All constructed pairs up to42](../family1-subsequence-recovery-through42/README.md)
- [Minimum pools plus one substitution](../family1-subsequence-recovery-minimum-substitute1/README.md)
- [All pairs up to42 plus one substitution](../family1-subsequence-recovery-through42-substitute1/README.md)
- [Class2221624 up to45, ten-million cap](../family1-subsequence-recovery-class2221624-through45/README.md)

The initial implementation was preserved before extension in `out/family1-subsequence-recovery/minimum-version/`. Later reports pin source/executable/driver snapshots in their work directories. No existing native production module, CMake file, earlier search report, or manuscript file was edited.

From the repository root, rebuild and reproduce each expanded report into a fresh directory:

```powershell
cmd.exe /c out\family1-subsequence-recovery\build.cmd
$python = 'C:\Users\chenxu\.local\bin\python3.11.exe'
& $python scripts/family1_subsequence_recovery.py --selection upto --max-source-length 42 --max-nodes 100000000 --output results/family1-subsequence-recovery-through42-repeat --work-dir out/family1-subsequence-recovery/through42-repeat
& $python scripts/family1_subsequence_recovery.py --selection minimum --substitutions 1 --max-nodes 100000000 --output results/family1-subsequence-recovery-minimum-substitute1-repeat --work-dir out/family1-subsequence-recovery/minimum-substitute1-repeat
& $python scripts/family1_subsequence_recovery.py --selection upto --max-source-length 42 --substitutions 1 --max-nodes 100000000 --output results/family1-subsequence-recovery-through42-substitute1-repeat --work-dir out/family1-subsequence-recovery/through42-substitute1-repeat
& $python scripts/family1_subsequence_recovery.py --selection upto --max-source-length 45 --ordinals 2221624 --max-profiles 10000000 --max-words 10000000 --max-nodes 1000000000 --output results/family1-subsequence-recovery-class2221624-through45-repeat --work-dir out/family1-subsequence-recovery/class2221624-through45-repeat
```
