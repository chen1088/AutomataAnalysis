#!/usr/bin/env python3
"""Truth-free ranking, graph invariants, parent joins and output integrity."""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import family1_rank_edit_candidates as ranker
from family1_graph_candidate_search import graph_metadata, reachable, root_bundle
from family1_threshold_cli_test import classes, exact_score


def graph(table):
    return graph_metadata({"canonical_table": table})


def four_shapes():
    result = {}
    for table in classes(3):
        row = graph(table)
        result.setdefault(root_bundle(row)["shape_key"], row)
    return list(result.values())[:4]


class RankerTest(unittest.TestCase):
    def test_parent_certificate_contradictions_rejected(self):
        parent = graph(((0, 1), (0, 1)))
        for fields in ({"status": "exact"}, {"status": "exact", "merge_length": 0},
                       {"status": "exact", "merge_length": True},
                       {"status": "exact", "merge_length": 3, "upper_bound": 2},
                       {"lower_bound": 3, "upper_bound": 2}, {"lower_bound": 2, "upper_bound": "3"}):
            with self.assertRaises(ValueError):
                ranker.certified_parent_rows([{**parent, **fields}])
        with self.assertRaises(ValueError):
            ranker.certified_parent_rows([{**parent, "lower_bound": 3}, {**parent, "lower_bound": 1, "upper_bound": 2}])

    def test_scalar_shape_features_all64_classes(self):
        rows = [graph(table) for m in (1, 2, 3) for table in classes(m)]
        ranked, features, summary = ranker.rank_rows(rows)
        self.assertEqual(len(ranked), 64)
        self.assertTrue(summary["root_multiset_unchanged"])
        self.assertFalse(summary["filters_applied"])
        for row in ranked:
            table = row["canonical_table"]
            m = len(table)
            roots = [root for root in range(m) if len(reachable(table, root)) == m]
            indegrees = [sum(target == state for ports in table for target in ports) for state in range(m)]
            feature = row["ranking"]
            self.assertEqual(feature["accessible_vertex_roots"], len(roots))
            self.assertEqual(feature["potential_hard_vertex_roots"], sum(table[root][0] != table[root][1] for root in roots))
            self.assertEqual(feature["indegree_multiset"], sorted(indegrees))
            self.assertEqual(feature["indegree_l1_distance_from_two"], sum(abs(value - 2) for value in indegrees))
            self.assertEqual(feature["strongly_connected"], len(roots) == m)

    def test_non_sc_and_coincident_graphs_are_retained(self):
        rows = [graph(((1, 2), (1, 1), (2, 2))), graph(((1, 1), (0, 0)))]
        ranked, _, summary = ranker.rank_rows(rows)
        self.assertEqual(len(ranked), 2)
        nonsc = next(row for row in ranked if row["m"] == 3)
        self.assertEqual(nonsc["ranking"]["accessible_vertex_roots"], 1)
        self.assertEqual(nonsc["ranking"]["potential_hard_vertex_roots"], 1)
        self.assertEqual(nonsc["ranking"]["coincident_port_vertices"], 2)
        self.assertEqual(summary["non_strongly_connected_shapes_retained"], 1)

    def test_candidate_labels_never_affect_order(self):
        rows = [graph(table) for table in classes(3)]
        changed = [{**row, "status": "exact", "merge_length": 999 - index, "lower_bound": 999,
                    "upper_bound": 0, "witness": ["saved word must be ignored", "other hint"]}
                   for index, row in enumerate(rows)]
        for strategy in ("discovery", "structural", "parent-strata"):
            original = ranker.rank_rows(rows, strategy=strategy)[0]
            modified = ranker.rank_rows(changed, strategy=strategy)[0]
            self.assertEqual([row["key"] for row in original], [row["key"] for row in modified])
        self.assertEqual(len(ranker.rank_rows(changed)[0]), len(rows))

    def test_parent_score_levels_round_robin_and_previous_size_only(self):
        candidates = four_shapes()
        parent_tables = list(classes(2))
        high = next(table for table in parent_tables if exact_score(table) == 3)
        low = next(table for table in parent_tables if exact_score(table) == 2)
        parents = [{**graph(high), "status": "exact", "merge_length": 3},
                   {**graph(low), "lower_bound": 2, "upper_bound": 999}]
        paths, rows = [], []
        for index, child in enumerate(candidates):
            parent = parents[0 if index < 2 else 1]
            paths.append({"path_id": index, "parent_key": parent["key"], "source_table": parent["canonical_table"],
                          "endpoint_key": child["key"], "endpoint_table": child["canonical_table"]})
            rows.append({**child, "path_ids": [index], "selection_index": index})
        ranked, features, summary = ranker.rank_rows(rows, paths, parents, "parent-strata")
        self.assertEqual([feature["previous_parent_score_levels"] for feature in features], [[3], [2], [3], [2]])
        self.assertEqual(Counter(row["key"] for row in ranked), Counter(row["key"] for row in rows))
        self.assertTrue(summary["previous_parent_lower_certificates_used"])
        # A same-size parent's score must not enter previous-size strata.
        same = candidates[0]
        paths[0] = {"path_id": 0, "parent_key": same["key"], "source_table": same["canonical_table"],
                    "endpoint_key": same["key"], "endpoint_table": same["canonical_table"]}
        _, features, _ = ranker.rank_rows(rows, paths, parents + [{**same, "lower_bound": 999}], "parent-strata")
        feature = next(feature for feature in features if feature["shape_key"] == root_bundle(same)["shape_key"])
        self.assertEqual(feature["previous_parent_score_levels"], [])

    def test_native_parent_and_reroot_links_validated(self):
        parent = graph(((0, 1), (0, 1)))
        endpoint = graph(((0, 1), (1, 2), (0, 1)))
        root = 1
        child_key = ranker.reroot_key(endpoint["canonical_table"], root)
        child = next(row for row in root_bundle(endpoint)["roots"] if row["key"] == child_key)
        path = {"path_id": 0, "parent_key": parent["key"], "source_table": parent["canonical_table"],
                "endpoint_key": endpoint["key"], "endpoint_table": endpoint["canonical_table"]}
        row = {**child, "root_metadata": [{"path_id": 0, "endpoint_key": endpoint["key"],
                                           "root_in_endpoint": root, "root_fixed_path": False}]}
        parents = [{**parent, "lower_bound": 3}]
        _, features, _ = ranker.rank_rows([row], [path], parents, "parent-strata")
        self.assertEqual(features[0]["previous_parent_score_levels"], [3])
        with self.assertRaises(ValueError):
            ranker.rank_rows([row], [{**path, "parent_key": "00000000"}], parents, "parent-strata")
        bad = {**row, "root_metadata": [{**row["root_metadata"][0], "root_fixed_path": True}]}
        with self.assertRaises(ValueError):
            ranker.rank_rows([bad], [path], parents, "parent-strata")

    def test_nonzero_automorphic_root_can_retain_root_fixed_class(self):
        parent = graph(((0, 0),))
        endpoint = graph(((1, 1), (0, 0)))
        path = {"path_id": 0, "parent_key": parent["key"], "source_table": parent["canonical_table"],
                "endpoint_key": endpoint["key"], "endpoint_table": endpoint["canonical_table"]}
        row = {**endpoint, "path_ids": [0], "root_metadata": [{"path_id": 0, "endpoint_key": endpoint["key"],
                                                                 "root_in_endpoint": 1, "root_fixed_path": True}]}
        ranked, features, _ = ranker.rank_rows([row], [path], [{**parent, "lower_bound": 1}], "parent-strata")
        self.assertEqual(len(ranked), 1)
        self.assertEqual(features[0]["accessible_vertex_roots"], 2)
        self.assertEqual(features[0]["distinct_accessible_root_classes"], 1)
        self.assertEqual(features[0]["previous_parent_score_levels"], [1])

    def test_determinism_and_whole_blocks_original_indices(self):
        rows = [{**graph(table), "selection_index": 100 + index} for index, table in enumerate(classes(3))]
        first = ranker.rank_rows(rows, seed=1088)
        self.assertEqual(first, ranker.rank_rows(rows, seed=1088))
        self.assertNotEqual([row["key"] for row in first[0]], [row["key"] for row in ranker.rank_rows(rows, seed=1089)[0]])
        shape_order = [row["ranking"]["shape_key"] for row in first[0]]
        self.assertEqual(len([shape for index, shape in enumerate(shape_order) if not index or shape != shape_order[index - 1]]), len(set(shape_order)))
        self.assertEqual(sorted(row["original_selection_index"] for row in first[0]), list(range(100, 100 + len(rows))))

    def test_cli_resume_and_corruption(self):
        with tempfile.TemporaryDirectory(prefix="f1-rank-") as temporary:
            base = Path(temporary)
            source = base / "candidates.jsonl"
            source.write_text("".join(json.dumps(graph(table)) + "\n" for table in classes(3)))
            output = base / "ranked"
            args = ["--candidates", str(source), "--out", str(output), "--strategy", "structural", "--seed", "1088"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(ranker.main(args), 0)
                self.assertEqual(ranker.main(args + ["--resume"]), 0)
            ranked = output / "candidates.jsonl"
            old = ranked.read_bytes()
            ranked.write_bytes(old + b" ")
            with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                ranker.main(args + ["--resume"])
            ranked.write_bytes(old)
            (output / "candidates.sha256").write_text("bad\n")
            with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                ranker.main(args + ["--resume"])


if __name__ == "__main__":
    unittest.main()
