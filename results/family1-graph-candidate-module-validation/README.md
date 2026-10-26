# General candidate scorer validation

The native edit generator produced a capped radius-1 pool from the rooted three-state seed `000101020001`: four ordinary shapes and all 12 rooted classes. The general scorer queried length cap 5 using the same settings for every class. It made 14 native invocations, independently replayed every positive witness on all eight static masks, eliminated 10 classes and retained two unresolved classes. A full resume rerun passed all integrity checks.

Only after generation and scoring finished, a separate straightforward exhaustive word/product-state implementation computed the exact scores of these 12 graphs. All 10 excluded graphs had H<6; the two survivors both had H=6. There were no false exclusions. One returned witness has length 5 for a graph with H=4, illustrating why a heuristic upper witness does not establish the shortest merge length.

This validates the finite pipeline on the recorded pool. The native candidate budget was reached; this is not exhaustive neighborhood or global graph coverage. Survival alone supplied no lower bound. The cutoff 6 was an explicit retrospective, size-wide query setting and was never supplied as each graph's score.

`cases.jsonl` retains every graph, exact audit score, observed interval and verified witness. `validation.json` pins the generator, scorer, test and raw-run metadata. Raw native evidence and source/executable snapshots are under `out/family1-candidate-module-pilot/`.

The final focused suite passed 10/10 tests with both Release and Debug executables, including contradictory redundant exact-interval fields. The pilot was repeated in `scored-m3-winner-v2` under the final source pin; the first run and its source snapshot remain unchanged.

```powershell
uv run --no-project python tests/family1_graph_candidate_search_test.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

Reproduce the pool in a fresh directory:

```powershell
out/build/msvc-vcpkg/Release/Family1Edit.exe --graph 000101020001 --target-m 3 --radius 1 --max-paths 24 --max-candidates 4 --root-closure --out out/candidate-validation-repeat/edit
uv run --no-project python scripts/family1_graph_candidate_search.py --candidates out/candidate-validation-repeat/edit/candidates.jsonl --out out/candidate-validation-repeat/scored --incumbent-lower 6 --jobs 2 --enable-stage2 --stage1-samples 8 --stage1-prefix-pairs 8 --stage1-prefix-depth 4 --stage1-prefix-words 16 --prefix-samples-per-depth 16 --stage1-timeout 5 --stage2-samples 16 --stage2-prefix-pairs 16 --stage2-prefix-depth 4 --stage2-prefix-words 16 --stage2-expansions 500 --stage2-timeout 5
```

Add `--resume` to the scorer command to verify and reuse completed attempts. See `docs/FAMILY1_GRAPH_CANDIDATE_SEARCH.md` for the general API, proof boundaries, memory planning and output schema.
