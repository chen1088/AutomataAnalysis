# Radius-three expansion at eight states

The crowded-band trigger had five candidates after lookahead 16 at edit radius two. This bounded expansion used all 55 certified previous-size parent classes, radius three, seed 65537, at most 16,000 accepted paths and 4,096 direct target endpoints. Root closure produced 25,471 rooted classes in 3,250 ordinary shapes. The candidate cap was reached; this is not an exhaustive radius-three ball or a global search certificate.

Parent-strata ranking used previous-size information only. Selecting whole ordinary-shape blocks absent from both earlier radius-one and radius-two pools gave 261 roots in 33 new shapes. All 261 selected graphs happen to have indegree two; the generator permits arbitrary indegree. All selected shapes have three-edit source paths, with 34 two-edge insertions, 31 loop insertions, 24 two-edge smoothings, 8 loop smoothings and 2 retargets across the 33 linked paths. Rerooting is recorded separately and has no rooted edit-distance cost claim.

Each selected graph completed the same finite k=8, beam=16, 1,024-prefix-seed refinement with common-prefix depth 8, 256 coordinate viability/distance checks, 100,000 expansions per seed, tail threshold 8, 20-second per-query budget, best-of-seeds and checkpoints every 16 seeds. All 261 returned independently verified equal-length word pairs over all 256 static masks. They qualify alongside the prior 50 graphs, giving 311 qualified classes. All 45,004 accumulated classes, including unselected and unknown graphs, remain archived.

The historical R3 screening result had two length-51 upper-bound ties. Subsequent word refinement is separate: the current active estimate is published in `results/family1-m8-estimates`. A verified finder pair is an upper bound, and the user's L-1 estimate and [L-2,L] band remain heuristic. Misses never increase a lower bound. No exact eight-state maximum is claimed.

Independent audit replayed every one of the 10,047 generated rooted paths (19,076 primitive edits), checked all selected shapes were new and whole, revalidated all 261 observations, and tested read-only resume using the original pinned producer. Resume launched zero backend processes, left 1,044 native artifacts unchanged, and reproduced identical qualified records and active ties after JSON normalization. Concurrent observation arrival order is compared as a multiset.

The first bootstrap caller passed JSON lists where the Python graph adapter required tuples; native results had already committed. The final controller canonicalizes graph metadata and reused those intact results with native resume. The reported 20.922-second controller invocation was this adoption/validation pass, not the full fresh study runtime.

Resume from the repository root using the historical executables (the current Release producer is newer and is deliberately rejected by the hash guard):

```powershell
uv run --no-project python scripts/family1_adaptive_edit_search.py --generation out/family1-m8-r3-instant-generated --score-exe out/family1-m8-adaptive-edit-r3/native-used/Family1Sample.exe --edit-exe out/family1-m8-adaptive-edit-r3/native-used/Family1Edit.exe --resume
uv run --no-project python tests/family1_adaptive_edit_audit.py
```

For a fresh bounded run with the same frozen inputs, use a new `--out` directory, the two pinned executables, and omit `--resume`. Omitting `--generation` regenerates the same specified parent/edit pool. Sources, inputs, generation paths, executables, dependencies, observations, checkpoints and native results are preserved in the content-addressed raw evidence ZIP; `raw-inventory.json` maps each original path to its object hash. The original 311-class qualified export is retained here separately from later refinements.
