#!/usr/bin/env python3
"""Bounded witness refinement of every selected root in a frozen graph plan.

Only newly verified witnesses tighten a query cap. No source score or saved
word enters the finder. A capped miss leaves the supplied lower bound intact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil

import family1_graph_candidate_search as search

REPO = Path(__file__).resolve().parents[1]
PHASES = [
    {"name": "coarse96", "stage": 0, "cap": 96, "seed": 1088},
    {"name": "coarse64", "stage": 0, "cap": 64, "seed": 2027},
    {"name": "coarse48", "stage": 0, "cap": 48, "seed": 65537},
    {"name": "heavy48", "stage": 1, "cap": 48, "seed": 1088},
    {"name": "heavy-refine1", "stage": 1, "cap": None, "seed": 2027},
    {"name": "heavy-refine2", "stage": 1, "cap": None, "seed": 65537},
    {"name": "screen34", "stage": 1, "cap": 34, "seed": 104729},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=REPO / "out/family1-edit-candidate-pilot-8-20/m8/scored/plan.json")
    parser.add_argument("--bounds", type=Path, default=REPO / "out/family1-edit-candidate-pilot-8-20/m8/scored/records.jsonl")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--m", type=int, default=8)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--memory-mib", type=int, default=1024)
    parser.add_argument("--coarse-timeout", type=int, default=20)
    parser.add_argument("--heavy-timeout", type=int, default=30)
    parser.add_argument("--stop-after-phase", type=int, default=0, help="Operational checkpoint;0 runs the full pinned schedule.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.out, args.exe, args.plan, args.bounds = (path.resolve() for path in (args.out, args.exe, args.plan, args.bounds))
    if not 1 <= args.m <= 20 or not 1 <= args.jobs <= 16 or not 512 <= args.memory_mib <= 1024 or min(args.coarse_timeout, args.heavy_timeout) < 1:
        parser.error("require m1..20, jobs1..16, memory512..1024MiB, positive invocation timeouts")
    if not 0 <= args.stop_after_phase <= len(PHASES):
        parser.error("stop-after-phase is0 or a valid phase count")
    plan = search.read_json(args.plan)
    graph_rows, shape_roots = {}, {}
    for shape in plan["shapes"]:
        if shape["m"] != args.m or not shape["selected"]:
            continue
        for row in shape["roots"]:
            graph = search.graph_metadata(row)
            graph_rows[graph["key"]] = graph
            shape_roots[graph["key"]] = shape["shape_key"]
    if not graph_rows:
        raise ValueError("selected plan contains no graphs at the requested size")
    imported = {row["key"]: search.interval_record(row) for _, row in search.jsonl(args.bounds)
                if row["m"] == args.m and row["key"] in graph_rows}
    helper_args = search.arguments(["--candidates", str(args.plan), "--out", str(args.out), "--enable-stage2",
                                   "--memory-mib", str(args.memory_mib), "--beam-width", "16",
                                   "--stage1-timeout", str(args.coarse_timeout), "--stage2-timeout", str(args.heavy_timeout),
                                   "--viability-coordinates", str(min(1024, 1 << args.m))])
    stages = {key: search.stage_settings(graph, helper_args) for key, graph in graph_rows.items()}
    config = {"schema": 1, "method": "bounded-all-root-upper-witness-refinement",
              "plan": search.reference(args.plan), "supplied_bounds": search.reference(args.bounds),
              "native_executable": search.reference(args.exe),
              "native_dlls": [search.reference(path) for path in sorted(args.exe.parent.glob("*.dll"))],
              "runner": search.reference(Path(__file__)), "scorer": search.reference(Path(search.__file__)),
              "canonicalizer": search.reference(REPO / "scripts/family1_study.py"),
              "graphs": [graph_rows[key] for key in graph_rows], "shape_keys": shape_roots,
              "stages": stages, "phases": PHASES, "jobs": args.jobs,
              "all_selected_root_classes_retained": True, "source_scores_and_words_not_search_hints": True,
              "misses_do_not_change_lower_bounds": True}
    config = json.loads(search.compact(config))
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume or search.read_json(args.out / "run.json") != config:
            raise ValueError("refinement requires fresh output or identical pinned --resume")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        native = args.out / "native-used"
        native.mkdir()
        shutil.copy2(args.exe, native / args.exe.name)
        for path in args.exe.parent.glob("*.dll"):
            shutil.copy2(path, native / path.name)
        sources = args.out / "sources-used"
        sources.mkdir()
        for path in (Path(__file__), Path(search.__file__), REPO / "scripts/family1_study.py"):
            shutil.copy2(path, sources / path.name)
        shutil.copy2(args.plan, args.out / "input-plan.json")
        shutil.copy2(args.bounds, args.out / "input-bounds.jsonl")
        search.atomic_json(args.out / "run.json", config)
    executable = args.out / "native-used" / args.exe.name
    if search.digest(executable) != config["native_executable"]["sha256"]:
        raise ValueError("saved executable integrity mismatch")
    for item in config["native_dlls"]:
        if search.digest(executable.parent / Path(item["path"]).name) != item["sha256"]:
            raise ValueError("saved DLL integrity mismatch")
    best, attempts, phase_summaries = {}, {}, []
    def export():
        records = []
        for key, graph in graph_rows.items():
            original = imported.get(key, {"lower_bound": 1, "upper_bound": None})
            upper = original["upper_bound"]
            witness = original.get("witness")
            result = best.get(key)
            if result is not None and (upper is None or result["upper_bound"] < upper):
                upper, witness = result["upper_bound"], result["witness"]
            lower = original["lower_bound"]
            if upper is not None and lower > upper:
                raise ValueError("new witness contradicts a supplied lower proof")
            records.append({**graph, "shape_key": shape_roots[key], "lower_bound": lower, "upper_bound": upper,
                            "witness": witness, "status": "exact" if lower == upper else "bounded" if upper is not None else "incomplete",
                            "merge_length": lower if lower == upper else None,
                            "supplied_lower_source": config["supplied_bounds"],
                            "upper_certificate": result if result is not None else None,
                            "shortestness_claimed_by_sampler": False, "global_optimality_claimed": False})
        observations = [attempts[key] for key in sorted(attempts)]
        search.write_jsonl(args.out / "records.jsonl", sorted(records, key=lambda row: row["key"]))
        search.write_jsonl(args.out / "observations.jsonl", observations)
        summary = {"schema": 1, "m": args.m, "selected_graphs": len(graph_rows),
                   "ordinary_shapes": len(set(shape_roots.values())), "phases": phase_summaries,
                   "native_attempts": len(attempts), "verified_upper_graphs": len(best),
                   "verified_upper_histogram": dict(sorted(Counter(str(item["upper_bound"]) for item in best.values()).items())),
                   "all_graphs_and_ties_retained": True, "misses_give_no_lower_bound": True,
                   "new_lower_bounds": 0, "global_maximum_certified": False,
                   "run_sha256": search.digest(args.out / "run.json")}
        search.atomic_json(args.out / "summary.json", summary)
    for phase_index, phase in enumerate(PHASES):
        selected = []
        for key in graph_rows:
            if best.get(key, {}).get("upper_bound", 4097) <= 33:
                continue  # Already certified below the separate size incumbent34.
            upper = best.get(key, {}).get("upper_bound")
            requested = phase["cap"] if phase["cap"] is not None else (upper - 1 if upper is not None else 96)
            cap = min(requested, upper - 1) if upper is not None else requested
            if cap < 1:
                continue
            stage = {**stages[key][phase["stage"]], "seed": phase["seed"]}
            selected.append((key, stage, cap))
        phase_record = {"index": phase_index, "name": phase["name"], "selected_graphs": len(selected), "completed_graphs": 0}
        phase_summaries.append(phase_record)
        def worker(item):
            key, stage, cap = item
            answer = search.run_attempt(executable, graph_rows[key], stage, cap,
                                        args.out / "queries" / f"phase-{phase_index}-{phase['name']}" / key)
            return key, cap, answer
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(worker, item) for item in selected]
            for future in as_completed(futures):
                key, cap, answer = future.result()
                attempts[(phase_index, key)] = {"phase": phase["name"], "shape_key": shape_roots[key], **answer}
                observation = answer["observation"]
                if observation["upper_bound"] is not None:
                    if key not in best or observation["upper_bound"] < best[key]["upper_bound"]:
                        best[key] = {"upper_bound": observation["upper_bound"], "witness": observation["witness"],
                                     "native_result": answer["native_result"], "verification": observation["verification"],
                                     "phase": phase["name"]}
                phase_record["completed_graphs"] += 1
                export()
                print(search.compact({"phase": phase["name"], "key": key, "shape_key": shape_roots[key],
                                      "length_cap": cap, "outcome": answer["outcome"],
                                      "new_upper": observation["upper_bound"], "verified_upper_graphs": len(best)}), flush=True)
        export()
        if args.stop_after_phase and phase_index + 1 >= args.stop_after_phase:
            break
    export()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
