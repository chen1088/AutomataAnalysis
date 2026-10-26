# One-vertex predecessors of the 4-state maximizers

Exactly 0 of the 1 rooted maximizers has a rooted 3-state global maximizer as a predecessor under the operation below. The certified maxima are 6 and 10.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 1 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 10 | 3-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 443 | `0102000201030003` | 4 | 5 | 5 | no |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 0 of the 1 rooted children have a predecessor of an ordinary winning 3-state shape. They cover 0 of the 1 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 7 | `000101020001` | none under this operation |
| 45 | `010200010102` | none under this operation |

## Insertion from a previous global maximizer

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 443: `0102000201030003`

Best parent score 5; increase 5. Best parent classes: `000101020002`, `010200010002`.

- Operation 0: remove v=1 with outgoing ports [0, 2]; reconnect 0[port 0] -> 0; 2[port 0] -> 2. Parent `000101020002`.
- Operation 3: remove v=2 with outgoing ports [1, 3]; reconnect 0[port 1] -> 3; 1[port 1] -> 1. Parent `010200010002`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
