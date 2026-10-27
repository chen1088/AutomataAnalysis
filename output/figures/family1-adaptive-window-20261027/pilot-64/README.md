# Adaptive joint-window figures

Exact oracle disabled. k labels state the configured range and actual winning lookahead sequence.
An empty sequence is a bounded seed collision (k=N/A), not an exact-layer search.

Default display selects one shortest NEW result per graph, breaking ties by configuration name.
This is post-hoc display selection, not an evaluated portfolio or a quality/cost improvement.
Every case/configuration pair remains in the complete CSV tables.

| Configuration | m | Key | Producing k | L | Figure |
|---|---:|---|---|---:|---|
| action-low | 1 | 0000 | N/A (bounded seed collision) | 1 | [pair and D trace](action-low-m1-0000/witness.svg) |
| action-low | 2 | 00010001 | 2..5; winning lookaheads 2 | 3 | [pair and D trace](action-low-m2-00010001/witness.svg) |
| action-low | 3 | 000101020001 | 2..5; winning lookaheads 5 | 6 | [pair and D trace](action-low-m3-000101020001/witness.svg) |
| action-low | 3 | 010200010102 | 2..5; winning lookaheads 5 | 6 | [pair and D trace](action-low-m3-010200010102/witness.svg) |
| action-low | 4 | 0102000201030003 | 2..5; winning lookaheads 2×4 | 10 | [pair and D trace](action-low-m4-0102000201030003/witness.svg) |
| action-low | 5 | 00010203000103040204 | 2..5; winning lookaheads 2×6 | 15 | [pair and D trace](action-low-m5-00010203000103040204/witness.svg) |
| action-low | 5 | 00010203000301040204 | 2..5; winning lookaheads 2×7 | 15 | [pair and D trace](action-low-m5-00010203000301040204/witness.svg) |
| action-low | 5 | 01020003010203040004 | 2..5; winning lookaheads 2×4 | 15 | [pair and D trace](action-low-m5-01020003010203040004/witness.svg) |
| action-low | 5 | 01020003010402030104 | 2..5; winning lookaheads 5×4→2×9 | 15 | [pair and D trace](action-low-m5-01020003010402030104/witness.svg) |
| action-low | 5 | 01020003030400030104 | 2..5; winning lookaheads 2×8 | 15 | [pair and D trace](action-low-m5-01020003030400030104/witness.svg) |
| action-low | 6 | 000102030304020500010405 | 2..5; winning lookaheads 2×15 | 24 | [pair and D trace](action-low-m6-000102030304020500010405/witness.svg) |
| action-low | 6 | 010200030405020300010405 | 2..5; winning lookaheads 2×16 | 24 | [pair and D trace](action-low-m6-010200030405020300010405/witness.svg) |
| action-low | 7 | 0001020302030405000604060105 | 2..5; winning lookaheads 2×28 | 35 | [pair and D trace](action-low-m7-0001020302030405000604060105/witness.svg) |
| action-low | 7 | 0001020304050406050600010203 | 2..5; winning lookaheads 2×13 | 34 | [pair and D trace](action-low-m7-0001020304050406050600010203/witness.svg) |
| rolling4 | 7 | 0102000301040204050600030506 | 4; winning lookaheads 4×14 | 34 | [pair and D trace](rolling4-m7-0102000301040204050600030506/witness.svg) |
| action-low | 7 | 0102000304050106000304050206 | 2..5; winning lookaheads 2×15 | 35 | [pair and D trace](action-low-m7-0102000304050106000304050206/witness.svg) |
| action-low | 7 | 0102010203040005030604060005 | 2..5; winning lookaheads 2×21 | 34 | [pair and D trace](action-low-m7-0102010203040005030604060005/witness.svg) |
| action-low | 7 | 0102010203040005050600060304 | 2..5; winning lookaheads 2×23 | 36 | [pair and D trace](action-low-m7-0102010203040005050600060304/witness.svg) |
| action-low | 7 | 0102020304050006000604050103 | 2..5; winning lookaheads 2×17 | 34 | [pair and D trace](action-low-m7-0102020304050006000604050103/witness.svg) |
| action-low | 7 | 0102030405060001000203040506 | 2..5; winning lookaheads 2×13 | 34 | [pair and D trace](action-low-m7-0102030405060001000203040506/witness.svg) |
