# Offline Family 1 executable

For four-symbol `00,01,10,11` lookahead, use the
[joint word-pair finder](family1-joint.md). The word-finder mode documented
here selects distinct prefixes and then explores common suffixes (`00,11`);
its k-step windows have `2^k` leaves. Verified pairs remain valid upper bounds,
but this restricted mode does not implement the joint greedy window.

`Family1Offline.exe` searches one exact reachable size `m` in `1..20`. It has
exact and heuristic modes and writes machine-readable findings. The Windows
release is compiled with the static MSVC runtime: copy the executable and its
documentation to another Windows x64 machine and run it without Python,
vcpkg, a GPU or an internet connection. No repository datasets are required
at runtime. Outputs go to the directory supplied with `--out`.

The runner now uses deterministic search throughout: canonical graph-edit
ordering, complete lexicographic prefix layers within the word budget, and
lexicographic suffix ties. It performs no shuffled traversal, random prefix
sampling, or seeded tie ranking. `--deterministic` explicitly records the same
default behavior. Legacy `--seed` and `--prefix-samples` arguments remain
accepted for command compatibility and do not affect search choices.

For reproducible fixed-work experiments, use `--per-graph-ms 0` and
`--wall-seconds 0`, with explicit word, pair, expansion and memory budgets.
Time-limited runs can still stop at different work positions on different
machines. Deterministic word search remains bounded and does not by itself
prove that its best pair is shortest.

If the candidate set is defined as every graph within edit distance at most
`d` of specified parents, complete that entire neighborhood and test every
member. Require `neighborhood_generation_complete: true`, no generation cap,
and `pending_graphs: 0` before describing that experiment as complete. A
generation cap or unfinished scoring leaves an incomplete experiment; a
finder miss leaves an unresolved graph. Moving the root is recorded separately
from primitive rooted edits.

## Quick start

Extract the release ZIP, open PowerShell in that directory, and run:

```powershell
.\Family1Offline.exe --help
.\Family1Offline.exe --m 4 --heuristics off --depth 16 --max-layer-states 65536 --out exact-m4
.\Family1Offline.exe --m 8 --heuristics on --radius 1 --max-candidates 32 --max-graphs 32 --window 8 --max-window 12 --prefix-pairs 128 --per-graph-ms 2000 --out heuristic-m8
```

The first search enumerates all rooted accessible four-state classes and
scores them exactly, subject to its explicit resource limits. The second is
a bounded heuristic experiment. A large size with heuristics disabled can
require an impractical amount of time; use explicit caps when experimenting.

`--m` means exactly `m` reachable vertices. To examine the cumulative size
budget `1..m`, run each size independently and compare their certified scores
or bounds. The executable does not combine several seed graphs into a product.

For a bounded heuristic sweep through every size:

```powershell
1..20 | ForEach-Object {
    .\Family1Offline.exe --m $_ --heuristics on --max-graphs 16 --max-candidates 16 --max-paths 256 --wall-seconds 60 --out "runs\m$_"
    if ($LASTEXITCODE -ne 0) { throw "Search invocation failed at m=$_" }
}
```

Each directory is a separate experiment. These small illustrative budgets do
not certify maxima, and a size can remain without a found pair. To carry every
tied best graph from size eight into a new size-nine neighborhood:

```powershell
$searchArgs = @('--m', '9', '--heuristics', 'on', '--radius', '2', '--out', 'runs\m9-from-m8')
Get-Content runs\m8\best.jsonl | ForEach-Object {
    $finding = $_ | ConvertFrom-Json
    $searchArgs += @('--parent', $finding.key)
}
.\Family1Offline.exe @searchArgs
```

Supplying parents overrides the default parent catalogue. Considering only
prior winners is a heuristic restriction; additional near-top or unresolved
parents can be passed with further `--parent` options. The journal retains
them so later search choices need not rely solely on the best-only view.

## Modes and controls

Option values are separated by spaces. Run `--help` for the authoritative
defaults and accepted range checks.

