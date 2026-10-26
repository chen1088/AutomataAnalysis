# Family 1 TikZ atlas

`atlas.tex` contains every retained best-certified-bound tie, grouped by size
1 through 20. Global maxima are labeled proved only when the source summary
contains a certificate. Candidate bounds are not claims of global maximality.

Each `snippets/mXX-graph-NN.tex` is a reusable TikZ picture without a caption.
In a paper, load `tikz`, call `\usetikzlibrary{arrows.meta}`, and use
`\input{snippets/mXX-graph-NN.tex}`. The root is a double circle; port 0 is
solid and port 1 is dashed. Every node and both outgoing ports are preserved.
The default `--port-labels small` prints per-edge numerals through six states;
larger graphs use the solid/dashed distinction and page legend. Use
`--port-labels all` or `--port-labels none` to change only the redundant numerals.

Compile `atlas.tex` from this directory. Compile an individual wrapper from
the `standalone/` directory, for example:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error atlas.tex
Set-Location standalone
pdflatex -interaction=nonstopmode -halt-on-error m20-graph-01.tex
```

The five-state hand-arranged pictures are copied by verified transition table;
the certified seven-state pictures retain their shared shape embeddings when
`--manual-m7` is supplied. Their original files are not modified. The manifest records every table,
input hash, source layout, score interval, status, and page assignment.
