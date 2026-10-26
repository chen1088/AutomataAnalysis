#!/usr/bin/env python3
"""Durable m8 all-pool cap96, then conditional cap48/cap40 upper screening.

Retains every root and every attempt; upper bounds are merged with the prior
cap34 screen. No heuristic miss or long witness supplies any lower bound.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import time

from family1_graph_candidate_search import graph_metadata, score_graph, verify_witness
from family1_m8_initial_screen import digest, rows, write_json, write_rows

REPO = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", type=Path, default=REPO / "out/family1-m8-search-v1")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    require(1 <= args.jobs <= 32, "jobs must be1..32")
    args.search = args.search.resolve()
    args.out = args.out.resolve() if args.out else args.search / "cheap-upper-r1"
    previous = args.search / "cheap-r1"
    pool = json.loads((previous / "pool.json").read_text())
    require(json.loads((previous / "summary.json").read_text())["all_roots_processed"], "Prior cap34 screen incomplete")
    prior = rows(previous / "records.jsonl")
    require(len(prior) == pool["rooted_classes"] == 11266 and len({row["key"] for row in prior}) == len(prior), "All-pool input changed")
    stage = {**pool["stage"], "name": "upper-r1"}
    native = args.search / "initial-screen-inputs/native-used/Family1Sample.exe"
    source_names = ["scripts/family1_m8_upper_screen.py", "scripts/family1_m8_initial_screen.py", "scripts/family1_graph_candidate_search.py", "scripts/family1_study.py"]
    source_pins = {str(REPO / name): digest(REPO / name) for name in source_names}
    configuration = {"schema": 1, "method": "all11266-cap96-then-best-upper-conditional48-and40",
                     "prior_records": {"path": str(previous / "records.jsonl"), "sha256": digest(previous / "records.jsonl")},
                     "native_executable": {"path": str(native), "sha256": digest(native)}, "source_pins": source_pins,
                     "stage": stage, "caps": [96, 48, 40], "jobs": args.jobs,
                     "selection": "cap96 allroots; later cap only if bestupper>cap or unknown", "misses_give_no_lower_bound": True}
    if args.out.exists() and any(args.out.iterdir()):
        require(args.resume and json.loads((args.out / "run.json").read_text()) == configuration, "Resume settings/input/source pins differ")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        snapshots = args.out / "sources-used"; snapshots.mkdir()
        for name in source_names:
            shutil.copy2(REPO / name, snapshots / Path(name).name)
        write_json(args.out / "run.json", configuration)
    records = {}
    for row in prior:
        graph = graph_metadata(row)
        require(row["lower_bound"] == 1 and row["screening"]["observation"]["upper_bound"] == row["upper_bound"], "Prior bound scope differs")
        if row["upper_bound"] is not None:
            verify_witness(graph["canonical_table"], row["witness"], 34)
            reference = row["screening"]["native_result"]
            require(reference and digest(Path(reference["path"])) == reference["sha256"], "Prior upper certificate changed")
        else:
            require(row["witness"] is None, "Prior miss carries a witness")
        records[row["key"]] = {**row, "upper_screening_observations": []}
    total_started = time.perf_counter()
    stage_reports = []

    def export(complete=False):
        values = [records[row["key"]] for row in prior]
        histogram = Counter(row["upper_bound"] for row in values if row["upper_bound"] is not None)
        result = {"schema": 1, "pool_roots": len(values), "stage_reports": stage_reports,
                  "all_scheduled_stages_complete": complete, "best_verified_upper_histogram": dict(sorted(histogram.items())),
                  "unknown_upper_roots": sum(row["upper_bound"] is None for row in values),
                  "potential_strict_improvement_over34": sum(row["upper_bound"] is None or row["upper_bound"] > 34 for row in values),
                  "upper34_potential_ties": sum(row["upper_bound"] == 34 for row in values),
                  "any_new_lower_bound": False, "global_maximum_certified": False, "seconds": time.perf_counter() - total_started}
        write_json(args.out / "summary.json", result)
        return result

    for cap in (96, 48, 40):
        selected = prior if cap == 96 else [row for row in prior if records[row["key"]]["upper_bound"] is None or records[row["key"]]["upper_bound"] > cap]
        directory = args.out / f"cap-{cap}"; directory.mkdir(exist_ok=True)
        selection = {"cap": cap, "selected_keys": [row["key"] for row in selected], "stage": stage}
        if (directory / "selection.json").exists():
            require(json.loads((directory / "selection.json").read_text()) == selection, "Materialized stage selection changed")
        else:
            write_json(directory / "selection.json", selection)
        started = time.perf_counter()
        attempts, outcomes, decisions = {}, Counter(), Counter()
        improvements = 0
        temporary = directory / "observations.jsonl.tmp"
        with temporary.open("w", encoding="utf-8", newline="\n") as journal:
            def score(row):
                result = score_graph(native, graph_metadata(row), [stage], [cap], cap, directory / "queries" / row["key"])
                require(len(result) == 1, "Expected one cheap stage per root/cap")
                return row["key"], result[0]
            with ThreadPoolExecutor(max_workers=args.jobs) as workers:
                futures = [workers.submit(score, row) for row in selected]
                for future in as_completed(futures):
                    key, attempt = future.result()
                    attempts[key] = attempt
                    outcomes[attempt["outcome"]] += 1; decisions[attempt["observation"]["decision"]] += 1
                    answer = attempt["observation"]
                    record = records[key]
                    old_upper, upper = record["upper_bound"], answer["upper_bound"]
                    if upper is not None and (old_upper is None or upper < old_upper):
                        record["upper_bound"], record["witness"] = upper, answer["witness"]
                        record["best_upper_source"] = attempt["native_result"]
                        record["status"] = "exact" if upper == 1 else "bounded"
                        record["merge_length"] = 1 if upper == 1 else None
                        improvements += 1
                    record["upper_screening_observations"].append({"cap": cap, "outcome": attempt["outcome"],
                        "upper_bound": upper, "native_result": attempt["native_result"], "seconds": attempt["seconds"]})
                    journal.write(json.dumps(attempt, sort_keys=True, separators=(",", ":")) + "\n")
                    if len(attempts) % 100 == 0:
                        journal.flush()
                        progress = {"cap": cap, "processed": len(attempts), "selected": len(selected), "outcomes": dict(outcomes),
                                    "decisions": dict(decisions), "improved_best_upper": improvements, "seconds": time.perf_counter() - started}
                        write_json(directory / "progress.json", progress)
                        print(json.dumps(progress), flush=True)
        # Stable materialized ordering, independently of process completion order.
        write_rows(directory / "observations.jsonl", [attempts[row["key"]] for row in selected])
        report = {"cap": cap, "selected": len(selected), "processed": len(attempts), "all_selected_processed": len(attempts) == len(selected),
                  "outcomes": dict(outcomes), "decisions": dict(decisions), "improved_best_upper": improvements, "seconds": time.perf_counter() - started}
        write_json(directory / "summary.json", report)
        stage_reports.append(report)
        values = [records[row["key"]] for row in prior]
        write_rows(args.out / "records.jsonl", values)
        write_rows(args.out / f"records-after-{cap}.jsonl", values)
        write_rows(args.out / "survivors-strict-improvement.jsonl", [row for row in values if row["upper_bound"] is None or row["upper_bound"] > 34])
        write_rows(args.out / "potential-ties34.jsonl", [row for row in values if row["upper_bound"] is None or row["upper_bound"] >= 34])
        print(json.dumps({"stage_complete": report, "overall": export()}), flush=True)
    print(json.dumps(export(True)), flush=True)


if __name__ == "__main__":
    main()