| Control | Meaning |
|---|---|
| `--m M` | Exact reachable seed size, from 1 through 20. |
| `--heuristics off` | Enumerate rooted classes and use exact per-length scoring; no graph heuristic filtering. |
| `--heuristics on` | Generate a bounded edit neighborhood and use the native word finder. |
| `--out DIR` | New result directory; use `--resume` to reuse a compatible existing run. |
| `--graph KEY` | Evaluate a supplied graph instead of claiming whole-space enumeration; repeat for several graphs. |
| `--parent KEY` | Explicit graph-only edit parent; repeat to retain several parents. |
| `--depth D` | Exact-mode scoring depth, currently 0 through 31. |
| `--exact-depth D` | Initial exact check in heuristic mode; zero skips it and exercises the word finder directly. |
| `--max-layer-states N` | Bound exact layer words; reaching it leaves a lower bound, not an exact score. |
| `--memory-mib N` | Planned memory budget for exact arrays and heuristic working storage; not a process-wide OS limit. |
| `--per-graph-ms N` | Per-graph time budget; see the timing scope below. |
| `--wall-seconds N` | Overall soft stopping budget; zero disables it. |
| `--max-graphs N` | New graph evaluations per invocation; zero disables the count limit. A compatible resume can evaluate the next batch. |
| `--deterministic` | Canonical edits, complete prefix layers and lexical ties; enabled by default. |
| `--seed N` | Legacy configuration field; ignored by deterministic search. |
| `--radius R` | Primitive graph edit radius, from 1 through 3. |
| `--max-paths N` | Accepted edit-path budget. |
| `--max-candidates N` | Distinct direct rooted endpoint budget before all-accessible-root expansion. |
| `--window K` | Initial common-suffix lookahead length. |
| `--max-window K` | Maximum lookahead during crowded-band refinement. |
| `--beam N` | Number of retained suffix alternatives. |
| `--prefix-depth N` | Prefix-generation depth. |
| `--prefix-words N` | Maximum completely enumerated words per prefix layer. |
| `--prefix-pairs N` | Maximum retained prefix-pair trials. |
| `--prefix-samples N` | Legacy configuration field; random sampling is disabled. |
| `--common-prefix-depth N` | Retain diverse actual common-prefix strata, from 0 through 8. |
| `--tail-threshold N` | Start bounded exact suffix search once few masks remain unmerged. |
| `--tail-states N`, `--tail-depth N` | Exact conditional suffix BFS state and depth budgets. |
| `--viability-coordinates N` | Check a bounded set of residual coordinates for a proved inability to merge. |
| `--distance-coordinates N` | Use single-coordinate shortest suffix distances as an admissible remaining-length bound. |
| `--expansions N` | Requested minimum window expansion quota per prefix-pair trial; automatically raised for the chosen window and beam. Effective quota is recorded. |
| `--max-length N` | Maximum total word-pair length sought. |
| `--target-upper L` | Stop a graph after a verified pair of length at most L; zero disables. This excludes H>L without claiming a shortest pair. |
| `--crowding N`, `--band-width N` | Refine when sufficiently many estimated leaders lie in the top band. |
| `--window-reports N` | Retain the latest N compact drop-distribution reports per graph; zero disables retention. |
| `--dot` | Export graph drawings as unlabelled Graphviz source. |
| `--resume` | Check and recover compatible saved findings. |

The runner does not download anything. Default seed tables are compiled into
the executable and contain graph transitions only. Exact mode ignores this
catalogue and enumerates the actual graph universe unless `--graph` is given.
The heuristic bootstrap, scoring metric and limitations are explained in
[the method document](family1-heuristic-method.md).

Graph keys encode the two destinations of every row in order, with each
destination written as two decimal digits. Thus `00010001` represents
`[[0,1],[0,1]]`. Each key has `4*m` characters. The root is vertex zero;
graphs are canonicalized under root-preserving relabeling and port swaps.

## Findings and evidence

The result directory contains these files:

| File | Content |
|---|---|
| `run.json` | Immutable effective configuration and executable SHA256. |
| `checkpoint.journal` | Hash-chained graph checkpoints and every shorter verified positive. |
| `records.jsonl` | Current row for every observed graph; includes pending rows in a generated pool. |
| `best.jsonl` | Every rooted class tied at the current best exact score or heuristic estimate. |
| `summary.json` | Enumeration/scoring coverage, caps, counts and certification flags. |
| `dot/` | Optional unlabelled Graphviz sources for all current best ties. |

Each evaluated graph retains its canonical table, witness when found, and
certified bounds. Heuristic estimates are separate from these bounds. Every
distinct rooted class tied at the current best score or estimate is retained.
Pending or unresolved classes must be consulted when interpreting that list.

When testing whether a complete neighborhood contains a graph with `H>50`,
`--target-upper 50` gives a deterministic certificate-based stopping rule for
each graph. Every graph still receives its scheduled test. A verified pair of
length at most 50 rules that graph out; larger pairs and misses remain
unresolved and can receive a stronger pass. This threshold mode is an
exclusion screen, so its best-only export is not a shortest-pair ranking.

