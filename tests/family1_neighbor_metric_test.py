#!/usr/bin/env python3
"""Proof-bound semantics for the metric-guided neighborhood backend."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import family1_neighbor_search as search


class MetricBackendTests(unittest.TestCase):
    def setUp(self):
        self.args = argparse.Namespace(query_method="metric", threshold=34, exe=Path(sys.executable))
        self.root = dict(m=1, key="0000", canonical_table=((0, 0),))
        self.answer = dict(**self.root, length=34, decision="collision", lower_bound=1,
                           upper_bound=3, witness=["010", "100"], scalar_witness_masks_verified=2)

    def test_accepts_actual_verified_length_below_requested_cap(self):
        row = search.observation_from_native(self.answer, self.root, self.args, {})
        self.assertEqual((row["lower_bound"], row["upper_bound"]), (1, 3))

    def test_misses_and_agreement_scores_never_raise_lower_bound(self):
        answer = self.answer | dict(decision="unknown", upper_bound=None, witness=None,
                                    scalar_witness_masks_verified=0, merged_count=2, total_masks=2)
        self.assertEqual(search.observation_from_native(answer, self.root, self.args, {})["lower_bound"], 1)
        for change in (dict(lower_bound=2), dict(upper_bound=34), dict(decision="no_collision", lower_bound=35)):
            with self.assertRaises(ValueError):
                search.observation_from_native(answer | change, self.root, self.args, {})

    def test_full_mask_replay_and_equal_length_are_required(self):
        for change in (dict(scalar_witness_masks_verified=1), dict(witness=["010", "10"]),
                       dict(witness=["010", "010"]), dict(upper_bound=35), dict(length=33)):
            with self.assertRaises(ValueError):
                search.observation_from_native(self.answer | change, self.root, self.args, {})

    def test_imported_key_must_describe_the_supplied_table(self):
        with self.assertRaisesRegex(ValueError, "key disagrees"):
            search.normalize(dict(self.root, key="0101", lower_bound=1, upper_bound=None))
        legacy = search.normalize(dict(self.root, key="00", lower_bound=1, upper_bound=None))
        self.assertEqual(legacy["key"], "0000")

    def test_replay_is_bound_and_unknown_preserves_existing_lower(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(self.answer))
            proof = dict(path=str(path), sha256=search.file_hash(path))
            row = search.observation_from_native(self.answer, self.root, self.args, proof)
            self.assertEqual(search.compact(search.replay_observation(row, self.args)), search.compact(row))
            altered = copy.deepcopy(row)
            altered["upper_bound"] = 2
            with self.assertRaisesRegex(ValueError, "journal observation"):
                search.replay_observation(altered, self.args)
        records = {}
        graph = dict(self.root, lower_bound=2, upper_bound=None)
        search.merge_record(records, graph, {"kind": "existing-proof"})
        row = search.merge_record(records, graph | dict(lower_bound=1), {"kind": "sampling-miss"})
        self.assertEqual(row["lower_bound"], 2)


if __name__ == "__main__":
    unittest.main()
