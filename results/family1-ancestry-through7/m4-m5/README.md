# One-vertex predecessors of the 5-state maximizers

Exactly 0 of the 5 rooted maximizers has a rooted 4-state global maximizer as a predecessor under the operation below. The certified maxima are 10 and 15.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 5 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 15 | 4-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 1391 | `00010203000103040204` | 3 | 9 | 6 | no |
| 1511 | `00010203000301040204` | 6 | 9 | 6 | no |
| 5982 | `01020003010203040004` | 4 | 9 | 6 | no |
| 6241 | `01020003010402030104` | 4 | 9 | 6 | no |
| 6811 | `01020003030400030104` | 3 | 8 | 7 | no |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 1 of the 5 rooted children have a predecessor of an ordinary winning 4-state shape. They cover 1 of the 4 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|
| 1511 | `0001020300030102` | 9 |

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 443 | `0102000201030003` | none under this operation |

## Insertion from a previous global maximizer

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 1391: `00010203000103040204`

Best parent score 9; increase 6. Best parent classes: `0001020300010203`.

- Operation 4: remove v=3 with outgoing ports [3, 4]; reconnect 1[port 1] -> 4. Parent `0001020300010203`.
- Operation 5: remove v=4 with outgoing ports [2, 4]; reconnect 3[port 1] -> 2. Parent `0001020300010203`.

### Child 1511: `00010203000301040204`

Best parent score 9; increase 6. Best parent classes: `0001020300010203`, `0001020300030102`.

- Operation 7: remove v=1 with outgoing ports [2, 3]; reconnect 0[port 1] -> 3; 3[port 0] -> 2. Parent `0001020300010203`.
- Operation 11: remove v=3 with outgoing ports [1, 4]; reconnect 1[port 1] -> 4; 2[port 1] -> 1. Parent `0001020300010203`.
- Operation 12: remove v=4 with outgoing ports [2, 4]; reconnect 3[port 1] -> 2. Parent `0001020300030102`.

### Child 5982: `01020003010203040004`

Best parent score 9; increase 6. Best parent classes: `0102000301020003`.

- Operation 16: remove v=3 with outgoing ports [3, 4]; reconnect 1[port 1] -> 4. Parent `0102000301020003`.
- Operation 17: remove v=4 with outgoing ports [0, 4]; reconnect 3[port 1] -> 0. Parent `0102000301020003`.

### Child 6241: `01020003010402030104`

Best parent score 9; increase 6. Best parent classes: `0102000201030103`.

- Operation 20: remove v=3 with outgoing ports [2, 3]; reconnect 1[port 1] -> 2. Parent `0102000201030103`.

### Child 6811: `01020003030400030104`

Best parent score 8; increase 7. Best parent classes: `0102000301030003`.

- Operation 24: remove v=4 with outgoing ports [1, 4]; reconnect 2[port 1] -> 1. Parent `0102000301030003`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
