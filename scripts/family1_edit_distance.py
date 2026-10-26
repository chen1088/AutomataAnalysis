#!/usr/bin/env python3
"""Certify rooted edit distances between consecutive Family 1 winner sets.

Every move has unit cost: retarget one port, insert/smooth a routing vertex
in two edge occurrences, or subdivide/smooth an edge with a loop at the new
vertex. Rooted relabelings and independent port swaps are free. All intermediate
graphs are accessible. This script does not evaluate Family 1 merge lengths.
"""

from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
from pathlib import Path

from family1_study import REPO, canonical_table, compact, file_hash, fixed_key, validate_table
from family1_ancestry import canonical_mapping, relabel_with_ports


def _edge(table, raw, operation):
    """A unit edit followed by a free rooted isomorphism."""
    raw = validate_table(raw)
    after = canonical_table(raw)
    if after == table:
        return None
    return {"before": table, "after": after, "raw_after_edit": raw,
            "operation": operation, "cost": 1}


def neighbors(table):
    """Every adjacent rooted class, with one deterministic operation per class."""
    table = validate_table(table)
    if canonical_table(table) != table:
        raise ValueError("neighbors expects a canonical rooted table")
    m = len(table)
    edges = tuple(itertools.product(range(m), range(2)))
    found = {}

    def keep(raw, operation):
        try:
            edge = _edge(table, raw, operation)
        except ValueError:  # Inaccessible intermediates are not allowed.
            return
        if edge is not None:
            found.setdefault(fixed_key(edge["after"]), edge)

    # A growth edit always preserves accessibility. Distinct port occurrences
    # may share their source, target, or both.
    if m < 20:
        for pair in itertools.combinations(edges, 2):
            raw = [list(row) for row in table]
            targets = [table[source][port] for source, port in pair]
            for source, port in pair:
                raw[source][port] = m
            raw.append(targets)
            keep(raw, {"kind": "insert-two-edges", "new_vertex": m,
                       "edges": [{"source": source, "port": port, "target": table[source][port]}
                                 for source, port in pair], "new_outgoing": targets})
        for source, port in edges:
            raw = [list(row) for row in table]
            target = raw[source][port]
            raw[source][port] = m
            raw.append([target, m])
            keep(raw, {"kind": "insert-loop", "new_vertex": m,
                       "edges": [{"source": source, "port": port, "target": target}],
                       "new_outgoing": [target, m]})

    # Exact inverse growth operations. Keep both edge-occurrence bijections;
    # the rooted-class neighbor dictionary can merge equivalent results.
    for vertex in range(1, m):
        incoming = [(source, port) for source, row in enumerate(table) if source != vertex
                    for port, target in enumerate(row) if target == vertex]
        outgoing = [port for port, target in enumerate(table[vertex]) if target != vertex]
        if len(incoming) != len(outgoing) or len(incoming) not in (1, 2):
            continue
        remaining = [state for state in range(m) if state != vertex]
        labels = {state: index for index, state in enumerate(remaining)}
        for assignment in itertools.permutations(outgoing):
            raw = [list(row) for row in table]
            reconnections = []
            for (source, port), outgoing_port in zip(incoming, assignment):
                target = table[vertex][outgoing_port]
                raw[source][port] = target
                reconnections.append({"source": source, "port": port,
                                      "target": target, "outgoing_port": outgoing_port})
            raw = [[labels[target] for target in raw[source]] for source in remaining]
            keep(raw, {"kind": "smooth-vertex", "vertex": vertex,
                       "remaining_old_labels": remaining, "reconnections": reconnections})

    for source, port in edges:
        for target in range(m):
            if target == table[source][port]:
                continue
            raw = [list(row) for row in table]
            old = raw[source][port]
            raw[source][port] = target
            keep(raw, {"kind": "retarget", "source": source, "port": port,
                       "old_target": old, "new_target": target})
    return found


def _step(edge, reverse=False):
    return {"direction": "reverse" if reverse else "forward", "edge": edge}


