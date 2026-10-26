# One-vertex predecessors of the 2-state maximizers

Exactly 1 of the 1 rooted maximizers has a rooted 1-state global maximizer as a predecessor under the operation below. The certified maxima are 1 and 3.

## Operation

Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.

Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.

This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.

## All 1 rooted classes

| Child ordinal | Child key | Distinct parents | Best parent H | Increase to 3 | 1-state maximizer parent? |
|---:|---|---:|---:|---:|:---:|
| 1 | `00010001` | 1 | 1 | 2 | yes |

## Ordinary shapes and the starting vertex

If only the predecessor's root is ignored for an isomorphism comparison, 1 of the 1 rooted children have a predecessor of an ordinary winning 1-state shape. They cover 1 of the 1 ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.

| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |
|---:|---|---:|
| 1 | `0000` | 1 |

## Coverage of every previous global maximizer

| Parent ordinal | Parent key | Winning child keys |
|---:|---|---|
| 0 | `0000` | `00010001` |

## Insertion from a previous global maximizer

Start with the canonical 1-state maximizer `0000`:

```json
[[0,0]]
```

Replace parent edges 0 -> 0 (port 1) by edges to new vertex 1. Give the new vertex outgoing ports [0, 1]. The result is:

```json
[[0,1],[0,1]]
```

Its rooted canonical key is `00010001`; H increases from 1 to 3, a gain of 2.

## Best parent operations

Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.

### Child 1: `00010001`

Best parent score 1; increase 2. Best parent classes: `0000`.

- Operation 0: remove v=1 with outgoing ports [0, 1]; reconnect 0[port 1] -> 0. Parent `0000`.

## Reproduce

```powershell
uv run python scripts/family1_ancestry.py --all-sizes
uv run python tests/family1_ancestry_test.py
```

`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.
