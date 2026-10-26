# Truth-free ranking validation

Both structural and parent-stratified ordering were run on the same sealed complete-growth seven-state pool: 13,329 rooted classes in 1,926 ordinary shapes. Every row and root class was retained, whole shape blocks stayed contiguous, and output/resume checks passed. No child-score truth was loaded for these ranking runs.

Parent strata used explicitly supplied six-state lower certificates at levels 23, 22 and 21. The features preserve accessible vertex multiplicities separately from rooted-class counts. Candidate scores, upper bounds and saved words were not inputs to the ordering. The ranking introduces no graph filter, score certificate or additional enumeration coverage claim.

The focused suite passed 9/9 tests, including independent scalar feature checks on all 64 rooted classes through 3 states, deliberately altered child-score labels, non-strongly-connected graphs, coincident ports, whole-block/tie preservation, automorphic root metadata and corrupted-output rejection.

`validation.json` pins source, tests and both full-pool outputs. Raw evidence is in `out/family1-rank-validation/`. Same-pool winner-recall assessment is a separate benchmark and must load child truth only after sealing the rankings.

```powershell
uv run --no-project python tests/family1_rank_edit_candidates_test.py
```

Usage and the Python API are documented in `docs/FAMILY1_CANDIDATE_RANKING.md`.
