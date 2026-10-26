#!/usr/bin/env python3
"""Leakage-separated edit-candidate recall benchmark with fair random baselines.

Generation sees only previous-size exact winner/near-top parents and fixed
budgets. All candidate files are sealed before current-size truth is loaded.
This measures finite candidate coverage; it never certifies a new maximum.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_study import canonical_table, fixed_key, validate_table

CLASS_COUNTS = {1: 1, 2: 6, 3: 57, 4: 678, 5: 10398, 6: 192181, 7: 4166855}


def ref(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": name, "sha256": digest}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def json_rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def dump(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def dump_rows(path, rows):
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def root_classes(table):
    """All accessible rerootings, preserving every vertex multiplicity."""
    table = tuple(map(tuple, table))
    classes = {}
    for root in range(len(table)):
        old_order = [root] + [state for state in range(len(table)) if state != root]
        mapping = {old: new for new, old in enumerate(old_order)}
        rerooted = tuple(tuple(mapping[target] for target in table[state]) for state in old_order)
        try:
            canonical = canonical_table(rerooted)
        except ValueError:
            continue
        key = fixed_key(canonical)
        classes.setdefault(key, {"key": key, "canonical_table": canonical, "roots_in_input": []})["roots_in_input"].append(root)
    return classes


def shape_key(table):
    # Taking the minimum accessible rooted class is a complete ordinary-shape
    # invariant on accessible graphs, even when not every vertex can be a root.
    return min(root_classes(table))


def parent_pools(journal, sizes, output):
    """Only parent-size scores determine generation inputs."""
    wanted = {m - 1 for m in sizes if m > 1}
    parents = defaultdict(list)
    for record in json_rows(journal):
        m = record.get("m")
        if m not in wanted:
            continue
        assert record["status"] == "exact"
        table = validate_table(record["canonical_table"])
        assert canonical_table(table) == table
        parents[m].append({"m": m, "key": fixed_key(table), "canonical_table": table,
                           "merge_length": record["merge_length"], "status": "exact"})
    result = {}
    for m in sorted(wanted):
        assert len(parents[m]) == CLASS_COUNTS[m]
        maximum = max(row["merge_length"] for row in parents[m])
        for pool, gap in [("winners", 0), ("near2", 2)]:
            selected = sorted((row for row in parents[m] if row["merge_length"] >= maximum - gap), key=lambda row: row["key"])
            path = output / f"m{m}-{pool}.jsonl"
            dump_rows(path, selected)
            result[(m + 1, pool)] = {"parents": selected, "source": ref(path),
                                     "parent_maximum": maximum, "parent_score_gap": gap}
    return result


def generate_random(m, seed, closure, count, path, max_draws):
    started = time.perf_counter()
    rng = random.Random((seed ^ (m * 0x9E3779B97F4A7C15)) & ((1 << 64) - 1))
    result, seen, draws, inaccessible, duplicate = [], set(), 0, 0, 0
    count = min(count, CLASS_COUNTS[m])
    while len(result) < count and draws < max_draws:
        raw = tuple((rng.randrange(m), rng.randrange(m)) for _ in range(m))
        draws += 1
        try:
            canonical = canonical_table(raw)
        except ValueError:
            inaccessible += 1
            continue
        roots = root_classes(canonical) if closure else {fixed_key(canonical): {"key": fixed_key(canonical), "canonical_table": canonical}}
        closure_shape = min(roots)
        for key in sorted(roots):
            if key in seen:
                duplicate += 1
                continue
            seen.add(key)
            result.append({"key": key, "m": m, "canonical_table": roots[key]["canonical_table"],
                           "shape_key": closure_shape, "discovery_index": len(result), "raw_draw": draws})
        # Keep the entire last closure, both in artifacts and budget metrics.
    dump_rows(path, result)
    return {"m": m, "seed": seed, "root_closure": closure, "candidate_file": ref(path),
            "candidates": len(result), "raw_draws": draws, "inaccessible_rejected": inaccessible,
            "duplicate_rooted_candidates": duplicate, "seconds": time.perf_counter()-started,
            "requested_unique_candidates": count, "draw_capped": len(result) < count,
            "distribution": "IID ordered labelled two-port tables, conditioned on accessibility; not uniform rooted classes."}


def load_truth(journal, sizes):
    """Called only after the complete generation seal is written."""
    exact = defaultdict(dict)
    for record in json_rows(journal):
        if record["m"] not in sizes or record["m"] > 6:
            continue
        assert record["status"] == "exact"
        exact[record["m"]][fixed_key(record["canonical_table"])] = record["merge_length"]
    truth = {}
    for m in sizes:
        if m <= 6:
            assert len(exact[m]) == CLASS_COUNTS[m]
            maximum = max(exact[m].values())
            winners = {key for key, score in exact[m].items() if score == maximum}
            near = {key for key, score in exact[m].items() if score >= maximum - 2}
        else:
            summary = read(REPO / "results/family1-m7/summary.json")
            assert summary["maximum_value_certified"] and summary["maximizing_collection_complete"]
            maximum = summary["maximum_merge_length"]
            winners = set(summary["maximizer_keys"])
            near = None
        shapes = defaultdict(set)
        shape_for_root_class = {}
        for key in sorted(winners):
            values = [int(key[i:i+2]) for i in range(0, len(key), 2)]
            table = tuple(zip(values[::2], values[1::2]))
            roots = root_classes(table)
            shape = min(roots)
            shapes[shape].add(key)
            for root_key in roots:
                assert root_key not in shape_for_root_class or shape_for_root_class[root_key] == shape
                shape_for_root_class[root_key] = shape
        truth[m] = {"maximum": maximum, "winners": winners, "near": near, "winner_shapes": dict(shapes),
                    "shape_for_root_class": shape_for_root_class, "scores": exact[m]}
    return truth


def prefix_metrics(rows, budget, truth, whole_shapes=False):
    stop = min(budget, len(rows))
    if whole_shapes and 0 < stop < len(rows):
        final_shape = rows[stop-1]["shape_key"]
        while stop < len(rows) and rows[stop]["shape_key"] == final_shape:
            stop += 1
    selected = rows[:stop]
    keys = {row["key"] for row in selected}
    shapes = {truth["shape_for_root_class"][key] for key in keys if key in truth["shape_for_root_class"]}
    found = keys & truth["winners"]
    near = truth["near"]
    scores = [truth["scores"][key] for key in keys] if truth["scores"] else []
    per_shape = [{"shape_key": shape, "winning_rooted_classes": len(rooted),
                  "generated_winning_rooted_classes": len(rooted & keys),
                  "ordinary_shape_observed": shape in shapes,
                  "all_winning_roots_observed": rooted <= keys}
                 for shape, rooted in sorted(truth["winner_shapes"].items())]
    return {"actual_candidates": len(selected), "winner_rooted_recall": len(found)/len(truth["winners"]),
            "winner_rooted_hits": len(found), "winner_rooted_total": len(truth["winners"]),
            "winner_shape_hits": sum(row["ordinary_shape_observed"] for row in per_shape),
            "winner_shape_total": len(per_shape),
            "winner_shapes_with_all_winning_roots": sum(row["all_winning_roots_observed"] for row in per_shape),
            "winner_keys_found": sorted(found), "winner_shapes": per_shape,
            "near_top_hits": len(keys & near) if near is not None else None,
            "near_top_total": len(near) if near is not None else None,
            "near_top_recall": len(keys & near)/len(near) if near is not None else None,
            "exact_score_histogram": dict(sorted(Counter(scores).items())),
            "best_exact_score": max(scores) if scores else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Edit.exe")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-edit-candidate-benchmark")
    parser.add_argument("--work-dir", type=Path, default=REPO / "out/family1-edit-candidate-benchmark")
    parser.add_argument("--journal", type=Path, default=REPO / "out/family1-m1-m6/graphs.jsonl")
    parser.add_argument("--sizes", type=int, nargs="+", default=list(range(1, 8)))
    parser.add_argument("--radii", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1088, 2027, 65537])
    parser.add_argument("--budgets", type=int, nargs="+", default=[32, 128, 512, 2048])
    parser.add_argument("--closure-grid", choices=["off", "on"], nargs="+", default=["off", "on"])
    parser.add_argument("--max-paths", type=int, default=10000)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-random-draws", type=int, default=1000000)
    parser.add_argument("--skip-complete-growth", action="store_true")
    args = parser.parse_args()
    assert set(args.sizes) <= set(range(1, 8)) and set(args.radii) <= {1, 2, 3}
    assert min(args.budgets) > 0 and 1 <= args.jobs <= 32
    work, output = args.work_dir.resolve(), args.out.resolve()
    work.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    parents_dir = work / "parents"; parents_dir.mkdir(exist_ok=True)
    binary_dir = work / "binary"; binary_dir.mkdir(exist_ok=True)
    executable = binary_dir / args.exe.name
    if executable.exists():
        assert ref(executable)["sha256"] == ref(args.exe)["sha256"], "Use a fresh work directory for a changed binary."
    else:
        shutil.copy2(args.exe, executable)
    for dll in args.exe.parent.glob("*.dll"):
        destination = binary_dir / dll.name
        if not destination.exists():
            shutil.copy2(dll, destination)
        assert ref(destination)["sha256"] == ref(dll)["sha256"]
    binding = {"schema": 1, "exe": ref(executable), "journal": ref(args.journal),
               "radii": sorted(set(args.radii)), "seeds": sorted(set(args.seeds)),
               "budgets": sorted(set(args.budgets)), "closure_grid": sorted(set(args.closure_grid)),
               "max_paths": args.max_paths, "max_candidates": max(args.budgets),
               "complete_radius1_near2_allroots": not args.skip_complete_growth,
               "no_child_truth_used_for_generation": True,
               "parent_pools": "all previous-size exact winners; separately all scores within2 of previous maximum"}
    binding_path = work / "binding.json"
    if binding_path.exists():
        assert read(binding_path) == binding, "Use a fresh work directory for different settings."
    else:
        dump(binding_path, binding)
    pools = parent_pools(args.journal, args.sizes, parents_dir)
    generation_jobs = []
    for m in sorted(set(args.sizes) - {1}):
        for pool in ["winners", "near2"]:
            for radius in sorted(set(args.radii)):
                for seed in sorted(set(args.seeds)):
                    for closure_name in sorted(set(args.closure_grid)):
                        closure = closure_name == "on"
                        run_id = f"m{m}-{pool}-r{radius}-s{seed}-roots{int(closure)}"
                        directory = work / "native" / run_id
                        parent_info = pools[(m, pool)]
                        command = [str(executable)]
                        for parent in parent_info["parents"]:
                            command += ["--graph", parent["key"]]
                        command += ["--target-m", str(m), "--radius", str(radius), "--seed", str(seed),
                                    "--max-paths", str(args.max_paths), "--max-candidates", str(max(args.budgets)),
                                    "--out", str(directory)]
                        if closure:
                            command += ["--root-closure"]
                        if (directory / "summary.json").is_file():
                            command += ["--resume"]
                        generation_jobs.append({"run_id": run_id, "m": m, "pool": pool, "radius": radius,
                                                "seed": seed, "root_closure": closure, "directory": directory,
                                                "parent_source": parent_info["source"],
                                                "parent_count": len(parent_info["parents"]), "command": command})
        if not args.skip_complete_growth:
            parent_info = pools[(m, "near2")]
            run_id = f"m{m}-near2-complete-growth-r1-s1088-roots1"
            directory = work / "native" / run_id
            command = [str(executable)]
            for parent in parent_info["parents"]:
                command += ["--graph", parent["key"]]
            command += ["--target-m", str(m), "--radius", "1", "--seed", "1088",
                        "--max-paths", "20000", "--max-candidates", "8192", "--root-closure", "--out", str(directory)]
            if (directory / "summary.json").is_file():
                command += ["--resume"]
            generation_jobs.append({"run_id": run_id, "m": m, "pool": "near2", "radius": 1,
                                    "seed": 1088, "root_closure": True, "complete_growth_run": True,
                                    "directory": directory, "parent_source": parent_info["source"],
                                    "parent_count": len(parent_info["parents"]), "command": command})

    def execute(job):
        started = time.perf_counter()
        process = subprocess.run(job["command"], text=True, capture_output=True, timeout=args.timeout, cwd=REPO)
        if process.returncode:
            raise RuntimeError(f"{job['run_id']}: {process.stderr[-2000:]}")
        directory = job["directory"]
        (directory / "benchmark-invocation.log").write_text(process.stdout+process.stderr, encoding="utf-8")
        summary = read(directory / "summary.json")
        assert summary["completed"] is True
        result = {key: value for key, value in job.items() if key != "directory"}
        result.update({"whole_invocation_seconds": time.perf_counter()-started,
                       "native_summary": summary, "summary_file": ref(directory / "summary.json"),
                       "candidate_file": ref(directory / "candidates.jsonl"), "path_file": ref(directory / "paths.jsonl"),
                       "native_configuration": ref(directory / "run.json")})
        return result

    generations = []
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = {workers.submit(execute, job): job for job in generation_jobs}
        for future in as_completed(futures):
            result = future.result(); generations.append(result)
            print(json.dumps({"completed": len(generations), "total": len(generation_jobs), "run_id": result["run_id"]}), flush=True)
    generations.sort(key=lambda row: row["run_id"])
    random_records = []
    baseline_dir = work / "random"; baseline_dir.mkdir(exist_ok=True)
    for m in sorted(set(args.sizes)):
        for seed in sorted(set(args.seeds)):
            for closure_name in sorted(set(args.closure_grid)):
                closure = closure_name == "on"
                path = baseline_dir / f"m{m}-s{seed}-roots{int(closure)}.jsonl"
                complete_counts = [g["native_summary"]["candidate_count"] for g in generations
                                   if g["m"] == m and g.get("complete_growth_run") and closure]
                baseline_goal = max([max(args.budgets)] + complete_counts) + 2*m
                random_records.append(generate_random(m, seed, closure, baseline_goal, path, args.max_random_draws))
    seal = {"schema": 1, "binding": ref(binding_path), "parent_sources": [v["source"] for _, v in sorted(pools.items())],
            "benchmark_script": ref(Path(__file__)),
            "generations": generations, "random_generations": random_records,
            "all_candidate_files_pinned_before_child_truth_load": True,
            "child_truth_not_an_input_to_native_generation_or_random_baseline": True}
    dump(work / "generation-seal.json", seal)
    # No current-size maxima, winner keys or near-top labels are loaded above.
    truth = load_truth(args.journal, set(args.sizes))
    baseline = {(r["m"], r["seed"], r["root_closure"]): list(json_rows(REPO / r["candidate_file"]["path"])) for r in random_records}
    observations = []
    for generation in generations:
        candidates = list(json_rows(REPO / generation["candidate_file"]["path"]))
        assert len({r["key"] for r in candidates}) == len(candidates)
        for budget in sorted(set(args.budgets)):
            edit_metrics = prefix_metrics(candidates, budget, truth[generation["m"]], generation["root_closure"])
            fair_budget = edit_metrics["actual_candidates"]
            random_metrics = prefix_metrics(baseline[(generation["m"], generation["seed"], generation["root_closure"])], fair_budget, truth[generation["m"]], generation["root_closure"])
            assert random_metrics["actual_candidates"] >= fair_budget
            observations.append({"run_id": generation["run_id"], "m": generation["m"], "pool": generation["pool"],
                                 "radius": generation["radius"], "seed": generation["seed"],
                                 "root_closure": generation["root_closure"], "nominal_budget": budget,
                                 "parent_count": generation["parent_count"], "edit": edit_metrics,
                                 "random_budget_difference": random_metrics["actual_candidates"] - fair_budget,
                                 "budget_policy": "Whole observed shape/root blocks; baseline receives at least the edit count, overshoot recorded.",
                                 "fair_random": random_metrics, "native_summary_file": generation["summary_file"]})
        if generation.get("complete_growth_run"):
            full_metrics = prefix_metrics(candidates, len(candidates), truth[generation["m"]])
            full_random = prefix_metrics(baseline[(generation["m"], generation["seed"], True)], len(candidates), truth[generation["m"]], True)
            observations.append({"run_id": generation["run_id"], "m": generation["m"], "pool": generation["pool"],
                                 "radius": 1, "seed": 1088, "root_closure": True,
                                 "nominal_budget": "all_generated", "parent_count": generation["parent_count"],
                                 "complete_growth_run": True, "edit": full_metrics, "fair_random": full_random,
                                 "random_budget_difference": full_random["actual_candidates"] - len(candidates),
                                 "native_summary_file": generation["summary_file"]})
    if 1 in args.sizes:
        observations.append({"run_id": "m1-base-case", "m": 1, "pool": "base-case", "radius": 0,
                             "seed": None, "root_closure": True, "nominal_budget": 1,
                             "edit": prefix_metrics([{"key": "0000", "canonical_table": [[0, 0]]}], 1, truth[1]),
                             "scope": "One-state base case; no zero-state predecessor or edit claim."})
    dump_rows(output / "observations.jsonl", observations)
    dump(output / "generation-seal.json", seal)
    dump(output / "binding.json", binding)
    dump(output / "summary.json", {"schema": 1, "native_generation_runs": len(generations),
                                     "metric_rows": len(observations), "generation_sealed_before_truth": True,
                                     "truth_sources": {"exact_m1_m6": ref(args.journal), "complete_m7_winners": ref(REPO / "results/family1-m7/summary.json")},
                                     "complete_global_search_claimed": False,
                                     "random_baseline_uniform_graph_classes_claimed": False})
    fields = ["run_id", "m", "pool", "radius", "seed", "root_closure", "nominal_budget", "parent_count",
              "actual_candidates", "winner_rooted_hits", "winner_rooted_total", "winner_shape_hits", "winner_shape_total",
              "near_top_hits", "near_top_total", "random_winner_rooted_hits", "random_winner_shape_hits", "random_near_top_hits"]
    with (output / "observations.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in observations:
            result = {key: row.get(key) for key in fields}
            result.update({key: row["edit"].get(key) for key in fields if key in row["edit"]})
            result.update({"random_"+key: row.get("fair_random", {}).get(key) for key in ["winner_rooted_hits", "winner_shape_hits", "near_top_hits"]})
            writer.writerow(result)
    print(json.dumps({"native_runs": len(generations), "metric_rows": len(observations), "out": str(output)}, indent=2))


if __name__ == "__main__":
    main()