def verify_edge(edge, include_isomorphism=False):
    """Rebuild the entire ordered table and independently check its isomorphism."""
    before = validate_table(edge["before"])
    after = validate_table(edge["after"])
    if canonical_table(before) != before or canonical_table(after) != after or edge["cost"] != 1:
        raise AssertionError("noncanonical endpoint or invalid edit cost")
    op = edge["operation"]
    raw = [list(row) for row in before]
    kind = op["kind"]
    if kind == "retarget":
        source, port = op["source"], op["port"]
        assert raw[source][port] == op["old_target"] != op["new_target"]
        raw[source][port] = op["new_target"]
    elif kind in ("insert-two-edges", "insert-loop"):
        assert op["new_vertex"] == len(before)
        chosen = {(item["source"], item["port"]) for item in op["edges"]}
        assert len(chosen) == len(op["edges"]) == (2 if kind == "insert-two-edges" else 1)
        targets = []
        for item in op["edges"]:
            source, port, target = item["source"], item["port"], item["target"]
            assert raw[source][port] == target
            targets.append(target)
            raw[source][port] = len(before)
        expected = targets if kind == "insert-two-edges" else targets + [len(before)]
        assert op["new_outgoing"] == expected
        raw.append(expected)
        old_indegrees = Counter(target for row in before for target in row)
        new_indegrees = Counter(target for row in raw for target in row)
        assert all(old_indegrees[state] == new_indegrees[state] for state in range(len(before)))
        assert new_indegrees[len(before)] == 2
    elif kind == "smooth-vertex":
        vertex = op["vertex"]
        assert 0 < vertex < len(before)
        remaining = [state for state in range(len(before)) if state != vertex]
        assert op["remaining_old_labels"] == remaining
        incoming = {(source, port) for source, row in enumerate(before) if source != vertex
                    for port, target in enumerate(row) if target == vertex}
        outgoing = {port for port, target in enumerate(before[vertex]) if target != vertex}
        assert 1 <= len(incoming) == len(outgoing) <= 2
        assert {(item["source"], item["port"]) for item in op["reconnections"]} == incoming
        assert {item["outgoing_port"] for item in op["reconnections"]} == outgoing
        for item in op["reconnections"]:
            assert before[vertex][item["outgoing_port"]] == item["target"]
            raw[item["source"]][item["port"]] = item["target"]
        labels = {old: new for new, old in enumerate(remaining)}
        raw = [[labels[target] for target in raw[source]] for source in remaining]
    else:
        raise AssertionError("unknown edit")
    raw = validate_table(raw)
    assert raw == tuple(map(tuple, edge["raw_after_edit"]))
    canonical, mapping, flips = canonical_mapping(raw)
    assert canonical == after
    mapped = [list(row) for row in relabel_with_ports(raw, mapping)]
    for old, flip in enumerate(flips):
        if flip:
            mapped[mapping[old]].reverse()
    assert tuple(map(tuple, mapped)) == after
    if "free_isomorphism_after_edit" in edge:
        saved = edge["free_isomorphism_after_edit"]
        assert tuple(saved["old_to_canonical_vertices"]) == mapping
        assert tuple(saved["port_flip_at_old_source"]) == flips
    if include_isomorphism:
        edge["free_isomorphism_after_edit"] = {
            "old_to_canonical_vertices": mapping,
            "port_flip_at_old_source": flips,
        }


def verify_path(record, source_tables):
    current = tuple(map(tuple, record["source_table"]))
    assert current in source_tables
    for step in record["steps"]:
        edge = step["edge"]
        verify_edge(edge, include_isomorphism=True)
        before, after = tuple(map(tuple, edge["before"])), tuple(map(tuple, edge["after"]))
        if step["direction"] == "reverse":
            before, after = after, before
        else:
            assert step["direction"] == "forward"
        assert current == before
        current = after
    assert current == tuple(map(tuple, record["target_table"]))
    assert len(record["steps"]) == record["distance"]
    assert len(current) - len(record["source_table"]) == 1


