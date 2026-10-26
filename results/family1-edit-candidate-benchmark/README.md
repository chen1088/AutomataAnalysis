# Edit-candidate generation benchmark

All known maximizing rooted graph classes through seven states occur in the complete radius-one neighborhoods of the previous-size score-gap-at-most-two parent pools after accessible root closure. This is a measured finite-size coverage fact, not a theorem for later state sizes or a global search certificate.

Generation uses all previous-size winners, or separately every previous-size graph within2 of that size's exact maximum. The complete target-size truth is loaded only after candidate files and random baselines are sealed. The generator receives graph keys, radius, seed and resource budgets; it receives no current-size scores or word pairs.

| Target m | Previous near-top parents | Root-fixed candidates | After all accessible roots | Direct winning classes | Winning classes after roots | Matched random classes / winner hits | Complete unit neighborhood |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 2 | 1 | 2 | 2 | 1/1 | 1/1 | 3 / 1 | yes |
| 3 | 6 | 33 | 42 | 1/2 | 2/2 | 43 / 2 | yes |
| 4 | 25 | 276 | 364 | 1/1 | 1/1 | 365 / 0 | yes |
| 5 | 48 | 1065 | 1915 | 5/5 | 5/5 | 1917 / 2 | yes |
| 6 | 139 | 5066 | 11693 | 2/2 | 2/2 | 11694 / 0 | yes |
| 7 | 69 | 3581 | 13329 | 8/8 | 8/8 | 13334 / 0 | yes |

The one-state base case has one graph and H=1; there is no zero-state predecessor. Each extra complete-growth run uses radius1, seed1088,8192 direct-candidate slots and20000 accepted-path slots. All six actually exhaust their neighborhoods with no cap. Rerooted classes are retained explicitly; rerooting is not a free rooted edit and receives no false rooted-distance bound.

The budgeted grid contains216 runs: exact sizes2–7; winner versus gap≤2 parents; radii1,2,3; seeds1088,2027,65537; strict rooted versus accessible-root closure. Each uses10000 accepted-path slots and2048 direct rooted endpoint slots. Six extra complete-growth runs bring the native total to222; there are895 reported prefix/base-case observations. Candidate caps apply before root closure; final output counts can therefore exceed2048. All full outputs are retained.

At nominal budgets32,128,512,2048, prefixes retain the entire final ordinary-shape/root block. The matched random prefix receives at least the actual edit prefix count and also retains its whole final block; its extra candidates are recorded. Random sampling uses independent uniformly drawn labelled two-port tables, rejecting inaccessible graphs and deduplicating rooted classes. It is not uniform sampling of graph isomorphism classes, and these seed comparisons support no global confidence certificate.

Seven-state results at nominal2048 (ranges over the three fixed seeds; complete-growth extra runs excluded):

| Parents | Radius | Root closure | Actual candidates | Maximizing rooted hits /8 | Winning ordinary shapes /4 | Random maximizing rooted hits |
|---|---:|:---:|---:|---:|---:|---:|
| winners | 1 | no | 123 | 1 | 3 | 0 |
| winners | 1 | yes | 391 | 3 | 3 | 0 |
| winners | 2 | no | 2048 | 1 | 3 | 0 |
| winners | 2 | yes | 2050–2053 | 3 | 3 | 0 |
| winners | 3 | no | 2048 | 1–3 | 3–4 | 0 |
| winners | 3 | yes | 2050–2054 | 3 | 3 | 0 |
| near2 | 1 | no | 2048 | 5–6 | 4 | 0 |
| near2 | 1 | yes | 2051–2053 | 0 | 0 | 0 |
| near2 | 2 | no | 2048 | 1–3 | 3–4 | 0 |
| near2 | 2 | yes | 2050–2052 | 0 | 0 | 0 |
| near2 | 3 | no | 2048 | 0–3 | 2–4 | 0 |
| near2 | 3 | yes | 2048–2051 | 0 | 0 | 0 |

Ordering matters: the complete near-top/root-closed seven-state pool contains all eight maximizers, but its original first approximately2048 rows contain none. The strict rooted radius-one stream finds5–6 of8 within2048. Increasing radius under a fixed budget can also reduce recall because it allocates work to additional layers. These negative outcomes are retained; the benchmark does not select the best seed or a single parent after inspecting target truth.

`observations.jsonl` and `observations.csv` retain all budget outcomes, ordinary-shape coverage, coverage of every maximizing root per shape, and near-top recall/exact-score histograms where the complete exact journal is available (m≤6). `generation-seal.json` pins all candidate/path/source files, native parent/pattern/depth coverage, duplicate counters, timings, cap flags and random draw statistics. `independent-audit.json` compares the entire direct target set of each of the six complete-growth runs with independent Python unit-neighborhood enumeration of all288 supplied parent classes. It separately replays256 selected radius-three paths (616 primitive steps) at m4–7 and checks accessible-root closure of all4467 generated ordinary shapes in those full-growth runs. It does not enumerate edit neighborhoods of those4467 generated shapes.

The independent CLI suite passed4/4 in both MSVC Release and Debug. It checks all64 rooted classes of sizes1–3 against complete Python unit neighborhoods, factorial canonicalization, loops/coincident occurrences, nonstrongly connected roots, primitive operation replay, termination, caps, deterministic resume/hash integrity, and the intermediate-size20 representation limit.

Reproduce generation and analysis (existing Windows/MSVC setup):

```powershell
uv run --no-project python tests/family1_edit_candidate_cli_test.py --exe out/build/msvc-vcpkg/Release/Family1Edit.exe
uv run --no-project python tests/family1_edit_candidate_benchmark.py --exe out/build/msvc-vcpkg/Release/Family1Edit.exe
uv run --no-project python tests/family1_edit_candidate_analysis.py
```
