# New eight-state radius-two shapes

Generated23,736 rooted classes under a bounded radius-two search from all55 supplied seven-state parent classes. Parent-strata priority selected2,053 roots in257 whole ordinary shapes absent from the complete radius-one pool. Every selected graph is unbalanced; all generated graphs and21,683 unselected classes remain exported.

Of the2,053 selected classes,2,039 have independently verified upper bounds and14 remain unresolved. The cap64?40 scorer produced1,069 upper bounds at most40 and970 above40. Among these,107 upper bounds are at most34. Upper bounds do not prove that a graph is strong or maximizing. No lower bound above1 is inferred for edited graphs.

Generation uses seed2027, radius2,16000 path slots,4096 direct rooted endpoint slots and accessible-root closure. The native search was candidate-capped and is not an exhaustive radius-two ball. The selected classes are first in the fixed parent-strata order among shapes missing from radius1; no current-size score controls generation or selection. All unbalanced/nonstrongly-connected classes remain admissible.

Scoring uses k6, beam4,128 samples/prefix pairs, prefix depth16/65536 words,10000 expansions,10s per query and4 workers. It first asks for a pair of length at most64, then at most40 only if the first observation remains above40 or unknown. There are3,938 observations; every accepted pair is independently replayed over all256 static masks. All selected graphs received queries. Elapsed invocation time was158.795s.

All290 linked source edit paths were independently reconstructed:580 unit steps, including290 retargets,158 loop insertions and132 two-edge insertions. Root closure is recorded separately and does not imply that every rerooted class has a rooted distance-two path. Every selected shape was independently checked absent from radius1 and no selected root block was truncated.

`records.jsonl.gz` contains every generated graph, canonical table, status, bound/witness and generation provenance. `observations.jsonl.gz` retains every scoring observation and native result hash. `generation-paths.jsonl.gz` retains full source/raw/canonical transition tables and operations; `generated-candidates.jsonl.gz` preserves original generation metadata. `plan.json` and `run.json` pin inputs, native executables and exact source snapshots, retained under the raw output directory. `independent-audit.json` records the scope of additional checks.

This finite candidate search supplies no global maximum or exclusion certificate at eight states. The separate lower-bound proof runner is not part of this experiment.

```powershell
uv run --no-project python scripts/family1_m8_radius2_search.py --out out/family1-m8-r2-search-repeat
```
