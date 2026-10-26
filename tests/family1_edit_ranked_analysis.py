#!/usr/bin/env python3
"""Publish every ranked recall comparison and reuse already verified scores."""
from __future__ import annotations
import argparse
from pathlib import Path
import family1_edit_candidate_benchmark as generation

REPO = generation.REPO


def range_text(values):
    return str(min(values)) if min(values) == max(values) else f"{min(values)}–{max(values)}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=REPO / "results/family1-edit-ranked-candidate-benchmark")
    parser.add_argument("--scores", type=Path, default=REPO / "results/family1-edit-elimination-complete-m7/scores.jsonl")
    args = parser.parse_args()
    rows = list(generation.json_rows(args.folder / "observations.jsonl"))
    seal = generation.read(args.folder / "ranking-seal.json")
    scores = {row["key"]: row for row in generation.json_rows(args.scores)}
    score_reference = generation.ref(args.scores)
    overlaps = []
    seven_runs = {run["run_id"]+"/"+run["strategy"]: run for run in seal["runs"] if run["m"] == 7}
    for name, run in seven_runs.items():
        candidates = list(generation.json_rows(REPO / run["ranked_file"]["path"]))
        for observation in [r for r in rows if r["m"] == 7 and r["run_id"] == run["run_id"] and r["strategy"] == run["strategy"]]:
            selected = candidates[:observation["metrics"]["actual_candidates"]]
            missing = [r["key"] for r in selected if r["key"] not in scores]
            record = {k: observation[k] for k in ["run_id", "m", "pool", "radius", "root_closure", "seed", "strategy", "complete_growth_run", "nominal_budget"]}
            record.update({"actual_candidates": len(selected), "fully_scored": not missing,
                           "missing_scoring_count": len(missing), "score_source": score_reference})
            if not missing:
                observed = [scores[r["key"]] for r in selected]
                survivors = [r for r in observed if r["unresolved"]]
                winners = sum(r["winner_truth_for_evaluation_only"] for r in survivors)
                record.update({"certifiably_eliminated": sum(r["certifiably_eliminated"] for r in observed),
                               "survivors": len(survivors), "winning_survivors": winners,
                               "unresolved_nonwinners": len(survivors)-winners,
                               "survivor_precision": winners/len(survivors) if survivors else None,
                               "global_winner_recall": winners/8})
            overlaps.append(record)
    generation.dump_rows(args.folder / "scoring-overlap.jsonl", overlaps)
    lines = ["# Ordering the same sealed edit pools", "",
             "All666 ranked runs preserve every candidate from the222 original pools. Candidate scores and saved words are not ranker inputs. All ranked files were sealed before target-truth evaluation; the2,664 prefix observations include all sizes, seeds, radii, source pools and negative outcomes.", "",
             "The three fixed strategies are: discovery (first appearance of each whole shape block), structural (more accessible roots with distinct outgoing targets, then more accessible roots, then indegree nearer2, with seeded SHA-256 tie-breaking), and parent-strata (round-robin over certified previous-parent lower-score levels, structurally ordered within each). These are priorities, not filters or upper bounds. Nonstrongly connected and unbalanced graphs remain in every input pool.", "",
             "Seven-state winner counts at nominal2048, ranges over all three predefined seeds, on the SAME respective budgeted pools:", "",
             "| Parents | Radius | Accessible-root closure | Discovery | Structural | Parent strata |",
             "|---|---:|:---:|---:|---:|---:|"]
    for pool in ["winners", "near2"]:
        for radius in [1,2,3]:
            for closure in [False,True]:
                cells = []
                for strategy in ["discovery", "structural", "parent-strata"]:
                    selected = [r for r in rows if r["m"] == 7 and r["pool"] == pool and r["radius"] == radius
                                and r["root_closure"] == closure and not r["complete_growth_run"]
                                and r["nominal_budget"] == 2048 and r["strategy"] == strategy]
                    cells.append(range_text([r["metrics"]["winner_rooted_hits"] for r in selected]))
                lines.append(f"| {pool} | {radius} | {'yes' if closure else 'no'} | {' | '.join(cells)} |")
    lines += ["", "Thus the budgeted near-top/radius1/root-closed pool plus parent-strata priority recovers all8 maximizers within approximately2048 candidates for EACH fixed seed. This is a measured positive case, not a proof of recall on future graphs. Whole-shape blocks cause small count overshoots; actual counts appear in every record.", "",
              "The exhaustive13,329-class near-top/radius1/root-closed pool is a retained negative case. With this larger fixed input set, winner counts at nominal32/128/512/2048 are:", "",
              "| Strategy | 32 | 128 | 512 | 2048 |",
              "|---|---:|---:|---:|---:|"]
    for strategy in ["discovery", "structural", "parent-strata"]:
        subset = {r["nominal_budget"]: r for r in rows if r["m"] == 7 and r["complete_growth_run"] and r["strategy"] == strategy}
        lines.append("| "+strategy+" | "+" | ".join(str(subset[b]["metrics"]["winner_rooted_hits"]) for b in [32,128,512,2048])+" |")
    lines += ["", "A larger candidate pool can dilute a fixed ranking budget. Neither heuristic places all8 maximizers among the first2048 of the complete pool; both place3 there. Ranking cannot recover a graph absent from a generated pool, and no result here excludes better graphs outside an edit neighborhood.", "",
              "The complete13,329-class pool was already scored uniformly at cap33. Where every ranked prefix key belongs to that scored pool, the same verified observations are reused without new queries. The main positive configuration at nominal2048 gives:", "",
              "| Seed | Actual scored roots | Winner recall | Certified weaker | Unresolved survivors | Unresolved nonwinners |",
              "|---:|---:|---:|---:|---:|---:|"]
    for record in overlaps:
        if (record["pool"] == "near2" and record["radius"] == 1 and record["root_closure"]
                and not record["complete_growth_run"] and record["strategy"] == "parent-strata" and record["nominal_budget"] == 2048):
            assert record["fully_scored"]
            lines.append(f"| {record['seed']} | {record['actual_candidates']} | {record['winning_survivors']}/8 | {record['certifiably_eliminated']} | {record['survivors']} | {record['unresolved_nonwinners']} |")
    lines += ["", "Every true winner survives valid cutoff elimination. Remaining survivors are unresolved, not certified optimal. `scoring-overlap.jsonl` explicitly identifies prefixes lacking full score coverage instead of silently treating unscored candidates as misses or survivors.", "",
              "`ranking-seal.json` pins every original candidate/path/parent source, ranker snapshot, ranked file and feature file. `observations.jsonl`/`.csv` retain complete recall and exact small-case score distributions. Every strategy keeps the identical candidate class multiset; accessible-root groups remain whole. The ranker neither computes H nor uses candidate truth, upper bounds or witnesses.", "",
              "```powershell", "uv run --no-project python tests/family1_edit_ranked_candidate_benchmark.py",
              "uv run --no-project python tests/family1_edit_ranked_analysis.py", "```", ""]
    (args.folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print({"ranked_runs": len(seal["runs"]), "prefix_observations": len(rows), "scoring_overlap_rows": len(overlaps)})


if __name__ == "__main__":
    main()
