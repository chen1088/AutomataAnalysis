# One-vertex predecessors of the 3-state maximizers

Exactly 0 of the 2 rooted maximizers has a rooted 2-state global maximizer as a predecessor under the operation below. The certified maxima are 3 and 6.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 2 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 6 | 2-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 7 | `000101020001` | 0 | none | none | no |
| 45 | `010200010102` | 1 | 1 | 5 | no |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 0 of the 2 rooted children have a predecessor of an ordinary winning 2-state shape. They cover 0 of the 1 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 1 | `00010001` | none under this operation |

## Insertion from a previous global maximizer

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 7: `000101020001`

No permitted nonroot deletion gives an accessible parent. No score or gain is assigned.


### Child 45: `010200010102`

Best parent score 1; increase 5. Best parent classes: `01010001`.

- Operation 0: remove v=2 with outgoing ports [1, 2]; reconnect 0[port 1] -> 1. Parent `01010001`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
