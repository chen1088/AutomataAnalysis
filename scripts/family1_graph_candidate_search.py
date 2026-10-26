#!/usr/bin/env python3
"""General, resumable Family1 edit-candidate scoring with a bounded portfolio.

The scorer reads only a graph and explicit search settings, never saved words
or a graph's known H. A collision certifies an UPPER bound. Misses certify no
lower bound. Imported intervals are separately attributed to supplied sources.
Every accessible root of each selected ordinary shape is retained.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from family1_study import canonical_table, fixed_key, table_from_key, validate_table

REPO = Path(__file__).resolve().parents[1]


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def reference(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest(path)}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path, rows):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(compact(row) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def jsonl(path):
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            yield number, json.loads(line)


def graph_metadata(row):
    """Whitelist graph fields: truth/witness fields cannot enter the scorer."""
    if "canonical_table" in row:
        raw = validate_table(row["canonical_table"])
    elif "key" in row and "m" in row:
        raw = validate_table(table_from_key(row["key"], row["m"]))
    else:
        raise ValueError("graph requires canonical_table or m/key")
    if row.get("m", len(raw)) != len(raw):
        raise ValueError("graph size/table mismatch")
    if "key" in row and table_from_key(row["key"], len(raw)) != raw:
        raise ValueError("graph key/table mismatch")
    table = canonical_table(raw)
    return {"m": len(table), "key": fixed_key(table), "canonical_table": table}


def reachable(table, root):
    reached, todo = {root}, [root]
    while todo:
        for target in table[todo.pop()]:
            if target not in reached:
                reached.add(target)
                todo.append(target)
    return reached


def root_bundle(row):
    graph = graph_metadata(row)
    table, m = graph["canonical_table"], graph["m"]
    roots, excluded = {}, []
    for root in range(m):
        count = len(reachable(table, root))
        if count != m:
            excluded.append({"vertex": root, "reachable_count": count})
            continue
        permutation = list(range(m))
        permutation[0], permutation[root] = root, 0
        relabeled = [None] * m
        for source, targets in enumerate(table):
            relabeled[permutation[source]] = tuple(permutation[target] for target in targets)
        canonical = canonical_table(relabeled)
        key = fixed_key(canonical)
        item = roots.setdefault(key, {"m": m, "key": key, "canonical_table": canonical,
                                      "vertices_in_shape_table": []})
        item["vertices_in_shape_table"].append(root)
    return {"m": m, "shape_key": min(roots), "shape_table": table,
            "roots": [roots[key] for key in sorted(roots)], "excluded_vertices": excluded,
            "all_vertices_accounted_for": sum(len(item["vertices_in_shape_table"]) for item in roots.values()) + len(excluded) == m,
            "rerooting_is_separate_from_root_fixed_edit_distance": True}


@lru_cache(maxsize=20)
def static_mask_planes(m):
    count = 1 << m
    byte_count = (count + 7) // 8
    planes = []
    for state in range(m):
        if state < 3:
            pattern = (0xAA, 0xCC, 0xF0)[state]
            data = bytes([pattern]) * byte_count
        else:
            run = (1 << state) // 8
            data = (b"\0" * run + b"\xff" * run) * (byte_count // (2 * run))
        planes.append(int.from_bytes(data, "little") & ((1 << count) - 1))
    return tuple(planes)


def product_planes(table, word):
    """Independent arbitrary-precision bitsets, one bit per static mask."""
    m = len(table)
    sigmas = static_mask_planes(m)
    state_planes = [0] * m
    state_planes[0] = (1 << (1 << m)) - 1
    for symbol in word:
        bit = int(symbol)
        next_planes = [0] * m
        for state, active in enumerate(state_planes):
            if not active:
                continue
            ones = active & sigmas[state]
            zeros = active ^ ones
            next_planes[table[state][bit]] |= zeros
            next_planes[table[state][bit ^ 1]] |= ones
        state_planes = next_planes
    return tuple(state_planes)


def verify_witness(table, words, cap=None):
    if (not isinstance(words, list) or len(words) != 2 or any(not isinstance(word, str) for word in words)
            or not words[0] or words[0] == words[1] or len(words[0]) != len(words[1])
            or set(words[0] + words[1]) - {"0", "1"} or (cap is not None and len(words[0]) > cap)):
        raise ValueError("invalid distinct equal-length binary witness")
    first, second = product_planes(table, words[0]), product_planes(table, words[1])
    if first != second:
        raise ValueError("witness fails exact independent all-static-mask replay")
    count = 1 << len(table)
    width = (count + 7) // 8
    state_digest = hashlib.sha256(b"".join(plane.to_bytes(width, "little") for plane in first)).hexdigest()
    return {"method": "python-arbitrary-precision-all-static-mask-bitsets", "mask_count": count,
            "complete_state_vectors_compared": True, "product_state_sha256": state_digest}


def permutation_dfa_count(table):
    """Exact count of distinct both-letter-permutation realizations via XOR."""
    m = len(table)
    incoming = [[] for _ in range(m)]
    for source, ports in enumerate(table):
        for port, target in enumerate(ports):
            incoming[target].append((source, port))
    if any(len(values) != 2 for values in incoming):
        return 0
    adjacency = [[] for _ in range(m)]
    for ((a, p), (b, q)) in incoming:
        parity = 1 ^ p ^ q
        adjacency[a].append((b, parity))
        adjacency[b].append((a, parity))
    labels, components = {}, 0
    for start in range(m):
        if start in labels:
            continue
        labels[start] = 0
        todo, relevant = [start], False
        while todo:
            source = todo.pop()
            relevant |= table[source][0] != table[source][1]
            for target, parity in adjacency[source]:
                value = labels[source] ^ parity
                if target in labels:
                    if labels[target] != value:
                        return 0
                else:
                    labels[target] = value
                    todo.append(target)
        components += relevant
    return 1 << components


def stage_settings(graph, args):
    """Calibrated-style stages with explicit, conservative memory scaling."""
    m = graph["m"]
    profiles = permutation_dfa_count(graph["canonical_table"])
    stages = []
    for index in ((1, 2) if args.enable_stage2 else (1,)):
        k = getattr(args, f"stage{index}_k")
        requested_words = getattr(args, f"stage{index}_prefix_words")
        # Pair tracker worst case plus simultaneous beam/pool/DFS copies.
        tracker_bytes = m * (1 << m) // 4
        pair_working_bytes = (3 * args.beam_width + k + 8) * tracker_bytes
        available = args.memory_mib * (1 << 20) - pair_working_bytes
        per_word = 3 * (128 + 4 * profiles)
        word_limit = max(1, available // per_word)
        words = min(requested_words, 1 << (word_limit.bit_length() - 1))
        stages.append({"name": f"stage{index}", "window_k": k, "beam_width": args.beam_width,
                       "samples": getattr(args, f"stage{index}_samples"),
                       "prefix_pairs": getattr(args, f"stage{index}_prefix_pairs"),
                       "prefix_depth": getattr(args, f"stage{index}_prefix_depth"), "prefix_words": words,
                       "prefix_samples_per_depth": min(args.prefix_samples_per_depth, words),
                       "distance_coordinates": 0 if index == 1 else min(1024, 1 << m),
                       "ranking": "drop" if index == 1 else "remaining", "common_prefix_depth": 0 if index == 1 else 8,
                       "expansions": getattr(args, f"stage{index}_expansions"),
                       "timeout_seconds": getattr(args, f"stage{index}_timeout"),
                       "tail_threshold": args.tail_threshold, "tail_max_states": args.tail_max_states,
                       "viability_coordinates": min(args.viability_coordinates, 1 << m),
                       "seed": args.seed, "memory_budget_mib": args.memory_mib,
                       "memory_estimate_is_not_an_os_limit": True, "estimated_pair_working_bytes": pair_working_bytes,
                       "distinct_permutation_dfas": profiles, "requested_prefix_words": requested_words,
                       "prefix_word_budget_scaled": words != requested_words,
                       "pair_working_estimate_exceeds_budget": available <= 0})
    return stages


def native_command(executable, graph, stage, cap, output):
    """No score, truth field, or saved witness can enter this command."""
    return [str(executable), "--graph", graph["key"], "--out", str(output), "--mode", "finder",
            "--length", str(cap), "--samples", str(stage["samples"]), "--seed", str(stage["seed"]),
            "--window-k", str(stage["window_k"]), "--beam-width", str(stage["beam_width"]),
            "--tail-threshold", str(stage["tail_threshold"]), "--tail-max-states", str(stage["tail_max_states"]),
            "--prefix-max-pairs", str(stage["prefix_pairs"]), "--prefix-depth", str(stage["prefix_depth"]),
            "--prefix-max-words", str(stage["prefix_words"]),
            "--prefix-samples-per-depth", str(stage["prefix_samples_per_depth"]),
            "--max-expansions", str(stage["expansions"]), "--distance-coordinates", str(stage["distance_coordinates"]),
            "--beam-ranking", stage["ranking"], "--prefix-common-depth", str(stage["common_prefix_depth"]),
            "--viability-coordinates", str(stage["viability_coordinates"])]


def normalize_native(native, graph, cap):
    if (native.get("m") != graph["m"] or native.get("key") != graph["key"]
            or graph_metadata(native) != graph or native.get("mode") != "finder" or native.get("length") != cap
            or native.get("lower_bound") != 1 or native.get("shortest_proved") is not False
            or native.get("global_maximum_certified") is not False):
        raise ValueError("native identity/configuration/proof scope mismatch")
    answer = {"m": graph["m"], "key": graph["key"], "length_cap": cap,
              "decision": native.get("decision"), "lower_bound": 1, "upper_bound": native.get("upper_bound"),
              "witness": native.get("witness"), "verification": None}
    if answer["decision"] == "collision":
        answer["verification"] = verify_witness(graph["canonical_table"], answer["witness"], cap)
        if (type(answer["upper_bound"]) is not int or answer["upper_bound"] != len(answer["witness"][0])
                or native.get("scalar_witness_masks_verified") != 1 << graph["m"]):
            raise ValueError("native upper certificate inconsistent with replay")
    elif answer["decision"] != "unknown" or answer["upper_bound"] is not None or answer["witness"] is not None:
        raise ValueError("sampling miss contains an unsupported bound")
    return answer


def validate_native_configuration(path, native, graph, stage, cap):
    config = read_json(path)
    expected = {"m": graph["m"], "key": graph["key"], "source_key": graph["key"], "mode": "finder",
                "length": cap, "samples": stage["samples"], "seed": stage["seed"],
                "window_k": stage["window_k"], "beam_width": stage["beam_width"],
                "tail_threshold": stage["tail_threshold"], "tail_max_states": stage["tail_max_states"],
                "prefix_depth": stage["prefix_depth"], "prefix_max_words": stage["prefix_words"],
                "prefix_max_pairs": stage["prefix_pairs"], "prefix_samples_per_depth": stage["prefix_samples_per_depth"],
                "viability_coordinates": stage["viability_coordinates"], "first_prefix": "", "second_prefix": "",
                "full_guidance_max_nodes": stage["expansions"]}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("native settings do not match the pinned portfolio stage")
    for key, value, default in (("distance_coordinates", stage["distance_coordinates"], 0),
                                ("beam_ranking", stage["ranking"], "drop"),
                                ("prefix_common_depth", stage["common_prefix_depth"], 0)):
        if config.get(key, default) != value:
            raise ValueError("native optional settings do not match the pinned portfolio stage")
    if native.get("config_sha256") != digest(path):
        raise ValueError("native result is not bound to its checked configuration")


def load_attempt(directory, graph, stage, cap):
    metadata_path = directory / "attempt.json"
    if not metadata_path.exists():
        return None
    metadata = read_json(metadata_path)
    if metadata.get("graph") != json.loads(compact(graph)) or metadata.get("stage") != stage or metadata.get("length_cap") != cap:
        raise ValueError("attempt graph/settings changed")
    if metadata.get("native_result"):
        result_path = directory / "native/result.json"
        if metadata["native_result"] != reference(result_path):
            raise ValueError("native result integrity mismatch")
        if (result_path.with_name("result.sha256").read_text().strip() != digest(result_path)
                or metadata["native_configuration"] != reference(result_path.with_name("run.json"))):
            raise ValueError("native result/configuration checksum mismatch")
        native = read_json(result_path)
        validate_native_configuration(result_path.with_name("run.json"), native, graph, stage, cap)
        normalized = normalize_native(native, graph, cap)
        if normalized != metadata["observation"]:
            raise ValueError("journal observation disagrees with its hashed native JSON")
    else:
        expected = {"m": graph["m"], "key": graph["key"], "length_cap": cap,
                    "decision": "unknown", "lower_bound": 1, "upper_bound": None, "witness": None, "verification": None}
        if metadata.get("observation") != expected or metadata.get("outcome") not in ("timeout", "error", "resource-budget"):
            raise ValueError("noncertificate attempt contains a fabricated observation")
    return metadata


def run_attempt(executable, graph, stage, cap, directory):
    """Reusable truth-free graph scorer; suitable for independent benchmarks."""
    graph = graph_metadata(graph)
    existing = load_attempt(directory, graph, stage, cap)
    if existing is not None:
        return existing
    directory.mkdir(parents=True, exist_ok=True)
    native_dir = directory / "native"
    command = native_command(executable, graph, stage, cap, native_dir)
    if (native_dir / "run.json").exists():
        command.append("--resume")
    atomic_json(directory / "invocation.json", {"command": command, "graph": graph, "stage": stage, "length_cap": cap})
    started = time.perf_counter()
    outcome, returncode, stdout, stderr = "error", None, "", ""
    if stage.get("pair_working_estimate_exceeds_budget"):
        outcome = "resource-budget"
        stderr = "Conservative full-family beam estimate exceeds the explicit per-worker planning budget."
    else:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=stage["timeout_seconds"])
            returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
            outcome = "completed" if returncode == 0 else "error"
        except subprocess.TimeoutExpired as error:
            outcome = "timeout"
            stdout, stderr = error.stdout or "", error.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
    (directory / "stdout.txt").write_text(stdout, encoding="utf-8")
    (directory / "stderr.txt").write_text(stderr, encoding="utf-8")
    metadata = {"graph": graph, "stage": stage, "length_cap": cap, "outcome": outcome,
                "returncode": returncode, "seconds": time.perf_counter() - started, "native_result": None,
                "observation": {"m": graph["m"], "key": graph["key"], "length_cap": cap,
                                "decision": "unknown", "lower_bound": 1, "upper_bound": None, "witness": None, "verification": None}}
    result_path = native_dir / "result.json"
    if outcome == "completed":
        if not result_path.exists() or result_path.with_name("result.sha256").read_text().strip() != digest(result_path):
            raise ValueError("completed native invocation lacks a committed checked result")
        native = read_json(result_path)
        validate_native_configuration(native_dir / "run.json", native, graph, stage, cap)
        if json.loads(stdout) != native:
            raise ValueError("native stdout disagrees with committed JSON")
        metadata.update({"native_result": reference(result_path), "native_configuration": reference(native_dir / "run.json"),
                         "observation": normalize_native(native, graph, cap)})
    atomic_json(directory / "attempt.json", metadata)
    return metadata


def score_graph(executable, graph, stages, caps, target_upper, directory):
    """Portfolio selection depends only on this scorer's newly verified hits."""
    graph = graph_metadata(graph)
    attempts, best_upper = [], None
    for requested_cap in caps:
        for stage in stages:
            if best_upper is not None and best_upper <= target_upper:
                return attempts
            cap = min(requested_cap, best_upper - 1) if best_upper is not None else requested_cap
            if cap < 1:
                return attempts
            attempt = run_attempt(executable, graph, stage, cap,
                                  directory / f"cap-{requested_cap}" / stage["name"])
            attempts.append(attempt)
            upper = attempt["observation"]["upper_bound"]
            if upper is not None:
                best_upper = min(best_upper, upper) if best_upper is not None else upper
    return attempts


