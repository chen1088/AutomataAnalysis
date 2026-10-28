This C++ project computes generating functions of product automata and searches
Family 1 graph realizations for long shortest equal-length merges.

The repository includes source, compact results and current PDF/TikZ figures.
Large raw datasets and build artifacts stay local; see the
[artifact policy and fresh-checkout commands](docs/repository-artifacts.md).

## Shortest hard-pair finder

Start with [Heuristics for shortest hard word pairs](docs/shortest-hard-pair-heuristics.md).
It defines the distinct equal-length pair objective, the full alphabet
00,01,10,11, deterministic starting pairs, block and one-symbol rolling
lookahead, adaptive variance, work budgets, certificates and reporting rules.
Joint k enumerates all 4^k extensions per retained pair; common-suffix k
uses only 2^k extensions after distinct prefixes. Exact layers have k=N/A.

| Executable | Method | Commands |
|---|---|---|
| Family1NearPair | Exact layers followed by full-D/common-distance starting pairs and joint k=4, beam 16 | [CLI guide](docs/family1-near-cli.md) |
| Family1Certified | Union of complete seed closures, observer refinement, signature certificates and independently checked intervals | [Certified finder](docs/family1-certified-finder.md) |
| Family1Joint | Full four-symbol block lookahead with explicit startup and beam controls | [Joint finder](docs/family1-joint.md) |
| Family1Offline | Graph-edit runner with exact scoring or restricted common-suffix search | [Offline guide](docs/family1-offline.md) |

Build the dependency-free tools and their tests on Linux:

```sh
cmake -S . -B out/build/heuristics -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build out/build/heuristics -j 4
ctest --test-dir out/build/heuristics --output-on-failure
out/build/heuristics/Family1NearPair --m 7 --graph 0001020302030405000604060105 --k 4 --beam 16 --out out/my-pair-run
```