def solve_pair(sources, children):
    """Exact distances up to three, using complete bidirectional unit spheres."""
    sources = sorted(sources, key=lambda item: fixed_key(item["canonical_table"]))
    children = sorted(children, key=lambda item: fixed_key(item["canonical_table"]))
    source_by_key = {fixed_key(item["canonical_table"]): item for item in sources}
    source_paths = {key: {"source": record, "steps": [], "table": tuple(map(tuple, record["canonical_table"]))}
                    for key, record in source_by_key.items()}
    for source in sources:
        table = tuple(map(tuple, source["canonical_table"]))
        for key, edge in neighbors(table).items():
            source_paths.setdefault(key, {"source": source, "steps": [_step(edge)], "table": edge["after"]})

    target_spheres, found = {}, {}
    for child in children:
        key = fixed_key(child["canonical_table"])
        table = tuple(map(tuple, child["canonical_table"]))
        sphere = neighbors(table)
        target_spheres[key] = sphere
        if key in source_paths:
            found[key] = source_paths[key]
            continue
        common = sorted(set(source_paths).intersection(sphere))
        if common:
            middle = common[0]
            prefix = source_paths[middle]
            found[key] = {"source": prefix["source"],
                          "steps": prefix["steps"] + [_step(sphere[middle], reverse=True)], "table": table}

    # For every remaining child, exhaustive disjoint unit spheres already
    # exclude all paths of lengths zero, one, and two. A length-three path is
    # therefore optimal as soon as one is found; no radius-two exhaustivity
    # claim is needed or made.
    unresolved = {fixed_key(child["canonical_table"]) for child in children} - set(found)
    expanded_first_sphere_vertices = 0
    for middle in sorted(source_paths):
        if not unresolved:
            break
        prefix = source_paths[middle]
        if len(prefix["steps"]) != 1:
            continue
        expanded_first_sphere_vertices += 1
        for next_key, edge in neighbors(prefix["table"]).items():
            for target_key in sorted(tuple(unresolved)):
                tail = target_spheres[target_key].get(next_key)
                if tail is not None:
                    found[target_key] = {"source": prefix["source"],
                                         "steps": prefix["steps"] + [_step(edge), _step(tail, reverse=True)],
                                         "table": tail["before"]}
                    unresolved.remove(target_key)

    if unresolved:
        raise RuntimeError(f"no distance-at-most-three path for {sorted(unresolved)}; no exact score emitted")
    records = []
    source_tables = {tuple(map(tuple, source["canonical_table"])) for source in sources}
    for child in children:
        key = fixed_key(child["canonical_table"])
        result = found[key]
        source = result["source"]
        distance = len(result["steps"])
        if not 1 <= distance <= 3:
            raise AssertionError("unexpected distance")
        record = {
            "parent_m": source["m"], "child_m": child["m"],
            "source_key": fixed_key(source["canonical_table"]),
            "source_table": source["canonical_table"], "source_merge_length": source["merge_length"],
            "target_key": key, "target_table": child["canonical_table"],
            "target_ordinal": child["ordinal"], "target_merge_length": child["merge_length"],
            "distance": distance, "status": "exact", "steps": result["steps"],
            "distance_to": "complete rooted global-maximizer collection at previous exact size",
            "lower_bound_reason": "different vertex counts" if distance == 1 else (
                "complete source unit sphere excludes this target" if distance == 2 else
                "complete source radius-one ball and target unit sphere are disjoint"),
            "source_radius_one_ball_classes": len(source_paths),
            "target_unit_sphere_classes": len(target_spheres[key]),
            "source_unit_sphere_complete": True, "target_unit_sphere_complete": True,
        }
        verify_path(record, source_tables)
        records.append(record)
    return records, {"source_m": sources[0]["m"], "target_m": children[0]["m"],
                     "source_winners": len(sources), "target_winners": len(children),
                     "source_radius_one_ball_classes": len(source_paths),
                     "first_sphere_vertices_expanded_for_upper_paths": expanded_first_sphere_vertices,
                     "distances": [record["distance"] for record in records]}


