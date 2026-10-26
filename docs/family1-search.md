# Exact Family 1 graph search

`Family1Search` searches each rooted graph separately and exports every rooted
isomorphism class attaining a certified maximum. The existing `ProductAutomata`
and `MatM` generating-function experiments remain separate executables.

## Mathematical definition

A seed has vertices `0,...,m-1`, root `0`, and successor ports `tau0[s]` and
`tau1[s]`. Loops, coincident ports, arbitrary indegrees, and graphs that are not
strongly connected are allowed. For every fixed mask `sigma` in `{0,1}^m`,

```text
delta_sigma(s,x) = tau[x XOR sigma[s]][s].
```

The mask belongs to the vertex and stays fixed on every revisit. Starting from
the root, the product state of a word is its endpoint vector over all masks.
`H(G)` is the smallest positive length at which two distinct words of that same
length have equal endpoint vectors. Equality with a word at a different length
does not count.

Vertices unreachable from the root can be removed without changing `H(G)`:
no word visits them, and their mask bits only duplicate coordinates of the
endpoint vector. This justifies restricting enumeration to rooted accessible
graphs. It does not justify imposing strong connectivity or an indegree bound.

An **exact size** result for `m` concerns graphs with exactly `m` reachable
vertices. A **size budget** of `1,...,m` takes the maximum over those separate
seed searches. It never combines different graphs or sizes into one product.
Use `--min-m m --max-m m` for one exact size and `--min-m 1 --max-m m` for a
cumulative size budget. Other selected ranges are labeled as selected ranges
in the summary.

## Enumeration and graph identity

Each row is stored as an unordered successor pair, including repeated entries.
Sorting a row removes the independent swap of its two outgoing ports. Such a
swap permutes the static-mask coordinates and therefore preserves every word
collision.

The enumerator uses restricted-growth discovery labels. Root `0` is initially
known; scanning rows and then their two sorted destinations, the first unseen
vertex must receive the smallest unused label. A source row must already have
been discovered. Every accessible graph admits such a labeling. Moreover, its
lexicographically smallest rooted transition table has this property: if the
first unseen destination skipped a smaller unused label, swapping those labels
would decrease the table at its first differing entry. Thus this reduction
does not discard any rooted class.

The remaining duplicates are removed by an exact canonicalization test over
every vertex permutation fixing `0`. Each candidate relabels both sources and
destinations, sorts each successor pair, and compares the complete table
lexicographically. The least table is the canonical representative. No hash is
used to identify graph classes.

Canonical tables are visited in deterministic lexicographic order. Each record
contains a zero-based ordinal within its exact size and a table key containing
the two destinations of each row. The graph identifier is the size together
with this key.

## Exact scoring and bounds

The product backend encodes the complete endpoint vector over all `2^m` masks
as three 64-bit planes. A bit position identifies one fixed mask; the three
bits at that position encode its endpoint. This is a lossless representation
for the supported sizes, including loops and coincident ports. It does not
replace state equality with fingerprint equality.

Scoring expands words by increasing length. Every length uses a fresh collision
table. Before the first collision, each previous word has a distinct product
state, so its layer index also gives its lexicographic word index. This recovers
both witness words directly. Hashes locate candidate matches; complete planes
are compared before a collision is accepted.

The record statuses have the following meanings:

| Status | Meaning |
|---|---|
| `exact` | A witness pair was found at length `merge_length`, and every smaller positive length was collision-free. |
| `depth-capped` | Every layer through the requested depth completed without a collision. `merge_length` and `witness` are null. |
| `incomplete` | A resource limit, allocation failure, or interruption prevented completion. `reason` identifies the cause. |

`lower_bound` always means `H(G) >= lower_bound`. Completing depth `d` without
a collision certifies `H(G) >= d+1`. A partially completed layer does not improve
this bound. Finding a collision in that layer can still certify its exact
length when all smaller layers completed.

The current exact backend supports `1 <= m <= 6`, depths `0,...,31`, and a
positive layer-state budget up to `2^31`. Unsupported values are rejected.
The default depth is `30`; the default layer budget is `16777216` (`2^24`).
Memory and runtime grow exponentially in the collision depth. A larger depth
option alone does not guarantee that the resource budget can finish that
depth. Depth `0` certifies only the initial bound `H(G) >= 1`.

