# Eight-state search results

This is the sealed initial search and lower-certificate archive. The current
[active best-only estimates](../family1-m8-estimates/best-candidates.jsonl) and
[adaptive word/edit workflow](../../docs/FAMILY1_ADAPTIVE_CANDIDATES.md) include
later improvements; this archive keeps its original intervals and evidence.

The best certified lower bound in this run is **35**. One graph is currently
certified to attain at least that value, with **35 <= H(G) <= 52**. Its exact
shortest merge length and the absolute eight-state maximum remain unresolved.

The graph has key `01020002030403040506000705070206`, root 0, and rows
`(1,2),(0,2),(3,4),(3,4),(5,6),(0,7),(5,7),(2,6)`.

See the [paper figure](../../output/pdf/family1-m8-search/candidate.pdf),
[graph-only TikZ](../../output/pdf/family1-m8-search/snippet-candidate.tex),
[search/proof documentation](../../docs/FAMILY1_M8_SEARCH.md), and
[native validation](../family1-m8-validation/validation.json).

The independent length-34 injectivity certificate accounts for all 2^34
binary words, comparing full 256-mask vectors on every fingerprint match.
It took 354.211 seconds. A separately scalar-verified length-52 pair gives
the upper bound. The proof is independent of the graph's seven-state parent.
`lower-certificate.zip` preserves the exact program, checker, commands, report,
logs and executable snapshots, with their original pinned paths recorded.

## Coverage

- **26,924** distinct observed rooted classes exported, including unselected
  generated classes.
- **13,327** distinct rooted graphs evaluated, across **43,835** recorded native
  word queries.
- Complete local radius-one growth: **11,266** rooted classes, **1,424** shapes,
  from all 55 retained seven-state frontier parents.
- Additional bounded radius-two pool: **23,736** classes, with **2,053** roots in
  257 new unbalanced shapes selected and evaluated. The generation hit its
  candidate budget; it is not a complete radius-two neighborhood.
- **103,453,575** classes exist in the full accessible rooted eight-state
  universe. Global enumeration and a global exclusion certificate are absent.

The combined records have **25,795** remaining possible maximizers relative to
the current certified value 35. These include unselected and unresolved classes;
their survival is not a lower bound. The observed corpus is not the complete
universe. All classes and every possible tie are retained.

## Exports

- `records.jsonl.gz`: every observed rooted canonical table, interval, witness,
  exact/bounded/incomplete status and evidence references.
- `best-certified-lower.jsonl` and its compressed copy: all ties for the best
  certified lower bound, explicitly distinct from proven maximizers.
- `potential-maximizers.jsonl.gz`, `unresolved-challengers.jsonl.gz`: complete
  retained lists within the observed corpus.
- `observations.jsonl.gz`: every included word-query observation, including
  timeouts and misses.
- `generation-*.jsonl.gz`, `extra-generation-0-*.jsonl.gz`: every candidate and
  primitive edit path from both generation runs, including unselected graphs.
- `summary.json`, `inputs.json`, `manifest.json`: counts, scope and SHA-256 pins.
- `path-audit.json`, `reproduction-audit.json`: independent replay of all 10,655
  paths/12,646 primitive edits and byte-identical reproduction of ten exports.

No sampled miss increases a lower bound. Finite upper bounds are independently
replayed over all static masks during publication. Repeated fingerprints in the
exact layer checker receive complete state comparison. The statuses do not
claim a depth-capped or incomplete computation is an exact score.

Run `powershell -NoProfile -ExecutionPolicy RemoteSigned -File
results/family1-m8-search/reproduce.ps1 -Out out/my-m8-publication` to repeat the
merge and evidence audit from the preserved raw runs. Fresh generation, scoring
and the independent proof commands are in the linked documentation. Input and
binary hashes guard resumptions; use fresh directories for changed experiments.
