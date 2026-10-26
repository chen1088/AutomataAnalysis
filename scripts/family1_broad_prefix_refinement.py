#!/usr/bin/env python3
"""Separate bounded broad-prefix continuation of qualified candidate records.

Queries use graph metadata and newly verified upper lengths only. Optional
reference scores are read after the search is sealed, solely for calibration.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import time

import family1_adaptive_candidate_search as adaptive
import family1_graph_candidate_search as scoring

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--query-seconds", type=int, default=30)
    parser.add_argument("--wall-seconds", type=int, default=120)
    parser.add_argument("--memory-mib", type=int, default=1024)
    parser.add_argument("--samples", type=int, default=65536)
    parser.add_argument("--max-queries", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--band-width", type=int, default=2)
    parser.add_argument("--evaluate-against", type=Path)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("broad-prefix continuation requires fresh output")
    if not 1 <= args.jobs <= 12 or min(args.query_seconds, args.wall_seconds, args.memory_mib, args.samples, args.max_queries, args.batch_size) < 1:
        parser.error("invalid bounded refinement settings")
    args.records, args.out, args.exe = args.records.resolve(), args.out.resolve(), args.exe.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    records = {}
    for _, row in adaptive.rows(args.records):
        certified = scoring.interval_record(row)
        if certified["upper_bound"] is None:
            continue
        records[certified["key"]] = {**row, **certified, "eligible": True}
    source_pin = {"schema": 1, "method": "bounded-separate-broad-prefix-fallback", "records": scoring.reference(args.records),
                  "driver": scoring.reference(Path(__file__)), "adaptive_module": scoring.reference(Path(adaptive.__file__)),
                  "scorer": scoring.reference(Path(scoring.__file__)), "exe": scoring.reference(args.exe),
                  "settings": {key: value for key, value in vars(args).items() if key not in ("records", "out", "exe", "evaluate_against")},
                  "evaluation_scores_used_for_queries": False, "saved_word_hints_used": False,
                  "window_k": 16, "beam": 16, "seed": 1088, "strong_prefix": True,
                  "prefix_budget_actuals_reported_per_query": True}
    scoring.atomic_json(args.out / "run.json", source_pin)
    binary = args.out / "native-used"
    binary.mkdir()
    executable = binary / args.exe.name
    shutil.copy2(args.exe, executable)
    for path in args.exe.parent.glob("*.dll"):
        shutil.copy2(path, binary / path.name)
    shutil.copy2(args.records, args.out / "input-records.jsonl")
    snapshots = args.out / "sources-used"
    snapshots.mkdir()
    for path in (Path(__file__), Path(adaptive.__file__), Path(scoring.__file__), REPO / "scripts/family1_study.py"):
        shutil.copy2(path, snapshots / path.name)
    observations, batches, attempted = [], [], set()
    started = time.monotonic()
    def export(reason):
        ordered = sorted(records.values(), key=lambda row: (-row["upper_bound"], row["key"]))
        for row in ordered:
            row["estimate"] = adaptive.estimate(row["upper_bound"])
        active = [row for row in ordered if row["upper_bound"] == ordered[0]["upper_bound"]]
        scoring.write_jsonl(args.out / "records.jsonl", sorted(ordered, key=lambda row: row["key"]))
        scoring.write_jsonl(args.out / "active-best.jsonl", active)
        scoring.write_jsonl(args.out / "observations.jsonl", observations)
        scoring.atomic_json(args.out / "summary.json", {"schema": 1, "graphs": len(records), "queries": len(observations),
            "active_length": active[0]["upper_bound"], "active_estimate": adaptive.estimate(active[0]["upper_bound"]),
            "all_active_ties_retained": len(active), "top_band_count": sum(row["upper_bound"] >= active[0]["upper_bound"] - args.band_width for row in ordered),
            "batches": batches, "stopping_reason": reason, "wall_seconds": time.monotonic() - started,
            "new_lower_bounds": 0, "rough_band_certified": False, "global_optimum_claimed": False})
    reason = "no untested crowded-band query remains"
    while len(observations) < args.max_queries:
        remaining = args.wall_seconds - (time.monotonic() - started)
        waves = int((remaining - 2) // args.query_seconds)
        if waves < 1:
            reason = "wall budget reserved for already running/verified work"
            break
        ordered = sorted(records.values(), key=lambda row: (-row["upper_bound"], row["key"]))
        ceiling = ordered[0]["upper_bound"]
        cohort = [row for row in ordered if row["upper_bound"] >= ceiling - args.band_width
                  and row["upper_bound"] > 1 and (row["key"], row["upper_bound"] - 1) not in attempted]
        cohort = cohort[:min(args.batch_size, args.jobs * waves, args.max_queries - len(observations))]
        if not cohort:
            break
        plan = {"batch": len(batches), "pre_active_length": ceiling, "queries": []}
        for row in cohort:
            cap = row["upper_bound"] - 1
            stage = adaptive.build_stage(scoring.graph_metadata(row), 16, cap, seed=1088, samples=args.samples,
                                         memory_mib=args.memory_mib, strong_prefix=True, seconds=args.query_seconds)
            plan["queries"].append({"key": row["key"], "cap": cap, "stage": stage})
        plan_path = args.out / "plans" / f"batch-{len(batches)}.json"
        scoring.atomic_json(plan_path, plan)
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {pool.submit(adaptive.query, executable, scoring.graph_metadata(records[item["key"]]), item["stage"], item["cap"],
                                  args.out / "queries" / f"batch-{len(batches)}" / item["key"], scoring.digest(plan_path)): item
                       for item in plan["queries"]}
            for future in as_completed(futures):
                item, answer = futures[future], future.result()
                results.append((item, answer))
                print(scoring.compact({"key": item["key"], "cap": item["cap"], "completed": answer["completed_stage"],
                                       "upper": answer["best_positive"]["upper_bound"] if answer["best_positive"] else None}), flush=True)
        for item, answer in sorted(results, key=lambda value: value[0]["key"]):
            row = records[item["key"]]
            positive = answer["best_positive"]
            if positive and positive["upper_bound"] < row["upper_bound"]:
                if positive["upper_bound"] < row["lower_bound"]:
                    raise ValueError("broad-prefix witness contradicts a supplied lower certificate")
                row.update(upper_bound=positive["upper_bound"], witness=positive["witness"], upper_certificate=positive)
            row["status"] = "exact" if row["lower_bound"] == row["upper_bound"] else "bounded"
            row["merge_length"] = row["lower_bound"] if row["status"] == "exact" else None
            row["max_attempted_k"] = 16
            if answer["completed_stage"]:
                row["completed_k"] = 16
            attempted.add((item["key"], item["cap"]))
            observations.append({"key": item["key"], "batch": len(batches), **answer})
        batches.append(plan)
        export("batch checkpoint")
    export(reason)
    scoring.atomic_json(args.out / "scoring-seal.json", {"run": scoring.reference(args.out / "run.json"),
                         "records": scoring.reference(args.out / "records.jsonl"),
                         "summary": scoring.reference(args.out / "summary.json"), "evaluation_truth_not_used": True})
    if args.evaluate_against:
        truth = {row["key"]: row["merge_length"] for _, row in adaptive.rows(args.evaluate_against)}
        cases = [{"key": row["key"], "known_H": truth[row["key"]], "final_upper": row["upper_bound"],
                  "witness_gap": row["upper_bound"] - truth[row["key"]],
                  "rough_band_contains_truth": row["upper_bound"] - 2 <= truth[row["key"]] <= row["upper_bound"]}
                 for row in sorted(records.values(), key=lambda row: row["key"])]
        scoring.atomic_json(args.out / "retrospective-calibration.json", {"source": scoring.reference(args.evaluate_against),
                            "cases": cases, "rough_band_coverage": sum(row["rough_band_contains_truth"] for row in cases),
                            "no_new_exact_score_claim": True})
    print(json.dumps(scoring.read_json(args.out / "summary.json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
