# Ordering the same sealed edit pools

All666 ranked runs preserve every candidate from the222 original pools. Candidate scores and saved words are not ranker inputs. All ranked files were sealed before target-truth evaluation; the2,664 prefix observations include all sizes, seeds, radii, source pools and negative outcomes.

The three fixed strategies are: discovery (first appearance of each whole shape block), structural (more accessible roots with distinct outgoing targets, then more accessible roots, then indegree nearer2, with seeded SHA-256 tie-breaking), and parent-strata (round-robin over certified previous-parent lower-score levels, structurally ordered within each). These are priorities, not filters or upper bounds. Nonstrongly connected and unbalanced graphs remain in every input pool.

Seven-state winner counts at nominal2048, ranges over all three predefined seeds, on the SAME respective budgeted pools:

| Parents | Radius | Accessible-root closure | Discovery | Structural | Parent strata |
|---|---:|:---:|---:|---:|---:|
| winners | 1 | no | 1 | 1 | 1 |
| winners | 1 | yes | 3 | 3 | 3 |
| winners | 2 | no | 1 | 1 | 1 |
| winners | 2 | yes | 3 | 3 | 3 |
| winners | 3 | no | 1–3 | 1–3 | 1–3 |
| winners | 3 | yes | 3 | 3–8 | 3–8 |
| near2 | 1 | no | 5–6 | 5–6 | 5–6 |
| near2 | 1 | yes | 0 | 7–8 | 8 |
| near2 | 2 | no | 1–3 | 1–3 | 1–3 |
| near2 | 2 | yes | 0 | 7–8 | 7–8 |
| near2 | 3 | no | 0–3 | 0–3 | 0–3 |
| near2 | 3 | yes | 0 | 6–8 | 6–8 |

Thus the budgeted near-top/radius1/root-closed pool plus parent-strata priority recovers all8 maximizers within approximately2048 candidates for EACH fixed seed. This is a measured positive case, not a proof of recall on future graphs. Whole-shape blocks cause small count overshoots; actual counts appear in every record.

The exhaustive13,329-class near-top/radius1/root-closed pool is a retained negative case. With this larger fixed input set, winner counts at nominal32/128/512/2048 are:

| Strategy | 32 | 128 | 512 | 2048 |
|---|---:|---:|---:|---:|
| discovery | 0 | 0 | 0 | 0 |
| structural | 0 | 0 | 2 | 3 |
| parent-strata | 1 | 1 | 2 | 3 |

A larger candidate pool can dilute a fixed ranking budget. Neither heuristic places all8 maximizers among the first2048 of the complete pool; both place3 there. Ranking cannot recover a graph absent from a generated pool, and no result here excludes better graphs outside an edit neighborhood.

The complete13,329-class pool was already scored uniformly at cap33. Where every ranked prefix key belongs to that scored pool, the same verified observations are reused without new queries. The main positive configuration at nominal2048 gives:

| Seed | Actual scored roots | Winner recall | Certified weaker | Unresolved survivors | Unresolved nonwinners |
|---:|---:|---:|---:|---:|---:|
| 1088 | 2051 | 8/8 | 1890 | 161 | 153 |
| 2027 | 2050 | 8/8 | 1887 | 163 | 155 |
| 65537 | 2048 | 8/8 | 1886 | 162 | 154 |

Every true winner survives valid cutoff elimination. Remaining survivors are unresolved, not certified optimal. `scoring-overlap.jsonl` explicitly identifies prefixes lacking full score coverage instead of silently treating unscored candidates as misses or survivors.

`ranking-seal.json` pins every original candidate/path/parent source, ranker snapshot, ranked file and feature file. `observations.jsonl`/`.csv` retain complete recall and exact small-case score distributions. Every strategy keeps the identical candidate class multiset; accessible-root groups remain whole. The ranker neither computes H nor uses candidate truth, upper bounds or witnesses.

```powershell
uv run --no-project python tests/family1_edit_ranked_candidate_benchmark.py
uv run --no-project python tests/family1_edit_ranked_analysis.py
```
