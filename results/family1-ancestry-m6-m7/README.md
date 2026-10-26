# One-vertex predecessors of the 7-state maximizers

Exactly 1 of the 8 rooted maximizers has a rooted 6-state global maximizer as a predecessor under the operation below. The certified maxima are 23 and 34.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 8 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 34 | 6-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 539749 | `0001020302030405000604060105` | 9 | 21 | 13 | no |
| 679758 | `0001020304050406050600010203` | 10 | 22 | 12 | no |
| 1783759 | `0102000301040204050600030506` | 10 | 21 | 13 | no |
| 2221624 | `0102000304050106000304050206` | 9 | 23 | 11 | yes |
| 2470130 | `0102010203040005030604060005` | 9 | 22 | 12 | no |
| 2471796 | `0102010203040005050600060304` | 9 | 22 | 12 | no |
| 3411148 | `0102020304050006000604050103` | 10 | 22 | 12 | no |
| 4099217 | `0102030405060001000203040506` | 10 | 22 | 12 | no |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 3 of the 8 rooted children have a predecessor of an ordinary winning 6-state shape. They cover 3 of the 4 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|
| 539749 | `000102030203040500050104` | 20 |
| 2221624 | `010200030405020300010405` | 23 |
| 2470130 | `010201020304000403050005` | 22 |

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 33343 | `000102030304020500010405` | none under this operation |
| 117031 | `010200030405020300010405` | `0102000304050106000304050206` |

## Insertion from a previous global maximizer

Start with the canonical 6-state maximizer `010200030405020300010405`:

```json
[[1,2],[0,3],[4,5],[2,3],[0,1],[4,5]]
```

Replace parent edges 0 -> 1 (port 0), 1 -> 0 (port 0) by edges to new vertex 6. Give the new vertex outgoing ports [0, 1]. The result is:

```json
[[6,2],[6,3],[4,5],[2,3],[0,1],[4,5],[0,1]]
```

Its rooted canonical key is `0102000304050106000304050206`; H increases from 23 to 34, a gain of 11.

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 539749: `0001020302030405000604060105`

Best parent score 21; increase 13. Best parent classes: `000102030004020403050105`.

- Operation 1: remove v=1 with outgoing ports [2, 3]; reconnect 0[port 1] -> 3; 6[port 0] -> 2. Parent `000102030004020403050105`.

### Child 679758: `0001020304050406050600010203`

Best parent score 22; increase 12. Best parent classes: `000102030204040503050001`, `000102030304040502050001`.

- Operation 13: remove v=2 with outgoing ports [4, 5]; reconnect 1[port 0] -> 4; 6[port 0] -> 5. Parent `000102030304040502050001`.
- Operation 16: remove v=3 with outgoing ports [4, 6]; reconnect 1[port 1] -> 6; 6[port 1] -> 4. Parent `000102030304040502050001`.
- Operation 21: remove v=6 with outgoing ports [2, 3]; reconnect 3[port 1] -> 2; 4[port 1] -> 3. Parent `000102030304040502050001`.
- Operation 22: remove v=6 with outgoing ports [2, 3]; reconnect 3[port 1] -> 3; 4[port 1] -> 2. Parent `000102030204040503050001`.

### Child 1783759: `0102000301040204050600030506`

Best parent score 21; increase 13. Best parent classes: `000102030103040500020405`.

- Operation 23: remove v=1 with outgoing ports [0, 3]; reconnect 0[port 0] -> 0; 2[port 0] -> 3. Parent `000102030103040500020405`.

### Child 2221624: `0102000304050106000304050206`

Best parent score 23; increase 11. Best parent classes: `010200030405020300010405`.

- Operation 35: remove v=1 with outgoing ports [0, 3]; reconnect 0[port 0] -> 3; 3[port 0] -> 0. Parent `010200030405020300010405`.
- Operation 39: remove v=3 with outgoing ports [1, 6]; reconnect 1[port 1] -> 6; 4[port 1] -> 1. Parent `010200030405020300010405`.

### Child 2470130: `0102010203040005030604060005`

Best parent score 22; increase 12. Best parent classes: `010200030204040501050003`, `010201020304000400050305`, `010201020304000403050005`.

- Operation 45: remove v=2 with outgoing ports [3, 4]; reconnect 0[port 1] -> 3; 1[port 1] -> 4. Parent `010200030204040501050003`.
- Operation 51: remove v=5 with outgoing ports [4, 6]; reconnect 3[port 1] -> 4; 6[port 1] -> 6. Parent `010201020304000403050005`.
- Operation 53: remove v=6 with outgoing ports [0, 5]; reconnect 4[port 1] -> 0; 5[port 1] -> 5. Parent `010201020304000400050305`.

### Child 2471796: `0102010203040005050600060304`

Best parent score 22; increase 12. Best parent classes: `010201020304000400050305`.

- Operation 60: remove v=4 with outgoing ports [5, 6]; reconnect 2[port 1] -> 5; 6[port 1] -> 6. Parent `010201020304000400050305`.

### Child 3411148: `0102020304050006000604050103`

Best parent score 22; increase 12. Best parent classes: `010200020304000503040105`, `010202030405000100030405`.

- Operation 70: remove v=3 with outgoing ports [0, 6]; reconnect 1[port 1] -> 0; 6[port 1] -> 6. Parent `010200020304000503040105`.
- Operation 71: remove v=3 with outgoing ports [0, 6]; reconnect 1[port 1] -> 6; 6[port 1] -> 0. Parent `010202030405000100030405`.
- Operation 75: remove v=6 with outgoing ports [1, 3]; reconnect 3[port 1] -> 1; 4[port 1] -> 3. Parent `010202030405000100030405`.

### Child 4099217: `0102030405060001000203040506`

Best parent score 22; increase 12. Best parent classes: `010201030405000200030405`, `010202030405000100030405`.

- Operation 82: remove v=3 with outgoing ports [0, 1]; reconnect 1[port 0] -> 1; 5[port 0] -> 0. Parent `010201030405000200030405`.
- Operation 84: remove v=4 with outgoing ports [0, 2]; reconnect 1[port 1] -> 2; 5[port 1] -> 0. Parent `010202030405000100030405`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
