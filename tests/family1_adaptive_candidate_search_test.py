#!/usr/bin/env python3
"""Adaptive estimates, budget scaling, qualification and native resume guards."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import family1_adaptive_candidate_search as adaptive
import family1_graph_candidate_search as scoring

EXE = None


class AdaptiveTest(unittest.TestCase):
    def test_estimate_is_separate_and_uncertified(self):
        value = adaptive.estimate(52)
        self.assertEqual(value["point"], 51)
        self.assertEqual(value["rough_band"], [50, 52])
        self.assertFalse(value["certified"])
        self.assertNotIn("lower_bound", value)

    def test_pending_91_never_becomes_active_and_all_ties_remain(self):
        archive = {"a": {"key": "a", "eligible": True, "upper_bound": 52},
                   "b": {"key": "b", "eligible": True, "upper_bound": 52},
                   "c": {"key": "c", "eligible": True, "upper_bound": 50},
                   "pending": {"key": "pending", "eligible": False, "upper_bound": 91}}
        ordered = adaptive.leaderboard(archive)
        self.assertEqual([row["key"] for row in ordered], ["a", "b", "c"])
        self.assertEqual(len(adaptive.crowded_band(archive, 2)), 3)
        archive["a"]["upper_bound"] = 48
        archive["b"]["upper_bound"] = 49
        # The previous nonleader must be reconsidered after every update.
        self.assertEqual(adaptive.leaderboard(archive)[0]["key"], "c")

    def test_budget_covers_multiple_windows_and_all_beam_parents(self):
        for k in (6, 8, 10, 12, 16):
            quota = adaptive.expansion_budget(k, 16, 51)
            self.assertGreaterEqual(quota, 100000)
            self.assertGreaterEqual(quota, 4 * ((1 << (k + 1)) - 2) * 16)
            self.assertGreaterEqual(quota, adaptive.window_cost(k, 16, 50))
        self.assertEqual(adaptive.window_cost(10, 16, 50), 132990)
        self.assertEqual(adaptive.window_cost(16, 16, 50), 4325406)

    def test_stage_seed_and_prefix_are_constant(self):
        graph = scoring.graph_metadata({"canonical_table": [[0, 1], [0, 1]]})
        stages = [adaptive.build_stage(graph, k, 51) for k in (8, 10, 12, 16)]
        for field in ("seed", "samples", "prefix_pairs", "prefix_words", "prefix_depth", "prefix_samples_per_depth",
                      "common_prefix_depth", "beam_width", "distance_coordinates", "ranking"):
            self.assertEqual(len({stage[field] for stage in stages}), 1, field)

    def test_scalar_revisit_replay(self):
        graph = scoring.graph_metadata({"canonical_table": [[0, 1], [0, 1]]})
        checked = adaptive.replay_pair(graph["canonical_table"], "010", "100")
        self.assertEqual(checked["independent_scalar_masks_verified"], 4)
        with self.assertRaises(ValueError):
            adaptive.replay_pair(graph["canonical_table"], "0", "1")

    def test_resource_cap_is_unknown_without_completed_stage(self):
        graph = scoring.graph_metadata({"canonical_table": [[0, 1], [0, 1]]})
        stage = {**adaptive.build_stage(graph, 8, 8), "pair_working_estimate_exceeds_budget": True}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = adaptive.query(Path("missing.exe"), graph, stage, 8, directory, "plan-sha")
            self.assertEqual(result["outcome"], "resource-budget")
            self.assertIsNone(result["best_positive"])
            self.assertFalse(result["completed_stage"])
            self.assertIsNone(result["node_budget_cap_reported"])
            self.assertEqual(adaptive.query(Path("missing.exe"), graph, stage, 8, directory, "plan-sha"), result)

    def test_native_resume_checks_actual_evidence(self):
        if EXE is None:
            self.skipTest("native executable not supplied")
        graph = scoring.graph_metadata({"canonical_table": [[0, 1], [0, 1]]})
        stage = adaptive.build_stage(graph, 8, 8, samples=16, beam=4)
        with tempfile.TemporaryDirectory(prefix="f1-adaptive-") as temporary:
            directory = Path(temporary)
            result = adaptive.query(EXE, graph, stage, 8, directory, "plan-sha")
            self.assertTrue(result["completed_stage"])
            self.assertEqual(result["best_positive"]["upper_bound"], 3)
            self.assertEqual(adaptive.query(EXE, graph, stage, 8, directory, "plan-sha"), result)
            path = directory / "observation.json"
            original = path.read_bytes()
            for field, changed in (("upper_bound", 2), ("witness", ["0", "1"])):
                corrupted = json.loads(original)
                corrupted["best_positive"][field] = changed
                scoring.atomic_json(path, corrupted)
                with self.assertRaises(ValueError):
                    adaptive.query(EXE, graph, stage, 8, directory, "plan-sha")
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                adaptive.query(EXE, graph, stage, 8, directory, "different-plan-sha")

    def test_controller_qualifies_pending_without_losing_archive(self):
        if EXE is None:
            self.skipTest("native executable not supplied")
        prior = {**scoring.graph_metadata({"canonical_table": [[0, 1], [0, 1]]}),
                 "lower_bound": 1, "upper_bound": 3, "witness": ["010", "100"]}
        pending = {**scoring.graph_metadata({"canonical_table": [[1, 1], [0, 0]]}),
                   "lower_bound": 1, "upper_bound": 7, "witness": ["0" * 7, "1" * 7]}
        with tempfile.TemporaryDirectory(prefix="f1-adaptive-controller-") as temporary:
            base = Path(temporary)
            source, qualified, output = base / "input.jsonl", base / "qualified.jsonl", base / "run"
            scoring.write_jsonl(source, [prior, pending])
            scoring.write_jsonl(qualified, [prior])
            command = ["--records", str(source), "--refined-records", str(qualified), "--exe", str(EXE),
                       "--out", str(output), "--m", "2", "--admit-pending", "1", "--admit-first",
                       "--max-queries", "1", "--crowding-threshold", "10", "--jobs", "1",
                       "--query-seconds", "5", "--wall-seconds", "10"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(adaptive.main(command), 0)
            summary = scoring.read_json(output / "summary.json")
            self.assertEqual(summary["query_count"], 1)
            self.assertEqual(summary["eligible_refined_classes"], 2)
            self.assertEqual(summary["pending_coarse_classes"], 0)
            self.assertEqual(summary["active_verified_upper_length"], 3)
            active = [row for _, row in scoring.jsonl(output / "active-best.jsonl")]
            self.assertEqual([row["key"] for row in active], [prior["key"]])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(adaptive.main(command + ["--resume"]), 0)
            self.assertEqual(scoring.read_json(output / "summary.json"), summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    args, rest = parser.parse_known_args()
    EXE = args.exe.resolve() if args.exe else None
    unittest.main(argv=[sys.argv[0], *rest])
