#!/usr/bin/env python3
"""Independent tiny fixtures and regression checks for one-vertex smoothing."""

import json
import itertools
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_ancestry import canonical_mapping, reconstruct_child, smoothing_operations
from family1_study import canonical_table, fixed_key, validate_table


class AncestryTests(unittest.TestCase):
    def test_two_edge_insertion_has_both_bijections(self):
        # Subdivide both root loops with one new vertex.
        child = ((1, 1), (0, 0))
        operations = list(smoothing_operations(child))
        self.assertEqual(len(operations), 2)  # Port-distinct bijections survive coincident targets.
        self.assertNotEqual(operations[0]["incoming_to_outgoing_port_bijection"],
                            operations[1]["incoming_to_outgoing_port_bijection"])
        for operation in operations:
            self.assertEqual(operation["parent_canonical_table"], ((0, 0),))
            self.assertEqual(reconstruct_child(((0, 0),), operation), child)

    def test_loop_subdivision(self):
        child = ((0, 1), (0, 1))
        operations = list(smoothing_operations(child))
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["kind"], "smooth-one-edge-and-remove-loop")
        self.assertEqual(reconstruct_child(((0, 0),), operations[0]), child)

    def test_inaccessible_reconnection_retained(self):
        child = ((0, 1), (0, 2), (0, 1))
        operations = list(smoothing_operations(child))
        inaccessible = [operation for operation in operations if not operation["accessible"]]
        self.assertTrue(inaccessible)
        self.assertTrue(all(operation["deleted_vertex"] != 0 for operation in operations))

    def test_factorial_canonical_mapping_preserves_root_and_ports(self):
        table = ((2, 0), (2, 1), (0, 1))
        canonical, mapping, flips = canonical_mapping(table)
        self.assertEqual(canonical, canonical_table(table))
        self.assertEqual(mapping[0], 0)
        for source, row in enumerate(table):
            self.assertEqual(tuple(mapping[target] for target in row)[:: -1 if flips[source] else 1],
                             canonical[mapping[source]])

    def test_all_reported_reverse_insertions_and_all_best_ties(self):
        directory = REPO / "results/family1-ancestry-m6-m7"
        if not (directory / "summary.json").exists():
            self.skipTest("run ancestry script to generate regression data")
        summary = json.loads((directory / "summary.json").read_text())
        operations = [json.loads(line) for line in (directory / "operations.jsonl").read_text().splitlines()]
        self.assertEqual([child["best_parent_merge_length"] for child in summary["children"]],
                         [21, 22, 21, 23, 22, 22, 22, 22])
        self.assertEqual(summary["children_with_global_maximizing_parent"], 1)
        self.assertEqual(summary["children_with_ordinary_winning_shape_parent"], 3)
        self.assertEqual(summary["child_ordinary_shape_count"], 4)
        self.assertEqual(summary["child_ordinary_shapes_with_ordinary_winning_shape_parent"], 3)
        children = {child["key"]: tuple(map(tuple, child["canonical_table"])) for child in summary["children"]}
        for operation in operations:
            if operation["accessible"]:
                self.assertEqual(reconstruct_child(operation["parent_table_before_canonicalization"], operation),
                                 children[operation["child_key"]])
                growth = operation["canonical_parent_growth"]
                reconstructed = [list(row) for row in operation["parent_canonical_table"]]
                reconstructed.append(growth["new_vertex_outgoing_ports"])
                for edge in growth["replace_parent_edges"]:
                    self.assertEqual(reconstructed[edge["source"]][edge["port"]], edge["target"])
                    reconstructed[edge["source"]][edge["port"]] = growth["new_vertex"]
                self.assertEqual(reconstructed, growth["resulting_child_table"])
                self.assertEqual(canonical_table(reconstructed), children[operation["child_key"]])
        for child in summary["children"]:
            eligible = [operation for operation in operations if operation["child_key"] == child["key"] and operation["accessible"]]
            best = max(operation["parent_merge_length"] for operation in eligible)
            self.assertEqual(child["best_operation_ids"], [operation["operation_id"] for operation in eligible if operation["parent_merge_length"] == best])

    def test_all_consecutive_steps_and_complete_winner_coverage(self):
        directory = REPO / "results/family1-ancestry-through7"
        if not (directory / "summary.json").exists():
            self.skipTest("run ancestry script --all-sizes to generate regression data")
        summary = json.loads((directory / "summary.json").read_text())
        pairs = summary["pairs"]
        self.assertEqual([(pair["parent_m"], pair["child_m"]) for pair in pairs], list(zip(range(1, 7), range(2, 8))))
        self.assertEqual([pair["child_count"] for pair in pairs], [1, 2, 1, 5, 2, 8])
        self.assertEqual([pair["children_with_global_maximizing_parent"] for pair in pairs], [1, 0, 0, 0, 1, 1])
        self.assertEqual([pair["parent_maximizer_count"] for pair in pairs], [1, 1, 2, 1, 5, 2])
        self.assertEqual(sum(pair["operation_count"] for pair in pairs), 137)
        for pair in pairs:
            operations = [json.loads(line) for line in (directory / f"m{pair['parent_m']}-m{pair['child_m']}" / "operations.jsonl").read_text().splitlines()]
            children = {child["key"]: tuple(map(tuple, child["canonical_table"])) for child in pair["children"]}
            expected_links = {}
            for operation in operations:
                if not operation["accessible"]:
                    continue
                self.assertEqual(reconstruct_child(operation["parent_table_before_canonicalization"], operation), children[operation["child_key"]])
                if operation["parent_merge_length"] == pair["parent_global_maximum"]:
                    expected_links.setdefault((operation["parent_key"], operation["child_key"]), []).append(operation["operation_id"])
            self.assertEqual({(link["parent_key"], link["child_key"]): link["operation_ids"] for link in pair["winner_links"]}, expected_links)
            for parent in pair["parent_winner_coverage"]:
                self.assertEqual(parent["has_winning_child"], any(key[0] == parent["key"] for key in expected_links))
        five_to_six = pairs[4]
        self.assertEqual([(parent["ordinal"], parent["has_winning_child"]) for parent in five_to_six["parent_winner_coverage"]],
                         [(1391, True), (1511, True), (5982, False), (6241, False), (6811, False)])

    def test_independent_forward_growth_matches_inverse_at_small_sizes(self):
        # Generate forward from EVERY accessible parent class, independently of
        # deleted-vertex routing, and compare all parent classes for the winners.
        directory = REPO / "results/family1-ancestry-through7"
        if not (directory / "summary.json").exists():
            self.skipTest("run ancestry script --all-sizes to generate regression data")
        parents = {1: [], 2: []}
        with (REPO / "out/family1-m1-m6/graphs.jsonl").open(encoding="utf-8-sig") as source:
            for line in source:
                record = json.loads(line)
                if record["m"] in parents:
                    parents[record["m"]].append(record["canonical_table"])
        for parent_m in (1, 2):
            forward = {}
            for parent in parents[parent_m]:
                parent_key = fixed_key(parent)
                ports = list(itertools.product(range(parent_m), (0, 1)))
                selections = [(port,) for port in ports] + list(itertools.combinations(ports, 2))
                for selected in selections:
                    grown = [list(row) for row in parent]
                    targets = [grown[source][port] for source, port in selected]
                    grown.append(targets + ([parent_m] if len(selected) == 1 else []))
                    for source, port in selected:
                        grown[source][port] = parent_m
                    key = fixed_key(canonical_table(validate_table(grown)))
                    forward.setdefault(key, set()).add(parent_key)
            pair_directory = directory / f"m{parent_m}-m{parent_m + 1}"
            pair = json.loads((pair_directory / "summary.json").read_text())
            operations = [json.loads(line) for line in (pair_directory / "operations.jsonl").read_text().splitlines()]
            for child in pair["children"]:
                inverse = {operation["parent_key"] for operation in operations if operation["accessible"] and operation["child_key"] == child["key"]}
                self.assertEqual(inverse, forward.get(child["key"], set()))


if __name__ == "__main__":
    unittest.main()
