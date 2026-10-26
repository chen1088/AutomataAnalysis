#!/usr/bin/env python3
"""Describe every graph in a certified Family 1 maximizing collection.

Input must contain summary.json and maximizers.jsonl with explicit certificates
for the global maximum and the complete maximizing collection. The shared
read-only loader validates these flags, rooted canonical tables and all static
mask witnesses. Structural observations describe this finite collection only.

Ordinary shape grouping uses all vertex permutations for m <= 8; it permits
moving the root and never removes a rooted class from the report. Automorphism
counts count vertex permutations preserving each unordered pair of ports.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import permutations
import json
from pathlib import Path

from family1_certified_tikz import check, check_output_directory, load_certified_collection


def table_key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def relabel(table, mapping):
    result = [None] * len(table)
    for old, row in enumerate(table):
        result[mapping[old]] = tuple(sorted(mapping[target] for target in row))
    return tuple(result)


def ordinary_shape(table):
    """Exact ordinary canonical form and vertex symmetries, by all m! maps."""
    check(len(table) <= 8, "brute-force ordinary grouping is limited to eight states")
    best, best_mapping, canonical_roots, count = None, None, set(), 0
    for mapping in permutations(range(len(table))):
        candidate = relabel(table, mapping)
        if best is None or candidate < best:
            best, best_mapping = candidate, mapping
            canonical_roots, count = {mapping[0]}, 1
        elif candidate == best:
            canonical_roots.add(mapping[0])
            count += 1
    check(best is not None and count % len(canonical_roots) == 0, "invalid ordinary automorphism orbit")
    return {
        "ordinary_canonical_key": table_key(best),
        "ordinary_canonical_table": [list(row) for row in best],
        "old_to_ordinary_canonical_map": list(best_mapping),
        "root_in_ordinary_canonical_table": best_mapping[0],
        "root_orbit_in_ordinary_canonical_table": sorted(canonical_roots),
        "ordinary_vertex_automorphism_count": count,
        "rooted_vertex_automorphism_count": count // len(canonical_roots),
    }


def graph_statistics(table):
    m = len(table)
    indegrees = [0] * m
    loop_ports, coincident = [], []
    for state, row in enumerate(table):
        for port, target in enumerate(row):
            indegrees[target] += 1
            if target == state:
                loop_ports.append([state, port])
        if row[0] == row[1]:
            coincident.append(state)

    reachable = []
    for root in range(m):
        seen, pending = {root}, [root]
        for state in pending:
            for target in table[state]:
                if target not in seen:
                    seen.add(target)
                    pending.append(target)
        reachable.append(seen)
    remaining, components = set(range(m)), []
    while remaining:
        first = min(remaining)
        component = sorted(state for state in remaining
                           if state in reachable[first] and first in reachable[state])
        check(bool(component), "empty strongly connected component")
        components.append(component)
        remaining.difference_update(component)
    check(sum(indegrees) == 2 * m, "indegree count lost an outgoing port")
    return {
        "indegree_by_state": indegrees,
        "indegree_sequence_descending": sorted(indegrees, reverse=True),
        "root_indegree": indegrees[0],
        "loop_ports": loop_ports,
        "loop_port_count": len(loop_ports),
        "loop_states": sorted({state for state, _ in loop_ports}),
        "coincident_port_states": coincident,
        "coincident_port_count": len(coincident),
        "strongly_connected_components": components,
        "scc_sizes_descending": sorted((len(component) for component in components), reverse=True),
        "strongly_connected": len(components) == 1,
    }


def observations(records, states, shape_count):
    """Finite-set counts, without extrapolating an extremal characterization."""
    count = len(records)
    strong = sum(record["strongly_connected"] for record in records)
    loops = Counter(record["loop_port_count"] for record in records)
    coincident = Counter(record["coincident_port_count"] for record in records)
    indegrees = {tuple(record["indegree_sequence_descending"]) for record in records}
    result = [f"The certified m={states} collection contains {count} distinct rooted maximizing classes.",
              f"{strong} of these {count} rooted classes are strongly connected.",
              "Loop-port counts among the rooted classes: " + "; ".join(
                  f"{ports}: {number} classes" for ports, number in sorted(loops.items())) + ".",
              "Coincident-port state counts among the rooted classes: " + "; ".join(
                  f"{vertices}: {number} classes" for vertices, number in sorted(coincident.items())) + ".",
              f"There are {len(indegrees)} distinct sorted indegree sequences in this collection."]
    if shape_count is not None:
        result.append(f"Allowing the root to move groups these {count} rooted classes into {shape_count} ordinary shapes.")
    return result


def build_report(directory, states=7):
    summary, source_records, provenance = load_certified_collection(directory, states)
    records = []
    for index, source in enumerate(source_records, 1):
        table = tuple(tuple(row) for row in source["canonical_table"])
        record = {
            "index": index,
            "m": states,
            "key": source["key"],
            "canonical_table": source["canonical_table"],
            "merge_length": source["merge_length"],
            "status": "exact",
            "witness": source["witness"],
            **graph_statistics(table),
        }
        if states <= 8:
            record.update(ordinary_shape(table))
        records.append(record)

    groups = None
    if states <= 8:
        groups = []
        for index, key in enumerate(sorted({record["ordinary_canonical_key"] for record in records}), 1):
            members = [record for record in records if record["ordinary_canonical_key"] == key]
            for record in members:
                record["ordinary_shape_index"] = index
            groups.append({
                "ordinary_shape_index": index,
                "ordinary_canonical_key": key,
                "ordinary_canonical_table": members[0]["ordinary_canonical_table"],
                "ordinary_vertex_automorphism_count": members[0]["ordinary_vertex_automorphism_count"],
                "rooted_class_count": len(members),
                "rooted_keys": [record["key"] for record in members],
                "canonical_root_orbits": [record["root_orbit_in_ordinary_canonical_table"] for record in members],
            })
    shape_count = None if groups is None else len(groups)
    report = {
        "schema_version": 1,
        "m": states,
        "maximum_merge_length": summary["maximum_merge_length"],
        "maximum_value_certified": True,
        "maximizing_collection_complete": True,
        "rooted_class_count": len(records),
        "ordinary_shape_count": shape_count,
        "ordinary_grouping": "all-vertex-permutations" if groups is not None else "not-computed-above-eight-states",
        "ordinary_permutations_per_graph": None if groups is None else factorial(states),
        "conventions": {
            "indegrees": "Both outgoing ports count, including loops and coincident ports; sequences are descending.",
            "loop_ports": "Each pair is [source state, port index] in the rooted canonical table.",
            "automorphisms": "Vertex permutations preserving the unordered pair of outgoing targets; port swaps are not counted separately.",
            "ordinary_shapes": "Root-moving equivalence is reported separately; every rooted class is retained.",
            "observations": "Descriptive statements concern only this finite certified collection.",
        },
        "provenance": {name: value for name, value in provenance.items() if name != "summary_bytes"},
        "records": records,
        "ordinary_shape_groups": groups,
        "finite_collection_observations": observations(records, states, shape_count),
    }
    return report


def factorial(value):
    result = 1
    for factor in range(2, value + 1):
        result *= factor
    return result


def comma_list(values):
    return ",".join(str(value) for value in values) if values else "none"


def markdown(report):
    states, count = report["m"], report["rooted_class_count"]
    lines = [f"# Family 1 maximizing graph structures: m={states}", "",
             f"Certified maximum H={report['maximum_merge_length']}; complete collection of {count} rooted classes.", "",
             "Indegrees count both ports and are sorted in descending order. Loop ports use `state:port`. "
             "The root column gives its positions in the ordinary canonical table. Automorphisms count vertex permutations.", "",
             "| Class | Rooted key | H | Indegrees | Loop ports | Coincident states | SCC sizes | Shape | Root orbit | Aut |",
             "| --- | --- | ---: | --- | --- | --- | --- | ---: | --- | ---: |"]
    for record in report["records"]:
        loops = ",".join(f"{state}:{port}" for state, port in record["loop_ports"]) or "none"
        lines.append("| " + " | ".join((
            str(record["index"]), f"`{record['key']}`", str(record["merge_length"]),
            comma_list(record["indegree_sequence_descending"]), loops,
            comma_list(record["coincident_port_states"]), comma_list(record["scc_sizes_descending"]),
            str(record.get("ordinary_shape_index", "uncomputed")),
            comma_list(record["root_orbit_in_ordinary_canonical_table"]) if "root_orbit_in_ordinary_canonical_table" in record else "uncomputed",
            str(record.get("ordinary_vertex_automorphism_count", "uncomputed")),
        )) + " |")
    if report["ordinary_shape_groups"] is not None:
        lines += ["", "| Shape | Ordinary canonical key | Rooted classes | Canonical root orbits | Vertex automorphisms |",
                  "| ---: | --- | ---: | --- | ---: |"]
        for group in report["ordinary_shape_groups"]:
            roots = "; ".join(comma_list(orbit) for orbit in group["canonical_root_orbits"])
            lines.append(f"| {group['ordinary_shape_index']} | `{group['ordinary_canonical_key']}` | "
                         f"{group['rooted_class_count']} | {roots} | {group['ordinary_vertex_automorphism_count']} |")
    lines += ["", "Observed within this finite certified collection:", ""]
    lines.extend(f"- {observation}" for observation in report["finite_collection_observations"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Certified directory containing summary.json and maximizers.jsonl")
    parser.add_argument("--states", default=7, type=int)
    parser.add_argument("--out", required=True, type=Path, help="New or empty report directory")
    parser.add_argument("--validate-only", action="store_true", help="Build the report in memory; create no output files or directories")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.input, args.states)
        output = check_output_directory(args.out)
        files = {
            "structure.json": (json.dumps(report, indent=2) + "\n").encode("utf-8"),
            "structure.md": markdown(report).encode("utf-8"),
        }
        if not args.validate_only:
            # Validate and compute everything before changing the destination.
            output = check_output_directory(output)
            output.mkdir(parents=True, exist_ok=True)
            for name, data in sorted(files.items()):
                with (output / name).open("xb") as destination:
                    destination.write(data)
        print(json.dumps({"m": args.states, "maximum_merge_length": report["maximum_merge_length"],
                          "rooted_classes": report["rooted_class_count"], "ordinary_shapes": report["ordinary_shape_count"],
                          "files_authored": 0 if args.validate_only else len(files),
                          "file_sha256": {} if args.validate_only else {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"family1_structure_report: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
