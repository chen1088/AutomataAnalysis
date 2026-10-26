# Family 1 study and figures for every size from one to twenty

**Historical study snapshot.** The seven-state coverage and atlas description
below have been superseded by the [certified seven-state result](../family1-m7/README.md)
and [current atlas dataset](../family1-atlas-current/README.md). The original
55-picture atlas is preserved under `out/family1-atlas-before-certified-through7/`.
The current PDF has 24 pages and 33 graphs, with all maximizing classes through
seven states and explicit `H>=34` constructions for exact sizes 8 through 20.
The observations and proof attempts in this directory remain unchanged;
unresolved challengers have not been excluded.

The study has an explicit row for each exact reachable-state count `1,...,20`.
Global optimality and a complete maximizing collection are proved for `1..6`
by the earlier exhaustive computation. They remain unresolved for `7..20`.
The rarity of known maximizers is motivation to search, not evidence that a
stronger unobserved graph cannot exist.

The larger runs evaluated 64 distinct graph classes. Of these, 63 still lack
an exact individual score. All remain in the observation data; none is ruled
out merely because its current lower bound is smaller. One twenty-state graph
has certified `H>=27`, independently replayed using ordinary integer states on
64 specified static masks through all `2^26` words of length 26.

- `study.csv` and `summary.json`: all twenty sizes, exact values or bounds,
  unresolved challenger counts, and separate optimum-value/collection flags.
- `champions.jsonl`: every graph tied for the largest certified lower bound at
  its size. This is not a complete list of actual maximizers above six states.
- `larger-graph-observations.jsonl`: all 64 larger classes, including unresolved
  graphs outside the displayed best-bound collection.
- `global-proof-attempts/`: whole-graph symbolic attempts at every size. UNSAT
  results through four include reproducible DIMACS CNF; later UNKNOWN results
  do not establish global upper bounds.
- `m4-independent-cnf-check.json`: the fourth-state CNF was also UNSAT in the
  independent PicoSAT solver. These checks are not DRAT/LRAT proof traces.
- `m20-independent-projection.jsonl` and `validation.json`: independent
  lower-bound replay, tested scope, code hashes, and final PDF hashes.

The complete 203,321 exact small-graph records remain in
`out/family1-m1-m6/graphs.jsonl`. Larger run journals and merged full study data
are under `out/family1-study-1-20/`. Generated run files are ignored by Git.

The paper-ready, vector-only atlas is
`output/pdf/family1-atlas/family1-atlas-1-20.pdf`: twenty pages and 55 reusable
TikZ pictures. Every displayed tied best-bound graph is retained. The complete
TikZ sources, standalone wrappers, transition tables, and proof-aware captions
are in `figures/family1-atlas/` and its ZIP beside the PDF. The separately
arranged five-state plate and all five individual graph PDFs are in
`output/pdf/family1-m5/`, with source in `figures/family1-m5/`.

Build the drawings with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-family1-m5.ps1
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-family1-atlas.ps1
```

Add `-Individual` to the atlas build to compile all standalone wrappers. For
global certificate logic and continuation commands see
`docs/family1-global-certificates.md`; for search and bounds see
`docs/family1-scaling.md`.
