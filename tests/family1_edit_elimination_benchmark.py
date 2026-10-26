#!/usr/bin/env python3
"""Retrospective incumbent-cutoff scoring on already sealed candidate pools."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import family1_edit_candidate_benchmark as generation

REPO = generation.REPO


def prefix(rows, budget, closure):
    stop = min(budget, len(rows))
    if closure and 0 < stop < len(rows):
        shape = rows[stop-1]["shape_key"]
        while stop < len(rows) and rows[stop]["shape_key"] == shape:
            stop += 1
    return rows[:stop]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, default=REPO / "results/family1-edit-candidate-benchmark/generation-seal.json")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-edit-elimination-benchmark")
    parser.add_argument("--work-dir", type=Path, default=REPO / "out/family1-edit-elimination-benchmark")
    parser.add_argument("--budgets", type=int, nargs="+", default=[32, 128])
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--beam", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--complete-size7-only", action="store_true")
    parser.add_argument("--reuse-work-dir", type=Path)
    args = parser.parse_args()
    output, work = args.out.resolve(), args.work_dir.resolve()
    output.mkdir(parents=True, exist_ok=True); work.mkdir(parents=True, exist_ok=True)
    seal = generation.read(args.generation)
    assert seal["all_candidate_files_pinned_before_child_truth_load"]
    binary = work / "binary"; binary.mkdir(exist_ok=True)
    native = binary / args.exe.name
    scorer_source = REPO / "scripts/family1_graph_candidate_search.py"
    scorer_snapshot = work / "scorer-used.py"
    for source, destination in [(args.exe, native), (scorer_source, scorer_snapshot)]:
        if destination.exists():
            assert source.read_bytes() == destination.read_bytes(), "Fresh output required for changed scorer/executable."
        else:
            shutil.copy2(source, destination)
    for dll in args.exe.parent.glob("*.dll"):
        destination = binary / dll.name
        if not destination.exists():
            shutil.copy2(dll, destination)
    spec = importlib.util.spec_from_file_location("edit_benchmark_pinned_scorer", scorer_snapshot)
    scorer = importlib.util.module_from_spec(spec); spec.loader.exec_module(scorer)
    baseline = {}
    for row in seal["random_generations"]:
        path = REPO / row["candidate_file"]["path"]
        assert generation.ref(path) == row["candidate_file"]
        baseline[(row["m"], row["seed"], row["root_closure"])] = list(generation.json_rows(path))
    cohorts, queries = [], {}
    for row in seal["generations"]:
        if args.complete_size7_only and not (row["m"] == 7 and row.get("complete_growth_run")):
            continue
        path = REPO / row["candidate_file"]["path"]
        assert generation.ref(path) == row["candidate_file"]
        candidates = list(generation.json_rows(path))
        if args.complete_size7_only:
            selected = candidates
            cohorts.append({"run_id": row["run_id"], "m": row["m"], "pool": row["pool"], "radius": row["radius"],
                            "seed": row["seed"], "root_closure": row["root_closure"], "method": "edit-complete-growth",
                            "nominal_scoring_budget": len(candidates), "actual_scored_candidates": len(candidates),
                            "keys": [r["key"] for r in candidates]})
            for candidate in selected:
                key = (7, candidate["key"])
                queries[key] = scorer.graph_metadata(candidate)
            continue
        for budget in sorted(set(args.budgets)):
            edited = prefix(candidates, budget, row["root_closure"])
            random_rows = prefix(baseline[(row["m"], row["seed"], row["root_closure"])], len(edited), row["root_closure"])
            for method, selected in [("edit", edited), ("fair_random", random_rows)]:
                cohort = {"run_id": row["run_id"], "m": row["m"], "pool": row["pool"], "radius": row["radius"],
                          "seed": row["seed"], "root_closure": row["root_closure"], "method": method,
                          "nominal_scoring_budget": budget, "actual_scored_candidates": len(selected),
                          "keys": [r["key"] for r in selected]}
                cohorts.append(cohort)
                for candidate in selected:
                    key = (row["m"], candidate["key"])
                    graph = scorer.graph_metadata(candidate)
                    assert key not in queries or graph == queries[key]
                    queries[key] = graph
    # Current-size truth is consulted only after candidate generation/selection;
    # it supplies one shared retrospective incumbent cutoff per state count.
    binding = generation.read(REPO / seal["binding"]["path"])
    journal = REPO / binding["journal"]["path"]
    truth = generation.load_truth(journal, {m for m, _ in queries})
    settings_args = scorer.arguments([
        "--candidates", str(args.generation.resolve()), "--out", str(work), "--exe", str(native),
        "--beam-width", str(args.beam), "--stage1-samples", str(args.samples),
        "--stage1-prefix-pairs", str(args.samples), "--stage1-timeout", str(args.timeout),
        "--stage1-k", "6", "--stage1-prefix-depth", "16", "--stage1-prefix-words", "65536",
        "--stage1-expansions", "10000", "--tail-threshold", "8", "--viability-coordinates", "128",
    ])
    configuration = {"generation_seal": generation.ref(args.generation), "exe": generation.ref(native),
                     "scorer": generation.ref(scorer_snapshot), "budgets": sorted(set(args.budgets)),
                     "samples": args.samples, "beam": args.beam, "timeout": args.timeout,
                     "complete_size7_only": args.complete_size7_only,
                     "reuse_work_dir": str(args.reuse_work_dir.resolve()) if args.reuse_work_dir else None,
                     "same_size_cutoffs": {m: t["maximum"]-1 for m, t in truth.items()},
                     "query_count": len(queries), "per_size_query_count": dict(Counter(m for m, _ in queries)),
                     "retrospective_operating_point": True, "per_graph_truth_or_word_hints_passed": False}
    config_path = work / "run.json"
    if config_path.exists():
        saved_configuration = generation.read(config_path)
        saved_configuration.setdefault("complete_size7_only", False)
        saved_configuration.setdefault("reuse_work_dir", None)
        assert saved_configuration == json.loads(json.dumps(configuration)), "Changed scoring settings require fresh output."
    else:
        generation.dump(config_path, configuration)
    if args.reuse_work_dir:
        previous = generation.read(args.reuse_work_dir / "run.json")
        assert previous["exe"]["sha256"] == configuration["exe"]["sha256"]
        assert previous["scorer"]["sha256"] == configuration["scorer"]["sha256"]
    generation.dump(output / "query-plan.json", configuration)
    print(json.dumps({"queries": len(queries), "per_size": configuration["per_size_query_count"]}), flush=True)
    if args.plan_only:
        return

    def evaluate(item):
        (m, key), graph = item
        stage = scorer.stage_settings(graph, settings_args)[0]
        cap = truth[m]["maximum"] - 1
        query_directory = work / "queries" / f"m{m}" / key
        reused = False
        if args.reuse_work_dir:
            previous_directory = args.reuse_work_dir / "queries" / f"m{m}" / key
            if (previous_directory / "attempt.json").is_file():
                query_directory = previous_directory
                reused = True
        metadata = scorer.run_attempt(native, graph, stage, cap, query_directory)
        observation = metadata["observation"]
        eliminated = observation["decision"] == "collision"
        if eliminated:
            assert key not in truth[m]["winners"], "A verified cutoff hit contradicts the existing maximum certificate."
            assert observation["upper_bound"] <= cap
        exact = truth[m]["scores"].get(key)
        gap = observation["upper_bound"] - exact if eliminated and exact is not None else None
        assert gap is None or gap >= 0
        return {"m": m, "key": key, "cutoff": cap, "incumbent": truth[m]["maximum"],
                "certifiably_eliminated": eliminated, "unresolved": not eliminated,
                "winner_truth_for_evaluation_only": key in truth[m]["winners"],
                "exact_H_for_evaluation_only": exact, "witness_length_gap": gap,
                "reused_prior_query": reused, "attempt_file": generation.ref(query_directory / "attempt.json"),
                "attempt": metadata}

    scored = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(evaluate, item) for item in sorted(queries.items())]
        for future in as_completed(futures):
            result = future.result(); scored[(result["m"], result["key"])] = result
            if len(scored) % 128 == 0 or len(scored) == len(queries):
                print(json.dumps({"completed": len(scored), "queries": len(queries)}), flush=True)
    observations = []
    for cohort in cohorts:
        entries = [scored[(cohort["m"], key)] for key in cohort["keys"]]
        survivors = [r for r in entries if r["unresolved"]]
        winners = [r for r in entries if r["winner_truth_for_evaluation_only"]]
        weak = [r for r in entries if not r["winner_truth_for_evaluation_only"]]
        gaps = [r["witness_length_gap"] for r in entries if r["witness_length_gap"] is not None]
        observations.append({**cohort, "eliminated": sum(r["certifiably_eliminated"] for r in entries),
                             "nonwinner_count": len(weak),
                             "nonwinner_fraction_certifiably_eliminated": sum(r["certifiably_eliminated"] for r in weak)/len(weak) if weak else None,
                             "survivor_count": len(survivors), "survivor_winner_count": len(winners),
                             "survivor_precision": len(winners)/len(survivors) if survivors else None,
                             "generated_winner_recall_after_scoring": 1.0 if winners else None,
                             "global_winner_recall": len(winners)/len(truth[cohort["m"]]["winners"]),
                             "witness_gap_histogram": dict(sorted(Counter(gaps).items())),
                             "scope": "Survivors are unresolved scored graphs, not certified maximizers; unscored candidates remain outside this scoring-budget population."})
    generation.dump_rows(output / "scores.jsonl", [scored[key] for key in sorted(scored)])
    generation.dump_rows(output / "observations.jsonl", observations)
    summary = {**configuration, "cohort_rows": len(observations),
               "eliminated_unique_graphs": sum(r["certifiably_eliminated"] for r in scored.values()),
               "unresolved_unique_graphs": sum(r["unresolved"] for r in scored.values()),
               "false_eliminations": 0,
               "reused_prior_queries": sum(r["reused_prior_query"] for r in scored.values()),
               "scorer_outcomes": dict(Counter(r["attempt"]["outcome"] for r in scored.values())),
               "no_new_global_optimality_claim": True}
    generation.dump(output / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ["query_count", "eliminated_unique_graphs", "unresolved_unique_graphs", "false_eliminations"]}, indent=2))


if __name__ == "__main__":
    main()
