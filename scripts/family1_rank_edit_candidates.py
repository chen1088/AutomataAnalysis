#!/usr/bin/env python3
"""Truth-free ordering of a sealed edit-candidate pool; never drops a row.

Whole ordinary shapes stay together. Structural features and explicitly supplied
previous-size parent lower certificates determine priority. Candidate scores,
upper bounds and witnesses are preserved as opaque data and never rank inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil

from family1_graph_candidate_search import graph_metadata, root_bundle, reference, read_json, jsonl
from family1_study import canonical_table, fixed_key

REPO = Path(__file__).resolve().parents[1]


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def text_json(value):
    return json.dumps(value, indent=2) + "\n"


def text_jsonl(rows):
    return "".join(compact(row) + "\n" for row in rows)


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def canonical_path_graph(row, table_field, key_field):
    table = row.get(table_field)
    key = row.get(key_field)
    if table is None or key is None:
        raise ValueError("native path requires source/endpoint tables and keys")
    graph = graph_metadata({"canonical_table": table, "key": key})
    if tuple(map(tuple, table)) != graph["canonical_table"] or key != graph["key"]:
        raise ValueError("native path table/key must be a canonical rooted graph")
    return graph


def certified_parent_rows(rows):
    parents = {}
    for row in rows:
        graph = graph_metadata(row)
        exact = row.get("merge_length") if row.get("status") == "exact" else None
        if row.get("status") == "exact" and (type(exact) is not int or exact < 1):
            raise ValueError("exact parent certificate requires a positive integer merge_length")
        lower = exact if exact is not None else row.get("lower_bound", 1)
        upper = exact if exact is not None else row.get("upper_bound")
        if type(lower) is not int or lower < 1:
            raise ValueError("invalid supplied parent lower certificate")
        supplied_upper = row.get("upper_bound")
        if supplied_upper is not None and (type(supplied_upper) is not int or supplied_upper < lower):
            raise ValueError("parent upper certificate contradicts its lower/exact score")
        if exact is not None:
            redundant = row.get("lower_bound")
            if redundant is not None and (type(redundant) is not int or redundant < 1 or redundant > exact):
                raise ValueError("contradictory parent lower/exact certificate")
        identity = graph["m"], graph["key"]
        old = parents.get(identity)
        merged_lower = max(old["lower_bound"], lower) if old is not None else lower
        uppers = [value for value in (old.get("upper_bound") if old else None, upper) if value is not None]
        merged_upper = min(uppers) if uppers else None
        if merged_upper is not None and merged_lower > merged_upper:
            raise ValueError("different supplied parent certificates contradict each other")
        parents[identity] = {**graph, "lower_bound": merged_lower, "upper_bound": merged_upper}
    return parents


@lru_cache(maxsize=65536)
def reroot_key(table, root):
    m = len(table)
    if type(root) is not int or not 0 <= root < m:
        raise ValueError("path root is outside endpoint graph")
    permutation = list(range(m))
    permutation[0], permutation[root] = root, 0
    renamed = [None] * m
    for source, targets in enumerate(table):
        renamed[permutation[source]] = tuple(permutation[target] for target in targets)
    return fixed_key(canonical_table(renamed))


def validated_paths(rows):
    paths, graphs = {}, {}
    def graph(row, table_field, key_field):
        key = row.get(key_field)
        table = row.get(table_field)
        identity = key, tuple(map(tuple, table)) if table is not None else None
        if identity not in graphs:
            graphs[identity] = canonical_path_graph(row, table_field, key_field)
        return graphs[identity]
    for row in rows:
        path_id = row.get("path_id")
        if type(path_id) is not int or path_id < 0 or path_id in paths:
            raise ValueError("native path IDs must be distinct nonnegative integers")
        parent = graph(row, "source_table", "parent_key")
        endpoint = graph(row, "endpoint_table", "endpoint_key")
        paths[path_id] = {"path_id": path_id, "parent": parent, "endpoint": endpoint}
    return paths


def row_parent_links(row, graph, paths):
    links = {}
    for path_id in row.get("path_ids", []):
        if type(path_id) is not int or path_id not in paths:
            raise ValueError("candidate references an unknown direct path")
        path = paths[path_id]
        if path["endpoint"]["key"] != graph["key"]:
            raise ValueError("direct path endpoint disagrees with candidate root")
        links[path_id] = path
    for origin in row.get("root_metadata", []):
        path_id = origin.get("path_id")
        if type(path_id) is not int or path_id not in paths:
            raise ValueError("candidate root metadata references an unknown path")
        path = paths[path_id]
        endpoint = path["endpoint"]
        if origin.get("endpoint_key") != endpoint["key"]:
            raise ValueError("root metadata endpoint disagrees with its path")
        root = origin.get("root_in_endpoint")
        if reroot_key(endpoint["canonical_table"], root) != graph["key"]:
            raise ValueError("rerooted path endpoint disagrees with candidate graph")
        # A nonzero root may be automorphic to root0. Native metadata marks
        # the same rooted canonical class as root-fixed in that situation.
        if origin.get("root_fixed_path") and endpoint["key"] != graph["key"]:
            raise ValueError("root-fixed metadata silently changes the root")
        links[path_id] = path
    return list(links.values())


def shape_features(bundle):
    table, m = bundle["shape_table"], bundle["m"]
    indegrees = [0] * m
    for targets in table:
        for target in targets:
            indegrees[target] += 1
    accessible = [root for item in bundle["roots"] for root in item["vertices_in_shape_table"]]
    return {"m": m, "shape_key": bundle["shape_key"],
            "accessible_vertex_roots": len(accessible),
            "potential_hard_vertex_roots": sum(table[root][0] != table[root][1] for root in accessible),
            "distinct_accessible_root_classes": len(bundle["roots"]),
            "indegree_l1_distance_from_two": sum(abs(value - 2) for value in indegrees),
            "indegree_multiset": sorted(indegrees), "balanced_indegree_two": all(value == 2 for value in indegrees),
            "loop_occurrences": sum(target == source for source, targets in enumerate(table) for target in targets),
            "coincident_port_vertices": sum(a == b for a, b in table),
            "strongly_connected": len(accessible) == m,
            "all_vertices_accounted_for": bundle["all_vertices_accounted_for"]}


def rank_rows(rows, path_rows=(), parent_rows=(), strategy="structural", seed=1088):
    """Pure reusable API; candidate label fields are opaque and never read."""
    if strategy not in ("discovery", "structural", "parent-strata") or type(seed) is not int or not 0 <= seed < 1 << 64:
        raise ValueError("invalid ranking strategy/seed")
    rows = list(rows)
    paths = validated_paths(path_rows)
    parents = certified_parent_rows(parent_rows)
    shapes, rooted_cache, source_identities = {}, {}, []
    for index, row in enumerate(rows):
        graph = graph_metadata(row)
        rooted = graph["m"], graph["key"]
        source_identities.append(rooted)
        shape = rooted_cache.get(rooted)
        if shape is None:
            bundle = root_bundle(graph)
            identity = bundle["m"], bundle["shape_key"]
            shape = shapes.get(identity)
            if shape is None:
                shape = {"bundle": bundle, "features": shape_features(bundle), "rows": [],
                         "first_seen": index, "parents": {}, "score_levels": set()}
                shapes[identity] = shape
            for root in bundle["roots"]:
                rooted_cache[root["m"], root["key"]] = shape
        shape["rows"].append((index, row, graph))
        if paths:
            for path in row_parent_links(row, graph, paths):
                parent = path["parent"]
                identity = parent["m"], parent["key"]
                proof = parents.get(identity)
                previous_size = parent["m"] == graph["m"] - 1
                score = proof["lower_bound"] if previous_size and proof is not None else None
                item = shape["parents"].setdefault(identity, {"m": parent["m"], "key": parent["key"],
                                                            "path_ids": set(), "previous_size": previous_size,
                                                            "certified_lower_bound": score})
                item["path_ids"].add(path["path_id"])
                if score is not None:
                    shape["score_levels"].add(score)
        elif strategy == "parent-strata" and (row.get("path_ids") or row.get("root_metadata")):
            raise ValueError("parent-strata requires the path file referenced by candidate metadata")
    def structural(shape):
        feature = shape["features"]
        tie = hashlib.sha256(f"{seed}:{feature['m']}:{feature['shape_key']}".encode()).hexdigest()
        return (-feature["potential_hard_vertex_roots"], -feature["accessible_vertex_roots"],
                feature["indegree_l1_distance_from_two"], tie, feature["m"], feature["shape_key"])
    for shape in shapes.values():
        shape["tie_sha256"] = structural(shape)[3]
    selected_strata = Counter()
    if strategy == "discovery":
        ordered = sorted(shapes.values(), key=lambda shape: shape["first_seen"])
    elif strategy == "structural":
        ordered = sorted(shapes.values(), key=structural)
    else:
        strata = {}
        for shape in shapes.values():
            for level in shape["score_levels"] or {None}:
                strata.setdefault(level, []).append(shape)
        levels = sorted((level for level in strata if level is not None), reverse=True)
        if None in strata:
            levels.append(None)
        streams = {level: deque(sorted(strata[level], key=structural)) for level in levels}
        ordered, emitted = [], set()
        while any(streams.values()):
            for level in levels:
                while streams[level] and id(streams[level][0]) in emitted:
                    streams[level].popleft()
                if streams[level]:
                    shape = streams[level].popleft()
                    ordered.append(shape)
                    emitted.add(id(shape))
                    selected_strata[str(level)] += 1
    ranked, features, ranked_identities = [], [], []
    for ordinal, shape in enumerate(ordered):
        observed = {graph["key"] for _, _, graph in shape["rows"]}
        parent_links = [{**value, "path_ids": sorted(value["path_ids"])} for _, value in sorted(shape["parents"].items())]
        feature = {**shape["features"], "shape_rank": ordinal, "input_first_seen_index": shape["first_seen"],
                   "tie_sha256": shape["tie_sha256"], "seed": seed, "strategy": strategy,
                   "observed_root_classes": len(observed),
                   "input_contains_all_accessible_root_classes": len(observed) == len(shape["bundle"]["roots"]),
                   "previous_parent_score_levels": sorted(shape["score_levels"], reverse=True),
                   "linked_parents": parent_links}
        features.append(feature)
        for index, row, graph in shape["rows"]:
            ranked_identities.append((graph["m"], graph["key"]))
            ranked.append({**row, "original_selection_index": row.get("original_selection_index", row.get("selection_index", index)),
                           "ranking_input_index": index, "ranking_previous_selection_index": row.get("selection_index"),
                           "selection_index": len(ranked), "ranking": feature})
    if len(ranked) != len(rows) or Counter(ranked_identities) != Counter(source_identities):
        raise AssertionError("ranking changed the candidate multiset")
    summary = {"schema": 1, "method": "truth-free-whole-shape-post-generation-ranking", "strategy": strategy, "seed": seed,
               "candidate_rows": len(rows), "ordinary_shapes": len(ordered), "all_rows_retained": True,
               "whole_shape_blocks": True, "root_multiset_unchanged": True,
               "candidate_score_upper_or_witness_used": False, "candidate_labels_are_opaque": True,
               "previous_parent_lower_certificates_used": strategy == "parent-strata",
               "parent_strata_selected_shape_counts": dict(sorted(selected_strata.items())),
               "non_strongly_connected_shapes_retained": sum(not feature["strongly_connected"] for feature in features),
               "incomplete_input_root_blocks": sum(not feature["input_contains_all_accessible_root_classes"] for feature in features),
               "filters_applied": False, "enumeration_coverage_unchanged": True,
               "global_maximum_certified": False, "score_computation_performed": False}
    return ranked, features, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--paths", type=Path)
    parser.add_argument("--parents", type=Path, action="append", default=[])
    parser.add_argument("--strategy", choices=("discovery", "structural", "parent-strata"))
    parser.add_argument("--seed", type=int, default=1088)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    args.candidates, args.out = args.candidates.resolve(), args.out.resolve()
    if args.paths is None and (args.candidates.parent / "paths.jsonl").exists():
        args.paths = args.candidates.parent / "paths.jsonl"
    args.paths = args.paths.resolve() if args.paths else None
    args.parents = sorted(set(path.resolve() for path in args.parents))
    args.strategy = args.strategy or ("parent-strata" if args.parents else "structural")
    rows = [row for _, row in jsonl(args.candidates)]
    path_rows = [row for _, row in jsonl(args.paths)] if args.paths else []
    parent_rows = [row for path in args.parents for _, row in jsonl(path)]
    ranked, features, summary = rank_rows(rows, path_rows, parent_rows, args.strategy, args.seed)
    dependencies = [Path(__file__), REPO / "scripts/family1_graph_candidate_search.py", REPO / "scripts/family1_study.py"]
    config = {"schema": 1, "method": summary["method"], "strategy": args.strategy, "seed": args.seed,
              "candidates": reference(args.candidates), "paths": reference(args.paths) if args.paths else None,
              "parent_lower_certificate_sources": [reference(path) for path in args.parents],
              "sources": [reference(path) for path in dependencies], "candidate_score_fields_ignored": True,
              "source_run": reference(args.candidates.parent / "run.json") if (args.candidates.parent / "run.json").exists() else None,
              "source_summary": reference(args.candidates.parent / "summary.json") if (args.candidates.parent / "summary.json").exists() else None}
    outputs = {"candidates.jsonl": text_jsonl(ranked), "features.jsonl": text_jsonl(features),
               "summary.json": text_json(summary), "run.json": text_json(config)}
    manifest = {"schema": 1, "files": {name: digest_bytes(value.encode()) for name, value in outputs.items()},
                "paths_sha256": config["paths"]["sha256"] if config["paths"] else None,
                "candidate_multiset_preserved": True}
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume or read_json(args.out / "manifest.json") != manifest:
            raise ValueError("nonempty output requires identical pinned --resume")
        for name, value in outputs.items():
            if (args.out / name).read_bytes() != value.encode():
                raise ValueError("ranked output integrity mismatch")
            if (args.out / Path(name).with_suffix(".sha256")).read_text().strip() != digest_bytes(value.encode()):
                raise ValueError("ranked checksum sidecar integrity mismatch")
        if args.paths and reference(args.out / "paths.jsonl")["sha256"] != config["paths"]["sha256"]:
            raise ValueError("ranked path snapshot integrity mismatch")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            (args.out / name).write_text(value, encoding="utf-8", newline="\n")
            (args.out / Path(name).with_suffix(".sha256")).write_text(digest_bytes(value.encode()) + "\n")
        shutil.copy2(args.candidates, args.out / "source-candidates.jsonl")
        input_dir = args.out / "inputs-used"
        input_dir.mkdir()
        shutil.copy2(args.candidates, input_dir / "candidates.jsonl")
        if args.paths:
            shutil.copy2(args.paths, args.out / "paths.jsonl")
            shutil.copy2(args.paths, input_dir / "paths.jsonl")
            (args.out / "paths.sha256").write_text(config["paths"]["sha256"] + "\n")
        for index, path in enumerate(args.parents):
            shutil.copy2(path, args.out / f"source-parents-{index:03d}.jsonl")
            shutil.copy2(path, input_dir / f"parents-{index:03d}.jsonl")
        for name in ("run.json", "summary.json"):
            if (args.candidates.parent / name).is_file():
                shutil.copy2(args.candidates.parent / name, args.out / f"source-generation-{name}")
                shutil.copy2(args.candidates.parent / name, input_dir / f"generation-{name}")
        source_dir = args.out / "sources-used"
        source_dir.mkdir()
        for path in dependencies:
            shutil.copy2(path, source_dir / path.name)
        (args.out / "manifest.json").write_text(text_json(manifest), encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