def interval_record(row):
    graph = graph_metadata(row)
    exact = row.get("merge_length") if row.get("status") == "exact" else None
    if exact is not None:
        if type(exact) is not int or exact < 1:
            raise ValueError("invalid imported exact score")
        redundant_lower, redundant_upper = row.get("lower_bound"), row.get("upper_bound")
        if (redundant_lower is not None and (type(redundant_lower) is not int or redundant_lower < 1 or redundant_lower > exact)
                or redundant_upper is not None and (type(redundant_upper) is not int or redundant_upper < exact)):
            raise ValueError("imported exact score contradicts redundant interval fields")
    lower = exact if exact is not None else row.get("lower_bound", 1)
    upper = exact if exact is not None else row.get("upper_bound")
    if type(lower) is not int or lower < 1 or (upper is not None and (type(upper) is not int or upper < lower)):
        raise ValueError("invalid imported score interval")
    if row.get("witness") is not None:
        checked = verify_witness(graph["canonical_table"], row["witness"])
        if upper is None or len(row["witness"][0]) < upper:
            upper = len(row["witness"][0])
        if lower > upper:
            raise ValueError("imported lower bound contradicts its witness")
    else:
        checked = None
    return {**graph, "lower_bound": lower, "upper_bound": upper, "witness": row.get("witness"),
            "imported_witness_verification": checked}


