# Paired-word calibration figures

All actual pairs are independently scalar-replayed. Joint k=4, B=16; exact-layer producers have k=N/A.
The fallback depth is 24, word-layer cap 16,777,216 and array-payload cap 256 MiB.
A match to the exhaustive reference and the native minimum-proof flag remain separate.

| m | Key | Producing k | L | Reference | Pair and D trace |
|---:|---|---|---:|---|---|
| 1 | 0000 | N/A | 1 | H=1 | [figure](m1-0000/witness.svg) |
| 2 | 00010001 | N/A | 3 | H=3 | [figure](m2-00010001/witness.svg) |
| 3 | 000101020001 | N/A | 6 | H=6 | [figure](m3-000101020001/witness.svg) |
| 3 | 010200010102 | N/A | 6 | H=6 | [figure](m3-010200010102/witness.svg) |
| 4 | 0102000201030003 | N/A | 10 | H=10 | [figure](m4-0102000201030003/witness.svg) |
| 5 | 00010203000103040204 | N/A | 15 | H=15 | [figure](m5-00010203000103040204/witness.svg) |
| 5 | 00010203000301040204 | N/A | 15 | H=15 | [figure](m5-00010203000301040204/witness.svg) |
| 5 | 01020003010203040004 | N/A | 15 | H=15 | [figure](m5-01020003010203040004/witness.svg) |
| 5 | 01020003010402030104 | N/A | 15 | H=15 | [figure](m5-01020003010402030104/witness.svg) |
| 5 | 01020003030400030104 | N/A | 15 | H=15 | [figure](m5-01020003030400030104/witness.svg) |
| 6 | 000102030304020500010405 | N/A | 23 | H=23 | [figure](m6-000102030304020500010405/witness.svg) |
| 6 | 010200030405020300010405 | N/A | 23 | H=23 | [figure](m6-010200030405020300010405/witness.svg) |
| 7 | 0001020302030405000604060105 | 4 | 35 | H=34 | [figure](m7-0001020302030405000604060105/witness.svg) |
| 7 | 0001020304050406050600010203 | 4 | 36 | H=34 | [figure](m7-0001020304050406050600010203/witness.svg) |
| 7 | 0102000301040204050600030506 | 4 | 34 | H=34 | [figure](m7-0102000301040204050600030506/witness.svg) |
| 7 | 0102000304050106000304050206 | 4 | 35 | H=34 | [figure](m7-0102000304050106000304050206/witness.svg) |
| 7 | 0102010203040005030604060005 | 4 | 34 | H=34 | [figure](m7-0102010203040005030604060005/witness.svg) |
| 7 | 0102010203040005050600060304 | 4 | 36 | H=34 | [figure](m7-0102010203040005050600060304/witness.svg) |
| 7 | 0102020304050006000604050103 | 4 | 34 | H=34 | [figure](m7-0102020304050006000604050103/witness.svg) |
| 7 | 0102030405060001000203040506 | 4 | 34 | H=34 | [figure](m7-0102030405060001000203040506/witness.svg) |
| 8 | 01020003040501060003020705060407 | 4 | 53 | prior verified upper=50; H unknown | [figure](m8-01020003040501060003020705060407/witness.svg) |