The separate Windows build uses the static MSVC runtime and needs no vcpkg
installation. It builds the offline tools and test targets before running CTest:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-family1-offline.ps1 -Configuration Release -Package
.\out\build\family1-offline\Release\Family1Offline.exe --m 4 --heuristics off --depth 16 --max-layer-states 65536 --out out\offline-m4
```

Use a fresh output directory. The Family1NearPair default exact phase is
depth 24 with 256 MiB of planned payload; its producing k is N/A. On the
20 certified winners through m=7, the hybrid pipeline matches 18 exact lengths
and stays within one on all 20. With the exact oracle disabled and the same
joint k=4, beam 16, 512 starts per ranking, it matches 16 and stays within one.
Broader saved-graph tests still expose large errors and misses. A verified
pair supplies an upper certificate, not a general shortestness guarantee.

| Evidence | Scope |
|---|---|
| [Finder strategies](docs/family1-finder-strategies-report.md) | Seed scoring, exact budgets, rolling search, local rewrites and unsuccessful alternatives |
| [Adaptive windows](docs/family1-adaptive-window-report.md) | Complete joint k=2..5 and k=4..6 variance policies, oracle-off fixed controls, and actual winning k sequences |
| [Candidate and finder adaptiveness](docs/family1-adaptiveness-report.md) | Complete edit neighborhoods, exhaustive winner ties and the limits of champion crowding |
| [Generic joint benchmark](results/hard-pair-joint-benchmark-20261026/README.md) | Family 1, fixed heterogeneous DFA sets and complete local-swap closures at joint k=2,4,6,8 |
| [Complete m=8 recheck](results/family1-m8-joint-audit-20261026/README.md) | Every member of a 3,010-class radius-one neighborhood at joint k=6 and k=8 |
| [Paired-word figures](docs/hard-pair-figures.md) | Actual u,v, full D traces, original-mask counts and producing parameters beside each graph |

Candidate ordering, starting pairs and lexical ties are deterministic.
An experiment defined by an edit radius must generate and test every member
of that neighborhood. Bounded catalogues and capped generation report their
coverage explicitly. Source/configuration pins, all ties, negative outcomes,
and historical certificates remain in the evidence; large raw runs stay
under ignored out/. The [common-suffix method](docs/family1-heuristic-method.md)
documents the older restricted algorithm separately.

## Family 1 graph search

The **absolute maximum and every maximizing rooted class** are certified
through seven states. For **m=7 the maximum is 34**, attained by **eight rooted
classes across four underlying shapes**. The independent certificate covers
all **4,166,855** accessible seven-state classes: every other class has a
verified witness of length at most 33, and every maximizer has a complete
length-33 injectivity proof over all 128 static masks. Indegrees are unrestricted;
loops and coincident ports are included, without imposing strong connectivity.

The maxima for reachable sizes 1 through 7 are **1, 3, 6, 10, 15, 23, 34**.
See the [certificate and all maximizing tables](results/family1-m7/README.md),
[structural report](results/family1-m7-structures/structure.md),
[complete PDF plate](output/pdf/family1-m7/family1-m7.pdf), and
[reusable TikZ sources](figures/family1-m7/README.md).
The absolute maxima for sizes eight through twenty remain unresolved. The
[eight-state search](docs/FAMILY1_M8_SEARCH.md) now has an independently certified
**lower bound of 35**, exhaustively covering the entire length-34 layer of one
graph. The current [adaptive search](docs/FAMILY1_ADAPTIVE_CANDIDATES.md) keeps
only the best refined estimates and every top tie in its
[active shortlist](results/family1-m8-estimates/best-candidates.jsonl). The
historical search used crowded top bands to trigger larger windows and then
wider edit neighborhoods; the new exhaustive benchmark exposes failures of
that trigger.
The [best-only PDF](output/pdf/family1-m8-active-best/active-best.pdf) and
[TikZ picture](output/pdf/family1-m8-active-best/graph-01.tex) display the current
working leader, estimated at 49 from a verified length-50 pair.

The updated [1--20 PDF atlas](output/pdf/family1-atlas/family1-atlas-1-20.pdf)
groups the 20 certified rooted winners through seven states into 13 underlying
graphs, marking every optimal starting vertex. All edges are unlabelled and
drawn alike. At size eight it shows the one current candidate, with working
estimate 49 and verified pair length 50. The separate rigorous bound `F(8)>=35`
comes from another graph. Sizes nine through twenty show `H>=34` examples. See the
[current grouped presentation data](results/family1-grouped-atlas/README.md),
[all consecutive-size predecessors](results/family1-ancestry-through7/README.md),
and [rooted edit distances](results/family1-edit-distance-through7/README.md).
The [edit definition](docs/family1-graph-edits.md) keeps the root fixed and
separates graph distance from the change in merge length.

The [root-aware edit search](docs/family1-neighbor-search.md) expands winners
and possible near-winners through size 20, ranks certified hard-root support,
and queries every accessible root of each selected shape. Generation budgets
are explicit; they do not give global pruning certificates. `Family1Threshold`
tests one chosen equal length and preserves `unknown` without adding a bound.
The original Windows exact/threshold validation passed in Debug and Release,
including 170 independent threshold decisions over all 64 classes through
three states. Test registration depends on build options, Python/uv and the
optional regenerated evaluation journal; use ctest -N for the configured
suite, as described in the artifact policy.
See also the [edit-priority limits](docs/family1-edit-priority.md) and
[circulant construction comparison](docs/family1-circulant-comparison.md).

The native [edit-based candidate finder](docs/FAMILY1_EDIT_CANDIDATES.md)
generates bounded edit neighborhoods, retains every accessible root, and feeds
the calibrated hard-pair scorer. Its benchmark expands all previous near-top
classes: at seven states, parent-strata priority retains all eight known
maximizers within about 2,048 candidate roots for each of three seeds. Verified
short words then reduce those pools to 161--163 unresolved candidates, including
all eight winners. These are measured shortlists, not global certificates;
all negative cases, ties and unresolved graphs remain exported.

The reusable [hard-pair finder](docs/hard-pair-finder.md) works with arbitrary
finite families of binary DFAs, including different coordinate sizes and roots.
It records complete common-window gain distributions, retains multiple suffix
candidates, and invokes exact conditional tail search near completion. Its
Family 1 adapter uses all static masks in the objective and independently
replays every accepted pair. The updated blind benchmark finds pairs for all
24 test graphs, but neither a sampling miss nor a shortest conditional suffix
certifies the graph's global merge length.

The [seven-state lookahead calibration](results/family1-finder-calibration/README.md)
now independently reconstructs minimum-length 34 pairs for all eight maximizing
classes, using larger windows and broader prefix coverage. Controlled tests
through k=16 show that increasing k alone does not solve every case. The report
preserves complete configurations, timing limits, failures, and every verified
pair; it uses the previously certified H=34 as its target length.

`Family1GlobalCheck.exe` searches the whole accessible graph space for
stronger graphs and exports replayable exclusion certificates only after
UNSAT. An `unknown` result supplies no global bound. The larger candidate
atlas and `Family1Explore.exe` do not meet this completion criterion.

The five-state results include five rooted classes but four underlying shapes:
the former (a) and (c) have the same graph with different roots. The current
atlas combines them and marks both starting vertices. The independent
[five-state audit](docs/family1-rooted-isomorphism.md) verifies their exact
scores and all TikZ edges; the original rooted sources remain available.

`Family1Search.exe` enumerates rooted accessible seed graphs, identifies them
under root-preserving relabeling and independent port swaps, and scores each
seed using all static XOR masks. It retains **every** class tied for each
maximum. Exact, depth-capped, and incomplete scores are kept distinct.

After the Release build below:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Search.exe --out .\out\family1-new-run --min-m 1 --max-m 6 --depth 24 --dot
```

