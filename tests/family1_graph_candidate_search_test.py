#!/usr/bin/env python3
"""Independent all-mask, portfolio-proof, root-closure and resume regressions."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import family1_graph_candidate_search as search
from family1_threshold_cli_test import classes, endpoint

EXE = None


class CandidateSearchTest(unittest.TestCase):
    def test_full_static_vectors_and_permutation_counts(self):
        for m in (1, 2, 3):
            for table in classes(m):
                for n in range(5):
                    for letters in itertools.product("01", repeat=n):
                        word = "".join(letters)
                        packed = search.product_planes(table, word)
                        for mask in range(1 << m):
                            expected = endpoint(table, mask, word)
                            self.assertEqual([state for state, plane in enumerate(packed) if plane >> mask & 1], [expected])
                distinct = set()
                for mask in range(1 << m):
                    zero = tuple(table[state][(mask >> state) & 1] for state in range(m))
                    one = tuple(table[state][1 ^ ((mask >> state) & 1)] for state in range(m))
                    if len(set(zero)) == len(set(one)) == m:
                        distinct.add((zero, one))
                self.assertEqual(search.permutation_dfa_count(table), len(distinct))

    def test_large_exact_replay(self):
        table = tuple(((state + 1) % 20, (state + 1) % 20) for state in range(20))
        checked = search.verify_witness(table, ["0" * 64, "1" * 64])
        self.assertEqual(checked["mask_count"], 1 << 20)
        with self.assertRaises(ValueError):
            search.verify_witness(((0, 1), (0, 1)), ["0", "1"])

    def test_root_closure_includes_multiplicities_and_exclusions(self):
        graph = {"canonical_table": [[1, 1], [1, 1]]}
        bundle = search.root_bundle(graph)
        self.assertTrue(bundle["all_vertices_accounted_for"])
        self.assertEqual(len(bundle["roots"]), 1)
        self.assertEqual(bundle["excluded_vertices"], [{"vertex": 1, "reachable_count": 1}])
        bundle = search.root_bundle({"canonical_table": [[1, 1], [0, 0]]})
        self.assertEqual(len(bundle["roots"]), 1)
        self.assertEqual(bundle["roots"][0]["vertices_in_shape_table"], [0, 1])

    def test_no_truth_or_word_hints_enter_command(self):
        graph = {"canonical_table": [[0, 1], [0, 1]], "merge_length": 999,
                 "witness": ["evil", "hint"], "known_H": 999}
        args = search.arguments(["--candidates", __file__, "--out", "out/test-unused", "--enable-stage2"])
        clean = search.graph_metadata(graph)
        stages = search.stage_settings(clean, args)
        for stage in stages:
            actual = search.native_command("exe", clean, stage, 7, "output")
            self.assertNotIn("evil", actual)
            self.assertNotIn("hint", actual)
            self.assertNotIn("999", actual)
        self.assertEqual(search.graph_metadata(graph), search.graph_metadata({"canonical_table": graph["canonical_table"]}))

    def test_native_priority_and_root_bundle_cache(self):
        shapes = {}
        for table in classes(3):
            bundle = search.root_bundle({"canonical_table": table})
            shapes[bundle["shape_key"]] = bundle
        selected = [shapes[key] for key in sorted(shapes, reverse=True)[:2]]
        rows = []
        for bundle in selected:
            for root in bundle["roots"]:
                rows.append({**root, "path_ids": [len(rows)], "selection_index": len(rows)})
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "candidates.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with patch.object(search, "root_bundle", wraps=search.root_bundle) as closure:
                plan = search.materialize_plan([source], max_shapes=1)
                self.assertEqual(closure.call_count, 2)
            self.assertEqual(plan["shapes"][0]["shape_key"], selected[0]["shape_key"])
            self.assertGreater(plan["shapes"][0]["shape_key"], plan["shapes"][1]["shape_key"])
            self.assertTrue(plan["shapes"][0]["selected"])
            self.assertFalse(plan["shapes"][1]["selected"])
            self.assertEqual(sum(len(shape["source_links"]) for shape in plan["shapes"]), len(rows))
            self.assertEqual(plan["shapes"][0]["source_links"][0]["native_path_ids"], [0])

    def test_memory_and_elimination_mode(self):
        args = search.arguments(["--candidates", __file__, "--out", "out/test-unused", "--incumbent-lower", "34",
                                 "--enable-stage2", "--memory-mib", "32"])
        self.assertEqual(args.length_caps, [33])
        self.assertEqual(args.target_upper, 33)
        graph = search.graph_metadata({"canonical_table": [[(s + 1) % 20, (s + 6) % 20] for s in range(20)]})
        for stage in search.stage_settings(graph, args):
            self.assertTrue(stage["pair_working_estimate_exceeds_budget"])
            self.assertEqual(stage["prefix_words"], 1)
        args = search.arguments(["--candidates", __file__, "--out", "out/test-unused", "--incumbent-lower", "1"])
        self.assertEqual(args.length_caps, [])

    def test_all_lower_ties_and_potential_challengers_retained(self):
        tables = list(classes(2))[:3]
        imported = []
        for table, lower, upper in zip(tables, (2, 2, 1), (3, 2, None)):
            imported.append((search.interval_record({"canonical_table": table, "lower_bound": lower, "upper_bound": upper}), {"source": "test-certified"}))
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            summary = search.export(out, {"shapes": []}, imported, {}, set(), "hash")
            self.assertEqual(len(list(search.jsonl(out / "top-lower-bound-ties.jsonl"))), 2)
            self.assertEqual(len(list(search.jsonl(out / "unresolved-or-competitive.jsonl"))), 3)
            self.assertFalse(summary["global_maximum_certified"])
            self.assertFalse(summary["sizes"][0]["finite_record_maximum_value_certified"])
        records = {}
        first = search.interval_record({"canonical_table": tables[0], "lower_bound": 3})
        search.merge_interval(records, first, {})
        with self.assertRaises(ValueError):
            search.merge_interval(records, {**first, "lower_bound": 1, "upper_bound": 2}, {})

    def test_redundant_exact_interval_fields_must_not_contradict(self):
        row = {"canonical_table": [[0, 1], [0, 1]], "status": "exact", "merge_length": 3}
        for extra in ({"lower_bound": 4}, {"upper_bound": 2}, {"lower_bound": True}, {"upper_bound": "3"}):
            with self.assertRaises(ValueError):
                search.interval_record({**row, **extra})
        # Weaker, consistent certificates may coexist with the exact score.
        value = search.interval_record({**row, "lower_bound": 1, "upper_bound": 5})
        self.assertEqual((value["lower_bound"], value["upper_bound"]), (3, 3))

    def test_resource_skip_and_timeout_do_not_invent_bounds(self):
        graph = search.graph_metadata({"canonical_table": [[0, 1], [0, 1]]})
        args = search.arguments(["--candidates", __file__, "--out", "out/test-unused"])
        stage = search.stage_settings(graph, args)[0]
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            skipped = search.run_attempt(Path("missing.exe"), graph, {**stage, "pair_working_estimate_exceeds_budget": True}, 2, out / "resource")
            self.assertEqual(skipped["outcome"], "resource-budget")
            self.assertEqual(skipped["observation"]["lower_bound"], 1)
            self.assertIsNone(skipped["observation"]["upper_bound"])
            with patch.object(search.subprocess, "run", side_effect=subprocess.TimeoutExpired("native", 1)):
                timeout = search.run_attempt(Path("missing.exe"), graph, stage, 2, out / "timeout")
            self.assertEqual(timeout["outcome"], "timeout")
            self.assertEqual(timeout["observation"]["lower_bound"], 1)
            self.assertIsNone(timeout["observation"]["upper_bound"])

    def test_native_pipeline_all_roots_resume_and_corruption(self):
        if EXE is None:
            self.skipTest("native executable not supplied")
        with tempfile.TemporaryDirectory(prefix="f1-candidate-") as temporary:
            root = Path(temporary)
            source = root / "candidates.jsonl"
            rows = [{"canonical_table": [[0, 1], [0, 1]], "paths": [{"parent": "preserve-me"}]},
                    {"canonical_table": [[0, 1], [1, 2], [0, 1]], "root_metadata": {"native": True}}]
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            output = root / "run"
            command = ["--candidates", str(source), "--out", str(output), "--exe", str(EXE), "--incumbent-lower", "4",
                       "--jobs", "2", "--stage1-samples", "4", "--stage1-prefix-pairs", "4",
                       "--stage1-prefix-depth", "2", "--stage1-prefix-words", "4", "--prefix-samples-per-depth", "4",
                       "--stage1-timeout", "10"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(search.main(command), 0)
            summary = search.read_json(output / "summary.json")
            self.assertTrue(summary["all_selected_roots_scored"])
            self.assertGreaterEqual(summary["selected_root_classes"], 3)
            observations = list(search.jsonl(output / "observations.jsonl"))
            self.assertTrue(any(row["observation"]["decision"] == "collision" for _, row in observations))
            self.assertTrue(any(row["observation"]["decision"] == "unknown" for _, row in observations))
            old_summary = summary
            with redirect_stdout(io.StringIO()):
                self.assertEqual(search.main(command + ["--resume"]), 0)
            self.assertEqual(search.read_json(output / "summary.json"), old_summary)
            attempt_path = next(path for path in output.glob("queries/**/attempt.json")
                                if search.read_json(path)["native_result"])
            original = attempt_path.read_bytes()
            metadata = json.loads(original)
            graph = search.graph_metadata(metadata["graph"])
            for field, value in (("lower_bound", 999), ("witness", ["0", "1"]), ("key", "0000")):
                modified = json.loads(original)
                modified["observation"][field] = value
                search.atomic_json(attempt_path, modified)
                with self.assertRaises(ValueError):
                    search.load_attempt(attempt_path.parent, graph, metadata["stage"], metadata["length_cap"])
            attempt_path.write_bytes(original)
            plan_path = output / "plan.json"
            original_plan = plan_path.read_bytes()
            plan_path.write_bytes(original_plan + b" ")
            with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                search.main(command + ["--resume"])
            plan_path.write_bytes(original_plan)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    args, remaining = parser.parse_known_args()
    EXE = args.exe.resolve() if args.exe else None
    unittest.main(argv=[sys.argv[0], *remaining])
