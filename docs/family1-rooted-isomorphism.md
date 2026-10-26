# Rooted and unrooted five-state extremal graphs

The five-state plate contains five **rooted** classes, as required by the search
specification. Forgetting the starting vertex leaves four unrooted shapes.
Panels (a) and (c) share one underlying directed graph; no other pair shares
an unrooted shape under the allowed independent port swaps.

The explicit map from (a) to (c) is

```text
old vertex in (a):  0  1  2  3  4
new vertex in (c):  2  1  0  3  4
```

The two ports swap at old vertices 0 and 2. This map sends the root of (a) to
vertex 2 of (c), rather than its root. There is no root-preserving isomorphism:
the root of (a) has a loop, whereas the root of (c) has none.

Root choice matters for the quantity being maximized. For the underlying graph
in (a), using vertices 0 through 4 as the starting vertex gives respectively

```text
H = 15, 12, 15, 14, 14.
```

Panel (c) corresponds to selecting vertex 2 of (a). Both choices attain 15 and
must remain in the rooted collection. No drawing or PDF was removed or changed
in this audit.

## Independent verification

`tests/family1_m5_isomorphism_test.py` tries all 120 vertex bijections for each
pair and checks both ordinary and root-preserving isomorphism. It parses the
actual TikZ drawing commands with comments removed, checking all 25 vertices,
five roots, and all 50 directed ports against the canonical tables.

It also independently recomputes the exact score of every displayed graph.
Complete endpoint vectors over all 32 static masks are distinct for every
length from 1 through 14; distinct words first coincide at length 15. Direct
per-mask word simulation additionally checks every word through length 7 and
all saved or discovered witnesses. Results are recorded in
`results/family1-m5-audit.json`.

```powershell
uv run --no-project python tests\family1_m5_isomorphism_test.py
```

This audit establishes the five individual scores and the rooted/unrooted
distinction. It does not by itself prove a global optimum at another size.
The absolute global problem for sizes 7 through 20 remains unfinished; their
sampled candidates and lower bounds must not be treated as its solution.
