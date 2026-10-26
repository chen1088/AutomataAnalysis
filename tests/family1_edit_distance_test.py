#!/usr/bin/env python3
"""Independent tiny-class checks and complete saved edit certificates."""

import itertools
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_edit_distance import neighbors, verify_path
from family1_study import fixed_key, validate_table


def independent_key(table):
    """Try every root-fixing vertex permutation, independently of discovery."""
    m = len(table)
    result = []
    for tail in itertools.permutations(range(1, m)):
        mapping = (0,) + tail
        rows = [None] * m
        for source, row in enumerate(table):
            rows[mapping[source]] = tuple(sorted(mapping[target] for target in row))
        result.append(tuple(rows))
    return min(result)


class EditDistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiny = {}
        for m in range(1, 4):
            for values in itertools.product(range(m), repeat=2 * m):
                table = tuple(zip(values[::2], values[1::2]))
                try:
                    validate_table(table)
                except ValueError:
                    continue
                canonical = independent_key(table)
                cls.tiny[fixed_key(canonical)] = canonical
        cls.adjacency = {key: neighbors(table) for key, table in cls.tiny.items()}

    def test_exhaustive_tiny_classes_and_metric_connectivity(self):
        self.assertEqual(len(self.tiny), 1 + 6 + 57)
        reached = {"0000"}
        todo = ["0000"]
        while todo:
            current = todo.pop()
            for key in self.adjacency[current]:
                if key in self.tiny and key not in reached:
                    reached.add(key)
                    todo.append(key)
        self.assertEqual(reached, set(self.tiny))

    def test_every_tiny_move_is_reversible_on_classes(self):
        for source, sphere in self.adjacency.items():
            for target in sphere:
                if target in self.tiny:
                    self.assertIn(source, self.adjacency[target])

    def test_root_loops_and_coincident_occurrences(self):
        sphere = neighbors(((0, 0),))
        expected = {independent_key(((1, 1), (0, 0))),
                    independent_key(((0, 1), (0, 1)))}
        self.assertEqual({tuple(map(tuple, edge["after"])) for edge in sphere.values()}, expected)
        self.assertTrue(all(edge["operation"]["new_vertex"] == 1 for edge in sphere.values()))

    def test_saved_paths_complete_and_accessible(self):
        directory = REPO / "results/family1-edit-distance-through7"
        if not (directory / "paths.jsonl").is_file():
            self.skipTest("generate the edit-distance report first")
        records = [json.loads(line) for line in (directory / "paths.jsonl").read_text().splitlines()]
        sources = [json.loads(line) for line in (REPO / "results/family1-m1-m6/maximizers.jsonl").read_text().splitlines()]
        expected = {1: [1], 2: [2, 2], 3: [2], 4: [3, 3, 3, 2, 2], 5: [1, 2], 6: [3, 3, 3, 1, 3, 3, 3, 3]}
        self.assertEqual(len(records), 19)
        for m, distances in expected.items():
            subset = [record for record in records if record["parent_m"] == m]
            self.assertEqual([record["distance"] for record in subset], distances)
            source_tables = {tuple(map(tuple, source["canonical_table"])) for source in sources if source["m"] == m}
            ball = {fixed_key(table) for table in source_tables}
            for table in source_tables:
                ball.update(neighbors(table))
            for record in subset:
                verify_path(record, source_tables)
                if record["distance"] >= 2:
                    self.assertNotIn(record["target_key"], ball)
                if record["distance"] == 3:
                    self.assertFalse(ball.intersection(neighbors(record["target_table"])))


if __name__ == "__main__":
    unittest.main()
