# Eight-state upper-witness refinement

All 16 rooted classes in the two selected pilot shapes were retained. Every final witness was independently replayed with straightforward scalar state loops on all 256 static masks, in addition to native replay and the general scorer's exact bitset check. Native result/checkpoint hashes and configuration bindings were checked.

The final verified upper bounds range from 38 to 51. These graphs retain their supplied graph-specific lower bound 1. This run proves no new lower bound, exact score or global optimum. A longer heuristic upper witness is not evidence that a graph is harder. The separate projection construction supplies a size-wide incumbent lower bound, not a lower bound for every selected root.

| Shape | Rooted canonical key | Verified upper bound |
|---|---|---:|
| A | 00010203040504060507020603070001 | 44 |
| A | 01020003010404050607020300050607 | 42 |
| A | 01020003030405060107000705060204 | 38 |
| A | 01020003040500040607020301050607 | 41 |
| A | 01020003040502060107040500070306 | 45 |
| A | 01020102030405060507000603070004 | 44 |
| A | 01020304030504060105020600070007 | 39 |
| A | 01020304050600010207030705060004 | 42 |
| B | 00010203010403040506000702070506 | 43 |
| B | 00010203040504060203010706070005 | 46 |
| B | 01020003000403050506040701020607 | 42 |
| B | 01020003020304050106060704050007 | 47 |
| B | 01020003020401050506040706070003 | 39 |
| B | 01020003040501060003020705060407 | 51 |
| B | 01020003040502030006060704050107 | 49 |
| B | 01020304030501020006050604070007 | 43 |

Shape labels identify the complete eight-root blocks from the frozen pilot plan. `records.jsonl` contains every transition table, best witness, interval and proof reference. `independent-scalar-audit.json` records all 4096 mask replays and complete endpoint-state hashes.

The blind main pass used coarse caps 96, 64 and 48 followed by dynamic upper-minus-one queries and a cap-34 screen. It ran 112 native invocations: 49 completed and 63 time-capped. Coarse settings were k=6, beam 16 and 1024 prefix attempts/pairs. Heavy settings were k=16, beam 16, 65536 attempts/pairs, depth 21, 2²¹ words per layer, exact distance checks on all 256 coordinates, common-prefix strata through 8, remaining-count ranking and 50000 expansions per seed. Each heavy invocation had a 30-second cap. Misses and timeouts preserved existing bounds.

A separate best-of-seeds pass ran 16 invocations with 8192 attempts/pairs and k=6. Frequent native checkpoints preserved already verified witnesses when eight invocations reached their 20-second cap. Those checkpoint witnesses were checked against their hashed native configurations and independently replayed; no completed-run claim was substituted for a timeout.

The subsequently authorized warm-start experiment explicitly used the known seven-state winner word pairs, separate from the blind benchmark. Of 25,984 distinct prefix/common-prefix variants screened across the roots, 25,977 had a complete single-DFA pair obstruction. Seven viable variants remained; six bounded native queries ran without improving the uppers. This only assesses those warm starts and supplies no graph lower bound.

Useful targets for an independent lower-certificate calculation are the root with upper 38 and the shape-B root with upper 39. A collision-free layer at 37 or 38, respectively, would match those uppers. These are narrow certificate targets, not a ranking of global hardness. All other roots remain unresolved.

Reproduce the blind main pass in a fresh directory:

```powershell
uv run --no-project python scripts/family1_refine_candidate_uppers.py --out out/m8-upper-refinement-repeat --jobs 4
```

Add `--resume` with the same sources/settings to verify and reuse completed attempts. `complete-raw-evidence.zip` preserves all three used drivers, snapshots, native invocations, configurations, results and checkpoint evidence. `manifest.json` pins the publication files.
