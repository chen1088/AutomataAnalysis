#!/usr/bin/env python3
"""Audit rooted predecessors obtained by deleting one balanced nonroot vertex.

This tests a specified graph operation, not a unique genealogy or a recurrence
for extremal merge lengths. Scores are read from the complete exact small-case
journal; no Family 1 scoring is repeated here.
"""

from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
from pathlib import Path

from family1_study import (
    REPO, canonical_table, compact, file_hash, fixed_key, jsonl,
    table_from_key, validate_table,
)


def relabel_with_ports(table, mapping):
    rows = [None] * len(table)
    for old, row in enumerate(table):
        rows[mapping[old]] = tuple(mapping[target] for target in row)
    return tuple(rows)


def canonical_mapping(table):
    """Independent factorial check and an explicit rooted isomorphism."""
    table = validate_table(table)
    best, chosen = None, None
    for tail in itertools.permutations(range(1, len(table))):
        mapping = (0,) + tail
        candidate = tuple(tuple(sorted(row)) for row in relabel_with_ports(table, mapping))
        if best is None or candidate < best:
            best, chosen = candidate, mapping
    if best != canonical_table(table):
        raise AssertionError("factorial and discovery canonicalization disagree")
    mapped = relabel_with_ports(table, chosen)
    flips = [int(mapped[chosen[source]] != best[chosen[source]]) for source in range(len(table))]
    return best, chosen, tuple(flips)


def ordinary_key(table):
    """Exact ordinary isomorphism key, without treating any vertex as root."""
    return fixed_key(min(tuple(tuple(sorted(row)) for row in relabel_with_ports(table, mapping))
                         for mapping in itertools.permutations(range(len(table)))))


def reconstruct_child(parent, operation):
    """Insert the deleted vertex, preserving the original ordered ports."""
    old_labels = operation["parent_to_child_labels"]
    vertex = operation["deleted_vertex"]
    result = [None] * (len(parent) + 1)
    for source, row in enumerate(parent):
        result[old_labels[source]] = [old_labels[target] for target in row]
    result[vertex] = list(operation["deleted_outgoing_ports"])
    for edge in operation["reconnections"]:
        source, port = edge["child_source"], edge["port"]
        if result[source][port] != edge["child_target_after_deletion"]:
            raise AssertionError("inverse insertion does not find the recorded edge")
        result[source][port] = vertex
    return validate_table(result)


def smoothing_operations(table):
    """All allowed deletions, including port-distinct reconnection bijections.

    A vertex without a loop has two external incoming ports and two outgoing
    ports; try both bijections. A vertex with one loop has one external port
    in each direction; smooth it and remove its loop. Root 0 is retained.
    Each yielded parent is accessible. Inaccessible results are counted too.
    """
    table = validate_table(table)
    m = len(table)
    for vertex in range(1, m):
        incoming = [(source, port) for source, row in enumerate(table)
                    if source != vertex for port, target in enumerate(row) if target == vertex]
        outgoing_ports = [port for port, target in enumerate(table[vertex]) if target != vertex]
        if len(incoming) != len(outgoing_ports) or len(incoming) not in (1, 2):
            continue
        for assignment in itertools.permutations(outgoing_ports):
            remaining = [state for state in range(m) if state != vertex]
            renumber = {state: index for index, state in enumerate(remaining)}
            rows = [list(row) for row in table]
            edits = []
            for (source, port), outgoing_port in zip(incoming, assignment):
                target = table[vertex][outgoing_port]
                rows[source][port] = target
                edits.append({
                    "child_source": source, "port": port,
                    "child_target_before_deletion": vertex,
                    "child_target_after_deletion": target,
                    "deleted_vertex_outgoing_port": outgoing_port,
                    "parent_source": renumber[source], "parent_target": renumber[target],
                })
            parent = tuple(tuple(renumber[target] for target in rows[source]) for source in remaining)
            operation = {
                "kind": "smooth-one-edge-and-remove-loop" if len(incoming) == 1 else "reconnect-two-edges",
                "deleted_vertex": vertex,
                "deleted_outgoing_ports": list(table[vertex]),
                "incoming_to_outgoing_port_bijection": list(assignment),
                "parent_to_child_labels": remaining,
                "reconnections": edits,
                "parent_table_before_canonicalization": parent,
            }
            try:
                validate_table(parent)
            except ValueError:
                operation["accessible"] = False
                yield operation
                continue
            operation["accessible"] = True
            if reconstruct_child(parent, operation) != table:
                raise AssertionError("reverse insertion failed ordered transition equality")
            canonical, mapping, flips = canonical_mapping(parent)
            child_to_growth_labels = [None] * m
            for old_parent, old_child in enumerate(remaining):
                child_to_growth_labels[old_child] = mapping[old_parent]
            child_to_growth_labels[vertex] = m - 1
            growth_table = [list(row) for row in relabel_with_ports(table, child_to_growth_labels)]
            for old_parent, flip in enumerate(flips):
                if flip:
                    growth_table[mapping[old_parent]].reverse()
            growth_edges = [{
                "source": mapping[edge["parent_source"]],
                "port": edge["port"] ^ flips[edge["parent_source"]],
                "target": mapping[edge["parent_target"]],
            } for edge in edits]
            reconstructed = [list(row) for row in canonical] + [growth_table[m - 1]]
            for edge in growth_edges:
                if reconstructed[edge["source"]][edge["port"]] != edge["target"]:
                    raise AssertionError("canonical insertion does not find its parent edge")
                reconstructed[edge["source"]][edge["port"]] = m - 1
            if reconstructed != growth_table or canonical_table(growth_table) != canonical_table(table):
                raise AssertionError("canonical parent insertion reconstruction failed")
            operation.update({
                "parent_key": fixed_key(canonical), "parent_canonical_table": canonical,
                "parent_old_to_canonical_labels": mapping,
                "parent_port_flip_at_old_source": flips,
                "canonical_parent_growth": {
                    "new_vertex": m - 1, "replace_parent_edges": growth_edges,
                    "new_vertex_outgoing_ports": growth_table[m - 1],
                    "child_to_growth_labels": child_to_growth_labels,
                    "resulting_child_table": growth_table,
                },
                "reverse_insertion_verified": True,
            })
            yield operation


