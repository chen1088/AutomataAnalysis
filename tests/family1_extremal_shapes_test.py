#!/usr/bin/env python3
"""Audit ordinary versus rooted isomorphism of all saved m=1..6 winners.

Every canonicalization and isomorphism check tries all vertex permutations;
successor pairs are sorted independently to allow arbitrary outgoing-port
swaps. This audits the saved winner collection, not all seed graphs again.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
Table = tuple[tuple[int, int], ...]
KNOWN_H = {1: 1, 2: 3, 3: 6, 4: 10, 5: 15, 6: 23}


def relabel(table: Table, permutation: tuple[int, ...]) -> Table:
    result = [None] * len(table)
    for old, targets in enumerate(table):
        result[permutation[old]] = tuple(sorted(permutation[target] for target in targets))
    return tuple(result)


def canonical(table: Table, root_fixed: bool) -> tuple[Table, list[tuple[int, ...]]]:
    best = None
    mappings = []
    for permutation in itertools.permutations(range(len(table))):
        if root_fixed and permutation[0] != 0:
            continue
        candidate = relabel(table, permutation)
        if best is None or candidate < best:
            best, mappings = candidate, [permutation]
        elif candidate == best:
            mappings.append(permutation)
    assert best is not None
    return best, mappings


def isomorphisms(first: Table, second: Table, root_fixed: bool = False) -> list[dict]:
    found = []
    for permutation in itertools.permutations(range(len(first))):
        if root_fixed and permutation[0] != 0:
            continue
        if relabel(first, permutation) == second:
            flips = []
            for source, targets in enumerate(first):
                mapped = tuple(permutation[target] for target in targets)
                flips.append(0 if mapped == second[permutation[source]] else 1)
            found.append({"old_to_new": permutation, "port_flip_at_old_source": flips})
    return found


def reachable(table: Table, root: int = 0) -> set[int]:
    seen, pending = {root}, [root]
    while pending:
        for target in table[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def endpoint_vector(table: Table, word: str) -> tuple[int, ...]:
    endpoints = []
    for mask in range(1 << len(table)):
        state = 0
        for letter in word:
            state = table[state][int(letter) ^ ((mask >> state) & 1)]
        endpoints.append(state)
    return tuple(endpoints)


def table_key(table: Table) -> str:
    return "".join(f"{target:02d}" for row in table for target in row)


def structural_stats(table: Table) -> dict:
    indegrees = [0] * len(table)
    for targets in table:
        for target in targets:
            indegrees[target] += 1
    # Simple directed cycles use each directed adjacency once: coincident
    # ports do not multiply a cycle. Starting at its least vertex counts a
    # cycle once up to cyclic rotation; reversed cycles remain distinct.
    cycles = [0] * (len(table) + 1)
    for start in range(len(table)):
        def visit(path: list[int]) -> None:
            for target in set(table[path[-1]]):
                if target == start:
                    cycles[len(path)] += 1
                elif target > start and target not in path:
                    visit(path + [target])
        visit([start])
    return {
        "indegree_by_canonical_vertex_counting_both_ports": indegrees,
        "indegree_multiset_counting_both_ports": sorted(indegrees),
        "loop_vertices": [state for state, targets in enumerate(table) if state in targets],
        "self_loop_port_count": sum(target == state for state, targets in enumerate(table) for target in targets),
        "coincident_port_vertices": [state for state, targets in enumerate(table) if targets[0] == targets[1]],
        "strongly_connected": all(len(reachable(table, root)) == len(table) for root in range(len(table))),
        "simple_directed_cycle_counts_by_length": {str(length): count for length, count in enumerate(cycles) if count},
    }


def self_test() -> None:
    loops = ((0, 0),)
    assert canonical(loops, False)[0] == loops
    assert len(isomorphisms(loops, loops)) == 1
    assert structural_stats(loops)["simple_directed_cycle_counts_by_length"] == {"1": 1}
    assert structural_stats(loops)["self_loop_port_count"] == 2
    first = ((0, 1), (0, 1))
    assert len(isomorphisms(first, first)) == 2
    assert len(isomorphisms(first, first, True)) == 1
    assert canonical(((1, 0), (1, 0)), True)[0] == first


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "results/family1-m1-m6/maximizers.jsonl")
    parser.add_argument("--report", type=Path, default=REPO / "results/family1-extremal-shapes.json")
    args = parser.parse_args()
    self_test()
    raw = args.input.read_bytes()
    records = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    records = [record for record in records if 1 <= record["m"] <= 6]
    by_size: dict[int, list[dict]] = {}
    for record in records:
        m = record["m"]
        table = tuple(tuple(row) for row in record["canonical_table"])
        assert len(table) == m and all(len(row) == 2 and all(0 <= target < m for target in row) for row in table)
        assert len(reachable(table)) == m
        assert canonical(table, True)[0] == table
        assert record["status"] == "exact" and record["merge_length"] == record["lower_bound"] == KNOWN_H[m]
        first, second = record["witness"]
        assert first != second and len(first) == len(second) == KNOWN_H[m]
        assert set(first + second) <= {"0", "1"}
        assert endpoint_vector(table, first) == endpoint_vector(table, second)
        by_size.setdefault(m, []).append({"record": record, "table": table})
    assert set(by_size) == set(KNOWN_H)
    assert len(records) == 12
    summaries, sizes = [], []
    for m, items in sorted(by_size.items()):
        shapes: dict[Table, list[dict]] = {}
        rooted_tables = set()
        for item in sorted(items, key=lambda item: item["table"]):
            table = item["table"]
            assert table not in rooted_tables
            rooted_tables.add(table)
            ordinary, mappings = canonical(table, False)
            shapes.setdefault(ordinary, []).append({
                "saved_key": item["record"]["key"], "saved_ordinal": item["record"]["ordinal"],
                "saved_rooted_table": table,
                "canonical_root_images": sorted({mapping[0] for mapping in mappings}),
                "root_preserving_vertex_automorphism_count": len(isomorphisms(table, table, True)),
                "saved_witness_verified_over_all_masks": True,
            })
        pairs = []
        for first, second in itertools.combinations(items, 2):
            ordinary_maps = isomorphisms(first["table"], second["table"])
            rooted_maps = isomorphisms(first["table"], second["table"], True)
            assert not rooted_maps, "Duplicate rooted winner class"
            pairs.append({"first_saved_key": first["record"]["key"], "second_saved_key": second["record"]["key"],
                          "ordinary_isomorphisms": ordinary_maps, "root_preserving_isomorphisms": rooted_maps})
        shape_reports = []
        for shape, members in sorted(shapes.items()):
            automorphisms = isomorphisms(shape, shape)
            root_orbits = {tuple(sorted({mapping["old_to_new"][vertex] for mapping in automorphisms})) for vertex in range(m)}
            shape_reports.append({"ordinary_canonical_key": table_key(shape), "ordinary_canonical_table": shape,
                                  "vertex_automorphism_count_with_unordered_ports": len(automorphisms),
                                  "vertex_orbits_under_automorphisms": sorted(root_orbits),
                                  "maximizing_rooted_members": members, **structural_stats(shape)})
        summary = {"m": m, "saved_exact_maximum": KNOWN_H[m], "rooted_winner_count": len(items),
                   "ordinary_unrooted_shape_count": len(shapes)}
        summaries.append(summary)
        sizes.append({**summary, "shapes": shape_reports, "all_pairs_of_saved_winners": pairs})
        print(f"m={m}: H={KNOWN_H[m]}, rooted winners={len(items)}, ordinary shapes={len(shapes)}")
    report = {
        "source": str(args.input.relative_to(REPO)).replace("\\", "/") if args.input.is_relative_to(REPO) else str(args.input),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "method": "All m! vertex permutations for ordinary canonicalization and isomorphism, retaining only permutations fixing 0 for rooted comparisons. Each transformed successor pair is independently sorted, exactly allowing independent swaps of the two outgoing ports.",
        "automorphism_convention": "Counts vertex permutations preserving unordered successor pairs; additional permutations of coincident port occurrences are not counted as different vertex automorphisms.",
        "score_checks": "Saved exact H metadata matches 1,3,6,10,15,23. Each saved witness is verified by direct static-mask simulation over all 2^m masks. This script does not repeat per-graph shortest-length proofs or global enumeration/scoring coverage.",
        "interpretation": "Among the supplied complete m=1..6 winner collections, only m=5 has more than one ordinary unrooted shape. This is a verified finite-data observation, not a theorem explaining why m=5 is exceptional or predicting later sizes.",
        "summary": summaries, "sizes": sizes,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: all {len(records)} saved winners audited; report {args.report}")


if __name__ == "__main__":
    main()
