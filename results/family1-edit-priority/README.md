# Edit priority validation

`validation.json` records the mathematical checks and pinned inputs behind
[the edit-neighborhood analysis](../../docs/family1-edit-priority.md).

- All eight certified seven-state maximizers have an accessible one-retarget
  neighbor with exact score one; twelve full neighbor operations are retained.
- A binary-tree construction proves that no universal constant bounds score
  changes under one retargeting. Instances through 64 vertices were checked.
- The general two-retarget construction to a score-one graph was checked on
  every rooted class through size three and all eight seven-state winners.
- Previous near-maximizing parent coverage and winning-root profiles are
  extracted from the complete certified small-case results.
- All 13 loop-chain extensions at exact sizes 8–20 are accessible from every
  root. Their projection-root fibers contain respectively 2–14 distinct rooted
  classes with certified lower bound 34, for 104 exported classes in total.

`root-lift-candidates.jsonl` is a candidate input, not a complete search journal
or a maximizer collection. Each graph is rooted canonical, has its own static
mask projection certificate, and is marked incomplete with unknown exact
score and upper bound. All 128 base masks were checked against the projection
identity at every state for both symbols. This supplies rigorous lower bounds
without searching the larger graphs' product layers.

The export includes every root mapping to the certified base root. The other
six roots of each extension remain unscored candidates and are not excluded.
No global coverage or optimality is claimed for sizes greater than seven.
