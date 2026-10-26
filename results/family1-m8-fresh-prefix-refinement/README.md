# Fresh eight-state prefix refinement

The first four ordinary-shape blocks of the fresh ranked radius-1 pool supplied all 32 rooted classes. Two explicitly selected projection roots were added as certified-baseline anchors. Every graph was retained. Previously verified upper witnesses for the eight overlapping roots were reused; the older 16-root results were not changed.

In 143 seconds, 34 best-of-seeds queries completed and improved 24 upper bounds. A further 23 prioritized heavy queries reached their 20-second caps without improvement. Every final witness passed independent scalar simulation over all 256 static masks, for 8704 graph/mask checks in total.

The projection-anchor results are:

| Rooted canonical key | Supplied lower | New verified upper |
|---|---:|---:|
| 01020002030403040506000705070206 | 34 | 52 |
| 01020002030403040506010705070206 | 34 | 50 |

The first anchor's separately completed depth-34 layer report establishes lower bound 35. That proof is deliberately not attributed to the sampler or inserted into these frozen input-derived rows; the final publisher merges it with its pinned certificate manifest. These remain individual intervals, not a certified global maximum.

The best-of pass used k=6, beam width 16, 1024 prefix attempts/pairs, explicit full-family distance checks, common-prefix strata and frequent checkpoints. Heavy priority was the two projection anchors, followed by previously unrefined fresh roots in sealed ranking order. It used k=16, 65536 attempts/pairs, depth 20, at most 2²⁰ prefix words per layer and 50000 expansions per seed. No known merge length or saved word was supplied as a finder seed. Verified current upper lengths were used to request shorter collisions.

`records.jsonl` is the compact publisher/TikZ input and preserves all transition tables, intervals, witnesses and evidence references. `independent-scalar-audit.json` records all final scalar checks. `raw-evidence.zip` preserves the used driver, native commands, configurations, results and intact positive checkpoints. Its CRC was checked. The 23 timeout outcomes supply no lower bound, and larger heuristic upper witnesses are not evidence of greater hardness.
