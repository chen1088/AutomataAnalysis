# Certified Family 1 extremal graphs

This focused plate contains all 8 certified maximizing rooted
classes with 7 states and H=34.
`plate.tex` uses at most six panels per page. Every rooted class is retained;
underlying-shape indices provide a separate grouping and remove no drawings.
Members of the same underlying shape share vertex positions. Each drawing
keeps its original canonical state numbers and double-circled root 0; the
manifest records the map to the shared shape and its local port swaps.

Each `snippets/*.tex` is a reusable `tikzpicture`. Load `tikz` and
`\usetikzlibrary{arrows.meta}` in the paper, then input the chosen snippet.
The double circle marks root 0; solid/dashed arrows distinguish ports 0/1.
Compile `plate.tex` from this directory. Compile wrappers from `standalone/`:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error plate.tex
Set-Location standalone
pdflatex -interaction=nonstopmode -halt-on-error m07-graph-01.tex
```

`source-manifest.json` records original input digests, every canonical table,
witness, drawing digest, geometry and page assignment. `certified-summary.json`
preserves the source summary bytes. The exporter verifies exact metadata,
canonicality and every witness over all original static masks; global coverage
and shortest-length proofs are inherited from the certified input run.
Compilation and visual PDF inspection must be completed separately.