## Windows build and validation

From the repository root, use the existing native MSVC/vcpkg build script:

```powershell
Set-Location C:\Users\chenxu\Projects\SWP\AutomataAnalysis
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows-vcpkg.ps1 -Configuration Debug
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows-vcpkg.ps1 -Configuration Release
```

The script finds CMake on `PATH` or through Visual Studio's `vswhere`, and uses
the existing vcpkg manifest and project-local dependency overlay. It also builds
the legacy generating-function executables.

Run the registered regression checks in both configurations:

```powershell
ctest --test-dir .\out\build\msvc-vcpkg -C Debug --output-on-failure
ctest --test-dir .\out\build\msvc-vcpkg -C Release --output-on-failure
```

If CMake/CTest are absent from `PATH`, use the binaries from the Visual Studio
CMake installation reported by the build script; `ctest.exe` is beside
`cmake.exe`. For a Visual Studio 2022 installation with the C++ CMake tools:

```powershell
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vsInstall = & $vswhere -latest -products '*' -version '[17.0,18.0)' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$cmakeBin = Join-Path $vsInstall 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin'
& (Join-Path $cmakeBin 'ctest.exe') --test-dir .\out\build\msvc-vcpkg -C Release --output-on-failure
```

## Reproduce a complete search

Use a new, empty output directory. The following requests all exact sizes
through six, with a depth sufficient for the previously reported maxima:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Search.exe --out .\out\family1-m1-m6 --min-m 1 --max-m 6 --depth 24 --dot
Get-Content .\out\family1-m1-m6\summary.json
```

For only six reachable vertices:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Search.exe --out .\out\family1-m6 --min-m 6 --max-m 6 --depth 24 --dot
```

