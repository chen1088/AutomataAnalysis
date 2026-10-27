# Adaptive joint-window figures

Exact oracle disabled. k labels state the configured range and actual winning lookahead sequence.
An empty sequence is a bounded seed collision (k=N/A), not an exact-layer search.

Default display selects one shortest NEW result per graph, breaking ties by configuration name.
This is post-hoc display selection, not an evaluated portfolio or a quality/cost improvement.
Every case/configuration pair remains in the complete CSV tables.

| Configuration | m | Key | Producing k | L | Figure |
|---|---:|---|---|---:|---|
| block4 | 1 | 0000 | N/A (bounded seed collision) | 1 | [pair and D trace](block4-m1-0000/witness.svg) |
| block4 | 2 | 00010001 | 4; winning lookaheads 4 | 3 | [pair and D trace](block4-m2-00010001/witness.svg) |
| block4 | 3 | 000101020001 | 4; winning lookaheads 4×2 | 6 | [pair and D trace](block4-m3-000101020001/witness.svg) |
| block4 | 3 | 010200010102 | 4; winning lookaheads 4×2 | 6 | [pair and D trace](block4-m3-010200010102/witness.svg) |
| block4 | 4 | 0102000201030003 | 4; winning lookaheads 4→2 | 10 | [pair and D trace](block4-m4-0102000201030003/witness.svg) |
| block4 | 5 | 00010203000103040204 | 4; winning lookaheads 4→1 | 15 | [pair and D trace](block4-m5-00010203000103040204/witness.svg) |
| block4 | 5 | 00010203000301040204 | 4; winning lookaheads 4×2 | 15 | [pair and D trace](block4-m5-00010203000301040204/witness.svg) |
| block4 | 5 | 01020003010203040004 | 4; winning lookaheads 4→2 | 15 | [pair and D trace](block4-m5-01020003010203040004/witness.svg) |
| block4 | 5 | 01020003010402030104 | 4; winning lookaheads 4×3→1 | 15 | [pair and D trace](block4-m5-01020003010402030104/witness.svg) |
| block4 | 5 | 01020003030400030104 | 4; winning lookaheads 4×3 | 15 | [pair and D trace](block4-m5-01020003030400030104/witness.svg) |
| block4 | 6 | 000102030304020500010405 | 4; winning lookaheads 4×4 | 24 | [pair and D trace](block4-m6-000102030304020500010405/witness.svg) |
| block4 | 6 | 010200030405020300010405 | 4; winning lookaheads 4×5 | 24 | [pair and D trace](block4-m6-010200030405020300010405/witness.svg) |
| block4 | 7 | 0001020302030405000604060105 | 4; winning lookaheads 4×8 | 35 | [pair and D trace](block4-m7-0001020302030405000604060105/witness.svg) |
| block4 | 7 | 0001020304050406050600010203 | 4; winning lookaheads 4×3→3 | 34 | [pair and D trace](block4-m7-0001020304050406050600010203/witness.svg) |
| block4 | 7 | 0102000301040204050600030506 | 4; winning lookaheads 4×3→3 | 34 | [pair and D trace](block4-m7-0102000301040204050600030506/witness.svg) |
| block4 | 7 | 0102000304050106000304050206 | 4; winning lookaheads 4×4 | 35 | [pair and D trace](block4-m7-0102000304050106000304050206/witness.svg) |
| block4 | 7 | 0102010203040005030604060005 | 4; winning lookaheads 4×6 | 34 | [pair and D trace](block4-m7-0102010203040005030604060005/witness.svg) |
| block4 | 7 | 0102010203040005050600060304 | 4; winning lookaheads 4×3→3 | 34 | [pair and D trace](block4-m7-0102010203040005050600060304/witness.svg) |
| block4 | 7 | 0102020304050006000604050103 | 4; winning lookaheads 4×4→3 | 34 | [pair and D trace](block4-m7-0102020304050006000604050103/witness.svg) |
| block4 | 7 | 0102030405060001000203040506 | 4; winning lookaheads 4×3→2 | 34 | [pair and D trace](block4-m7-0102030405060001000203040506/witness.svg) |