An exact score belongs to one graph. A global maximum additionally requires
complete graph enumeration and sufficient scoring bounds for every graph.
Depth-capped, memory-capped, time-capped and heuristic runs must not be read
as global optimality certificates. `--graph` evaluates only supplied graphs.
All-positive witness replay checks the complete static-mask family.

Increasing a graph's word-search effort can shorten its witness and demote
it from the estimated top tier. A missed pair cannot promote a certified lower
bound. Keep the full journal when comparing runs; the best-only export is a
convenient view, not a replacement for coverage information.

The record fields `merge_length`, `lower_bound` and `upper_bound` are certified
only to the extent stated by the score status. `estimated_merge_length` and
`estimated_band` are separate heuristic fields. `finished` means that the
configured attempt ended; it does not imply an exact score. A no-hit graph has
no numerical estimate. The upper witness is independently replayed over all
`2^m` static masks.

`window_distributions` retains compact reports from returned finder calls.
They include the initial disagreement, window length, leaf count, completion
flag, drop statistics and a histogram with at most 64 bins. A bin width of one
is an exact histogram; coarser bins are explicitly marked. No complete ranked
list of `2^k` windows is exported. `window_reports_truncated` counts omitted
reports. Deadline-aborted calls may leave partial work absent from counters;
the record describes that counter scope explicitly.

For a compatible continuation, repeat exactly the original arguments and add
`--resume`. `--max-graphs` counts new evaluations in this invocation, allowing
a second batch to extend an earlier capped run. Canonical enumeration restarts
and skips finished journal entries. Changed semantic settings or a different
executable require a new output directory. Resume checks the complete journal
hash chain and every saved witness before reusing it; a corrupt or partial
journal is rejected rather than silently trusted.

Exit code zero means the bounded invocation completed; inspect the summary to
learn whether a maximum was certified. Interrupted runs return 130. Invalid
arguments, incompatible resumes and integrity failures return 2.

Time and memory controls are cooperative algorithm budgets. A graph's exact
scorer checks its deadline internally. Prefix preparation, edit-neighborhood
generation, canonicalization, a bounded window/tail call and complete witness
replay may finish their current unit before the next clock check. Memory
estimates exclude some allocator/runtime overhead. These flags do not impose
an operating-system-wide hard limit.

## Historical eight-state word-finder benchmark

This command supplies only the graph, with no saved word pair or score hint:

```powershell
.\Family1Offline.exe --m 8 --heuristics on --graph 01020003040501060003020705060407 --exact-depth 0 --window 8 --max-window 8 --beam 16 --prefix-depth 18 --prefix-words 262144 --prefix-pairs 1024 --prefix-samples 32768 --max-length 80 --per-graph-ms 10000 --memory-mib 512 --out m8-word-benchmark
```

The earlier packaged version found a verified length-50 pair in about 7.34 seconds on
the development machine. The estimate is 49, not a certificate. Slower machines
may need a larger `--per-graph-ms` budget. The method document records the
seven-state benchmark as well, including the cases where the short run missed
the actual shortest pair.

That benchmark used the earlier seeded search. The current deterministic
runner uses a different prefix and tie order, so its returned lengths and
timings must be measured separately.

## Build and package

On a development machine with Visual Studio 2022 C++ Build Tools and CMake,
run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-family1-offline.ps1 -Configuration Release -Package
```

The dedicated `FAMILY1_OFFLINE_ONLY` CMake option skips the generating-function
and symbolic-solver dependency configuration. It requires no vcpkg install.
The existing default project build continues to produce its previous tools.
Release binaries and ZIPs live under ignored `out/`; they are distributed as
build artifacts rather than committed to the source repository.

The integration test command is:

```powershell
uv run --no-project python tests/family1_offline_cli_test.py --exe out/build/family1-offline/Release/Family1Offline.exe
```

Python is used only by this independent development test, not by the executable
or by its offline users. The test independently enumerates small graph classes,
checks shortest equal-length collisions, verifies saved witnesses and exercises
resource limits and resumption.

The generic exact backend currently supports depth through 31. A larger
`--m` is still accepted, but this depth ceiling can prevent certification of
its shortest merge length. In particular, this runner does not replace the
specialized seven-state depth-33 global-certificate replay tools. Never read
a capped large-size exact run as an exact maximum.
