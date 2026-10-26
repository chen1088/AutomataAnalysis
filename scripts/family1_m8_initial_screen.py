#!/usr/bin/env python3
"""Complete r1 generation and cheap cap34 screening from all55 m7 parents.

Every hit is an upper certificate; a miss or timeout adds no lower bound.
Graphs with upper34 remain potential ties. No current-size truth or saved
witness hints enter the finder. Raw attempts make interrupted runs resumable.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from family1_graph_candidate_search import graph_metadata, score_graph

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_rows(path, values):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def invoke(command, log):
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    log.write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"Invocation failed; see {log}: {completed.stderr[-1000:]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-m8-search-v1")
    parser.add_argument("--edit-exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Edit.exe")
    parser.add_argument("--finder-exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--parents", type=Path, default=REPO / "results/family1-neighbor-seeds/near-top.jsonl")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error("jobs must be1..32")
    for name in ("out", "edit_exe", "finder_exe", "parents"):
        setattr(args, name, getattr(args, name).resolve())
    parents = sorted([row for row in rows(args.parents) if row["m"] == 7], key=lambda row: row["key"])
    require = lambda condition, message: None if condition else (_ for _ in ()).throw(ValueError(message))
    require(len(parents) == 55 and len({row["key"] for row in parents}) == 55, "Expected all55 distinct m7 near-top parents")
    stage = {"name": "cheap-r1", "window_k": 6, "beam_width": 4, "samples": 128,
             "prefix_pairs": 128, "prefix_depth": 16, "prefix_words": 65536,
             "prefix_samples_per_depth": 16384, "distance_coordinates": 0,
             "ranking": "drop", "common_prefix_depth": 0, "expansions": 10000,
             "timeout_seconds": 10, "tail_threshold": 8, "tail_max_states": 100000,
             "viability_coordinates": 128, "seed": 1088}
    source_names = ["Family1EditSearch.h", "Family1EditSearch.cpp", "family1_edit.cpp", "Family1LargeGraph.h", "Family1LargeGraph.cpp",
                    "family1_sample.cpp", "Family1PairAgreement.h", "Family1CliArtifacts.h", "Family1FullGuidance.h",
                    "HardPairFinder.h", "HardPairPrefixSeeds.h", "HardPairViability.h", "scripts/family1_study.py",
                    "scripts/family1_graph_candidate_search.py", "scripts/family1_rank_edit_candidates.py", "scripts/family1_m8_initial_screen.py"]
    pins = {str(REPO / name): digest(REPO / name) for name in source_names}
    for path in [args.parents, args.edit_exe, args.finder_exe] + list(args.finder_exe.parent.glob("*.dll")):
        pins[str(path)] = digest(path)
    configuration = {"schema": 1, "method": "all55-m7-parent-complete-unit-growth-then-cap34-finder",
                     "source_pins": pins, "parent_keys": [row["key"] for row in parents],
                     "generation": {"radius": 1, "max_paths": 30000, "max_candidates": 12000, "seed": 1088, "root_closure": True},
                     "stage": stage, "length_cap": 34, "jobs": args.jobs,
                     "strict_improvement_requires_H_at_least": 35, "misses_give_no_lower_bound": True,
                     "upper34_potential_ties_are_retained": True, "saved_word_hints_used": False}
    own = args.out / "initial-screen-inputs"
    config_path = own / "run.json"
    if config_path.exists():
        require(args.resume and json.loads(config_path.read_text()) == configuration, "Resume settings/source/executable pins changed")
    else:
        require(not own.exists() or not any(own.iterdir()), "Use a new input snapshot directory")
        own.mkdir(parents=True, exist_ok=True)
        native = own / "native-used"; native.mkdir()
        for source, name in ((args.edit_exe, "Family1Edit.exe"), (args.finder_exe, "Family1Sample.exe")):
            shutil.copy2(source, native / name)
        for path in args.finder_exe.parent.glob("*.dll"):
            shutil.copy2(path, native / path.name)
        snapshots = own / "sources-used"; snapshots.mkdir()
        for name in source_names:
            shutil.copy2(REPO / name, snapshots / Path(name).name)
        write_rows(own / "parents.jsonl", parents)
        write_json(config_path, configuration)
    native = own / "native-used"
    require(digest(native / "Family1Edit.exe") == pins[str(args.edit_exe)] and digest(native / "Family1Sample.exe") == pins[str(args.finder_exe)], "Saved native executable changed")
    generation, ranked, screening = (args.out / name for name in ("generation-r1", "ranked-r1", "cheap-r1"))
    command = [str(native / "Family1Edit.exe")]
    for row in parents:
        command += ["--graph", row["key"]]
    command += ["--target-m", "8", "--radius", "1", "--max-paths", "30000", "--max-candidates", "12000", "--seed", "1088", "--root-closure", "--out", str(generation)]
    if (generation / "summary.json").exists():
        command.append("--resume")
    invoke(command, own / "generation.log")
    generation_summary = json.loads((generation / "summary.json").read_text())
    require(generation_summary["enumeration_complete"] and generation_summary["supported_universe_complete"] and not generation_summary["representation_capped"], "r1 growth enumeration unexpectedly capped")
    command = [os.sys.executable, str(REPO / "scripts/family1_rank_edit_candidates.py"), "--candidates", str(generation / "candidates.jsonl"),
               "--paths", str(generation / "paths.jsonl"), "--parents", str(own / "parents.jsonl"), "--strategy", "parent-strata", "--seed", "1088", "--out", str(ranked)]
    if (ranked / "run.json").exists():
        command.append("--resume")
    invoke(command, own / "ranking.log")
    candidates = rows(ranked / "candidates.jsonl")
    require(len(candidates) == generation_summary["candidate_count"] and len({row["key"] for row in candidates}) == len(candidates), "Ranking lost/duplicated classes")
    screening.mkdir(exist_ok=True)
    coverage = {"schema": 1, "parents": len(parents), "rooted_classes": len(candidates), "direct_rooted_endpoints": generation_summary["root_fixed_candidate_count"],
                "ordinary_shapes": generation_summary["ordinary_shape_count"], "generation_complete_within_r1_parent_neighborhood": True,
                "global_graph_enumeration_complete": False, "generation_summary_sha256": digest(generation / "summary.json"),
                "ranked_candidates_sha256": digest(ranked / "candidates.jsonl"), "stage": stage}
    write_json(screening / "pool.json", coverage)
    print(json.dumps({"pool": coverage}), flush=True)
    if args.generate_only:
        return
    started = time.perf_counter()
    outcomes, decisions, records = Counter(), Counter(), {}
    journal_temporary = screening / "observations.jsonl.tmp"
    with journal_temporary.open("w", encoding="utf-8", newline="\n") as journal:
        def score(row):
            graph = graph_metadata(row)
            answer = score_graph(native / "Family1Sample.exe", graph, [stage], [34], 34,
                                 screening / "queries" / row["key"])
            require(len(answer) == 1, "Expected exactly one cheap stage per root")
            return row, answer[0]
        def summary(complete=False):
            value = {**coverage, "processed_roots": len(records), "all_roots_processed": complete,
                     "outcomes": dict(outcomes), "decisions": dict(decisions), "seconds": time.perf_counter() - started,
                     "strict_improvement_excluded_by_upper34": sum(value["upper_bound"] is not None for value in records.values()),
                     "potential_ties_upper34": sum(value["upper_bound"] == 34 for value in records.values()),
                     "unresolved_roots": sum(value["upper_bound"] is None for value in records.values()),
                     "any_new_lower_bound": False, "global_maximum_certified": False}
            write_json(screening / "summary.json", value)
            return value
        summary()
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(score, row) for row in candidates]
            for future in as_completed(futures):
                row, attempt = future.result()
                graph = graph_metadata(row)
                answer = attempt["observation"]
                upper = answer["upper_bound"]
                decisions[answer["decision"]] += 1; outcomes[attempt["outcome"]] += 1
                records[row["key"]] = {**row, "lower_bound": 1, "upper_bound": upper, "witness": answer["witness"],
                    "status": "bounded" if upper is not None else "incomplete", "merge_length": None,
                    "screening": {"length_cap": 34, "outcome": attempt["outcome"], "native_result": attempt["native_result"],
                                  "observation": answer, "seconds": attempt["seconds"],
                                  "strict_improvement_excluded": upper is not None,
                                  "could_still_tie34": upper is None or upper >= 34}}
                journal.write(json.dumps(attempt, sort_keys=True, separators=(",", ":")) + "\n")
                if len(records) % 100 == 0:
                    journal.flush()
                    print(json.dumps({"processed": len(records), "pool": len(candidates), "outcomes": dict(outcomes), "decisions": dict(decisions), "seconds": time.perf_counter() - started}), flush=True)
                    summary()
        journal.flush()
    journal_temporary.replace(screening / "observations.jsonl")
    values = [records[row["key"]] for row in candidates]
    write_rows(screening / "records.jsonl", values)
    write_rows(screening / "survivors-strict-improvement.jsonl", [row for row in values if row["upper_bound"] is None])
    write_rows(screening / "potential-ties34.jsonl", [row for row in values if row["upper_bound"] is None or row["upper_bound"] >= 34])
    write_rows(screening / "upper34-potential-ties.jsonl", [row for row in values if row["upper_bound"] == 34])
    write_rows(screening / "upper-below34.jsonl", [row for row in values if row["upper_bound"] is not None and row["upper_bound"] < 34])
    print(json.dumps(summary(True)), flush=True)


if __name__ == "__main__":
    main()
