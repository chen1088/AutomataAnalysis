#!/usr/bin/env python3
"""Mathematical graph/port and provenance regressions for the offline SVG atlas."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/family1_graph_atlas.py"
SPEC = importlib.util.spec_from_file_location("family1_graph_atlas", MODULE_PATH)
atlas = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas)
NS = {"svg": "http://www.w3.org/2000/svg"}


def record(table, lower=1, upper=None):
    result = {"m": len(table), "canonical_table": table, "status": "exact" if lower == upper else "lower-bound",
              "lower_bound": lower, "upper_bound": upper, "merge_length": upper if lower == upper else None,
              "key": "".join(str(target) for row in table for target in row),
              "witness": ["0" * upper, "1" * upper] if upper is not None else None}
    return result


class AtlasRegression(unittest.TestCase):
    def normalized(self, table):
        return atlas.normalize(record(table), Path("unverified.jsonl"), {})

    def test_every_state_and_port_preserved(self):
        examples = [
            [[0, 0]],
            [[1, 1], [0, 0]],
            [[0, 1], [1, 2], [0, 1]],
            [[(state + 1) % 20, (state + 7) % 20] for state in range(20)],
        ]
        for table in examples:
            graph = self.normalized(table)
            document = ET.fromstring(atlas.graph_svg(graph))
            nodes = document.findall('.//svg:g[@class="node"]', NS)
            self.assertEqual([int(node.attrib["data-state"]) for node in nodes], list(range(len(table))))
            self.assertEqual(len(nodes[0].findall("svg:circle", NS)), 2)
            self.assertTrue(all(len(node.findall("svg:circle", NS)) == 1 for node in nodes[1:]))
            edges = document.findall('.//svg:path[@class="edge"]', NS)
            actual = sorted((int(edge.attrib["data-source"]), int(edge.attrib["data-port"]), int(edge.attrib["data-target"])) for edge in edges)
            expected = sorted((state, port, target) for state, row in enumerate(table) for port, target in enumerate(row))
            self.assertEqual(actual, expected)
            for edge in edges:
                port = int(edge.attrib["data-port"])
                self.assertEqual(edge.attrib["stroke"], atlas.PORT_COLORS[port])
                self.assertEqual("stroke-dasharray" in edge.attrib, bool(port))
                self.assertIn(f"arrow{port}", edge.attrib["marker-end"])
            for source, row in enumerate(table):
                if row[0] == row[1]:
                    paths = [edge.attrib["d"] for edge in edges if int(edge.attrib["data-source"]) == source]
                    self.assertEqual(len(set(paths)), 2, "coincident ports must remain visually separate")

    def test_deterministic_nonoverlapping_layout(self):
        graph = self.normalized([[(state + 1) % 20, (state + 7) % 20] for state in range(20)])
        first, second = atlas.layout(graph), atlas.layout(graph)
        self.assertEqual(first, second)
        self.assertEqual(atlas.graph_svg(graph, first), atlas.graph_svg(graph, second))
        self.assertTrue(all(atlas.math.dist(first[a], first[b]) >= 35 for a in range(20) for b in range(a + 1, 20)))

    def test_evidence_merge_and_all_ties(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            rows = [record([[0, 1], [0, 0]], lower=2), record([[0, 1], [0, 1]], lower=3)]
            first.write_text("".join(json.dumps(row) + "\n" for row in rows))
            upgraded = record([[0, 1], [0, 0]], lower=3)
            upgraded["key"] = "00010000"  # Same table, a different export-key format.
            second.write_text(json.dumps(upgraded) + "\n")
            loaded = atlas.load_records([first, second])
            self.assertEqual(len(loaded), 2)
            self.assertTrue(all(row["best_bound_tie"] for row in loaded))
            self.assertEqual(loaded[0]["lower_bound"], 3)
            self.assertEqual(len(loaded[0]["sources"]), 2)
            self.assertFalse(any(row["maximum_certified"] for row in loaded))
            manifest = atlas.build_atlas([first, second], root / "atlas")
            self.assertEqual(manifest["graphs"], 2)
            self.assertEqual(manifest["sizes"][1]["best_bound_ties"], 2)
            self.assertEqual(len(list((root / "atlas/svg").glob("*.svg"))), 2)
            ET.fromstring((root / "atlas/contact-sheet.svg").read_text())
            html = (root / "atlas/index.html").read_text()
            self.assertIn("for(let m=1;m<=20;m++)", html)
            self.assertNotIn('src="http', html)
            self.assertNotIn('href="http', html)
            self.assertEqual(len((root / "atlas/graphs.jsonl").read_text().splitlines()), 2)

    def test_proof_badge_requires_explicit_matching_summary(self):
        raw = record([[0, 0]], lower=1, upper=1)
        self.assertFalse(atlas.normalize(raw, Path("maximizers.jsonl"), {})["maximum_certified"])
        summary = {"sizes": [{"m": 1, "enumeration_complete": True, "maximum_certified": True, "maximum_merge_length": 1}]}
        proved = atlas.normalize(raw, Path("maximizers.jsonl"), summary)
        self.assertTrue(proved["maximum_certified"])
        self.assertIn("PROVED MAXIMUM", atlas.graph_svg(proved))
        summary["sizes"][0]["maximum_merge_length"] = 2
        self.assertFalse(atlas.normalize(raw, Path("maximizers.jsonl"), summary)["maximum_certified"])
        unified = {"sizes": [{"m": 1, "maximum_value_certified": True,
                                "maximizing_collection_complete": False, "maximum_value": 1}]}
        self.assertFalse(atlas.normalize(raw, Path("champions.jsonl"), unified)["maximum_certified"])
        unified["sizes"][0]["maximizing_collection_complete"] = True
        self.assertTrue(atlas.normalize(raw, Path("champions.jsonl"), unified)["maximum_certified"])

    def test_inconsistent_certificates_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.jsonl"
            exact = record([[0, 0]], lower=1, upper=1)
            contradiction = record([[0, 0]], lower=2)
            path.write_text(json.dumps(exact) + "\n" + json.dumps(contradiction) + "\n")
            with self.assertRaisesRegex(ValueError, "Contradictory"):
                atlas.load_records([path])


if __name__ == "__main__":
    unittest.main()
