# Family 1 atlas and graph edits

**The current atlas uses the [grouped, unlabelled presentation](family1-grouped-atlas.md).**
The rest of this page describes the preserved older rooted presentation.
Use `-LegacyRooted` when building and `--legacy-rooted` when packaging that
historical version. The current main PDF groups isomorphic graphs, marks
alternative optimal starts, and has 21 pages with 26 diagrams.

The current vector PDF is `output/pdf/family1-atlas/family1-atlas-1-20.pdf`.
Its 24 pages contain 33 complete transition diagrams, a proof-status overview,
and consecutive-size edit comparisons. All 20 certified rooted maximizing
classes for exact reachable sizes 1 through 7 are included. The five-state
manual drawings and certified seven-state shared embeddings are preserved.
The earlier atlas and sources are archived without deletion under
`out/family1-atlas-before-certified-through7/`.

For exact sizes 8 through 20, the drawings are explicit accessible constructions
with proved `H>=34` by a static-mask projection onto a certified seven-state
maximizer. Individual exact scores, global maxima, and complete maximizing
collections at these sizes remain unknown. Historical unresolved observations
are retained separately; smaller known lower bounds do not exclude them.
The eight-state guess 48 is a heuristic, not a certified bound.

The illustrated eight-state graph now has the independently checked interval
`35 <= H(G) <= 52`. A complete check at length 34 supplies the lower
bound, and a pair of 52 symbols was replayed over all 256 static masks for the upper
bound. This updates only the overview and eight-state page; the exact graph
score and global maximum remain unresolved. The single-record proof overlay is
`results/family1-atlas-m8-update/`. The prior PDF with 24 pages, source ZIP, all TikZ,
and original input hashes are preserved in `out/family1-atlas-pre-m8-35/`.

A separate paper-ready comparison of the seven-state parent and eight-state
candidate is `output/pdf/family1-m8-search/candidate.pdf`, with editable TeX and
standalone `tikzpicture` snippets beside it. Its shaded fibre displays the
projection; every seed port is labeled explicitly. These files are also in
the source ZIP under `m8-candidate/`.

## Consecutive winners

The [edit model](family1-graph-edits.md) assigns unit cost to retargeting one
port, inserting a routing vertex into two edge occurrences, or subdividing one
edge with a loop at the new vertex, and to the inverse operations. Relabeling
that fixes the root and local port swaps are free. Every intermediate graph
must be accessible and have two outgoing ports; indegrees are unrestricted.

The [ancestry audit](../results/family1-ancestry-through7/README.md) exhausts
every allowed one-vertex smoothing of every maximizing child at each consecutive
size. The [distance certificates](../results/family1-edit-distance-through7/README.md)
give an exact shortest edit path from the complete previous-size winner set
to each child winner. The score difference and edit distance are separate.

For 5 to 6, panels (a) and (b) of size five both grow into size-six panel (a)
in one insertion, raising H from 15 to 23. Size-six panel (b) is two edits from
the five-state winner set, and is the six-state winner that grows directly into
seven-state panel (d). Thus no chain of maximizers from five through seven
uses just one routing insertion at each step. All 19 child winners from sizes
two through seven lie within three edits of the previous-size winning set.
This finite observation supplies no extremal recurrence at larger sizes.

## Reproduce

From the repository root, with the certified source results present:

```powershell
uv run --no-project python scripts/family1_atlas_dataset.py
uv run --no-project python scripts/family1_ancestry.py --all-sizes
uv run --no-project python scripts/family1_edit_distance.py
uv run --no-project python scripts/family1_atlas_m8_overlay.py
uv run --no-project python scripts/family1_tikz_atlas.py --input results/family1-atlas-current --input results/family1-atlas-m8-update/records.jsonl --overview --ancestry results/family1-ancestry-through7/summary.json --edit-distances results/family1-edit-distance-through7/summary.json
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-family1-atlas.ps1
uv run --no-project python scripts/family1_package_atlas.py
```

The ancestry audit requires the complete `out/family1-m1-m6/graphs.jsonl`
journal to look up every predecessor's exact score. The distance calculation
uses the compact certified maximizing collections and does not rescore H.
Add `-Individual` to the build command for all 33 standalone PDFs.

Validation commands:

```powershell
uv run --no-project python tests/family1_atlas_dataset_test.py
uv run --no-project python tests/family1_ancestry_test.py
uv run --no-project python tests/family1_edit_distance_test.py
uv run --no-project python tests/family1_tikz_atlas_test.py
```

The source ZIP beside the PDF contains `atlas.tex`, all 33 TikZ snippets and
standalone wrappers, complete tables and witnesses, all predecessor operations,
all shortest edit paths, and the construction projection proofs. When built
with `-Individual`, it also includes all 33 individual vector PDFs. In a paper:

```tex
\usepackage{tikz}
\usetikzlibrary{arrows.meta}
% In the document, with the extracted snippets directory available:
\input{snippets/m05-graph-01.tex}
```

Compile the extracted `atlas.tex` from the ZIP root. Each snippet is a complete
`tikzpicture` without a caption. Root 0 is double-circled, port 0 solid, port 1
dashed. Local port labels are arbitrary representatives under the stated
isomorphism convention.

The ZIP also includes separate numerical data for the user's circulant seed
and the different manuscript reference seed. These are reference constructions,
not additional claimed maximizers. They are not combined into a product, and
the pooled quadratic theorem is not imported as an individual graph bound.
See [the comparison](family1-circulant-comparison.md) and
[root-aware search commands](family1-neighbor-search.md).
