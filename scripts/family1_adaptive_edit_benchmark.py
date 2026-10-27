#!/usr/bin/env python3
"""Complete deterministic edit-pool coverage against exhaustive Family 1 ties.

Generation uses only previous-size exact winner/max-minus-two parents. Native
generation is sealed before target winner labels are joined. Every exported
pool is complete: a cap or interruption is an error, never a radius claim.
No pair search is performed, so generation and coverage have k=N/A.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_study import canonical_table, fixed_key, validate_table

CLASS_COUNTS = {1: 1, 2: 6, 3: 57, 4: 678, 5: 10398, 6: 192181, 7: 4166855}

HELPER = r'''#include "Family1EditSearch.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
int main(int argc, char** argv) {
  try {
    if (argc != 7) throw std::runtime_error("target radius parents candidates summary cap");
    std::ifstream source(argv[3]); std::string key;
    std::vector<family1::LargeGraph> parents;
    while (source >> key) parents.push_back(family1::LargeGraph::from_key(key));
    family1::edit::Options options;
    options.target_m = std::stoul(argv[1]); options.radius = std::stoul(argv[2]);
    options.max_paths = options.max_candidates = std::stoull(argv[6]);
    options.root_closure = true; options.deterministic = true;
    auto result = family1::edit::search(parents, options);
    std::sort(result.candidates.begin(), result.candidates.end(), [](const auto& a, const auto& b) {
      return a.graph.key() < b.graph.key();
    });
    std::ofstream candidates(argv[4]);
    for (const auto& candidate : result.candidates) {
      candidates << candidate.graph.key() << '\t' << candidate.shape_key << '\t'
                 << candidate.generation_depth << '\t' << !candidate.path_ids.empty() << '\n';
    }
    std::ofstream summary(argv[5]);
    summary << "{\"deterministic\":true,\"k\":null,\"window\":\"N/A: generation only\","
       << "\"enumeration_complete\":" << result.enumeration_complete
       << ",\"supported_universe_complete\":" << result.supported_universe_complete
       << ",\"path_capped\":" << result.path_capped << ",\"candidate_capped\":" << result.candidate_capped
       << ",\"interrupted\":" << result.interrupted << ",\"representation_capped\":" << result.unsupported_size_paths_possible
       << ",\"candidate_count\":" << result.candidates.size() << ",\"root_fixed_candidate_count\":" << result.root_fixed_candidate_count
       << ",\"accepted_paths\":" << result.accepted_paths << ",\"raw_proposals\":" << result.raw_proposals
       << ",\"seconds\":" << result.seconds << ",\"depths\":[";
    bool first = true;
    for (const auto& depth : result.depths) {
      if (!first) summary << ','; first = false;
      summary << "{\"depth\":" << depth.depth << ",\"frontier_nodes\":" << depth.frontier_nodes
          << ",\"raw_proposals\":" << depth.raw_proposals << ",\"accepted_paths\":" << depth.accepted_paths
          << ",\"complete\":" << depth.complete << ",\"path_capped\":" << depth.path_capped
          << ",\"candidate_capped\":" << depth.candidate_capped << '}';
    }
    summary << "]}\n";
    if (!result.enumeration_complete || result.path_capped || result.candidate_capped || result.interrupted)
      throw std::runtime_error("incomplete neighborhood: exported data is not a complete pool");
  } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
'''


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def ref(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": digest(path)}


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))


def table_from_key(key):
    values = [int(key[index:index + 2]) for index in range(0, len(key), 2)]
    return tuple(zip(values[::2], values[1::2]))


def root_classes(table):
    result = {}
    for root in range(len(table)):
        order = [root] + [vertex for vertex in range(len(table)) if vertex != root]
        labels = {vertex: index for index, vertex in enumerate(order)}
        moved = tuple(tuple(labels[target] for target in table[vertex]) for vertex in order)
        try:
            canonical = canonical_table(moved)
        except ValueError:
            continue
        result[fixed_key(canonical)] = canonical
    return result


def independent_growth(parents):
    """Direct Python occurrence enumeration, independent of the native cursors."""
    endpoints = {}
    for row in parents:
        table = tuple(map(tuple, row["canonical_table"]))
        m = len(table)
        edges = [(source, port) for source in range(m) for port in range(2)]
        for selected in itertools.chain(((edge,) for edge in edges), itertools.combinations(edges, 2)):
            changed = [list(row) for row in table]
            targets = [table[source][port] for source, port in selected]
            for source, port in selected:
                changed[source][port] = m
            changed.append(targets if len(targets) == 2 else [targets[0], m])
            canonical = canonical_table(tuple(map(tuple, changed)))
            endpoints[fixed_key(canonical)] = canonical
    closure = {}
    for table in endpoints.values():
        closure.update(root_classes(table))
    return endpoints, closure


def independent_retargets(tables):
    result = {}
    for table in tables:
        m = len(table)
        for source in range(m):
            for port in range(2):
                for target in range(m):
                    if target == table[source][port]:
                        continue
                    changed = [list(row) for row in table]
                    changed[source][port] = target
                    try:
                        canonical = canonical_table(tuple(map(tuple, changed)))
                    except ValueError:
                        continue
                    result[fixed_key(canonical)] = canonical
    return result


def independent_radius_two(parents):
    """Net growth +1 in <=2 edits is insert, retarget/insert, insert/retarget.

    Every primitive changes size by -1, 0, or +1. Thus no smoothing or pair of
    size-changing edits can contribute a net +1 path of length at most two.
    """
    inserted, _ = independent_growth(parents)
    endpoints = dict(inserted)
    endpoints.update(independent_retargets(inserted.values()))
    changed_parents = independent_retargets(tuple(map(tuple, row["canonical_table"])) for row in parents)
    after_retarget, _ = independent_growth([{"canonical_table": table} for table in changed_parents.values()])
    endpoints.update(after_retarget)
    closure = {}
    for table in endpoints.values():
        closure.update(root_classes(table))
    return endpoints, closure


def brute_canonical(table):
    """Factorial relabeling, independent of discovery-order canonicalization."""
    best = None
    for tail in itertools.permutations(range(1, len(table))):
        order = (0,) + tail
        labels = {vertex: index for index, vertex in enumerate(order)}
        candidate = tuple(tuple(sorted(labels[target] for target in table[vertex])) for vertex in order)
        if best is None or candidate < best:
            best = candidate
    return best


def validate_sealed_pools(args, pools):
    checks = []
    for pool in pools:
        directory = args.out / "sealed-pools" / pool["pool_id"]
        rows = list(read_rows(directory / "candidates.jsonl"))
        parents = list(read_rows(REPO / pool["parent_source"]["path"]))
        if pool["radius"] == 2:
            fixed, closed = independent_radius_two(parents)
            assert set(fixed) == {row["key"] for row in rows if row["root_fixed"]}, pool["pool_id"]
            assert set(closed) == {row["key"] for row in rows}, pool["pool_id"]
            pool["validation"]["independent_python_full_two_edit_enumeration"] = True
        sample_indices = sorted({0, len(rows) // 2, len(rows) - 1})
        for index in sample_indices:
            table = tuple(map(tuple, rows[index]["canonical_table"]))
            assert brute_canonical(table) == table
        pool["validation"]["factorial_canonical_samples"] = len(sample_indices)
        write_json(directory / "seal.json", pool)
        checks.append({"pool_id": pool["pool_id"], "validation": pool["validation"]})
    write_json(args.out / "independent-validation.json", {"k": None, "window": "N/A: generation only", "checks": checks})


def prepare_parents(args):
    """Only previous-size exact labels enter a target's generation request."""
    parent_manifest = json.loads(args.near_top.with_name("summary.json").read_text(encoding="utf-8-sig"))
    assert digest(args.near_top) == parent_manifest["output_sha256"]
    distribution = json.loads(args.distribution.read_text(encoding="utf-8-sig"))
    rows = defaultdict(list)
    for row in read_rows(args.near_top):
        m = row["m"]
        if m not in {target - 1 for target in args.sizes}:
            continue
        assert row["status"] == "exact", (m, row["status"])
        table = validate_table(row["canonical_table"])
        assert table == canonical_table(table)
        rows[m].append({"m": m, "key": fixed_key(table), "canonical_table": table,
                        "merge_length": row["merge_length"], "status": "exact"})
    result = {}
    for target in args.sizes:
        m = target - 1
        histogram = {int(score): count for score, count in distribution[str(m)].items()}
        assert sum(histogram.values()) == CLASS_COUNTS[m]
        maximum = max(histogram)
        expected = {score: count for score, count in histogram.items() if score >= maximum - 2}
        actual = dict(Counter(row["merge_length"] for row in rows[m]))
        assert actual == expected, (m, actual, expected)
        assert len({row["key"] for row in rows[m]}) == len(rows[m])
        for name, gap in [("winners", 0), ("near2", 2)]:
            chosen = sorted((row for row in rows[m] if row["merge_length"] >= maximum - gap), key=lambda row: row["key"])
            path = args.out / "parents" / f"m{m}-{name}.jsonl"
            write_rows(path, chosen)
            result[(target, name)] = {"rows": chosen, "source": ref(path), "parent_maximum": maximum,
                                      "parent_gap": gap, "parent_size": m, "count": len(chosen)}
    return result


