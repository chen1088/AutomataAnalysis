# Candidate ordering without child-score labels

`scripts/family1_rank_edit_candidates.py` reorders a sealed candidate pool before scoring. Every input row, rooted class and provenance field is retained. Rows belonging to the same ordinary graph shape remain in one contiguous block. The ranker computes no merge lengths and reads no candidate merge length, upper bound, lower bound or witness when choosing priority.

```powershell
uv run --no-project python scripts/family1_rank_edit_candidates.py --candidates out/candidates-m8/candidates.jsonl --parents results/family1-m7/maximizers.jsonl --strategy parent-strata --seed 1088 --out out/candidates-m8-ranked
uv run --no-project python scripts/family1_graph_candidate_search.py --candidates out/candidates-m8-ranked/candidates.jsonl --out out/candidates-m8-scored --incumbent-lower 34 --max-shapes 2
```

`--paths` defaults to `paths.jsonl` beside the candidate file when present. `--parents` is repeatable. The default strategy is `parent-strata` when parent files are supplied, otherwise `structural`.

The three strategies are:

- `discovery`: first appearance of each shape in the supplied file, preserving input order inside each shape. Native files already organized into contiguous shape blocks keep their original order. The raw `discovery_index` is preserved but does not replace native selection order.
- `structural`: descending number of accessible vertex roots with distinct outgoing ports, descending number of accessible vertex roots, ascending sum of absolute indegree deviations from 2, then a deterministic seeded SHA-256 tie-break.
- `parent-strata`: round-robin across distinct supplied parent lower-certificate levels, visiting higher levels first in each round. Shapes within each level follow structural order. Only path-linked parents with exactly one fewer state contribute a score level. A shape linked to multiple levels is emitted once. Missing previous-size certificates form an additional unresolved-parent stratum.

All root counts include vertex multiplicity; the number of distinct rooted isomorphism classes is reported separately. Loops, coincident ports, non-strongly-connected graphs and unrestricted indegrees are retained. These features define a heuristic priority, not a pruning theorem or evidence of a large shortest merge length.

Native source and endpoint tables are checked against canonical keys. Direct path IDs and root-closure metadata must identify the actual candidate graph. Nonzero automorphic roots may legitimately preserve the same rooted canonical class. Supplied parent intervals are validated for contradictions, but their mathematical certificates are attributed to the input source rather than regenerated.

Output includes all reordered `candidates.jsonl` rows, one `features.jsonl` record per shape, `summary.json`, and a source/output hash manifest. `selection_index` is replaced; `original_selection_index`, the previous selection index and input position are retained. The complete original path file and its checksum are copied beside the ranked candidates so the scorer can resolve the same path IDs. Original generation metadata and parent files are preserved in `inputs-used/`.

`--resume` checks identical inputs, code, seed, strategy, output bytes and checksums. It does not silently rerank an altered pool. To compare ranking recall, seal all ranking outputs before loading child-score truth, then compare whole-shape prefixes of the same original pool. Record raw native ordering as a separate baseline.

The pure Python API is:

```python
ranked_rows, shape_features, summary = rank_rows(
    candidate_rows, native_path_rows, certified_parent_rows,
    strategy="parent-strata", seed=1088,
)
```

Focused verification:

```powershell
uv run --no-project python tests/family1_rank_edit_candidates_test.py
```

The tests check all 64 rooted classes through 3 states against scalar root/degree calculations, candidate-label invariance, every-row retention, deterministic whole-shape blocks, non-strongly-connected and coincident-port cases, previous-size parent strata, automorphic roots, contradictory parent certificates and resume corruption guards.