def load_exact_scores(path, m, expected_count):
    scores = {}
    for _, record in jsonl(path):
        if record.get("m") != m:
            continue
        table = validate_table(record["canonical_table"])
        if table_from_key(record["key"], m) != table:
            raise ValueError("score journal key/table disagreement")
        if record.get("status") != "exact" or type(record.get("merge_length")) is not int:
            raise ValueError("a parent score is not exact")
        key = fixed_key(table)
        if key in scores:
            raise ValueError("duplicate parent class in score journal")
        scores[key] = record
    if len(scores) != expected_count:
        raise ValueError(f"expected {expected_count} exact parents, got {len(scores)}")
    return scores


def run(args):
    child_summary = json.loads((args.children / "summary.json").read_text(encoding="utf-8-sig"))
    if "sizes" in child_summary:
        if args.child_m is None:
            raise ValueError("--child-m is required for a collection covering multiple sizes")
        child_summary = dict(next(item for item in child_summary["sizes"] if item["m"] == args.child_m))
        child_summary["maximum_value_certified"] = child_summary["maximum_certified"]
        child_summary["maximizing_collection_complete"] = child_summary["enumeration_complete"] and child_summary["scoring_complete"]
    elif args.child_m is not None and child_summary["m"] != args.child_m:
        raise ValueError("--child-m disagrees with the certified collection")
    if not (child_summary.get("maximum_value_certified") and child_summary.get("maximizing_collection_complete")):
        raise ValueError("child collection has no complete maximum certificate")
    child_m = child_summary["m"]
    parent_m = child_m - 1
    parent_summary = json.loads(args.parent_summary.read_text(encoding="utf-8-sig"))
    size = next(item for item in parent_summary["sizes"] if item["m"] == parent_m)
    if not (size["enumeration_complete"] and size["scoring_complete"] and size["maximum_certified"]):
        raise ValueError("parent score collection is incomplete")
    scores = load_exact_scores(args.parents, parent_m, size["evaluated"])
    winners = []
    for _, record in jsonl(args.children / "maximizers.jsonl"):
        if record["m"] == child_m:
            if table_from_key(record["key"], child_m) != tuple(map(tuple, record["canonical_table"])):
                raise ValueError("child source key disagrees with table")
            winners.append({**record, "source_key": record["key"], "key": fixed_key(record["canonical_table"])})
    if len(winners) != child_summary["maximizer_count"]:
        raise ValueError("child maximizer count mismatch")
    if len({record["key"] for record in winners}) != len(winners):
        raise ValueError("child maximizer keys disagree with complete certificate")
    if "maximizer_keys" in child_summary and {fixed_key(table_from_key(key, child_m)) for key in child_summary["maximizer_keys"]} != {record["key"] for record in winners}:
        raise ValueError("child maximizer keys disagree with complete certificate")
    operations, by_parent, children = [], {}, []
    parent_global_max = size["maximum_merge_length"]
    parent_winning_shapes = {ordinary_key(record["canonical_table"]) for record in scores.values()
                             if record["merge_length"] == parent_global_max}
    for child in sorted(winners, key=lambda record: record["key"]):
        table = validate_table(child["canonical_table"])
        if (child["status"] != "exact" or child["merge_length"] != child_summary["maximum_merge_length"]
                or fixed_key(canonical_table(table)) != child["key"]):
            raise ValueError("child is not a canonical exact maximizer")
        child_operations, parent_keys = [], set()
        for operation in smoothing_operations(table):
            operation.update({"operation_id": len(operations), "child_key": child["key"],
                              "child_ordinal": child["ordinal"], "child_merge_length": child["merge_length"]})
            if operation["accessible"]:
                key = operation["parent_key"]
                score = scores[key]
                operation.update({"parent_merge_length": score["merge_length"],
                                  "merge_length_increase": child["merge_length"] - score["merge_length"]})
                parent_keys.add(key)
                if key not in by_parent:
                    by_parent[key] = {
                        "m": parent_m, "key": key, "canonical_table": operation["parent_canonical_table"],
                        "status": "exact", "merge_length": score["merge_length"],
                        "witness": score["witness"], "ordinal": score["ordinal"],
                        "is_global_maximizer": score["merge_length"] == parent_global_max,
                        "ordinary_isomorphic_to_global_maximizer": ordinary_key(operation["parent_canonical_table"]) in parent_winning_shapes,
                        "child_keys": [], "operation_ids": [],
                    }
                by_parent[key]["operation_ids"].append(operation["operation_id"])
                if child["key"] not in by_parent[key]["child_keys"]:
                    by_parent[key]["child_keys"].append(child["key"])
            child_operations.append(operation)
            operations.append(operation)
        best = max((scores[key]["merge_length"] for key in parent_keys), default=None)
        best_keys = sorted(key for key in parent_keys if scores[key]["merge_length"] == best)
        winning_shape_parents = sorted(key for key in parent_keys if by_parent[key]["ordinary_isomorphic_to_global_maximizer"])
        children.append({
            "key": child["key"], "ordinal": child["ordinal"], "canonical_table": table,
            "merge_length": child["merge_length"], "accessible_parent_count": len(parent_keys),
            "accessible_operation_count": sum(operation["accessible"] for operation in child_operations),
            "inaccessible_operation_count": sum(not operation["accessible"] for operation in child_operations),
            "parent_score_histogram": dict(sorted(Counter(scores[key]["merge_length"] for key in parent_keys).items())),
            "best_parent_merge_length": best, "best_parent_keys": best_keys,
            "increase_from_best_parent": child["merge_length"] - best if best is not None else None,
            "has_global_maximizing_parent": best == parent_global_max,
            "ordinary_shape_key": ordinary_key(table),
            "ordinary_winning_shape_parent_keys": winning_shape_parents,
            "ordinary_winning_shape_parent_scores": {key: scores[key]["merge_length"] for key in winning_shape_parents},
            "best_operation_ids": [operation["operation_id"] for operation in child_operations
                                   if operation["accessible"] and operation["parent_merge_length"] == best],
        })
    args.output.mkdir(parents=True, exist_ok=True)
    for name, records in (("operations.jsonl", operations), ("parents.jsonl", [by_parent[key] for key in sorted(by_parent)])):
        (args.output / name).write_text("".join(compact(record) + "\n" for record in records), encoding="utf-8")
    sources = {}
    for name, path in (("parent_scores", args.parents), ("parent_summary", args.parent_summary),
                       ("child_maximizers", args.children / "maximizers.jsonl"),
                       ("child_summary", args.children / "summary.json")):
        sources[name] = {"path": str(path.resolve()), "sha256": file_hash(path)}
    winner_links = []
    for parent_key in sorted(by_parent):
        parent = by_parent[parent_key]
        if not parent["is_global_maximizer"]:
            continue
        for child_key in sorted(parent["child_keys"]):
            linked = [operation for operation in operations if operation.get("parent_key") == parent_key and operation["child_key"] == child_key]
            winner_links.append({
                "parent_key": parent_key, "child_key": child_key,
                "parent_merge_length": parent_global_max,
                "child_merge_length": child_summary["maximum_merge_length"],
                "operations": [{"operation_id": operation["operation_id"], **operation["canonical_parent_growth"]} for operation in linked],
                "operation_ids": [operation["operation_id"] for operation in linked],
            })
    parent_winner_coverage = []
    for key, score in sorted(scores.items()):
        if score["merge_length"] == parent_global_max:
            parent_winner_coverage.append({
                "key": key, "ordinal": score["ordinal"], "canonical_table": score["canonical_table"],
                "merge_length": score["merge_length"],
                "has_winning_child": any(link["parent_key"] == key for link in winner_links),
                "child_keys": [link["child_key"] for link in winner_links if link["parent_key"] == key],
                "operation_ids": [operation_id for link in winner_links if link["parent_key"] == key for operation_id in link["operation_ids"]],
            })
    summary = {
        "schema": 1, "parent_m": parent_m, "child_m": child_m,
        "operation_scope": "Keep root 0; delete one nonroot indegree-2 vertex; reconnect both external edge bijections, or smooth one external edge and delete its single self-loop; retain root-accessible parents.",
        "scope_exhaustive": "Every allowed operation on all certified child maximizers, not every possible definition of graph growth.",
        "parent_global_maximum": parent_global_max,
        "child_global_maximum": child_summary["maximum_merge_length"],
        "child_maximizer_count": len(winners),
        "child_count": len(winners),
        "parent_maximizer_count": len(parent_winner_coverage),
        "parent_winners_with_winning_child": sum(parent["has_winning_child"] for parent in parent_winner_coverage),
        "winner_links": winner_links, "parent_winner_coverage": parent_winner_coverage,
        "children_with_global_maximizing_parent": sum(child["has_global_maximizing_parent"] for child in children),
        "children_with_ordinary_winning_shape_parent": sum(bool(child["ordinary_winning_shape_parent_keys"]) for child in children),
        "child_ordinary_shape_count": len({child["ordinary_shape_key"] for child in children}),
        "child_ordinary_shapes_with_ordinary_winning_shape_parent": len({child["ordinary_shape_key"] for child in children if child["ordinary_winning_shape_parent_keys"]}),
        "distinct_parent_classes": len(by_parent), "operation_count": len(operations),
        "accessible_operation_count": sum(operation["accessible"] for operation in operations),
        "inaccessible_operation_count": sum(not operation["accessible"] for operation in operations),
        "all_accessible_operations_reverse_verified": all(operation.get("reverse_insertion_verified") for operation in operations if operation["accessible"]),
        "parent_scores_loaded": len(scores), "sources": sources, "children": children,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# One-vertex predecessors of the {child_m}-state maximizers", "",
        f"Exactly {summary['children_with_global_maximizing_parent']} of the {len(winners)} rooted maximizers has a rooted {parent_m}-state global maximizer as a predecessor under the operation below. The certified maxima are {parent_global_max} and {summary['child_global_maximum']}.", "",
        "## Operation", "",
        "Keep the root. For a nonroot vertex v without a self-loop, remove v and connect its two incoming ports to its two outgoing targets in each of the two bijections. The inverse inserts v into two directed edges. If v has one self-loop, smooth its external incoming/outgoing edge; the inverse subdivides one edge and adds a loop. Discard inaccessible parents. Outdegrees remain two; balanced indegrees are preserved by this operation, but no balance assumption is made about the global search.", "",
        "Every accessible deletion was reversed and checked against the entire original ordered transition table. Parent canonicalization was independently checked by trying every root-fixing vertex permutation and sorting outgoing ports. All parent scores come from the complete exact small-case journal, whose SHA-256 is recorded in summary.json.", "",
        "This defines a structural relationship, not unique historical ancestry. It excludes deleting the root, arbitrary edge rewrites, graph quotients, and other growth operations.", "",
        f"## All {len(winners)} rooted classes", "",
        f"| Child ordinal | Child key | Distinct parents | Best parent H | Increase to {child_summary['maximum_merge_length']} | {parent_m}-state maximizer parent? |",
        "|---:|---|---:|---:|---:|:---:|",
    ]
    for child in children:
        best_text = child['best_parent_merge_length'] if child['best_parent_merge_length'] is not None else "none"
        increase_text = child['increase_from_best_parent'] if child['increase_from_best_parent'] is not None else "none"
        lines.append(f"| {child['ordinal']} | `{child['key']}` | {child['accessible_parent_count']} | {best_text} | {increase_text} | {'yes' if child['has_global_maximizing_parent'] else 'no'} |")
    lines.extend(["", "## Ordinary shapes and the starting vertex", "",
                  f"If only the predecessor's root is ignored for an isomorphism comparison, {summary['children_with_ordinary_winning_shape_parent']} of the {len(winners)} rooted children have a predecessor of an ordinary winning {parent_m}-state shape. They cover {summary['child_ordinary_shapes_with_ordinary_winning_shape_parent']} of the {summary['child_ordinary_shape_count']} ordinary child shapes. This does not change their rooted predecessor scores or the rooted winner-to-winner counts above.", "",
                  "| Child ordinal | Predecessor of ordinary winning shape | H at its inherited root |", "|---:|---|---:|"])
    for child in children:
        for key, score in child["ordinary_winning_shape_parent_scores"].items():
            lines.append(f"| {child['ordinal']} | `{key}` | {score} |")
    lines.extend(["", "## Coverage of every previous global maximizer", "",
                  "| Parent ordinal | Parent key | Winning child keys |", "|---:|---|---|"])
    for parent in parent_winner_coverage:
        lines.append(f"| {parent['ordinal']} | `{parent['key']}` | " + (", ".join(f"`{key}`" for key in parent["child_keys"]) or "none under this operation") + " |")
    lines.extend(["", "## Insertion from a previous global maximizer", ""])
    for child in children:
        if child["has_global_maximizing_parent"]:
            operation = operations[child["best_operation_ids"][0]]
            growth = operation["canonical_parent_growth"]
            edge_text = ", ".join(f"{edge['source']} -> {edge['target']} (port {edge['port']})" for edge in growth["replace_parent_edges"])
            lines.extend([
                f"Start with the canonical {parent_m}-state maximizer `{operation['parent_key']}`:", "",
                "```json", compact(operation["parent_canonical_table"]), "```", "",
                f"Replace parent edges {edge_text} by edges to new vertex {growth['new_vertex']}. Give the new vertex outgoing ports {growth['new_vertex_outgoing_ports']}. The result is:", "",
                "```json", compact(growth["resulting_child_table"]), "```", "",
                f"Its rooted canonical key is `{child['key']}`; H increases from {operation['parent_merge_length']} to {child['merge_length']}, a gain of {operation['merge_length_increase']}.", "",
            ])
    lines.extend(["## Best parent operations", "", "Labels below refer to the child table. Removing v first reconnects the listed edges; inverse insertion sends their sources to v and gives v its original two outgoing ports. All best ties are retained.", ""])
    for child in children:
        lines.extend([f"### Child {child['ordinal']}: `{child['key']}`", ""])
        if child["best_parent_merge_length"] is None:
            lines.extend(["No permitted nonroot deletion gives an accessible parent. No score or gain is assigned.", ""])
        else:
            lines.extend([f"Best parent score {child['best_parent_merge_length']}; increase {child['increase_from_best_parent']}. Best parent classes: " + ", ".join(f"`{key}`" for key in child["best_parent_keys"]) + ".", ""])
        for operation_id in child["best_operation_ids"]:
            operation = operations[operation_id]
            edits = "; ".join(f"{edge['child_source']}[port {edge['port']}] -> {edge['child_target_after_deletion']}" for edge in operation["reconnections"])
            lines.append(f"- Operation {operation_id}: remove v={operation['deleted_vertex']} with outgoing ports {operation['deleted_outgoing_ports']}; reconnect {edits}. Parent `{operation['parent_key']}`.")
        lines.append("")
    reproduce = "uv run python scripts/family1_ancestry.py --all-sizes" if args.all_sizes else "uv run python scripts/family1_ancestry.py"
    lines.extend(["## Reproduce", "", "```powershell", reproduce, "uv run python tests/family1_ancestry_test.py", "```", "",
                  "`parents.jsonl` retains every distinct accessible parent class and its exact witness; `operations.jsonl` retains every deletion/bijection, including inaccessible results and explicit label/port mappings. `summary.json` pins all source hashes.", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(compact({key: summary[key] for key in ("child_maximizer_count", "children_with_global_maximizing_parent", "distinct_parent_classes", "operation_count", "accessible_operation_count", "inaccessible_operation_count")}))
    return summary


def run_all_sizes(args):
    output = args.output or REPO / "results/family1-ancestry-through7"
    pairs = []
    for child_m in range(2, 8):
        pair_args = argparse.Namespace(**vars(args))
        pair_args.child_m = child_m
        pair_args.children = (REPO / "results/family1-m1-m6") if child_m <= 6 else args.children
        pair_args.output = output / f"m{child_m - 1}-m{child_m}"
        pairs.append(run(pair_args))
    summary = {
        "schema": 1, "min_m": 1, "max_m": 7,
        "operation_scope": pairs[0]["operation_scope"],
        "scope_exhaustive": "All certified rooted maximizers at every size 2 through 7; every allowed nonroot indegree-2 deletion and routing bijection; every accessible parent looked up in the complete exact source journal.",
        "pairs": pairs,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    links = [{"parent_m": pair["parent_m"], "child_m": pair["child_m"], **link} for pair in pairs for link in pair["winner_links"]]
    (output / "winner-links.jsonl").write_text("".join(compact(link) + "\n" for link in links), encoding="utf-8")
    lines = ["# Consecutive-size ancestry of every certified winner through seven states", "",
             "All rooted maximizing classes are retained at each size. Each step deletes a nonroot vertex of indegree two and routes its incoming ports to its outgoing ports; the single-loop case smooths one external edge and removes the loop. Every allowed routing is tested and every accessible predecessor receives its exact score from the full small-case journal. This is a defined growth relation, not a claim that all graph changes must have this form.", "",
             "| Step | Maximum H | Rooted child winners | Children with a rooted winning parent | Previous winners reaching a winning child | Winner links |", "|---|---:|---:|---:|---:|---:|"]
    for pair in pairs:
        lines.append(f"| {pair['parent_m']} -> {pair['child_m']} | {pair['parent_global_maximum']} -> {pair['child_global_maximum']} | {pair['child_count']} | {pair['children_with_global_maximizing_parent']}/{pair['child_count']} | {pair['parent_winners_with_winning_child']}/{pair['parent_maximizer_count']} | {len(pair['winner_links'])} |")
    lines.extend(["", "## All consecutive steps", ""])
    for pair in pairs:
        lines.extend([f"### {pair['parent_m']} to {pair['child_m']}", "",
                      f"[Complete operations, all best ties, and every previous winner](m{pair['parent_m']}-m{pair['child_m']}/README.md).", "",
                      "| Child ordinal | Child key | Best parent H | Increase | Rooted winning parent keys |", "|---:|---|---:|---:|---|"])
        for child in pair["children"]:
            parents = [link["parent_key"] for link in pair["winner_links"] if link["child_key"] == child["key"]]
            best_text = child['best_parent_merge_length'] if child['best_parent_merge_length'] is not None else "none"
            increase_text = child['increase_from_best_parent'] if child['increase_from_best_parent'] is not None else "none"
            lines.append(f"| {child['ordinal']} | `{child['key']}` | {best_text} | {increase_text} | " + (", ".join(f"`{key}`" for key in parents) or "none") + " |")
        lines.append("")
    lines.extend(["## Reproduce", "", "```powershell", "uv run python scripts/family1_ancestry.py --all-sizes", "uv run python tests/family1_ancestry_test.py", "```", "",
                  "Each step has its own source hashes, exact parent witnesses, all operation details, canonical-parent insertion reconstructions, and explicit coverage of every previous maximizing class. The ordinary-shape comparison is reported separately and never changes a rooted score.", ""])
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(compact({"output": str(output), "pairs": len(pairs), "winner_links": len(links)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parents", type=Path, default=REPO / "out/family1-m1-m6/graphs.jsonl")
    parser.add_argument("--parent-summary", type=Path, default=REPO / "results/family1-m1-m6/summary.json")
    parser.add_argument("--children", type=Path, default=REPO / "results/family1-m7")
    parser.add_argument("--child-m", type=int, help="select one size from a multi-size certified collection")
    parser.add_argument("--all-sizes", action="store_true", help="audit every consecutive step from 1->2 through 6->7")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.all_sizes:
        run_all_sizes(args)
    else:
        args.output = args.output or REPO / "results/family1-ancestry-m6-m7"
        run(args)


if __name__ == "__main__":
    main()