A small resumable run and continuation:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Search.exe --out .\out\family1-resume --min-m 1 --max-m 6 --depth 12 --limit-graphs 100
.\out\build\msvc-vcpkg\Release\Family1Search.exe --out .\out\family1-resume --min-m 1 --max-m 6 --depth 24 --resume --dot
```

`--limit-graphs N` stops after the requested number of newly recorded scoring
results in that invocation. It supplies a reproducible stopping point, not an
exhaustiveness certificate. `--max-layer-states N` changes the resource budget.

Resume requires the same size range, schema, enumeration method, and product
method recorded in `run.json`. Depth and layer budgets may change. Exact records
are reused; unresolved records are rescored when needed, and an earlier stronger
lower bound is preserved. A graph score restarts from the root; individual word
layers are not checkpointed. Enumeration is replayed deterministically to check
the stored ordinals and identify remaining graphs.

`checkpoint.jsonl` appends a newline-terminated record after each scoring
result. Later records for the same graph are revisions, not additional graph
classes. A final unterminated fragment from an interrupted write is discarded
on resume. Other invalid or incompatible checkpoint records cause an error.
The journal is flushed after each record; it is not a transactional database.

## Export files and exhaustive claims

| File | Contents |
|---|---|
| `run.json` | Run schema, methods, and selected size range. |
| `checkpoint.jsonl` | Append-only score history, including revisions on resume. |
| `graphs.jsonl` | Latest record for every evaluated canonical graph. |
| `summary.json` | Per-size and selected-range coverage, statuses, best exact scores, and certification flags. |
| `maximizers.jsonl` | Every class tied for the certified maximum at each fully enumerated and fully scored size. |
| `best_exact.jsonl` | Every evaluated class tied for the best exact score at its size, including uncertified searches. |
| `cumulative_maximizers.jsonl` | Every global tie over the selected sizes, only when the whole selected range is certified. |
| `dot/` | With `--dot`, Graphviz files for certified per-size maximizers, containing both port edges and the root marker. |

Every graph record includes its canonical table, size, ordinal, status,
exact length or null, certified lower bound, witness pair or null, reason,
and scoring limits. These tables are suitable for later drawings and structural
analysis. JSONL exports have deterministic size/key ordering.
Exports are regenerated at a normal stop, including a handled interrupt; after
a forced termination, resume regenerates them from the journal. Do not run two
processes against the same output directory. The `dot/` directory accumulates
previously exported drawings; `maximizers.jsonl` is the authoritative current
collection.

`enumeration_complete` records whether traversal finished for that exact size.
`scoring_complete` requires exact scores for all recorded graphs. A maximum is
certified only when both conditions hold and at least one graph was evaluated.
Unresolved graphs prevent a global maximum claim, even if the best exact score
matches a previously known value. Every tie is retained; different rooted graph
classes are never collapsed into one maximizing example.

Graphviz is optional. To render one exported graph after installing it, pass
its `.dot` filename to `dot -Tsvg INPUT.dot -o OUTPUT.svg`.

## Results and validation

The separate read-only [reference computation](https://github.com/chen1088/Analytic-Methods-for-Transition-Monoid/tree/main/family1_computation)
reports the following [complete results](https://github.com/chen1088/Analytic-Methods-for-Transition-Monoid/blob/main/family1_computation/reproduced_fixed_m1_m6.json).
The completed local run reproduced these counts, scores, and all ties.
The implementation here was integrated into this C++ project; no dissertation
source or reference-computation file is modified.

| Reachable states | Rooted accessible classes | Maximum merge length | Maximizing classes |
|---|---:|---:|---:|
| 1 | 1 | 1 | 1 |
| 2 | 6 | 3 | 1 |
| 3 | 57 | 6 | 2 |
| 4 | 678 | 10 | 1 |
| 5 | 10,398 | 15 | 5 |
| 6 | 192,181 | 23 | 2 |

On 2026-10-25, the native Release search evaluated all **203,321** classes
through six vertices with exact scores: no capped or incomplete records.
All **12** per-size maximizing classes, including both six-vertex classes,
are saved in [the result snapshot](../results/family1-m1-m6/README.md), with
canonical tables, witnesses, score distributions, Graphviz files, source hashes,
and a validation manifest. The complete 48 MB evaluated-graph export and its
resume journal are in `out/family1-m1-m6/`; generated run files and logs are
ignored by Git. The small result snapshot is retained with the source.

The following checks passed with MSVC 19.44.35229.0 and the existing vcpkg setup:

- Debug and Release builds; both registered CTest tests in each configuration.
- Independently enumerated all ordered labeled tables through `m=4` and matched
  the complete rooted class sets: `1,6,57,678`.
- Independently scored every class through `m=3` using per-word, per-mask direct
  simulation. All exact lengths, full class sets, and maximum ties matched.
- Independently simulated **all 203,321 saved witness pairs** over every static
  mask, using ordinary integer states rather than the bitplane backend.
- Static masks on revisits, loops, coincident ports, all 64 masks at `m=6`,
  equal-length semantics, root and port equivalence, forced hash collisions,
  enumeration ordering and termination, bounds, resource failure, interruption,
  and unreachable-state removal.
- Stop/resume, increased depth and memory budgets, final partial checkpoint
  recovery, incompatible-config rejection, and DOT exports in Debug and Release.
  Resuming the completed full run also reproduced every result.
- Legacy mask bounds, sink transitions, retained merged words, and shared
  prefixes. `ProductAutomata` and `MatM` exited successfully in both builds.

Reproduce the independent checks after the search:

```powershell
uv run --no-project python tests\family1_reference.py --max-m 3 --compare out\family1-m1-m6\graphs.jsonl --maximizers out\family1-m1-m6\maximizers.jsonl
uv run --no-project python tests\family1_verify_run.py out\family1-m1-m6 --all-witnesses
uv run --no-project python tests\family1_cli_test.py --exe out\build\msvc-vcpkg\Release\Family1Search.exe
uv run --no-project python tests\family1_cli_test.py --exe out\build\msvc-vcpkg\Debug\Family1Search.exe
```

These scripts use only the Python standard library; an available `python` can
replace `uv run --no-project python`. Witness verification proves that the saved
words collide; independent verification of *minimality* was performed through
`m=3`. For `m=4,...,6`, minimality follows from the tested exact C++ layer search,
and the complete output also matches the separate reference results. A full
Debug search through six and Linux/WSL builds were not run. Sizes above six and
depths above 31 are unsupported rather than silently approximated.

The legacy reset family deliberately keeps its historical size convention:
`BackToFirstDFA(s)` has `s` mask-controlled vertices **plus** sink `s`. Since
both sink ports coincide, its mask bit is redundant and sink transitions bypass
mask indexing. The new finite `Family1Graph` has exactly `m` total vertices and
does not inherit that extra sink convention.