def merge_interval(records, incoming, provenance):
    identity = incoming["m"], incoming["key"]
    record = records.setdefault(identity, {**graph_metadata(incoming), "lower_bound": 1, "upper_bound": None,
                                          "witness": None, "provenance": [], "observations": []})
    lower = max(record["lower_bound"], incoming.get("lower_bound", 1))
    uppers = [upper for upper in (record["upper_bound"], incoming.get("upper_bound")) if upper is not None]
    upper = min(uppers) if uppers else None
    if upper is not None and lower > upper:
        raise ValueError(f"contradictory certified intervals for{identity}: {lower}>{upper}")
    if incoming.get("witness") and incoming.get("upper_bound") == upper:
        record["witness"] = incoming["witness"]
    record.update(lower_bound=lower, upper_bound=upper,
                  status="exact" if lower == upper else "bounded" if upper is not None else "incomplete",
                  merge_length=lower if lower == upper else None)
    if provenance not in record["provenance"]:
        record["provenance"].append(provenance)
    return record


def materialize_plan(paths, max_shapes=0):
    bundles, root_cache = {}, {}
    for path in paths:
        source_ref = reference(path)
        path_file = path.parent / "paths.jsonl"
        path_ref = reference(path_file) if path_file.is_file() else None
        checksum_path = path.with_suffix(".sha256")
        if checksum_path.exists() and checksum_path.read_text().strip() != source_ref["sha256"]:
            raise ValueError("candidate input checksum mismatch")
        if path_ref and path_file.with_suffix(".sha256").exists():
            if path_file.with_suffix(".sha256").read_text().strip() != path_ref["sha256"]:
                raise ValueError("native path input checksum mismatch")
        for line, row in jsonl(path):
            graph = graph_metadata(row)
            rooted_identity = graph["m"], graph["key"]
            current = root_cache.get(rooted_identity)
            if current is None:
                bundle = root_bundle(graph)
                identity = bundle["m"], bundle["shape_key"]
                current = bundles.get(identity)
                if current is None:
                    current = {**bundle, "source_links": [], "first_seen_priority": len(bundles)}
                    bundles[identity] = current
                for root in current["roots"]:
                    root_cache[root["m"], root["key"]] = current
            link = {"source": source_ref, "line": line, "record_sha256": hashlib.sha256(compact(row).encode()).hexdigest(),
                    "rooted_source_key": graph["key"], "native_paths": row.get("paths"),
                    "native_path_ids": row.get("path_ids"), "native_paths_file": path_ref,
                    "native_root_metadata": row.get("root_metadata"),
                    "native_selection_index": row.get("selection_index"), "native_discovery_index": row.get("discovery_index"),
                    "native_generation_depth": row.get("generation_depth"),
                    "native_rooted_edit_distance_upper_bound": row.get("rooted_edit_distance_upper_bound"),
                    "native_shape_roots_complete": row.get("shape_roots_complete"),
                    "edit_distance_bound_applies_only_before_any_root_change": True}
            if link not in current["source_links"]:
                current["source_links"].append(link)
    # Input paths are sorted once; within each file the native selection order
    # is authoritative. Select whole first-seen shapes, never a lex-key prefix.
    ordered = list(bundles.values())
    for index, bundle in enumerate(ordered):
        bundle["selected"] = not max_shapes or index < max_shapes
    return {"schema": 1, "shapes": ordered, "shape_count": len(ordered),
            "selected_shape_count": sum(bundle["selected"] for bundle in ordered),
            "root_class_count": sum(len(bundle["roots"]) for bundle in ordered),
            "all_supplied_shapes_materialized": True, "global_graph_enumeration_complete": False,
            "shape_priority": "deterministic first appearance in input selection order; all roots kept together",
            "selection_is_a_budget_not_a_proof_of_irrelevance": True}


