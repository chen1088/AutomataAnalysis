# Family 1 grouped atlas

The 20 certified rooted maximizers through seven states are preserved as 13
ordinary shapes. Each marked vertex is a separate starting-state choice. All
accessible vertices were root-canonicalized; automorphic starts are included.
The JSON retains every original rooted record, proof source, witness and mapping.
Arbitrary local port labels/styles have been removed; parallel multiplicity stays.

The eight-state drawing is the current heuristic leader, estimate 49, finder
length 50, rigorous graph interval [1,50]. It is not a certified global optimum.
The independent global lower bound F(8)>=35 belongs to another graph.
The remaining pages are existing lower examples, not asserted maxima.

Reproduce from repository root:

    uv run --no-project python scripts/family1_grouped_atlas.py
    & "$env:APPDATA/TinyTeX/bin/windows/pdflatex.exe" '-interaction=nonstopmode' '-halt-on-error' '-output-directory=../../output/pdf/family1-grouped-atlas' atlas.tex

Run the TeX command with working directory figures/family1-grouped-atlas.
Reusable tikzpicture snippets and standalone wrappers are under that directory.
