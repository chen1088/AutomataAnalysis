# Complete seven-state edit-pool elimination

The complete radius-one near-top/all-roots pool has 13,329 classes and contains all eight certified maximizers. Applying the same cheap cap33 query to EVERY class certifies 12,691 weaker graphs and leaves 638 unresolved: all eight maximizers plus 630 known nonwinners. No maximizer is eliminated.

This eliminates 95.27% of known nonwinners. Retrospective survivor precision is 8/638 (1.254%). The 630 extra survivors are bounded-search misses, not graphs certified to attain34.

Generation was sealed before child truth was loaded. It uses all69 previous-size parents with certified H in21–23, performs complete radius-one routing growth and retains every accessible root:3581 direct rooted classes become13329 after root closure. Root0 remains fixed along actual edit paths; rerooting is separately labeled. The generator never receives current-size scores or saved word pairs.

Every graph is queried at the common retrospective cutoffF_7−1=33. The scorer receives graph metadata and this common cutoff only; no per-graph H, winner label or saved word is supplied. Settings: k6, beam4,128 samples/prefix pairs, prefix depth16/65536 words,10000 expansions, tail threshold8, one stage. Verified upper≤33 certifies weakness. A miss supplies no new lower bound. All accepted words are independently replayed against all128 static masks using the helper's separate exact bitset implementation.

All 13,329 native observations completed without timeout/error. 579 prior matching queries were checksum/config-validated and reused. Summed recorded invocation time is 540.659s, including reused observations; new invocations account for 510.475s. Four workers were used. These totals are sums of per-invocation measurements, not an elapsed wall-time claim.

`scores.jsonl` preserves every native observation, independently verified witness and provenance. `survivors.jsonl` exports all638 unresolved graph classes without target-truth labels so they can be reused as candidates. `observations.jsonl` contains the full-pool confusion counts; `query-plan.json` pins helper/executable settings and the generation seal. The source pool's complete neighborhood is a tiny subset of the4,166,855-class seven-state universe; this experiment supplies no global exclusion theorem for future sizes.

```powershell
uv run --no-project python tests/family1_edit_elimination_benchmark.py --complete-size7-only --reuse-work-dir out/family1-edit-elimination-benchmark --out results/family1-edit-elimination-complete-m7 --work-dir out/family1-edit-elimination-complete-m7
uv run --no-project python tests/family1_edit_candidate_analysis.py --scores results/family1-edit-elimination-complete-m7
```
