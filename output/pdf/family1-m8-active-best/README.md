# Active eight-state estimate

`active-best.pdf` draws every graph currently tied for the best refined
estimate. There is one leader: point 49, rough range 48-50, from a verified
length-50 pair. These are heuristic estimates of its shortest merge length.

Reuse `graph-01.tex` with `\usepackage{tikz}` and
`\usetikzlibrary{arrows.meta}`. It contains a complete `tikzpicture` with the
best estimated starting vertices marked by double circles. All arrows are
identical and carry no port labels. Isomorphic rooted cases share one drawing;
each marked start is chosen separately. Static masks stay fixed on revisits.

`active-best.tex` builds the complete plate. `records.json` retains the exact
canonical table, witness and source hashes. The generator checks all 16 edges
and independently replays all 256 masks before compiling the PDF.

Regenerate in a fresh directory with:

```powershell
uv run --no-project python scripts/family1_active_best_figure.py --out out/my-active-best-figure
```