def build_helper(args):
    directory = args.out / "native"
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "complete_edit_pool.cpp"
    source.write_text(HELPER)
    executable = directory / "complete_edit_pool"
    inputs = [source, REPO / "Family1EditSearch.cpp", REPO / "Family1LargeGraph.cpp",
              REPO / "Family1EditSearch.h", REPO / "Family1LargeGraph.h"]
    manifest_path = directory / "build.json"
    expected = {str(path): digest(path) for path in inputs}
    existing = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not executable.exists() or existing.get("inputs") != expected:
        command = [args.cxx, "-std=c++20", "-O3", "-DNDEBUG", "-I", str(REPO), str(source),
                   str(REPO / "Family1EditSearch.cpp"), str(REPO / "Family1LargeGraph.cpp"), "-o", str(executable)]
        subprocess.run(command, check=True)
        write_json(manifest_path, {"command": command, "inputs": expected, "executable": ref(executable)})
    return executable


def generate(args, executable, parents, target, name, radius):
    pool_id = f"m{target}-{name}-r{radius}"
    directory = args.out / "sealed-pools" / pool_id
    directory.mkdir(parents=True, exist_ok=True)
    candidates_path = directory / "candidates.jsonl"
    native_summary_path = directory / "native-summary.json"
    config = {"pool_id": pool_id, "target_m": target, "radius": radius,
              "parent_source": parents["source"], "parent_count": parents["count"],
              "parent_score_gap": parents["parent_gap"], "parent_maximum": parents["parent_maximum"],
              "root_closure": True, "deterministic": True, "randomness": False,
              "cap": args.cap, "executable": ref(executable), "k": None,
              "window": "N/A: generation only", "scoring_performed": False}
    config_path = directory / "config.json"
    seal_path = directory / "seal.json"
    if args.resume and seal_path.exists() and json.loads(config_path.read_text()) == config:
        seal = json.loads(seal_path.read_text())
        assert ref(candidates_path) == seal["candidates"]
        assert ref(native_summary_path) == seal["native_summary"]
        return seal
    write_json(config_path, config)
    parent_keys = directory / "parent-keys.txt"
    parent_keys.write_text("".join(row["key"] + "\n" for row in parents["rows"]))
    tsv = directory / "native-candidates.tsv"
    command = [str(executable), str(target), str(radius), str(parent_keys), str(tsv),
               str(native_summary_path), str(args.cap)]
    subprocess.run(command, check=True)
    native = json.loads(native_summary_path.read_text())
    assert native["enumeration_complete"] and native["supported_universe_complete"]
    assert not any(native[key] for key in ["path_capped", "candidate_capped", "interrupted", "representation_capped"])
    rows = []
    for line in tsv.read_text().splitlines():
        key, shape, depth, root_fixed = line.split("\t")
        table = table_from_key(key)
        assert len(table) == target and canonical_table(table) == table
        rows.append({"m": target, "key": key, "canonical_table": table, "shape_key": shape,
                     "generation_depth": int(depth), "root_fixed": root_fixed == "1"})
    assert len(rows) == native["candidate_count"] == len({row["key"] for row in rows})
    assert sum(row["root_fixed"] for row in rows) == native["root_fixed_candidate_count"]
    validation = {"all_tables_canonical": True, "native_completion_flags": True}
    if radius == 1:
        independent_fixed, independent_closed = independent_growth(parents["rows"])
        assert set(independent_fixed) == {row["key"] for row in rows if row["root_fixed"]}
        assert set(independent_closed) == {row["key"] for row in rows}
        validation["independent_python_full_occurrence_enumeration"] = True
    write_rows(candidates_path, rows)
    key_digest = hashlib.sha256("".join(row["key"] + "\n" for row in rows).encode()).hexdigest()
    seal = {**config, "configuration": ref(config_path), "candidates": ref(candidates_path),
            "native_summary": ref(native_summary_path), "ordered_keys_sha256": key_digest,
            "candidates_all_roots": len(rows), "candidates_root_fixed": sum(row["root_fixed"] for row in rows),
            "shapes": len({row["shape_key"] for row in rows}), "validation": validation,
            "generation_complete": True, "generation_seconds": native["seconds"], "command": command}
    write_json(seal_path, seal)
    print(json.dumps({"pool": pool_id, "all_roots": len(rows), "fixed": seal["candidates_root_fixed"],
                      "seconds": native["seconds"], "complete": True, "k": "N/A"}), flush=True)
    return seal


