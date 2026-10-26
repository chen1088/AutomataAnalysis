# One-vertex predecessors of the 6-state maximizers

Exactly 1 of the 2 rooted maximizers has a rooted 5-state global maximizer as a predecessor under the operation below. The certified maxima are 15 and 23.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 2 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 23 | 5-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 33343 | `000102030304020500010405` | 8 | 15 | 8 | yes |
| 117031 | `010200030405020300010405` | 8 | 14 | 9 | no |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 2 of the 2 rooted children have a predecessor of an ordinary winning 5-state shape. They cover 1 of the 1 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|
| 33343 | `00010203000103040204` | 15 |
| 33343 | `00010203000301040204` | 15 |
| 117031 | `01020003010402030004` | 14 |

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 1391 | `00010203000103040204` | `000102030304020500010405` |
| 1511 | `00010203000301040204` | `000102030304020500010405` |
| 5982 | `01020003010203040004` | none under this operation |
| 6241 | `01020003010402030104` | none under this operation |
| 6811 | `01020003030400030104` | none under this operation |

## Insertion from a previous global maximizer

Start with the canonical 5-state maximizer `00010203000301040204`:

```json
[[0,1],[2,3],[0,3],[1,4],[2,4]]
```

Replace parent edges 0 -> 1 (port 1), 2 -> 3 (port 1) by edges to new vertex 5. Give the new vertex outgoing ports [1, 3]. The result is:

```json
[[0,5],[2,3],[0,5],[1,4],[2,4],[1,3]]
```

Its rooted canonical key is `000102030304020500010405`; H increases from 15 to 23, a gain of 8.

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 33343: `000102030304020500010405`

Best parent score 15; increase 8. Best parent classes: `00010203000103040204`, `00010203000301040204`.

- Operation 0: remove v=1 with outgoing ports [2, 3]; reconnect 0[port 1] -> 2; 4[port 1] -> 3. Parent `00010203000301040204`.
- Operation 3: remove v=2 with outgoing ports [3, 4]; reconnect 1[port 0] -> 4; 3[port 0] -> 3. Parent `00010203000103040204`.

### Child 117031: `010200030405020300010405`

Best parent score 14; increase 9. Best parent classes: `01020003010402030004`, `01020102030400000304`.

- Operation 10: remove v=1 with outgoing ports [0, 3]; reconnect 0[port 0] -> 3; 4[port 1] -> 0. Parent `01020102030400000304`.
- Operation 15: remove v=4 with outgoing ports [0, 1]; reconnect 2[port 0] -> 1; 5[port 0] -> 0. Parent `01020003010402030004`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
