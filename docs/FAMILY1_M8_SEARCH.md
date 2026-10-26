# Eight-state edit search

This page describes the first sealed search/certificate snapshot. The current
[best-only adaptive search](FAMILY1_ADAPTIVE_CANDIDATES.md) has subsequently
improved upper bounds and expanded the edit neighborhood. Its estimates and
selection rules are separate from the certificate below.

The search has a certified eight-state example with **35 <= H(G) <= 52**.
Neither endpoint is presented as its exact score. The absolute eight-state
maximum and its complete maximizing collection remain unresolved.

Its rooted canonical transition table is:

| State | Port 0 | Port 1 |
|---:|---:|---:|
| 0 | 1 | 2 |
| 1 | 0 | 2 |
| 2 | 3 | 4 |
| 3 | 3 | 4 |
| 4 | 5 | 6 |
| 5 | 0 | 7 |
| 6 | 5 | 7 |
| 7 | 2 | 6 |

The key is `01020002030403040506000705070206`. The root is 0. Ports are
unordered for graph classification; each realization fixes its own local XOR
swaps on every revisit. The graph is accessible and has indegrees 1 and 3 as
well as 2. There is no indegree or strong-connectivity filter.

The [vector PDF](../output/pdf/family1-m8-search/candidate.pdf) compares it
with its seven-state parent. The [standalone TeX](../output/pdf/family1-m8-search/candidate.tex)
and [graph-only TikZ](../output/pdf/family1-m8-search/snippet-candidate.tex)
can be reused in a paper. This is a candidate drawing, not a plate of certified
eight-state maximizers.

## Individual lower certificate

`Family1M8LayerVerify` independently checks one equal-length layer. It does not
link any production Family 1 headers or scoring library. At length 34 it
generated all **8,589,934,592** words beginning with 0. Bitwise word complement
permutes the complete static masks, accounting for the other half of the
**17,179,869,184** words. A separate check covers a word colliding with its own
complement.

The run used 128 explicitly listed complement-closed masks for fingerprints.
Equal fingerprints were regenerated and compared as complete **256-mask**
scalar state vectors, in both complement orientations. Five repeated hash
groups contained ten records; all were false matches. Two low-bit hash buckets
completed, using about 32 GiB for their largest payload. The native check took
354.211 seconds on this machine.

Injectivity at length 34 proves injectivity at every shorter positive length:
any shorter collision could be extended by the same suffix to length 34.
Consequently **H(G) >= 35**. This is a formal exhaustive computational lower
certificate for this graph, independent of sampling. A separately replayed
length-52 pair supplies its upper bound.

The report, exact invocation, executable/source/reference-test snapshots,
validation logs and SHA-256 pins are in
`out/family1-m8-lower34-root-lift/`. The certificate acceptance code checks
completion, complete counts, every bucket, full replay accounting, mask closure,
the graph binding and invocation/artifact hashes. A timeout cannot promote a
lower bound.

## Search coverage

The independent Burnside reachable-set calculation gives **103,453,575**
accessible rooted eight-state classes, including loops and coincident ports.
The edit neighborhoods cover a small, explicitly bounded part of this universe.

The complete local radius-one growth from all 55 retained seven-state frontier
parents produced 4,153 direct rooted endpoints and, after all accessible roots,
**11,266 rooted classes in 1,424 ordinary shapes**. Eight parents have exact
score 34; the other 47 have verified upper bounds 32 or 33 and are possible
near-winners. Their membership is not a certified lower-score cutoff.

Every one of those 11,266 roots received the cap-34 screen and a cap-96 search,
then conditional cap-48/cap-40 searches. There were no native errors or timeouts
in these cheap screens. The resulting partition was:

| Best verified upper | Rooted classes |
|---|---:|
| Below 34 | 633 |
| 34 | 388 |
| 35-40 | 2,605 |
| 41-48 | 5,627 |
| Above 48 | 1,669 |
| No upper found | 344 |

All 10,922 retained witnesses were independently replayed over every static
mask. Larger witnesses and misses are not evidence of a large shortest length.
The two routing insertions preserve the parents' indegrees; 9,802 radius-one
candidates were balanced and 1,464 were unbalanced. An additional bounded
radius-two search includes retarget edits and explicitly explores new unbalanced
shapes. Its plan, selected roots, unselected classes and paths are preserved.
It retained 23,736 generated classes and evaluated 2,053 roots in 257 new
unbalanced shapes; generation was candidate-capped. The combined corpus has
26,924 observed classes and 13,327 evaluated graphs, with 43,835 recorded word
queries. All 25,795 possible maximizers within that observed corpus are kept.

Stronger passes cover all roots in selected shapes, two projection anchors,
multiple prefix/window settings and separately labelled inherited-word trials.
The [refinement report](../results/family1-m8-fresh-prefix-refinement/README.md)
retains timeouts and all checked pairs. None of those trials supplies a lower
bound. All observed classes, possible ties and unresolved challengers are kept
in the combined export; no graph is silently removed because a finder failed.

Local completeness is not global completeness. In particular, edit distance
has not supplied a theorem excluding the other eight-state graphs. The current
data does not certify the absolute best graph or its multiplicity.

## Reproduction

From the repository root in PowerShell, using the existing MSVC/vcpkg build:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-windows-vcpkg.ps1 -Configuration Release
uv run --no-project python scripts/family1_m8_initial_screen.py --out out/my-m8-search
uv run --no-project python tests/family1_burnside_count.py --max-m 8 --skip-brute --out out/my-m8-search/rooted-universe.json
uv run --no-project python scripts/family1_m8_upper_screen.py --search out/my-m8-search
```

Use a new output directory for a new experiment. The runners snapshot inputs,
sources and binaries; `--resume` reuses only matching pinned configurations and
validated completed attempts. The recorded original run also preserves the
repair history of a post-scoring export error, without discarding native work.
The layer wrapper reuses completed pinned proofs; an interrupted layer itself
must be restarted in a fresh directory.

Reproduce the length-34 certificate, using the preserved explicit mask list:

```powershell
uv run --no-project python scripts/family1_run_m8_layer.py --key 01020002030403040506000705070206 --depth 34 --fingerprint-mask-file out/family1-m8-search-v1/fingerprint-masks128.txt --threads 24 --bucket-bits 1 --memory-mib 40000 --timeout-seconds 1200 --out out/my-m8-lower34
```

This runs the independent scalar reference suite before starting the deep
check. The memory setting is a planning/payload limit, not an operating-system
RSS limit. More hash buckets reduce peak memory at the cost of extra complete
traversals. `--mask-list` alone checks a selected subfamily and reports a
projection collision conservatively; `--fingerprint-mask-file` checks complete
states on every match and can certify the full family.

The final combined export is reproducible with the command recorded in
`results/family1-m8-search/reproduce.ps1`. It includes canonical tables,
certified intervals, witnesses, all best-lower-bound ties, unresolved graphs,
generation paths, observations and source hashes. Best-lower-bound ties are
explicitly distinguished from exact or global maximizers.

Both native MSVC/vcpkg configurations pass **32/32 CTests**: Release in 37.79s
and Debug in 76.56s. The new reference suite includes all 64 accessible rooted
classes through three states, random cases through eight, static revisits,
loops/coincident ports, forced hash collisions, false projected self/cross
matches, non-block-aligned mask lists and resource/argument guards.
The final independent audit replayed all 10,655 saved graph-edit paths and all
12,646 primitive edits, checked the complete record/observation union and bound
minima, and rejected 18 altered proof/report cases. A fresh publication rerun
reproduced all ten data exports byte for byte.
