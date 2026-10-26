# Adaptive Family 1 candidate search, final bounded run

The final active heuristic tier contains **one rooted graph**, `01020003040501060003020705060407`, with an independently verified word-pair length **L=50**. Under the requested heuristic its point estimate is **49**, with rough band **[48,50]**. That band is not a certified interval for H. Five qualified graphs still lie within two of the active length after k=16 and broad-prefix fallback; the plateau remains unresolved.

All 311 qualified classes, their minimum verified upper witnesses, and their existing lower bounds remain in `records.jsonl`. `active-best.jsonl` retains every active tie. The complete radius-3 archive retains 45,004 rooted classes; 44,693 coarse or unqualified classes remain pending. Its pinned path and SHA256 are in `summary.json`; the outer edit publication already packages that archive. Better graphs may remain pending or outside the generated neighborhoods. No global maximum is claimed.

The primary projection anchor `01020002030403040506000705070206` now has independently certified lower bound 35 and a verified upper witness of length 46. Its lower proof is published separately by the parent task. The active heuristic leader has a longer upper witness; that fact alone does not prove a larger H.

The adaptive controller first admits explicitly refined records. Crowding of at least three graphs within two of the best length raises the exact-full-family window objective through k=8,10,12,16. It preserves all eligible graphs when recomputing the active tier. Eight conspicuous coarse candidates were admitted only after completed standard refinements: their old first-hit lengths 89–91 dropped to 42–50. Radius 3 then added 261 qualified classes. All hits and checkpoint pairs were replayed over all 256 static masks; the final packaging audit independently rechecked every final witness with scalar transitions and complete bitset vectors (79,616 graph/mask checks).

Default strong stages use seed 1088, beam 16, 1,024 prefix attempts/pairs, depth 16, common-prefix diversity 8, and 20 seconds per query. The per-prefix expansion budget is at least max(100000, 4*(2^(k+1)-2)*beam), scaled further if the complete conservative suffix budget requires it. The final broad fallback used k16, 8,388,480 expansions per prefix, 65,536 prefix attempts/pairs, complete prefix depth 21 with up to 2^21 words per layer, a nominal 1,024 MiB working estimate, and 30 seconds per query. All five final fallback calls timed out without a shorter committed witness. A working-memory estimate is not an OS-enforced memory limit. Window-block counters count leaves, not full rounds; only an explicit expansion-limit flag certifies node-budget truncation.

## Calibration and evidence limits

The graph-only m7 calibration loaded known H=34 labels only after sealing queries and never used saved witness strings as hints. The standard baseline returned 34,34,34,35,36,36,38,38. After bounded broad-prefix work the saved lengths were **34,34,34,34,34,35,36,38**. The rough band covers the known score for 7/8 classes; one gap of four remains. Thus the L-1 rule and rarity assumption remain heuristics, not a reliable error guarantee. All eight graph classes remain archived even when the active proxy tier has fewer ties.

Old runs used a producer that persisted improvements every 16 prefixes. A later expensive prefix could time out before a newly found pair was committed. Root fixed this with immediate atomic checkpoints for each independently verified shorter pair, retaining periodic saves. All old positive certificates remain valid; old timeouts mean no shorter committed certificate was recovered, not that no pair was internally found. Final R3 refinement and final broad fallback used the fixed producer. `phase-summary.json` distinguishes versions, and `raw-artifact-pins.jsonl` pins raw attempt/config/checkpoint/source/executable files without duplicating large native binaries. Final Release and Debug each passed all 34 CTests; the controller's dedicated suite passed all eight tests in both configurations.

Core m8 refinement used 58 native queries; broad m8 passes and continuation used 11 more, separate from the 261 outer-radius qualification calls. M7 calibration used 31 queries including its baseline. Stopping was due to explicit finite budgets and the maximum configured k. Misses and high agreement create no lower bounds.

## Reproduction

From the repository root, use fresh output directories for a new executable/source version. Inputs, native hashes and exact settings are pinned in each copied phase `run.json` and in the raw-artifact manifest. Existing completed runs can be resumed only with the matching producer/configuration.

```powershell
uv run --no-project python scripts/family1_adaptive_candidate_search.py --records out/family1-m8-adaptive-edit-r3/archive-records.jsonl.gz --refined-records out/family1-m8-adaptive-edit-r3/qualified-records.jsonl --out out/my-adaptive-run --start-window 10 --jobs 12 --query-seconds 20 --wall-seconds 240 --max-queries 64
uv run --no-project python scripts/family1_broad_prefix_refinement.py --records out/my-adaptive-run/records.jsonl --out out/my-broad-run
uv run --no-project python tests/family1_adaptive_candidate_search_test.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

`sources/` preserves the controller, general scorer, broad fallback and calibration/test drivers used for this package. `calibration-m7-records.jsonl` and its report retain the final calibration witnesses and retrospective gaps. The original final 311-record source is immutable, SHA256 `fea2859e148ae4a118b8d1a1c75f4727f4624853be1c474967a1ef814fe06e88`.
