#!/usr/bin/env python3
"""Graph-growth, root, proof replay, and resume tests for the local search."""

import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import family1_neighbor_search as search
from family1_atlas_dataset import extension
from family1_study import compact, file_hash, fixed_key


def options(output, **overrides):
    values = dict(out=Path(output), exe=Path(sys.executable), seeds=[], shape_seeds=[],
                  baselines=REPO / "results/family1-atlas-current/champions.jsonl",
                  min_m=8, max_m=8, radius=2, shapes_per_size=1, candidate_shapes=3,
                  path_budget=64, jobs=2, threshold=34, timeout_ms=50, solve_timeout_ms=50,
                  max_refinements=8, projection_masks=4, limit_graphs=0,
                  generate_only=True, resume=False)
    return argparse.Namespace(**(values | overrides))


class NeighborSearchTests(unittest.TestCase):
    def test_root_bundle_accounts_for_asymmetry_and_inaccessible_roots(self):
        bundle = search.root_bundle(((1, 1), (1, 1)))
        self.assertEqual([root["original_roots"] for root in bundle["roots"]], [[0]])
        self.assertEqual(bundle["excluded_roots"], [{"root": 1, "reachable_states": 1,
                                                   "reason": "not an exact-m reachable seed from this root"}])
        self.assertTrue(bundle["all_vertices_accounted_for"])
        # Both roots of the accessible two-cycle are represented by one orbit.
        cycle = search.root_bundle(((1, 1), (0, 0)))
        self.assertEqual(cycle["roots"][0]["original_roots"], [0, 1])

    def test_root_bound_applies_only_to_projection_start(self):
        baseline = extension(8)
        bundle = search.root_bundle(baseline["canonical_table"])
        bundle.update(baseline=True, construction=baseline["construction"])
        records = {}
        search.add_plan_records(records, {"candidate_shapes": [], "selected_shapes": [bundle]})
        projection = baseline["construction"]["canonical_projection_to_base"]
        for root in bundle["roots"]:
            expected = 34 if any(projection[state] == 0 for state in root["original_roots"]) else 1
            self.assertEqual(records[(8, root["key"])]["lower_bound"], expected)

    def test_unknown_preserves_lower_and_contradiction_fails(self):
        records = {}
        table = ((0, 0),)
        base = dict(m=1, canonical_table=table, lower_bound=34, upper_bound=None)
        search.merge_record(records, base, {"kind": "test"})
        row = search.merge_record(records, {**base, "lower_bound": 1}, {"kind": "unknown"})
        self.assertEqual(row["lower_bound"], 34)
        with self.assertRaises(ValueError):
            search.merge_record(records, {**base, "lower_bound": 1, "upper_bound": 33}, {"kind": "contradiction"})

    def test_root_robustness_uses_lower_evidence_and_vertex_multiplicity(self):
        table = ((1, 1), (0, 0))
        parent = search.normalize(dict(m=2, canonical_table=table, lower_bound=7, upper_bound=None))
        records = {(2, parent["key"]): parent}
        ranked = search.rank_parent_roots([parent], records)
        self.assertEqual(ranked[0]["root_robustness"]["certified_vertex_roots_near_leader"], 2)
        self.assertEqual(ranked[0]["root_robustness"]["certified_root_classes_near_leader"], 1)
        other = search.normalize(dict(m=2, canonical_table=((0, 1), (0, 0)), lower_bound=1, upper_bound=100))
        records[(2, other["key"])] = other
        ranked = search.rank_parent_roots([other], records)
        self.assertEqual(ranked[0]["root_robustness"]["certified_vertex_roots_near_leader"], 0)

    def test_resume_reconstructs_native_and_rejects_journal_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = options(temporary)
            table = ((0, 0),)
            root = dict(m=1, key=fixed_key(table), canonical_table=table)
            native = dict(**root, length=34, decision="unknown", lower_bound=1, upper_bound=None,
                          witness=None, scalar_witness_masks_verified=0, reason="test-budget")
            path = Path(temporary) / "result.json"
            path.write_text(json.dumps(native))
            proof = dict(path=str(path), sha256=file_hash(path))
            answer = search.observation_from_native(native, root, args, proof)
            self.assertEqual(compact(search.replay_observation(answer, args)), compact(answer))
            for field, value in (("lower_bound", 99), ("witness", ["0", "1"]), ("key", "0101")):
                bad = copy.deepcopy(answer)
                bad[field] = value
                with self.assertRaisesRegex(ValueError, "journal observation"):
                    search.replay_observation(bad, args)
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "integrity"):
                search.replay_observation(answer, args)

    def test_collision_needs_full_scalar_static_mask_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = options(temporary, threshold=1)
            root = dict(m=1, key="0000", canonical_table=((0, 0),))
            native = dict(**root, length=1, decision="collision", lower_bound=1, upper_bound=1,
                          witness=["0", "1"], scalar_witness_masks_verified=1)
            with self.assertRaisesRegex(ValueError, "scalar"):
                search.observation_from_native(native, root, args, {})
            native["scalar_witness_masks_verified"] = 2
            self.assertEqual(search.observation_from_native(native, root, args, {})["upper_bound"], 1)

    def test_generate_only_resume_and_plan_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = options(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                search.run(args)
            plan_path = args.out / "plans/m8/plan.json"
            first = plan_path.read_bytes()
            args.resume = True
            with contextlib.redirect_stdout(io.StringIO()):
                search.run(args)
            self.assertEqual(plan_path.read_bytes(), first)
            plan_path.write_bytes(first + b" ")
            with self.assertRaisesRegex(ValueError, "plan integrity"):
                search.run(args)

    def test_budgeted_generation_keeps_both_orders_and_root_bundles(self):
        known, _, _ = search.load_inputs(options("unused"))
        parents = [record for (m, _), record in known.items() if m == 7]
        args = options("unused", candidate_shapes=12, path_budget=256)
        parents = search.rank_parent_roots(parents, known)
        plan = search.generate_plan(8, parents, extension(8), args)
        patterns = {path["pattern"] for path in plan["generation_paths"]}
        self.assertEqual(patterns, {"G", "GR", "RG"})
        self.assertFalse(plan["generation_complete_within_requested_patterns"])
        for bundle in plan["selected_shapes"]:
            self.assertTrue(bundle["all_vertices_accounted_for"])
            self.assertEqual(sum(len(root["original_roots"]) for root in bundle["roots"]) + len(bundle["excluded_roots"]), 8)
        for path in plan["generation_paths"]:
            self.assertEqual(len(path["steps"]), path["rooted_edit_distance_upper_bound_before_root_closure"])
            self.assertFalse(path["root_change_included_in_distance_bound"])

    def test_baseline_cannot_import_an_invented_lower_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = options(temporary)
            baseline = extension(8)
            baseline["lower_bound"] = 35
            args.baselines = Path(temporary) / "bad-baseline.jsonl"
            search.write_jsonl(args.baselines, [baseline])
            with self.assertRaisesRegex(ValueError, "baseline"):
                search.load_inputs(args)

    def test_native_limit_resume_keeps_entire_selected_root_bundle(self):
        executable = REPO / "out/build/msvc-vcpkg/Release/Family1Threshold.exe"
        if not executable.is_file():
            self.skipTest("native threshold executable is not built")
        with tempfile.TemporaryDirectory() as temporary:
            args = options(temporary, exe=executable, threshold=1, timeout_ms=500, solve_timeout_ms=250,
                           candidate_shapes=1, path_budget=16, generate_only=False, limit_graphs=1)
            with contextlib.redirect_stdout(io.StringIO()):
                search.run(args)
            summary = json.loads((args.out / "summary.json").read_text())
            row = next(item for item in summary["sizes"] if item["m"] == 8)
            self.assertEqual(row["threshold_queries_complete"], 1)
            self.assertGreater(row["pending_selected_roots"], 0)
            self.assertFalse(summary["all_selected_query_traversal_complete"])
            args.resume, args.limit_graphs = True, 0
            with contextlib.redirect_stdout(io.StringIO()):
                search.run(args)
            summary = json.loads((args.out / "summary.json").read_text())
            self.assertTrue(summary["all_selected_query_traversal_complete"])
            row = next(item for item in summary["sizes"] if item["m"] == 8)
            self.assertEqual(row["pending_selected_roots"], 0)
            self.assertEqual(row["best_known_lower_bound"], 34)
            count = summary["native_query_results"]
            with contextlib.redirect_stdout(io.StringIO()):
                search.run(args)
            self.assertEqual(json.loads((args.out / "summary.json").read_text())["native_query_results"], count)

    def test_explicit_shape_is_additional_and_keeps_translation_roots(self):
        args = options("unused", candidate_shapes=1, path_budget=16, shapes_per_size=1)
        known, _, _ = search.load_inputs(args)
        parents = [record for (m, _), record in known.items() if m == 7]
        raw = [[(state + 1) % 8, (state + 2) % 8] for state in range(8)]
        seed = search.normalize(dict(m=8, canonical_table=raw, lower_bound=2, upper_bound=None))
        plan = search.generate_plan(8, parents, extension(8), args, [seed])
        explicit = [bundle for bundle in plan["selected_shapes"] if bundle.get("explicit_shape_seed_records")]
        self.assertEqual(len(explicit), 1)
        self.assertEqual(len(plan["selected_shapes"]), 3)
        self.assertEqual(len(explicit[0]["roots"]), 1)
        self.assertEqual(explicit[0]["roots"][0]["original_roots"], list(range(8)))
        self.assertEqual(explicit[0]["explicit_shape_seed_records"][0]["lower_bound"], 2)


if __name__ == "__main__":
    unittest.main()