The supported seed sizes are `1..6`. Results include all evaluated graphs,
all maximizing graphs, witnesses, coverage summaries, and optional Graphviz
drawings. Add `--resume` with the same size range to continue an existing run;
depth and memory budgets may be increased. See [the search documentation](docs/family1-search.md)
for the mathematics, export schema, bounds, tests, and complete reproduction
commands. The generating-function executables remain available independently.

`Family1Exhaustive.exe` extends complete graph-class traversal through seven
states using reusable, verified collision witnesses and exact packed scoring.
It retains interval bounds for unresolved graphs, supports deterministic resume
and stronger refinement passes, and exports all tied classes only after both
the maximum and complete collection are certified. The independent
`Family1ExhaustiveVerify.exe` checks every graph, rooted canonical form and
upper witness; `Family1LayerVerify.exe` supplies complete-mask lower checks.
See [the seven-state workflow](docs/family1-seven-state-search.md) for commands,
the independent Burnside count and complete proof. The optional
[GPU witness workflow](docs/family1-gpu-witness-search.md) accelerates proposals;
all accepted witnesses and final lower proofs are independently checked by
native C++ verifiers. The certificate can be replayed without a GPU.

`Family1Explore.exe` supports graphs through **20 states**, using exact discovery
canonicalization, sampled-mask lower bounds, SAT counterexample refinement, and
parallel scoring. Graph generation is heuristic; it retains every evaluated
class and every best exact/lower-bound tie without claiming a global maximum.

```powershell
.\out\build\msvc-vcpkg\Release\Family1Explore.exe --out out\family1-explore-new --min-m 7 --max-m 20 --candidates 16 --jobs 4 --dot
```

See [scaling to twenty states](docs/family1-scaling.md) for the algorithm,
certification limits, measured results, and independent certificate replay.

## Build

The project uses CMake and requires a C++23 compiler, Boost Dynamic Bitset,
FLINT, and Z3. The Windows build uses native MSVC and the pinned vcpkg manifest.

### Windows: MSVC + vcpkg

Prerequisites:

- Visual Studio 2022 / Build Tools 2022 version 17.13 or newer, with the C++
  workload, Windows SDK, and C++ CMake tools for Windows
- CMake 3.28 or newer, either on PATH or bundled with Visual Studio
- Git

From PowerShell:

```powershell
Set-Location C:\path\to\AutomataAnalysis
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows-vcpkg.ps1
```

`-ExecutionPolicy RemoteSigned` applies only to this PowerShell process. The script
finds CMake on PATH or through Visual Studio's `vswhere`, uses an existing
`VCPKG_ROOT` or clones vcpkg into `.deps/vcpkg`, installs the manifest
dependencies, and builds the `msvc-vcpkg` Debug configuration. Visual Studio's
bundled vcpkg is replaced with the local checkout unless supplied explicitly
with `-VcpkgRoot`.

To build Release, append `-Configuration Release` to the command. To use a
separate vcpkg checkout, append `-VcpkgRoot C:\path\to\vcpkg`.

The manifest pins the vcpkg registry revision. A local [MPFR overlay](vcpkg-overlays/mpfr/README.md)
checks GMP limb width at compile time and supplies the matching Debug or Release
DLL path to the remaining configure probes. It preserves validation and requires
no changes to Windows code integrity or other protection settings.

Run the console example from the repository directory:

```powershell
.\out\build\msvc-vcpkg\Debug\ProductAutomata.exe
```

The build also produces `MatM.exe` in the same directory. Release executables
are under `out\build\msvc-vcpkg\Release`.

To build manually with an existing vcpkg installation:

```powershell
$env:VCPKG_ROOT = "C:\path\to\vcpkg"
cmake --preset msvc-vcpkg
cmake --build --preset msvc-vcpkg-debug
```

In the configured VS Code workspace, **Ctrl+Shift+B** builds Debug. Choose
**Build AutomataAnalysis (Release)** from **Tasks: Run Build Task** for Release.
Select **ProductAutomata (Windows Debug)** or **MatM (Windows Debug)** in
**Run and Debug**, then press **F5** to build and debug the console example.

Microsoft's C/C++ and CMake Tools extensions provide debugging and IntelliSense.
For CMake Tools, select `msvc-vcpkg` with **CMake: Select Configure Preset**, then
select the Debug or Release build preset. The local workspace settings supply
the bundled CMake path and `VCPKG_ROOT`; these machine-specific `.vscode` files
are ignored by Git. In a fresh workspace, set those paths for your installation
or use the PowerShell build command above.

### Linux / WSL

Install FLINT and GMP using your system package manager, or build them locally in
one of the paths searched by `FindFLINT.cmake` and `FindGMP.cmake`. Then run:

```bash
cmake -S . -B out/build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build out/build/debug
```
