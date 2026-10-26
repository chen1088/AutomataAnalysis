# Bounded graph-candidate search

`scripts/family1_graph_candidate_search.py` scores arbitrary supplied graphs with 1–20 reachable states using the native hard-pair finder. It does not load a catalogue of winners, known merge lengths or saved words. The public `run_attempt()` and `score_graph()` functions can also be imported by a benchmark.

For a maximization search, use elimination mode. Given a separately justified incumbent lower bound L, the finder searches for an equal-length collision of length at most L−1. A verified hit certifies H(G)<L and excludes that graph. A miss or timeout leaves the graph unresolved. A long heuristic witness is only an upper bound and is not evidence that H(G) is large.

```powershell
out/build/msvc-vcpkg/Release/Family1Edit.exe --graph 000101020001 --target-m 4 --radius 2 --max-paths 1000 --max-candidates 32 --seed 1088 --root-closure --out out/candidates-m4
uv run --no-project python scripts/family1_graph_candidate_search.py --candidates out/candidates-m4/candidates.jsonl --out out/scored-m4 --incumbent-lower 10 --jobs 4
```

For sizes 8–20, `--incumbent-lower 34` requests cap 33. This option chooses a query; it does not import 34 as a lower bound for each candidate. Supply certified graph-specific intervals separately using repeatable `--bounds FILE` options. Their original proof metadata is preserved and attributed; the runner does not regenerate those mathematical proofs. Imported intervals never control the scorer's seed list or stage schedule.

Every accessible root of every supplied ordinary shape is materialized. Roots that cannot reach the entire graph are accounted for separately. The first appearance of each shape in the input preserves native generation priority. `--max-shapes N` selects whole shapes and leaves every unselected class exported as pending. Rerooting is recorded separately from the root-fixed edit path; its distance is not silently treated as free. Native `path_ids`, path files, root metadata and all supplied parent links are retained.

The default first stage uses k=6, beam width 16, 1024 prefix attempts/pairs, depth 16, at most 65536 words per layer, 10000 expansions per prefix and a 60-second native invocation cap. Stage 2 is opt-in:

```powershell
uv run --no-project python scripts/family1_graph_candidate_search.py --candidates out/candidates-m4/candidates.jsonl --out out/scored-m4-portfolio --incumbent-lower 10 --enable-stage2 --stage2-timeout 180 --memory-mib 512 --jobs 4
```

Stage 2 uses k=16, beam width 16, remaining-count ranking, common-prefix strata through 8, complete single-DFA distance bounds and configurable prefix/expansion budgets. Prefix words are reduced according to an explicit per-worker memory estimate, including the number of distinct permutation realizations and full-family beam states. A stage whose pair-state estimate already exceeds that budget is recorded as resource-capped and unresolved. The estimate is not an operating-system memory limit. Actual budgets are written into the materialized plan.

For general upper-witness experiments, omit `--incumbent-lower` and select, for example, `--length-caps 34,64,96 --target-upper 34`. The target is only a stopping goal. Stage 2 runs only after stage 1 fails to verify that goal. All positive results are independently replayed over every static mask using Python arbitrary-precision bitsets and complete endpoint-vector equality.

The output contains:

- `plan.json`: every shape/root, selection order, original path links and actual stage budgets.
- `records.jsonl`: all imported and candidate graph intervals, provenance and witnesses.
- `observations.jsonl`: every completed native invocation, miss, timeout or resource skip.
- `top-lower-bound-ties.jsonl`: every graph attaining the best supplied/certified lower bound at its size.
- `unresolved-or-competitive.jsonl`: every graph whose certified upper bound does not exclude a tie or improvement.
- `eliminated-by-upper-certificate.jsonl` and `survivors-unresolved-or-tied.jsonl`: the additional elimination-mode partition.
- `summary.json`: coverage and proof scope. It never asserts exhaustive graph enumeration or a global maximum.

All ties and unresolved challengers are retained. Finite-record maximum flags refer only to the explicitly materialized records and require sufficient interval certificates. An exact score can arise only by combining a valid supplied lower bound with a matching verified upper certificate, or by importing an exact certificate.

Resume uses the same command plus `--resume`. Inputs, source files, executable/DLLs, settings and plan bytes must match. Raw evidence and source/native snapshots are preserved. Each resumed observation is reconstructed from its hashed native JSON, checked against the native configuration, and positive witnesses are independently replayed again. Changing budgets or rebuilding dependencies requires a fresh run directory.

```powershell
uv run --no-project python tests/family1_graph_candidate_search_test.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

The focused suite checks independent scalar agreement for all 64 rooted classes through 3 states, exact 20-state replay, XOR permutation counting, all-root multiplicities, native-priority preservation, closure caching, every lower-bound tie, timeout/resource semantics and corrupted journal/plan rejection.