def export(output, plan, imported, attempts, completed, run_hash, incumbent_lower=None):
    records = {}
    for interval, source in imported:
        merge_interval(records, interval, source)
    selected, all_candidates = set(), set()
    for shape in plan["shapes"]:
        for root in shape["roots"]:
            identity = root["m"], root["key"]
            all_candidates.add(identity)
            if shape["selected"]:
                selected.add(identity)
            merge_interval(records, root, {"kind": "candidate-root-closure", "shape_key": shape["shape_key"],
                                           "selected": shape["selected"], "vertices": root["vertices_in_shape_table"]})
    observations = []
    for identity in sorted(attempts):
        for attempt in attempts[identity]:
            answer = attempt["observation"]
            record = merge_interval(records, answer, {"kind": "native-upper-certificate" if answer["upper_bound"] else "heuristic-miss",
                                                      "native_result": attempt["native_result"]})
            record["observations"].append({"stage": attempt["stage"]["name"], "cap": answer["length_cap"],
                                            "decision": answer["decision"], "outcome": attempt["outcome"],
                                            "upper_bound": answer["upper_bound"], "native_result": attempt["native_result"]})
            observations.append(attempt)
    values = [records[key] for key in sorted(records)]
    top, unresolved, sizes = [], [], []
    for m in sorted({record["m"] for record in values}):
        rows = [record for record in values if record["m"] == m]
        leader = max(record["lower_bound"] for record in rows)
        ties = [record for record in rows if record["lower_bound"] == leader]
        potential = [record for record in rows if record["upper_bound"] is None or record["upper_bound"] >= leader]
        top.extend(ties)
        unresolved.extend(potential)
        sizes.append({"m": m, "best_certified_lower_bound": leader, "all_top_lower_bound_ties": len(ties),
                      "recorded_rooted_classes": len(rows), "potential_tie_or_better_classes": len(potential),
                      "strictly_excluded_by_upper_certificate": sum(record["upper_bound"] is not None and record["upper_bound"] < leader for record in rows),
                      "selected_root_classes": sum(size == m for size, _ in selected),
                      "completed_root_classes": sum(size == m for size, _ in completed),
                      "finite_record_maximum_value_certified": all(record["upper_bound"] is not None and record["upper_bound"] <= leader for record in rows),
                      "finite_record_maximizer_collection_complete": all(record["lower_bound"] == record["upper_bound"] or
                                                                          (record["upper_bound"] is not None and record["upper_bound"] < leader) for record in rows),
                      "global_maximum_certified": False, "global_maximizer_collection_complete": False})
    write_jsonl(output / "records.jsonl", values)
    write_jsonl(output / "observations.jsonl", observations)
    write_jsonl(output / "top-lower-bound-ties.jsonl", top)
    write_jsonl(output / "unresolved-or-competitive.jsonl", unresolved)
    if incumbent_lower is not None:
        eliminated = [record for record in values if record["upper_bound"] is not None and record["upper_bound"] < incumbent_lower]
        survivors = [record for record in values if record["upper_bound"] is None or record["upper_bound"] >= incumbent_lower]
        write_jsonl(output / "eliminated-by-upper-certificate.jsonl", eliminated)
        write_jsonl(output / "survivors-unresolved-or-tied.jsonl", survivors)
    summary = {"schema": 1, "method": "general-bounded-calibrated-style-graph-candidate-portfolio",
               "run_sha256": run_hash, "sizes": sizes, "native_attempt_count": len(observations),
               "selected_root_classes": len(selected), "completed_root_classes": len(completed),
               "all_selected_roots_scored": selected <= completed,
               "all_candidate_roots_scored": all_candidates <= completed,
               "enumeration_complete": False, "global_maximum_certified": False,
               "all_ties_retained": True, "misses_give_no_lower_bounds": True,
               "long_heuristic_witness_is_only_an_upper_bound": True,
               "imported_lower_proofs_are_attributed_not_reproved": True}
    if incumbent_lower is not None:
        summary.update({"query_mode": "incumbent-elimination", "incumbent_lower": incumbent_lower,
                        "query_length_cap": incumbent_lower - 1,
                        "eliminated_recorded_classes": len(eliminated), "surviving_recorded_classes": len(survivors),
                        "survival_does_not_certify_competitiveness": True})
    atomic_json(output / "summary.json", summary)
    return summary


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", action="append", type=Path, required=True)
    parser.add_argument("--bounds", action="append", type=Path, default=[], help="Explicitly supplied certified interval/proof sources; not solver hints.")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--max-shapes", type=int, default=0, help="Select whole shapes;0 means all, unselected shapes remain exported.")
    parser.add_argument("--length-caps", default="34,64,96")
    parser.add_argument("--target-upper", type=int, default=34, help="Stop after this run verifies upper<=goal; never a lower bound.")
    parser.add_argument("--incumbent-lower", type=int, help="Elimination mode: query only capL-1; a hit proves H<L. A miss stays unresolved.")
    parser.add_argument("--enable-stage2", action="store_true", help="Opt in to the heavier k16 second stage; all stage budgets remain configurable.")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--beam-width", type=int, default=16)
    parser.add_argument("--memory-mib", type=int, default=512, help="Per-worker planning estimate, not an OS memory limit.")
    parser.add_argument("--tail-threshold", type=int, default=8)
    parser.add_argument("--tail-max-states", type=int, default=100000)
    parser.add_argument("--viability-coordinates", type=int, default=128)
    parser.add_argument("--prefix-samples-per-depth", type=int, default=16384)
    for index, defaults in ((1, (6, 1024, 1024, 16, 65536, 10000, 60)),
                            (2, (16, 65536, 65536, 21, 2097152, 50000, 180))):
        for name, value in zip(("k", "samples", "prefix-pairs", "prefix-depth", "prefix-words", "expansions", "timeout"), defaults):
            parser.add_argument(f"--stage{index}-{name}", type=int, default=value)
    args = parser.parse_args(argv)
    try:
        args.length_caps = sorted(set(int(value) for value in args.length_caps.split(",")))
    except ValueError:
        parser.error("length-caps must be comma-separated integers")
    if (not args.length_caps or min(args.length_caps) < 1 or max(args.length_caps) > 4096 or not 1 <= args.target_upper <= 4096
            or not 1 <= args.jobs <= 32 or not 1 <= args.beam_width <= 32 or args.memory_mib < 1 or args.max_shapes < 0
            or not 0 <= args.seed <= (1 << 64) - 1 or not 0 <= args.tail_threshold <= 1024
            or not 1 <= args.tail_max_states <= 10000000 or not 0 <= args.viability_coordinates <= 1024
            or not 1 <= args.prefix_samples_per_depth <= 4194304):
        parser.error("invalid search/shape/memory/tail budget")
    if args.incumbent_lower is not None:
        if not 1 <= args.incumbent_lower <= 4097:
            parser.error("incumbent-lower must be1..4097")
        args.length_caps = [args.incumbent_lower - 1] if args.incumbent_lower > 1 else []
        args.target_upper = args.incumbent_lower - 1
    args.query_mode = "incumbent-elimination" if args.incumbent_lower is not None else "upper-bound-research"
    for index in (1, 2):
        if (not 1 <= getattr(args, f"stage{index}_k") <= 16 or not 1 <= getattr(args, f"stage{index}_samples") <= 1000000000
                or not 1 <= getattr(args, f"stage{index}_prefix_pairs") <= 100000
                or not 1 <= getattr(args, f"stage{index}_prefix_depth") <= 32
                or not 1 <= getattr(args, f"stage{index}_prefix_words") <= 4194304
                or not 1 <= getattr(args, f"stage{index}_expansions") <= 1000000000
                or getattr(args, f"stage{index}_timeout") < 1):
            parser.error("invalid stage budget")
    args.out, args.exe = args.out.resolve(), args.exe.resolve()
    args.candidates = sorted(set(path.resolve() for path in args.candidates))
    args.bounds = sorted(set(path.resolve() for path in args.bounds))
    return args


