#!/usr/bin/env python3
"""Resumable heuristic search near earlier Family 1 leaders, with all roots.

Generation budgets select whole ordinary graph shapes. Every accessible root
of a selected shape is queued, including ties and roots without a useful bound.
Only an upper certificate can exclude a graph from beating the incumbent.
This is not exhaustive graph enumeration or a global upper certificate.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
from pathlib import Path
import subprocess

from family1_study import REPO, canonical_table, compact, file_hash, fixed_key, jsonl, table_from_key, validate_table
from family1_ancestry import relabel_with_ports
from family1_atlas_dataset import BASE_TABLE, certified_records, extension
from family1_edit_distance import neighbors


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(compact(value) + "\n" for value in values), encoding="utf-8")
    temporary.replace(path)


def identity(record):
    return record["m"], record["key"]


def normalize(record):
    raw_table = validate_table(record["canonical_table"])
    if "key" in record and table_from_key(record["key"], len(raw_table)) != raw_table:
        raise ValueError("source graph key disagrees with its transition table")
    table = canonical_table(raw_table)
    m = len(table)
    if record.get("m", m) != m:
        raise ValueError("record size/table mismatch")
    exact = record.get("merge_length") if record.get("status") == "exact" else None
    lower = exact if exact is not None else record.get("lower_bound", 1)
    upper = exact if exact is not None else record.get("upper_bound")
    if type(lower) is not int or lower < 1 or (upper is not None and (type(upper) is not int or upper < lower)):
        raise ValueError("invalid graph score interval")
    return {**record, "m": m, "key": fixed_key(table), "canonical_table": table,
            "lower_bound": lower, "upper_bound": upper,
            "status": "exact" if upper == lower else "bounded" if upper is not None else "lower-bound" if lower > 1 else "incomplete",
            "merge_length": lower if upper == lower else None}


def merge_record(records, record, provenance):
    record = normalize(record)
    key = identity(record)
    old = records.get(key)
    if old is None:
        old = {**record, "provenance": [], "observations": []}
        records[key] = old
    lower = max(old["lower_bound"], record["lower_bound"])
    uppers = [value for value in (old.get("upper_bound"), record.get("upper_bound")) if value is not None]
    upper = min(uppers) if uppers else None
    if upper is not None and lower > upper:
        raise ValueError(f"contradictory bounds for {key}: {lower}>{upper}")
    if provenance not in old["provenance"]:
        old["provenance"].append(provenance)
    observation = {"lower_bound": record["lower_bound"], "upper_bound": record.get("upper_bound"),
                   "reason": record.get("reason", ""), "provenance": provenance}
    if observation not in old["observations"]:
        old["observations"].append(observation)
    if record.get("upper_bound") == upper and record.get("witness"):
        old["witness"] = record["witness"]
    old.update({"lower_bound": lower, "upper_bound": upper,
                "status": "exact" if upper == lower else "bounded" if upper is not None else "lower-bound" if lower > 1 else "incomplete",
                "merge_length": lower if upper == lower else None})
    return old


def reachable(table, root):
    seen, pending = {root}, [root]
    while pending:
        for target in table[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def root_bundle(table):
    """Exact ordinary shape identity using all roots reaching the whole graph.

    The set of such rooted canonical forms is an ordinary-isomorphism invariant,
    including for accessible graphs which are not strongly connected.
    """
    table = validate_table(table)
    roots, excluded = {}, []
    for root in range(len(table)):
        reached = reachable(table, root)
        if len(reached) != len(table):
            excluded.append({"root": root, "reachable_states": len(reached),
                             "reason": "not an exact-m reachable seed from this root"})
            continue
        permutation = list(range(len(table)))
        permutation[0], permutation[root] = root, 0
        canonical = canonical_table(relabel_with_ports(table, permutation))
        key = fixed_key(canonical)
        item = roots.setdefault(key, {"m": len(table), "key": key,
                                      "canonical_table": canonical, "original_roots": []})
        item["original_roots"].append(root)
    hard_roots = sum(table[root][0] != table[root][1] for root in range(len(table)) if len(reachable(table, root)) == len(table))
    return {"m": len(table), "shape_key": min(roots), "table_before_root_closure": table,
            "roots": [roots[key] for key in sorted(roots)], "excluded_roots": excluded,
            "potential_hard_vertex_roots": hard_roots,
            "all_vertices_accounted_for": sum(len(item["original_roots"]) for item in roots.values()) + len(excluded) == len(table),
            "root_change_is_not_free_in_rooted_edit_metric": True}


@lru_cache(maxsize=64)
def unit_edges(table):
    return tuple(edge for _, edge in sorted(neighbors(table).items()))


def pattern_paths(table, pattern, budget, steps=()):
    if not pattern:
        yield table, steps
        return
    for edge in unit_edges(table):
        change = len(edge["after"]) - len(table)
        if change != {"G": 1, "R": 0, "S": -1}[pattern[0]]:
            continue
        if budget["edges"] >= budget["max_edges"]:
            budget["exhausted"] = True
            return
        budget["edges"] += 1
        yield from pattern_paths(edge["after"], pattern[1:], budget, steps + (edge,))


def generate_plan(m, parents, baseline, args, explicit_shape_seeds=()):
    parents = sorted(parents, key=lambda record: (-record["lower_bound"],
                                                 -record.get("root_robustness", {}).get("certified_vertex_roots_near_leader", 0),
                                                 -record.get("root_robustness", {}).get("certified_root_classes_near_leader", 0),
                                                 record.get("upper_bound") is not None,
                                                 -(record.get("upper_bound") or 10**9), record["key"]))
    patterns = ["G"]
    if args.radius >= 2:
        patterns += ["GR", "RG"]
    if args.radius >= 3:
        patterns += ["GRR", "RGR", "RRG", "GGS", "GSG", "SGG"]
    budget = {"edges": 0, "max_edges": args.path_budget, "exhausted": False}
    # Rotate patterns across parents so even a small breadth budget tries both
    # retarget/growth orders instead of spending everything on direct growth.
    streams = deque((parent, patterns[(index + phase) % len(patterns)],
                     pattern_paths(tuple(map(tuple, parent["canonical_table"])), patterns[(index + phase) % len(patterns)], budget))
                    for phase in range(len(patterns)) for index, parent in enumerate(parents))
    shapes, paths, seen_rooted = {}, [], set()
    per_parent = Counter()
    while streams and len(shapes) < args.candidate_shapes and not budget["exhausted"]:
        parent, pattern, stream = streams.popleft()
        try:
            table, steps = next(stream)
        except StopIteration:
            continue
        streams.append((parent, pattern, stream))
        key = fixed_key(table)
        path_id = len(paths)
        paths.append({"path_id": path_id, "m": m, "key": key, "canonical_table": table,
                      "parent_m": parent["m"], "parent_key": parent["key"], "pattern": pattern,
                      "rooted_edit_distance_upper_bound_before_root_closure": len(steps),
                      "steps": steps, "root_change_included_in_distance_bound": False})
        per_parent[parent["key"]] += 1
        if key in seen_rooted:
            continue
        seen_rooted.add(key)
        bundle = root_bundle(table)
        bundle["source_path_id"] = path_id
        bundle["parent_key"] = parent["key"]
        bundle["parent_lower_bound"] = parent["lower_bound"]
        bundle["parent_root_robustness"] = parent.get("root_robustness", {})
        bundle["path_length_before_root_closure"] = len(steps)
        shapes.setdefault(bundle["shape_key"], bundle)
    # Alternate indegree profiles when possible; this is a generation heuristic,
    # never a score exclusion. All unselected shapes remain in candidates.jsonl.
    ordered = sorted(shapes.values(), key=lambda bundle: (-bundle["parent_lower_bound"],
                                                        -bundle["parent_root_robustness"].get("certified_vertex_roots_near_leader", 0),
                                                        -bundle["parent_root_robustness"].get("certified_root_classes_near_leader", 0),
                                                        -bundle["potential_hard_vertex_roots"],
                                                        bundle["path_length_before_root_closure"], bundle["shape_key"]))
    chosen, remaining, profiles = [], [], set()
    for bundle in ordered:
        profile = tuple(sorted(Counter(target for row in bundle["table_before_root_closure"] for target in row).get(state, 0)
                               for state in range(m)))
        if profile not in profiles and len(chosen) < args.shapes_per_size:
            chosen.append(bundle)
            profiles.add(profile)
        else:
            remaining.append(bundle)
    for bundle in remaining:
        if len(chosen) < args.shapes_per_size:
            chosen.append(bundle)
    baseline_bundle = root_bundle(baseline["canonical_table"])
    baseline_bundle.update({"baseline": True, "construction": baseline["construction"]})
    selected = {bundle["shape_key"]: bundle for bundle in chosen}
    if baseline_bundle["shape_key"] in selected:
        selected[baseline_bundle["shape_key"]].update({"baseline": True, "construction": baseline["construction"],
                                                      "baseline_original_root_bundle": baseline_bundle})
    else:
        selected[baseline_bundle["shape_key"]] = baseline_bundle
    for seed in explicit_shape_seeds:
        explicit = root_bundle(seed["canonical_table"])
        seed_reference = {"m": seed["m"], "key": seed["key"], "lower_bound": seed["lower_bound"],
                          "upper_bound": seed.get("upper_bound"), "provenance": seed.get("provenance", [])}
        if explicit["shape_key"] in selected:
            selected[explicit["shape_key"]].setdefault("explicit_shape_seed_records", []).append(seed_reference)
        else:
            explicit.update({"explicit_shape_seed": True, "explicit_shape_seed_records": [seed_reference]})
            selected[explicit["shape_key"]] = explicit
    return {"schema": 1, "m": m, "source_parents": parents,
            "source_parent_path_counts": dict(per_parent), "patterns": patterns,
            "path_edges_examined": budget["edges"], "generation_paths": paths,
            "candidate_shapes": ordered, "selected_shapes": list(selected.values()),
            "generation_complete_within_requested_patterns": not streams and not budget["exhausted"],
            "generation_stop_reason": "path-budget" if budget["exhausted"] else "shape-budget" if streams else "patterns-exhausted",
            "global_enumeration_complete": False,
            "selection": "bounded heuristic edited-shape breadth with indegree diversity; constructive baseline and every explicitly supplied same-size shape are additional; no score-based exclusion"}


def rank_parent_roots(parents, records):
    """Add a secondary robustness rank using certified LOWER bounds only."""
    if not parents:
        return []
    m = parents[0]["m"]
    leader = max(record["lower_bound"] for (size, _), record in records.items() if size == m)
    target = max(1, leader - 2)
    ranked = []
    for parent in parents:
        bundle = root_bundle(parent["canonical_table"])
        strong = [root for root in bundle["roots"] if records.get((m, root["key"]), {}).get("lower_bound", 1) >= target]
        ranked.append({**parent, "root_robustness": {
            "previous_size_incumbent_lower_bound": leader, "near_leader_threshold": target,
            "certified_vertex_roots_near_leader": sum(len(root["original_roots"]) for root in strong),
            "certified_root_classes_near_leader": len(strong),
            "accessible_vertex_roots": sum(len(root["original_roots"]) for root in bundle["roots"]),
            "distinct_accessible_root_classes": len(bundle["roots"]),
            "inaccessible_vertex_roots": len(bundle["excluded_roots"]),
            "uses_upper_bounds_as_lower_evidence": False,
        }})
    return ranked


def load_inputs(args):
    known, provenance = certified_records(REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl")
    records = {}
    for record in known:
        merge_record(records, record, {"kind": "certified-complete-small-case-maximizer", "certificate": record["source_certificate"]})
    for path in args.seeds:
        source = {"kind": "optional-seed-observation", "path": str(path.resolve()), "sha256": file_hash(path)}
        for _, record in jsonl(path):
            merge_record(records, record, {**source, "original_record": record})
    for path in args.shape_seeds:
        source = {"kind": "explicit-shape-seed", "path": str(path.resolve()), "sha256": file_hash(path)}
        for _, record in jsonl(path):
            merge_record(records, record, {**source, "original_record": record})
    baselines = {}
    for _, record in jsonl(args.baselines):
        if record["m"] < 8:
            continue
        expected = extension(record["m"])
        if (record["key"] != expected["key"] or record["construction"] != expected["construction"]
                or tuple(map(tuple, record["canonical_table"])) != tuple(map(tuple, expected["canonical_table"]))
                or record.get("lower_bound") != 34 or record.get("upper_bound") is not None
                or record.get("merge_length") is not None or record.get("witness") is not None):
            raise ValueError("baseline differs from the checked static-mask projection construction")
        baselines[record["m"]] = record
        merge_record(records, record, {"kind": "static-mask-projection", "source": str(args.baselines.resolve()),
                                      "sha256": file_hash(args.baselines)})
    if any(m not in baselines for m in range(args.min_m, args.max_m + 1)):
        raise ValueError("missing a constructive baseline size")
    return records, baselines, provenance


def observation_from_native(answer, root, args, proof):
    if answer["key"] != root["key"] or answer["m"] != root["m"] or answer["length"] != args.threshold:
        raise ValueError("native query result belongs to another graph or threshold")
    table = validate_table(answer["canonical_table"])
    if fixed_key(canonical_table(table)) != root["key"] or table != tuple(map(tuple, root["canonical_table"])):
        raise ValueError("native canonical table differs from its graph key")
    decision = answer["decision"]
    metric = getattr(args, "query_method", "threshold") in ("metric", "finder")
    if metric:
        if (decision not in ("collision", "unknown") or answer["lower_bound"] != 1
                or (decision == "unknown" and (answer["upper_bound"] is not None or answer.get("witness") is not None))
                or (decision == "collision" and (type(answer["upper_bound"]) is not int
                                                or not 1 <= answer["upper_bound"] <= args.threshold))):
            raise ValueError("invalid native sampling interval; misses cannot certify a lower bound")
    else:
        expected = {"no_collision": (args.threshold + 1, None), "collision": (1, args.threshold), "unknown": (1, None)}
        if decision not in expected or (answer["lower_bound"], answer["upper_bound"]) != expected[decision]:
            raise ValueError("invalid native threshold interval")
    if decision == "collision":
        witness = answer.get("witness")
        if (not isinstance(witness, list) or len(witness) != 2 or witness[0] == witness[1]
                or any(not isinstance(word, str) or len(word) != answer["upper_bound"] or set(word) - {"0", "1"} for word in witness)
                or answer.get("scalar_witness_masks_verified") != 1 << root["m"]):
            raise ValueError("native collision lacks its complete scalar static-mask replay")
    return {"m": root["m"], "key": root["key"], "canonical_table": root["canonical_table"],
            "status": "bounded" if decision == "collision" else "lower-bound" if decision == "no_collision" else "incomplete",
            "lower_bound": answer["lower_bound"], "upper_bound": answer["upper_bound"],
            "witness": answer.get("witness"), "reason": answer.get("reason", ""),
            "decision": decision, "native_result": proof,
            "native_executable_sha256": file_hash(args.exe), "native_answer": answer}


def replay_observation(answer, args):
    proof = answer["native_result"]
    path = Path(proof["path"])
    if file_hash(path) != proof["sha256"]:
        raise ValueError("native result integrity mismatch")
    native = json.loads(path.read_text(encoding="utf-8-sig"))
    root = {"m": native["m"], "key": native["key"], "canonical_table": native["canonical_table"]}
    rebuilt = observation_from_native(native, root, args, proof)
    if compact(answer) != compact(rebuilt):
        raise ValueError("journal observation disagrees with its hashed native result")
    return rebuilt


def query_graph(root, args):
    directory = args.out / "queries" / f"m{root['m']}" / root["key"] / f"length-{args.threshold}"
    command = [str(args.exe), "--graph", root["key"], "--length", str(args.threshold), "--out", str(directory)]
    method = getattr(args, "query_method", "threshold")
    metric = method in ("metric", "finder")
    if metric:
        command += ["--mode", "finder" if method == "finder" else "guided", "--samples", str(args.samples),
                    "--seed", str(args.sampling_seed), "--beam-width", str(args.beam_width),
                    "--masks", str(args.projection_masks)]
        if method == "finder":
            command += ["--window-k", str(args.window_k), "--tail-threshold", str(args.tail_threshold),
                        "--tail-max-states", str(args.tail_max_states)]
            if args.best_of_seeds:
                command.append("--best-of-seeds")
        else:
            command += ["--lookahead", str(args.lookahead)]
        if args.full_agreement and method != "finder":
            command.append("--full-agreement")
        if getattr(args, "full_guidance", False) and method != "finder":
            command.append("--full-guidance")
    else:
        command += ["--timeout-ms", str(args.timeout_ms), "--solve-timeout-ms", str(args.solve_timeout_ms),
                    "--max-refinements", str(args.max_refinements), "--projection-masks", str(args.projection_masks)]
    if (directory / "run.json").exists():
        command.append("--resume")
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                            timeout=max(300 if metric else 60, args.timeout_ms / 1000 + 60))
    if result.returncode:
        raise RuntimeError(f"native query failure for {root['key']}: {result.stderr[-2000:]}")
    result_path = directory / "result.json"
    answer = json.loads(result_path.read_text(encoding="utf-8-sig"))
    if json.loads(result.stdout) != answer:
        raise ValueError("native stdout differs from its published result")
    if (directory / "result.sha256").read_text().strip() != file_hash(result_path):
        raise ValueError("native result checksum mismatch")
    return observation_from_native(answer, root, args, {"path": str(result_path.resolve()), "sha256": file_hash(result_path)})


def attach_query_diagnostics(row, answer, args):
    row["threshold_decision"] = answer["decision"]  # Historical export field.
    row["query_decision"] = answer["decision"]
    row["query_method"] = getattr(args, "query_method", "threshold")
    if row["query_method"] in ("metric", "finder"):
        native = answer["native_answer"]
        row["metric_search"] = {key: value for key, value in native.items()
                                if key not in ("canonical_table", "witness", "source_key", "key")}


def add_plan_records(records, plan):
    for bundle in plan["candidate_shapes"] + plan["selected_shapes"]:
        for root in bundle["roots"]:
            merge_record(records, {**root, "lower_bound": 1, "upper_bound": None},
                         {"kind": "root-closure", "shape_key": bundle["shape_key"], "original_roots": root["original_roots"],
                          "selected": bundle in plan["selected_shapes"], "edit_bound_applies_before_root_change_only": True})
            if root["canonical_table"][0][0] == root["canonical_table"][0][1]:
                merge_record(records, {**root, "lower_bound": 1, "upper_bound": 1, "witness": ["0", "1"]},
                             {"kind": "coincident-root-ports", "reason": "Both one-letter words reach the same state under every static mask."})
    for bundle in plan["selected_shapes"]:
        if not bundle.get("baseline"):
            continue
        original = bundle.get("baseline_original_root_bundle", bundle)
        projection = original["construction"]["canonical_projection_to_base"]
        for root in original["roots"]:
            lifting_roots = [vertex for vertex in root["original_roots"] if projection[vertex] == 0]
            if lifting_roots:
                merge_record(records, {**root, "lower_bound": 34, "upper_bound": None},
                             {"kind": "static-mask-projection-at-rerooted-start", "base_key": fixed_key(BASE_TABLE),
                              "base_lower_bound": 34, "original_roots_mapping_to_base_root": lifting_roots,
                              "construction": original["construction"]})


def export(args, records, plans, completed, generation_only=False):
    values = [records[key] for key in sorted(records)]
    write_jsonl(args.out / "records.jsonl", values)
    sizes, incumbent, possible, profiles = [], [], [], []
    for m in range(1, args.max_m + 1):
        rows = [record for record in values if record["m"] == m]
        if not rows:
            continue
        leader = max(record["lower_bound"] for record in rows)
        incumbent.extend(record for record in rows if record["lower_bound"] == leader)
        possible.extend(record for record in rows if record["upper_bound"] is None or record["upper_bound"] >= leader)
        plan = plans.get(m)
        selected_roots = {root["key"] for bundle in plan["selected_shapes"] for root in bundle["roots"]} if plan else set()
        scored = selected_roots.intersection(key for size, key in completed if size == m)
        sizes.append({"m": m, "best_known_lower_bound": leader, "best_lower_bound_ties": sum(record["lower_bound"] == leader for record in rows),
                      "observed_rooted_classes": len(rows), "selected_root_classes": len(selected_roots),
                      "threshold_queries_complete": len(scored), "pending_selected_roots": len(selected_roots - scored),
                      "unknown_threshold_results": sum(records[(m, key)].get("threshold_decision") == "unknown" for key in scored),
                      "query_method": getattr(args, "query_method", "threshold"),
                      "sampling_hits": sum(records[(m, key)].get("query_method") in ("metric", "finder") and records[(m, key)].get("query_decision") == "collision" for key in scored),
                      "sampling_misses": sum(records[(m, key)].get("query_method") in ("metric", "finder") and records[(m, key)].get("query_decision") == "unknown" for key in scored),
                      "potential_competitive_classes": sum(record["upper_bound"] is None or record["upper_bound"] >= leader for record in rows),
                      "certified_strictly_below_incumbent": sum(record["upper_bound"] is not None and record["upper_bound"] < leader for record in rows),
                      "maximum_value_certified": m <= 7, "maximizing_collection_complete": m <= 7,
                      "global_certificate_origin": "inherited complete small-case certificate, not this local search" if m <= 7 else None,
                      "local_record_coverage_exhaustive": False, "enumeration_complete": False,
                      "all_selected_roots_queried": selected_roots == scored,
                      "generation_complete_within_requested_patterns": plan["generation_complete_within_requested_patterns"] if plan else None})
        if plan:
            for bundle in plan["selected_shapes"]:
                roots = []
                for root in bundle["roots"]:
                    record = records[(m, root["key"])]
                    roots.append({**root, "lower_bound": record["lower_bound"], "upper_bound": record["upper_bound"],
                                  "threshold_decision": record.get("threshold_decision"), "query_complete": (m, root["key"]) in completed,
                                  "query_method": record.get("query_method"), "query_decision": record.get("query_decision"),
                                  "metric_search": record.get("metric_search"),
                                  "can_still_tie_or_beat_incumbent": record["upper_bound"] is None or record["upper_bound"] >= leader})
                profiles.append({**bundle, "roots": roots, "all_accessible_roots_queried": all(root["query_complete"] for root in roots),
                                 "size_incumbent_lower_bound": leader})
    write_jsonl(args.out / "incumbents.jsonl", incumbent)
    write_jsonl(args.out / "potential-competitive.jsonl", possible)
    write_jsonl(args.out / "root-profiles.jsonl", profiles)
    summary = {"schema": 1, "method": "bounded-root-aware-edit-neighborhood-search", "min_m": args.min_m, "max_m": args.max_m,
               "enumeration_complete": False, "maximum_value_certified": False, "maximizing_collection_complete": False,
               "all_selected_query_traversal_complete": all(item["pending_selected_roots"] == 0 for item in sizes if item["m"] >= args.min_m),
               "generation_only": generation_only, "scoring_threshold": args.threshold,
               "query_method": getattr(args, "query_method", "threshold"),
               "sampling_length_cap": args.threshold if getattr(args, "query_method", "threshold") in ("metric", "finder") else None,
               "metric_guidance_scope": "all-static-masks" if getattr(args, "full_guidance", False) or getattr(args, "query_method", "threshold") == "finder" else "sampled-masks" if getattr(args, "query_method", "threshold") == "metric" else None,
               "root_closure": "Every vertex is accounted for; all whole-graph-accessible root classes of every selected shape are queued. Other roots are reported with their smaller reachable count.",
               "edit_distances": "Only saved path-length upper bounds from a fixed parent root before root closure; changing the root is not a free rooted edit.",
               "coverage": "Candidate and shape budgets limit heuristic breadth. Unselected, pending, and UNKNOWN graphs remain recorded. Only certified upper bounds exclude beating an incumbent.",
               "inherited_small_global_proofs": "Sizes 1..7 and their complete maximizing collections are imported from pinned earlier certificates. This run does not enumerate those sizes; its local record coverage is not exhaustive.",
               "sizes": sizes, "native_query_results": len(completed), "root_profiles": len(profiles)}
    atomic_json(args.out / "summary.json", summary)
    return summary


def run(args):
    records, baselines, proof_sources = load_inputs(args)
    sources = [args.baselines] + args.seeds + args.shape_seeds
    configuration = {key: value for key, value in vars(args).items() if key not in ("resume", "generate_only", "limit_graphs", "out")}
    configuration = {key: str(value.resolve()) if isinstance(value, Path) else [str(path.resolve()) for path in value] if key in ("seeds", "shape_seeds") else value for key, value in configuration.items()}
    configuration.update({"schema": 1, "input_hashes": {str(path.resolve()): file_hash(path) for path in sources},
                          "small_certificate_sources": proof_sources,
                          "program_hashes": {name: file_hash(REPO / "scripts" / name) for name in (
                              "family1_neighbor_search.py", "family1_edit_distance.py", "family1_ancestry.py",
                              "family1_study.py", "family1_atlas_dataset.py", "family1_certified_tikz.py")},
                          "native_executable_sha256": file_hash(args.exe) if args.exe.is_file() else None})
    if getattr(args, "query_method", "threshold") in ("metric", "finder"):
        configuration["native_source_hashes"] = {name: file_hash(REPO / name) for name in (
            "family1_sample.cpp", "Family1CliArtifacts.h", "Family1PairAgreement.h", "Family1FullGuidance.h",
            "HardPairFinder.h", "HardPairPrefixSeeds.h", "HardPairViability.h")}
    args.out.mkdir(parents=True, exist_ok=True)
    config_path = args.out / "run.json"
    if config_path.exists():
        if not args.resume:
            raise ValueError("existing run requires --resume")
        if json.loads(config_path.read_text()) != json.loads(compact(configuration)):
            raise ValueError("resume settings or pinned input sources differ")
    else:
        if any(args.out.iterdir()):
            raise ValueError("new run requires an empty output directory")
        atomic_json(config_path, configuration)
    completed, plans = set(), {}
    journal = args.out / "query-results.jsonl"
    if journal.exists():
        data = journal.read_bytes()
        if data and not data.endswith(b"\n"):
            data = data[:data.rfind(b"\n") + 1]
            journal.write_bytes(data)
        for _, answer in jsonl(journal):
            answer = replay_observation(answer, args)
            if identity(answer) in completed:
                raise ValueError("duplicate completed query in journal")
            proof = answer["native_result"]
            row = merge_record(records, answer, {"kind": "native-fixed-length-query", "result": proof})
            attach_query_diagnostics(row, answer, args)
            completed.add(identity(answer))
    propagated = {key for key in records if key[0] == args.min_m - 1}
    launched = 0
    for m in range(args.min_m, args.max_m + 1):
        plan_path = args.out / "plans" / f"m{m}" / "plan.json"
        if plan_path.exists():
            manifest = json.loads((plan_path.parent / "integrity.json").read_text())
            if (set(manifest["sha256"]) != {"plan.json", "generation-paths.jsonl", "candidates.jsonl"}
                    or any(file_hash(plan_path.parent / name) != digest for name, digest in manifest["sha256"].items())):
                raise ValueError("cached generation plan integrity mismatch")
            plan = json.loads(plan_path.read_text())
        else:
            parents = [records[key] for key in sorted(propagated) if key[0] == m - 1]
            parents += [record for key, record in records.items() if key[0] == m - 1 and key not in propagated
                        and any(item.get("kind") == "optional-seed-observation" for item in record["provenance"])]
            if not parents:
                raise ValueError(f"no previous-size parents for m={m}")
            parents = rank_parent_roots(parents, records)
            explicit_seeds = [record for (size, _), record in records.items() if size == m
                              and any(item.get("kind") == "explicit-shape-seed" for item in record["provenance"])]
            plan = generate_plan(m, parents, baselines[m], args, explicit_seeds)
            atomic_json(plan_path, plan)
            write_jsonl(plan_path.parent / "generation-paths.jsonl", plan["generation_paths"])
            write_jsonl(plan_path.parent / "candidates.jsonl", plan["candidate_shapes"])
            atomic_json(plan_path.parent / "integrity.json", {"schema": 1, "sha256": {
                name: file_hash(plan_path.parent / name) for name in ("plan.json", "generation-paths.jsonl", "candidates.jsonl")}})
            print(f"m={m} generated_shapes={len(plan['candidate_shapes'])} selected_shapes={len(plan['selected_shapes'])} generation={plan['generation_stop_reason']}", flush=True)
        plans[m] = plan
        add_plan_records(records, plan)
        roots = {root["key"]: root for bundle in plan["selected_shapes"] for root in bundle["roots"]}
        propagated = {(m, key) for key in roots}
        if not args.generate_only:
            if not args.exe.is_file():
                raise ValueError(f"missing native threshold executable: {args.exe}")
            pending = [roots[key] for key in sorted(roots) if (m, key) not in completed]
            with ThreadPoolExecutor(max_workers=args.jobs) as workers:
                for offset in range(0, len(pending), args.jobs):
                    batch = pending[offset:offset + args.jobs]
                    if args.limit_graphs:
                        batch = batch[:max(0, args.limit_graphs - launched)]
                    if not batch:
                        break
                    futures = [workers.submit(query_graph, root, args) for root in batch]
                    launched += len(batch)
                    for future in futures:
                        answer = future.result()
                        with journal.open("a", encoding="utf-8") as target:
                            target.write(compact(answer) + "\n")
                            target.flush()
                        row = merge_record(records, answer, {"kind": "native-fixed-length-query", "result": answer["native_result"]})
                        attach_query_diagnostics(row, answer, args)
                        completed.add(identity(answer))
                    export(args, records, plans, completed)
            if any((m, key) not in completed for key in roots):
                break
        export(args, records, plans, completed, args.generate_only)
    summary = export(args, records, plans, completed, args.generate_only)
    print(compact({"out": str(args.out), "queries": len(completed), "selected_traversal_complete": summary["all_selected_query_traversal_complete"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "out/family1-neighbor-search")
    parser.add_argument("--exe", type=Path, help="defaults to the native executable for the selected query method")
    parser.add_argument("--query-method", choices=("threshold", "metric", "finder"), default="threshold")
    parser.add_argument("--samples", type=int, default=32, help="guided prefix-seed budget per rooted graph")
    parser.add_argument("--sampling-seed", type=int, default=1088)
    parser.add_argument("--beam-width", type=int)
    parser.add_argument("--lookahead", type=int)
    parser.add_argument("--full-agreement", action="store_true", help="record exact all-mask scores along the best native trace")
    parser.add_argument("--full-guidance", action="store_true", help="use the exact all-static-mask agreement count inside the native beam")
    parser.add_argument("--window-k", type=int, default=2)
    parser.add_argument("--tail-threshold", type=int, default=4)
    parser.add_argument("--tail-max-states", type=int, default=100000)
    parser.add_argument("--best-of-seeds", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seeds", type=Path, action="append", default=[])
    parser.add_argument("--shape-seeds", type=Path, action="append", default=[],
                        help="queue every supplied same-size shape in addition to edited selections and baseline, with all roots")
    parser.add_argument("--baselines", type=Path, default=REPO / "results/family1-atlas-current/champions.jsonl")
    parser.add_argument("--min-m", type=int, default=8)
    parser.add_argument("--max-m", type=int, default=20)
    parser.add_argument("--radius", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--shapes-per-size", type=int, default=2, help="edited shapes; constructive baseline shape is additional")
    parser.add_argument("--candidate-shapes", type=int, default=128)
    parser.add_argument("--path-budget", type=int, default=4096, help="primitive path edges examined per size")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--threshold", type=int, default=34)
    parser.add_argument("--timeout-ms", type=int, default=1000)
    parser.add_argument("--solve-timeout-ms", type=int, default=1000)
    parser.add_argument("--max-refinements", type=int, default=64)
    parser.add_argument("--projection-masks", type=int, default=64)
    parser.add_argument("--limit-graphs", type=int, default=0, help="new queries this invocation; pending root bundles remain explicit")
    parser.add_argument("--generate-only", action="store_true", help="freeze deterministic pools without running native queries")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.beam_width is None:
        args.beam_width = 4 if args.full_guidance or args.query_method == "finder" else 8
    if args.lookahead is None:
        args.lookahead = 1 if args.full_guidance else 2
    if args.exe is None:
        args.exe = REPO / "out/build/msvc-vcpkg/Release" / ("Family1Sample.exe" if args.query_method in ("metric", "finder") else "Family1Threshold.exe")
    if not 8 <= args.min_m <= args.max_m <= 20 or not 1 <= args.jobs <= 32 or not 1 <= args.projection_masks <= 64:
        parser.error("require sizes8..20, jobs1..32, masks1..64")
    if min(args.shapes_per_size, args.candidate_shapes, args.path_budget, args.threshold, args.timeout_ms,
           args.solve_timeout_ms, args.max_refinements, args.samples, args.beam_width) < 1 or args.limit_graphs < 0 or args.threshold > 4096:
        parser.error("positive budgets and threshold1..4096 required")
    if args.samples > 1000000000 or args.beam_width > 32 or not 0 <= args.lookahead <= (1 if args.full_guidance else 4) or not 0 <= args.sampling_seed < 1 << 64:
        parser.error("require samples<=1e9, beam-width<=32, lookahead0..1 for full guidance or0..4 otherwise, and sampling-seed in uint64 range")
    if not 1 <= args.window_k <= 6 or not 0 <= args.tail_threshold <= 1024 or not 1 <= args.tail_max_states <= 10000000:
        parser.error("require window-k1..6, tail-threshold0..1024, and tail-max-states1..10000000")
    run(args)


if __name__ == "__main__":
    main()
