#!/usr/bin/env python3
"""Independent checks of witness replay, score semantics, and provenance labels."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("hard_pair_witness_figure", REPO / "scripts/hard_pair_witness_figure.py")
figures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(figures)


class WitnessFigureTest(unittest.TestCase):
    def test_empty_agreement_and_later_loss_are_both_counted(self):
        family = [{"root": 0, "table": [[0, 1], [0, 0]]}]
        trace = figures.scalar_trace(["0000", "1111"], family)
        self.assertEqual(trace, [0, 1, 0, 1, 0])

    def test_family1_counts_every_original_mask_including_duplicates(self):
        certificate = figures.witness_record({"canonical_table": [[0, 0]], "witness": ["0", "1"], "upper_bound": 1, "attempts": 3})
        self.assertEqual(certificate["family_size"], 2)
        self.assertEqual(certificate["trace"], [{"length": 0, "differing": 0, "synchronized": 2},
                                                {"length": 1, "differing": 0, "synchronized": 2}])
        self.assertFalse(certificate["minimality_certified"])

    def test_refinement_k_does_not_become_witness_k(self):
        parameters = figures.search_parameters({"completed_k": 12, "max_attempted_k": 16})
        self.assertIsNone(parameters["k"])
        self.assertFalse(parameters["producer_k_known"])
        self.assertIn("k=unknown", figures.parameter_label(parameters))
        self.assertEqual(parameters["separate_refinement_completed_k"], 12)

    def test_bad_positive_or_saved_trace_is_rejected(self):
        family = [{"root": 0, "table": [[0, 1], [0, 0]]}]
        with self.assertRaisesRegex(ValueError, "fails scalar"):
            figures.scalar_trace(["0", "1"], family)
        with self.assertRaisesRegex(ValueError, "distinct"):
            figures.scalar_trace(["0", "0"], family)
        with self.assertRaisesRegex(ValueError, "metric trace"):
            figures.witness_record({"witness": ["00", "11"], "witness_metric_trace": [0, 0, 0]}, family)

    def test_native_startup_and_window_labels_keep_active_parameters(self):
        row = {"canonical_table": [[0, 1], [0, 1]], "witness": ["000", "110"], "k": 2,
               "alphabet": figures.ALPHABET, "startup": "divergence", "common_depth": 0,
               "prefix_pairs": 0, "common_prefix_depth": 8, "score": "total",
               "winning_attempt": {"initial_length": 1, "first_greedy_depth": 3},
               "greedy_advance": "whole joint window block", "witness_metric_trace": [0, 4, 2, 0]}
        record = figures.witness_record(row)
        label = figures.parameter_label(record["search_parameters"])
        self.assertIn("startup=divergence; c=0; score=total", label)
        self.assertNotIn("common-prefix depth=8", label)
        self.assertIn("first window ends at depth 3", figures.window_label(record))
        self.assertIn("First difference: depth 1", figures.window_label(record))
        record["search_parameters"]["winning_attempt"]["first_greedy_depth"] = 0
        self.assertIn("startup success before greedy windows", figures.window_label(record))
        self.assertNotIn("window ends at depth 0", figures.window_label(record))

    def test_saved_generic_fixture_cli_selects_case_and_k_and_keeps_all_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            family = [{"root": 0, "table": [[0, 1], [0, 0]]}, {"root": 0, "table": [[0, 0]]}]
            fixtures = {"cases": [{"id": "mixed", "family": family, "bases": family}]}
            row = {"id": "mixed", "k": 3, "alphabet": figures.ALPHABET, "beam": 2,
                   "upper_bound": 4, "witness": ["0000", "1111"], "verified_d_trace": [0, 1, 0, 1, 0]}
            (root / "fixtures.json").write_text(json.dumps(fixtures))
            (root / "records.jsonl").write_text(json.dumps(row) + "\n")
            process = subprocess.run([sys.executable, str(REPO / "scripts/hard_pair_witness_figure.py"),
                "--input", str(root / "records.jsonl"), "--fixtures", str(root / "fixtures.json"),
                "--case", "mixed", "--k", "3", "--out", str(root / "figure")], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            output = json.loads((root / "figure/witness.json").read_text())
            self.assertEqual(output["search_parameters"]["k"], 3)
            self.assertEqual(output["search_parameters"]["beam_width"], 2)
            self.assertEqual(output["family_size"], 2)
            self.assertEqual([entry["differing"] for entry in output["trace"]], [0, 1, 0, 1, 0])
            svg = ET.fromstring((root / "figure/witness.svg").read_text())
            edges = svg.findall('.//{http://www.w3.org/2000/svg}path[@data-source]')
            self.assertEqual(len(edges), 6)
            self.assertIn("k=3; joint-pair; B=2", (root / "figure/README.md").read_text())


if __name__ == "__main__":
    unittest.main()
