# Five-state extremal seed graphs

The five `graph-01.tex` through `graph-05.tex` files are reusable TikZ pictures.
Their vertex labels and all ten directed ports agree exactly with the five
canonical tables in `results/family1-m1-m6/maximizers.jsonl`.

In a paper preamble:

```tex
\usepackage{tikz}
\usetikzlibrary{arrows.meta}
```

Then input a snippet inside a figure or subfigure:

```tex
\input{figures/family1-m5/graph-01.tex}
```

Each snippet defines its drawing styles locally inside its own `tikzpicture`.
The root is a double circle, port 0 is solid, and port 1 is dashed; both ports
are also labeled numerically. The drawings remain readable in black and white.
All five pictures use the same scale and bounding box.

Compile `family1-m5.tex` from this directory for the complete plate. Compile
`graph-01-standalone.tex` through `graph-05-standalone.tex` for individual PDFs.