def load_target_winners(args):
    """The target labels are loaded only after generation-seal.json exists."""
    assert (args.out / "generation-seal.json").exists()
    result = defaultdict(dict)
    for source in args.winners:
        for row in read_rows(source):
            if row["m"] not in args.sizes:
                continue
            assert row["status"] == "exact"
            table = canonical_table(row["canonical_table"])
            result[row["m"]][fixed_key(table)] = {"key": fixed_key(table), "merge_length": row["merge_length"],
                                                   "shape_key": min(root_classes(table))}
    for m in args.sizes:
        assert result[m]
        assert len({row["merge_length"] for row in result[m].values()}) == 1
    return result


def analyze(args, pools):
    truth = load_target_winners(args)
    results = []
    for pool in pools:
        rows = list(read_rows(REPO / pool["candidates"]["path"]))
        target = pool["target_m"]
        winner_keys = set(truth[target])
        winner_shapes = {row["shape_key"] for row in truth[target].values()}
        for closure in [False, True]:
            selected = rows if closure else [row for row in rows if row["root_fixed"]]
            keys = {row["key"] for row in selected}
            shapes = {row["shape_key"] for row in selected}
            hits = sorted(keys & winner_keys)
            result = {"pool_id": pool["pool_id"], "m": target, "parent_size": target - 1,
                      "parent_set": "winners" if pool["parent_score_gap"] == 0 else "near2",
                      "parent_count": pool["parent_count"], "radius": pool["radius"],
                      "root_closure": closure, "candidate_count": len(selected), "shape_count": len(shapes),
                      "winner_hits": len(hits), "winner_total": len(winner_keys),
                      "winner_recall": len(hits) / len(winner_keys), "winner_keys": hits,
                      "missed_winner_keys": sorted(winner_keys - keys),
                      "winning_shape_hits": len(shapes & winner_shapes), "winning_shape_total": len(winner_shapes),
                      "exhaustive_class_count": CLASS_COUNTS[target], "complete_neighborhood": True,
                      "generation_seconds": pool["generation_seconds"], "k": None,
                      "window": "N/A: generation and exhaustive-label coverage only"}
            results.append(result)
    write_rows(args.out / "coverage.jsonl", results)
    fields = ["m", "parent_set", "parent_count", "radius", "root_closure", "candidate_count", "shape_count",
              "winner_hits", "winner_total", "winner_recall", "winning_shape_hits", "winning_shape_total",
              "generation_seconds", "k", "window"]
    with (args.out / "coverage.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**row, "k": "N/A"} for row in results)
    unions = {}
    for target in args.sizes:
        merged = {}
        for pool in pools:
            if pool["target_m"] != target:
                continue
            for row in read_rows(REPO / pool["candidates"]["path"]):
                entry = merged.setdefault(row["key"], {"m": target, "key": row["key"], "canonical_table": row["canonical_table"],
                                                       "shape_key": row["shape_key"], "pool_ids": []})
                entry["pool_ids"].append(pool["pool_id"])
        path = args.out / f"union-m{target}.jsonl"
        write_rows(path, (merged[key] for key in sorted(merged)))
        unions[target] = {"source": ref(path), "count": len(merged)}
    summary = {"schema": 1, "method": "complete-deterministic-prior-size-edit-coverage",
               "k": None, "window": "N/A: graph generation/coverage", "randomness": False,
               "generation_seal": ref(args.out / "generation-seal.json"), "coverage": ref(args.out / "coverage.jsonl"),
               "truth_sources": [ref(path) for path in args.winners], "pools": len(pools), "comparisons": len(results),
               "unions": unions, "all_neighborhoods_complete": True,
               "notes": ["All winner ties from exhaustive findings are evaluated; no pair finder ran here.",
                         "Root closure is a separate operation after root-fixed edit distance, never a zero-cost primitive edit.",
                         "The radius-2 growth benchmark includes one insertion and at most one retarget; larger target radii are not implied.",
                         "Coverage is not a proof that these edits recover unknown-size maxima."]}
    write_json(args.out / "summary.json", summary)
    return results


def publish(args, pools, results):
    """Compact audit artifacts; this reports coverage, not finder performance."""
    args.publish.mkdir(parents=True, exist_ok=True)
    (args.publish / "coverage.csv").write_bytes((args.out / "coverage.csv").read_bytes())
    generation = json.loads((args.out / "generation-seal.json").read_text())
    manifest = {"schema": 1, "k": None, "window": "N/A: generation and exhaustive-label coverage only",
                "randomness": False, "target_truth_loaded_after_seal": True,
                "generation_seal": ref(args.out / "generation-seal.json"),
                "parent_source": generation["near_top_source"], "parent_distribution": generation["distribution_source"],
                "parent_selection_manifest": generation["parent_selection_manifest"],
                "parent_label_original_source": generation["parent_label_original_source"],
                "parent_selection_completeness": "Every m1..6 selected row is exact, canonical, unique; selected score histogram exactly matches all exhaustive max-minus-two histogram levels. Thus no qualifying parent is omitted.",
                "source_files": generation["source_files"], "truth_sources": [ref(path) for path in args.winners],
                "independent_validation": ref(args.out / "independent-validation.json"),
                "native_build": ref(args.out / "native/build.json"),
                "pools": [{"pool_id": pool["pool_id"], "target_m": pool["target_m"], "radius": pool["radius"],
                           "parent_score_gap": pool["parent_score_gap"], "parent_maximum": pool["parent_maximum"],
                           "parent_count": pool["parent_count"], "parent_source": pool["parent_source"],
                           "candidate_source": pool["candidates"], "ordered_keys_sha256": pool["ordered_keys_sha256"],
                           "native_summary": pool["native_summary"], "generation_complete": True,
                           "candidates_all_roots": pool["candidates_all_roots"],
                           "candidates_root_fixed": pool["candidates_root_fixed"], "validation": pool["validation"],
                           "completion_flags": json.loads((REPO / pool["native_summary"]["path"]).read_text()),
                           "command": pool["command"]} for pool in pools],
                "reproduce": "python3 scripts/family1_adaptive_edit_benchmark.py --resume",
                "scope": "Complete root-fixed edit paths of length <= radius, then optional accessible-root closure. All intermediates accessible. No score or target winning key enters generation.",
                "limitations": ["Scoring each candidate is a separate controlled experiment; this manifest certifies generation and exhaustive winner coverage only.",
                                "Target m7 provides the complete eight-winner set and H<=33 for all others; no complete pergraph score journal is assumed.",
                                "Complete radius 2 is tested only for target sizes 2..5. Intermediate sizes cannot exceed target for these net +1 paths, so the size20 representation cap prunes no valid path.",
                                "Historical random-seeded or budget-capped pools are not used."]}
    write_json(args.publish / "generation-manifest.json", manifest)
    summary = json.loads((args.out / "summary.json").read_text())
    summary.update({"generation_manifest": ref(args.publish / "generation-manifest.json"),
                    "coverage_csv": ref(args.publish / "coverage.csv"), "coverage_rows": results})
    write_json(args.publish / "summary.json", summary)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams["svg.fonttype"] = "none"
    figure, (recall_axis, count_axis) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                                   gridspec_kw={"height_ratios": [2.4, 1.4]})
    colors = ["#b84332", "#e28743", "#276c91", "#278a70"]
    configs = [("winners", False), ("winners", True), ("near2", False), ("near2", True)]
    for (parent_set, closure), color in zip(configs, colors):
        rows = sorted((row for row in results if row["radius"] == 1 and row["parent_set"] == parent_set
                       and row["root_closure"] == closure), key=lambda row: row["m"])
        label = ("Winner parents" if parent_set == "winners" else "All previous scores >= maximum - 2")
        label += " / " + ("all accessible roots" if closure else "root fixed")
        style = "-" if closure else "--"
        x = [row["m"] for row in rows]
        recall_axis.plot(x, [row["winner_recall"] for row in rows], style, color=color, marker="o", label=label)
        count_axis.plot(x, [row["candidate_count"] for row in rows], style, color=color, marker="o")
    recall_axis.yaxis.set_major_formatter(PercentFormatter(1))
    recall_axis.set_ylim(-0.06, 1.1)
    recall_axis.set_ylabel("Recall of all exhaustive winner ties")
    recall_axis.legend(loc="lower right", fontsize=8)
    recall_axis.grid(alpha=0.2)
    count_axis.set_yscale("log")
    count_axis.set_ylabel("Complete pool size")
    count_axis.set_xlabel("Target m (each parent has m - 1 vertices)")
    count_axis.set_xticks(args.sizes)
    count_axis.grid(alpha=0.2)
    last_m = max(args.sizes)
    for (parent_set, closure), color in zip(configs, colors):
        row = next(row for row in results if row["m"] == last_m and row["radius"] == 1
                   and row["parent_set"] == parent_set and row["root_closure"] == closure)
        count_axis.annotate(f"{row['candidate_count']:,}", (last_m, row["candidate_count"]),
                            xytext=(10, 0), textcoords="offset points", fontsize=8, color=color, va="center")
    figure.suptitle("Complete deterministic radius-1 edit pools against exhaustive Family 1 winners\nk = N/A (graph generation and exact-label coverage; no pair finder)", fontsize=12)
    figure.tight_layout(rect=(0, 0.015, 0.97, 0.92))
    args.figure.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.figure, format="svg", metadata={"Date": None})
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-adaptiveness-20261026/edit")
    parser.add_argument("--sizes", type=int, nargs="+", default=[2, 3, 4, 5, 6, 7])
    parser.add_argument("--radius2-max-m", type=int, default=5)
    parser.add_argument("--cap", type=int, default=10000000)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--publish", type=Path, default=REPO / "results/family1-adaptiveness-20261026/edit")
    parser.add_argument("--figure", type=Path, default=REPO / "output/figures/family1-adaptiveness/coverage.svg")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--near-top", type=Path, default=REPO / "results/family1-neighbor-seeds/near-top.jsonl")
    parser.add_argument("--distribution", type=Path, default=REPO / "results/family1-m1-m6/score-distributions.json")
    parser.add_argument("--winners", type=Path, nargs="+", default=[REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl"])
    args = parser.parse_args()
    assert args.cap > 0 and all(2 <= m <= 7 for m in args.sizes)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    parents = prepare_parents(args)
    executable = build_helper(args)
    pools = []
    for radius in [1, 2]:
        for target in args.sizes:
            if radius == 2 and target > args.radius2_max_m:
                continue
            for name in ["winners", "near2"]:
                pools.append(generate(args, executable, parents[(target, name)], target, name, radius))
    validate_sealed_pools(args, pools)
    write_json(args.out / "generation-seal.json", {"schema": 1, "k": None, "window": "N/A: generation only",
                "randomness": False, "target_truth_loaded": False, "pools": pools,
                "near_top_source": ref(args.near_top), "distribution_source": ref(args.distribution),
                "parent_selection_manifest": ref(args.near_top.with_name("summary.json")),
                "parent_label_original_source": json.loads(args.near_top.with_name("summary.json").read_text(encoding="utf-8-sig"))["sources"][0],
                "source_files": [ref(REPO / name) for name in ["scripts/family1_adaptive_edit_benchmark.py", "scripts/family1_study.py", "Family1EditSearch.cpp", "Family1EditSearch.h", "Family1LargeGraph.cpp", "Family1LargeGraph.h"]]})
    results = analyze(args, pools)
    publish(args, pools, results)
    print(json.dumps({"summary": str(args.out / "summary.json"), "comparisons": len(results),
                      "seconds": time.perf_counter() - started, "k": "N/A"}), flush=True)


if __name__ == "__main__":
    main()