def main(argv=None):
    args = arguments(argv)
    if not args.exe.is_file() or any(not path.is_file() for path in args.candidates + args.bounds):
        raise ValueError("executable or input source does not exist")
    plan = materialize_plan(args.candidates, args.max_shapes)
    plan["source_neighborhood_summaries"] = [{"source": reference(path.parent / "summary.json"),
                                              "metadata": read_json(path.parent / "summary.json")}
                                             for path in args.candidates if (path.parent / "summary.json").is_file()]
    plan["source_neighborhood_artifacts"] = [reference(path.parent / name)
                                             for path in args.candidates for name in ("paths.jsonl", "run.json", "summary.json")
                                             if (path.parent / name).is_file()]
    plan["stage_settings"] = {f"{root['m']}:{root['key']}": stage_settings(root, args)
                              for shape in plan["shapes"] for root in shape["roots"] if shape["selected"]}
    imported = []
    for path in args.bounds:
        source_ref = reference(path)
        for line, row in jsonl(path):
            imported.append((interval_record(row), {"kind": "explicit-imported-certified-interval",
                                                   "source": source_ref, "line": line,
                                                   "original_proof_metadata": {key: value for key, value in row.items()
                                                                               if key not in ("witness", "canonical_table")}}))
    settings = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()
                if key not in ("out", "exe", "candidates", "bounds", "resume", "generate_only")}
    dependencies = [Path(__file__), REPO / "scripts/family1_study.py"]
    native_sources = [REPO / name for name in ("family1_sample.cpp", "Family1LargeGraph.h", "Family1LargeGraph.cpp", "Family1PairAgreement.h",
                                             "Family1FullGuidance.h",
                                             "HardPairFinder.h", "HardPairPrefixSeeds.h", "HardPairViability.h", "Family1CliArtifacts.h")]
    plan_text = json.dumps(plan, indent=2) + "\n"
    config = {"schema": 1, "method": "general-bounded-calibrated-style-graph-candidate-portfolio",
              "settings": settings, "candidates": [reference(path) for path in args.candidates],
              "bounds": [reference(path) for path in args.bounds], "native_executable": reference(args.exe),
              "native_dlls": [reference(path) for path in sorted(args.exe.parent.glob("*.dll"))],
              "sources": [reference(path) for path in dependencies + native_sources if path.is_file()],
              "plan_sha256": hashlib.sha256(plan_text.encode()).hexdigest(),
              "scorer_uses_only_graph_and_explicit_settings": True, "saved_word_hints_used": False,
              "imported_intervals_do_not_control_search_schedule": True,
              "default_stage2_memory_scaling_is_reported": True}
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume or read_json(args.out / "run.json") != config:
            raise ValueError("nonempty run requires --resume and identical input/executable/source/settings pins")
        if (args.out / "plan.json").read_bytes() != plan_text.encode():
            raise ValueError("materialized plan integrity mismatch")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "plan.json").write_text(plan_text, encoding="utf-8", newline="\n")
        native_dir = args.out / "native-used"
        native_dir.mkdir()
        shutil.copy2(args.exe, native_dir / args.exe.name)
        for path in args.exe.parent.glob("*.dll"):
            shutil.copy2(path, native_dir / path.name)
        source_dir = args.out / "sources-used"
        source_dir.mkdir()
        for path in dependencies + native_sources:
            if path.is_file():
                shutil.copy2(path, source_dir / path.name)
        input_dir = args.out / "inputs-used"
        input_dir.mkdir()
        for kind, paths in (("candidate", args.candidates), ("bounds", args.bounds)):
            for index, path in enumerate(paths):
                shutil.copy2(path, input_dir / f"{kind}-{index:03d}.jsonl")
                if kind == "candidate":
                    for name in ("paths.jsonl", "run.json", "summary.json", "paths.sha256", "run.sha256", "summary.sha256", "candidates.sha256"):
                        if (path.parent / name).is_file():
                            shutil.copy2(path.parent / name, input_dir / f"{kind}-{index:03d}-{name}")
        atomic_json(args.out / "run.json", config)
    executable = args.out / "native-used" / args.exe.name
    if digest(executable) != config["native_executable"]["sha256"]:
        raise ValueError("saved native executable integrity mismatch")
    for item in config["native_dlls"]:
        if digest(executable.parent / Path(item["path"]).name) != item["sha256"]:
            raise ValueError("saved native DLL integrity mismatch")
    run_hash = digest(args.out / "run.json")
    attempts, completed = {}, set()
    roots = {(root["m"], root["key"]): graph_metadata(root)
             for shape in plan["shapes"] if shape["selected"] for root in shape["roots"]}
    if args.generate_only:
        if any((args.out / "queries").glob("**/attempt.json")):
            raise ValueError("generate-only would replace existing scored exports; use ordinary --resume to verify and retain them")
        summary = export(args.out, plan, imported, attempts, completed, run_hash, args.incumbent_lower)
    else:
        def score(identity):
            graph = roots[identity]
            stages = plan["stage_settings"][f"{graph['m']}:{graph['key']}"]
            result = score_graph(executable, graph, stages, args.length_caps, args.target_upper,
                                 args.out / "queries" / f"m{graph['m']}" / graph["key"])
            return identity, result
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(score, identity) for identity in roots]
            for future in as_completed(futures):
                identity, result = future.result()
                attempts[identity] = result
                completed.add(identity)
                summary = export(args.out, plan, imported, attempts, completed, run_hash, args.incumbent_lower)
                print(compact({"completed_root_classes": len(completed), "selected_root_classes": len(roots),
                               "m": identity[0], "key": identity[1], "attempts": len(result)}), flush=True)
        summary = export(args.out, plan, imported, attempts, completed, run_hash, args.incumbent_lower)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
