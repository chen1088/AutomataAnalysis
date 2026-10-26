# Family 1 grouped graph atlas

The current [1-20 vector atlas](../output/pdf/family1-atlas/family1-atlas-1-20.pdf)
has **21 pages and 26 underlying graphs**. Isomorphic rooted cases are drawn
once, with every qualifying starting vertex marked by a shaded double circle.
Choose one marked start at a time; multiple marks do not define a product over
different roots. Vertex numbers are references, and every arrow is unlabelled
and uses the same solid style. Parallel edges and loops are preserved.

All 20 certified rooted maximizing classes through seven states remain
represented, grouped into 13 ordinary graph shapes:

| m | Maximum | Rooted classes | Underlying graphs |
|---:|---:|---:|---:|
| 1 | 1 | 1 | 1 |
| 2 | 3 | 1 | 1 |
| 3 | 6 | 2 | 1 |
| 4 | 10 | 1 | 1 |
| 5 | 15 | 5 | 4 |
| 6 | 23 | 2 | 1 |
| 7 | 34 | 8 | 4 |

For each graph, every accessible vertex is canonicalized as a separate root.
Marked vertices are exactly those whose rooted class belongs to the certified
maximizing set, including automorphically equivalent starts. The original
rooted tables, witnesses, vertex maps and certificate references are retained
in [the grouped data](../results/family1-grouped-atlas/graphs.jsonl).
For example, the first size-five shape combines the former two rooted cases
at starts 0 and 2. The fourth size-seven shape marks starts 0,2,3,4,5.

## Eight states

We found one current heuristic candidate. Its key is
`01020003040501060003020705060407`, with working estimate **49** (roughly 48-50)
and a verified length-50 pair. The heuristic run archived 45,004 rooted
candidates and strongly refined 311, increasing the window through 16 and
widening the edit radius through 3. The active top tier has one rooted class.

All eight starts of that same underlying graph were refined:

| Starting vertex | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Verified finder pair length | 50 | 42 | 49 | 39 | 43 | 47 | 43 | 46 |

The top two rooted observations are thus the same graph with different starts.
Only start 0 has the current largest estimate and is highlighted. Pair lengths
are verified upper bounds; this is not an exact score or global certificate.
The independently certified size-eight lower bound `F(8)>=35` belongs to a
different graph and is recorded separately in the overview.

The [single-candidate PDF](../output/pdf/family1-m8-active-best/active-best.pdf)
and [TikZ picture](../output/pdf/family1-m8-active-best/graph-01.tex) use the same
unlabelled style and starting-state convention. The full root audit checked
all 40,320 vertex permutations and every root witness against all 256 masks.

At sizes 9-20 the atlas retains one constructive lower-bound example per size.
A marked start there only certifies `H>=34`; those panels do not claim global
optimality or complete maximizing collections.

## Reproduce and reuse

From the repository root:

```powershell
uv run --no-project python scripts/family1_grouped_atlas.py
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-family1-atlas.ps1
uv run --no-project python scripts/family1_package_atlas.py
uv run --no-project python scripts/family1_active_best_figure.py --out out/my-m8-picture
```

The [TikZ source ZIP](../output/pdf/family1-atlas/family1-atlas-tikz.zip) contains
`atlas.tex`, all 26 pictures and standalone wrappers, grouped tables and full
starting-vertex mappings. Each snippet is a complete `tikzpicture`. In a paper:

```tex
\usepackage{tikz}
\usetikzlibrary{arrows.meta}
\input{snippets/m05-shape-01.tex}
```

`figures/family1-grouped-atlas/` contains the editable source. The original
rooted presentation and its edit/ancestry records remain unchanged in
`figures/family1-atlas/` and their results directories. The previously published
labelled PDFs and sources are backed up in
`out/family1-pre-unlabelled-update/`. Use the build flag `-LegacyRooted` and
packaging flag `--legacy-rooted` only to reconstruct that older presentation.