def run(args):
    small_dir = REPO / "results/family1-m1-m6"
    seven_dir = REPO / "results/family1-m7"
    small_summary = json.loads((small_dir / "summary.json").read_text(encoding="utf-8-sig"))
    seven_summary = json.loads((seven_dir / "summary.json").read_text(encoding="utf-8-sig"))
    small = [json.loads(line) for line in (small_dir / "maximizers.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    seven = [json.loads(line) for line in (seven_dir / "maximizers.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    grouped = {}
    for record in small + seven:
        assert record["status"] == "exact" and type(record["merge_length"]) is int
        table = validate_table(record["canonical_table"])
        assert canonical_table(table) == table
        grouped.setdefault(record["m"], []).append(record)
    for size in small_summary["sizes"]:
        m = size["m"]
        assert size["enumeration_complete"] and size["scoring_complete"] and size["maximum_certified"]
        assert len(grouped[m]) == size["maximizer_count"]
        assert all(record["merge_length"] == size["maximum_merge_length"] for record in grouped[m])
    assert seven_summary["maximum_value_certified"] and seven_summary["maximizing_collection_complete"]
    assert len(grouped[7]) == seven_summary["maximizer_count"]
    assert all(record["merge_length"] == seven_summary["maximum_merge_length"] for record in grouped[7])
    records, pairs = [], []
    for m in range(args.min_parent, args.max_parent + 1):
        distances, pair = solve_pair(grouped[m], grouped[m + 1])
        records.extend(distances)
        pairs.append(pair)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "paths.jsonl").write_text("".join(compact(record) + "\n" for record in records), encoding="utf-8")
    summary = {
        "schema": 1, "metric": "rooted-unit-retarget-routing-growth-v1",
        "status": "exact", "scope": "Distance from every certified rooted maximizer to the complete previous-size maximizer set.",
        "all_intermediates_accessible": True, "root_changes_allowed": False,
        "free_equivalences": ["root-preserving vertex relabeling", "independent outgoing-port swaps"],
        "unit_moves": ["one-port retarget", "two-edge routing insertion/smoothing", "one-edge loop insertion/smoothing"],
        "proof": "Complete unit neighborhoods exclude shorter paths; saved explicit paths prove the matching upper bound.",
        "pairs": pairs, "paths": len(records),
        "sources": {str(path.relative_to(REPO)): {"sha256": file_hash(path)} for path in (
            small_dir / "summary.json", small_dir / "maximizers.jsonl",
            seven_dir / "summary.json", seven_dir / "maximizers.jsonl")},
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Rooted edit distances between consecutive maximizers", "",
             "Each distance is to the complete set of rooted maximizers at the previous exact size. Root-preserving relabeling and independent port swaps are free. Unit moves are one-port retargeting, two-edge routing-vertex insertion/smoothing, and one-edge subdivision with a loop at the new vertex (or its inverse). Every intermediate graph remains root-accessible.", "",
             "The distance is a structural quantity. The change in Family 1 merge length is recorded separately and is not a graph-edit cost.", "",
             "| Previous size | Child size | Child ordinal | Shortest edit distance | Previous maximum H | Child H |",
             "|---:|---:|---:|---:|---:|---:|"]
    for record in records:
        lines.append(f"| {record['parent_m']} | {record['child_m']} | {record['target_ordinal']} | {record['distance']} | {record['source_merge_length']} | {record['target_merge_length']} |")
    lines.extend(["", "`paths.jsonl` stores every complete ordered transition table along a shortest path, every primitive edit, and the free rooted isomorphism after that edit. Lower bounds use complete bidirectional unit neighborhoods; an exhaustive radius-two search is not claimed or needed.", "",
                  "```powershell", "uv run --no-project python scripts/family1_edit_distance.py",
                  "uv run --no-project python tests/family1_edit_distance_test.py", "```", "",
                  "See [the mathematical definition and metric proof](../../docs/family1-graph-edits.md) and [the one-insertion ancestry audit](../family1-ancestry-through7/README.md).", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(compact({"paths": len(records), "pairs": pairs}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-parent", type=int, default=1, choices=range(1, 7))
    parser.add_argument("--max-parent", type=int, default=6, choices=range(1, 7))
    parser.add_argument("--output", type=Path, default=REPO / "results/family1-edit-distance-through7")
    args = parser.parse_args()
    if args.min_parent > args.max_parent:
        parser.error("minimum parent size exceeds maximum parent size")
    run(args)


if __name__ == "__main__":
    main()
