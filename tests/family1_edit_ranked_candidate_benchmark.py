#!/usr/bin/env python3
"""Order the same sealed graph pools without target labels, then measure recall."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import importlib.util
from pathlib import Path
import shutil
import sys

import family1_edit_candidate_benchmark as generation

REPO = generation.REPO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, default=REPO / "results/family1-edit-candidate-benchmark/generation-seal.json")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-edit-ranked-candidate-benchmark")
    parser.add_argument("--work-dir", type=Path, default=REPO / "out/family1-edit-ranked-candidate-benchmark")
    parser.add_argument("--strategies", nargs="+", default=["discovery", "structural", "parent-strata"])
    parser.add_argument("--budgets", type=int, nargs="+", default=[32, 128, 512, 2048])
    parser.add_argument("--full-m7-scores", type=Path, default=REPO / "results/family1-edit-elimination-complete-m7/scores.jsonl")
    args = parser.parse_args()
    output, work = args.out.resolve(), args.work_dir.resolve()
    output.mkdir(parents=True, exist_ok=True); work.mkdir(parents=True, exist_ok=True)
    source = REPO / "scripts/family1_rank_edit_candidates.py"
    snapshot = work / "ranker-used.py"
    if snapshot.exists():
        assert snapshot.read_bytes() == source.read_bytes(), "Changed ranker requires a fresh work directory."
    else:
        shutil.copy2(source, snapshot)
    spec = importlib.util.spec_from_file_location("edit_benchmark_pinned_ranker", snapshot)
    ranker = importlib.util.module_from_spec(spec); spec.loader.exec_module(ranker)
    seal = generation.read(args.generation)
    assert seal["all_candidate_files_pinned_before_child_truth_load"]
    ranked_runs = []
    for index, item in enumerate(seal["generations"]):
        candidate_file = REPO / item["candidate_file"]["path"]
        path_file = REPO / item["path_file"]["path"]
        parent_file = REPO / item["parent_source"]["path"]
        for path, expected in [(candidate_file, item["candidate_file"]), (path_file, item["path_file"]), (parent_file, item["parent_source"])]:
            assert generation.ref(path) == expected
        candidates, paths, parents = list(generation.json_rows(candidate_file)), list(generation.json_rows(path_file)), list(generation.json_rows(parent_file))
        original_keys = {r["key"] for r in candidates}
        assert len(original_keys) == len(candidates)
        for strategy in args.strategies:
            rows, features, summary = ranker.rank_rows(candidates, paths, parents, strategy=strategy, seed=item["seed"])
            assert len(rows) == len(candidates) and {r["key"] for r in rows} == original_keys
            directory = work / item["run_id"] / strategy
            directory.mkdir(parents=True, exist_ok=True)
            generation.dump_rows(directory / "candidates.jsonl", rows)
            generation.dump(directory / "features.json", features)
            generation.dump(directory / "summary.json", summary)
            ranked_runs.append({"run_id": item["run_id"], "m": item["m"], "pool": item["pool"], "radius": item["radius"],
                                "root_closure": item["root_closure"], "seed": item["seed"], "strategy": strategy,
                                "complete_growth_run": item.get("complete_growth_run", False),
                                "candidate_count": len(rows), "input_candidate_file": item["candidate_file"],
                                "parent_source": item["parent_source"], "path_file": item["path_file"],
                                "ranked_file": generation.ref(directory / "candidates.jsonl"),
                                "features_file": generation.ref(directory / "features.json"),
                                "ranking_summary": summary})
        if (index+1) % 12 == 0 or index+1 == len(seal["generations"]):
            print(f"ranked {index+1}/{len(seal['generations'])}", flush=True)
    ranking_seal = {"schema": 1, "source_generation_seal": generation.ref(args.generation),
                    "ranker_snapshot": generation.ref(snapshot), "runs": ranked_runs,
                    "target_truth_not_supplied_to_ranker": True, "all_input_classes_retained": True,
                    "ranked_files_sealed_before_truth_evaluation": True}
    generation.dump(output / "ranking-seal.json", ranking_seal)
    binding = generation.read(REPO / seal["binding"]["path"])
    truth = generation.load_truth(REPO / binding["journal"]["path"], set(range(1, 8)))
    scores = {}
    if args.full_m7_scores.is_file():
        scores = {r["key"]: r for r in generation.json_rows(args.full_m7_scores)}
    observations = []
    for run in ranked_runs:
        rows = list(generation.json_rows(REPO / run["ranked_file"]["path"]))
        for budget in sorted(set(args.budgets)):
            metrics = generation.prefix_metrics(rows, budget, truth[run["m"]], whole_shapes=True)
            entry = {**{k: run[k] for k in ["run_id", "m", "pool", "radius", "root_closure", "seed", "strategy", "complete_growth_run"]},
                     "nominal_budget": budget, "metrics": metrics}
            selected = rows[:metrics["actual_candidates"]]
            if run["m"] == 7 and run["complete_growth_run"] and scores:
                selected_scores = [scores[r["key"]] for r in selected]
                survivors = [r for r in selected_scores if r["unresolved"]]
                winner_survivors = sum(r["winner_truth_for_evaluation_only"] for r in survivors)
                entry["cheap_elimination"] = {"scored_candidates": len(selected_scores),
                                              "eliminated": sum(r["certifiably_eliminated"] for r in selected_scores),
                                              "survivors": len(survivors), "winning_survivors": winner_survivors,
                                              "survivor_precision": winner_survivors/len(survivors) if survivors else None,
                                              "global_winner_recall": winner_survivors/8,
                                              "source": generation.ref(args.full_m7_scores)}
            observations.append(entry)
    generation.dump_rows(output / "observations.jsonl", observations)
    generation.dump(output / "summary.json", {"schema": 1, "ranked_runs": len(ranked_runs),
                     "metric_rows": len(observations), "ranker": generation.ref(snapshot),
                     "same_candidate_classes_across_strategies": True, "no_target_truth_in_ranking": True,
                     "no_global_optimality_claim": True})
    columns = ["run_id", "m", "pool", "radius", "root_closure", "seed", "strategy", "complete_growth_run", "nominal_budget",
               "actual_candidates", "winner_rooted_hits", "winner_rooted_total", "winner_shape_hits", "winner_shape_total", "near_top_hits", "near_top_total"]
    with (output / "observations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader()
        for row in observations:
            writer.writerow({column: row.get(column, row["metrics"].get(column)) for column in columns})
    # Preserve all negative cases as well as the complete growth result.
    print("m7 complete-growth whole-root-block prefixes", flush=True)
    for row in observations:
        if row["m"] == 7 and row["complete_growth_run"]:
            print(row["strategy"], row["nominal_budget"], row["metrics"]["actual_candidates"], row["metrics"]["winner_rooted_hits"], flush=True)


if __name__ == "__main__":
    main()
