"""Independent checks of the atlas's larger-size lower-bound constructions."""

import json
from pathlib import Path
import random
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_atlas_dataset import BASE_TABLE, build_dataset, extension
from family1_graph_atlas import load_records
from family1_study import canonical_table


def reachable(table):
    reached = {0}
    while True:
        expanded = reached | {target for state in reached for target in table[state]}
        if expanded == reached:
            return reached
        reached = expanded


class AtlasDatasetTests(unittest.TestCase):
    def test_all_thirteen_exact_sizes_and_canonical_tables(self):
        for m in range(8, 21):
            record = extension(m)
            table = record["canonical_table"]
            self.assertEqual(len(table), m)
            self.assertEqual(reachable(table), set(range(m)))
            self.assertEqual(tuple(map(tuple, table)), canonical_table(table))
            self.assertEqual(record["lower_bound"], 34)
            self.assertIsNone(record["upper_bound"])
            self.assertIsNone(record["merge_length"])

    def test_raw_projection_commutes_including_entire_new_cycle(self):
        for m in range(8, 21):
            metadata = extension(m)["construction"]
            table, pi = metadata["raw_table"], metadata["raw_projection_to_base"]
            for state, row in enumerate(table):
                for port, target in enumerate(row):
                    self.assertEqual(pi[target], BASE_TABLE[pi[state]][port])
            state, cycle = 0, []
            while state not in cycle:
                cycle.append(state)
                state = table[state][0]
            self.assertEqual(cycle, [0] + list(range(7, m)))
            self.assertEqual(state, 0)

    def test_static_mask_lift_trajectories_on_revisits(self):
        rng = random.Random(81620)
        words = ["0" * 43, "1" * 43, "01" * 22, "10" * 22]
        words.extend("".join(rng.choice("01") for _ in range(43)) for _ in range(12))
        for m in range(8, 21):
            record = extension(m)
            table, data = record["canonical_table"], record["construction"]
            pi, flips = data["canonical_projection_to_base"], data["canonical_mask_lift_xor"]
            for base_mask in range(128):
                lifted = [((base_mask >> pi[state]) & 1) ^ flips[state] for state in range(m)]
                for word in words:
                    small_state = large_state = 0
                    for symbol in word:
                        bit = int(symbol)
                        small_state = BASE_TABLE[small_state][bit ^ ((base_mask >> small_state) & 1)]
                        large_state = table[large_state][bit ^ lifted[large_state]]
                        self.assertEqual(pi[large_state], small_state)

    def test_complete_small_collections_and_larger_unknown_flags(self):
        records, summary = build_dataset(REPO / "results/family1-m1-m6/maximizers.jsonl",
                                         REPO / "results/family1-m7/maximizers.jsonl")
        self.assertEqual(len(records), 33)
        self.assertEqual([row["maximizer_count"] for row in summary["sizes"][:7]],
                         [1, 1, 2, 1, 5, 2, 8])
        for row in summary["sizes"][7:]:
            self.assertFalse(row["maximum_value_certified"])
            self.assertFalse(row["maximizing_collection_complete"])
            self.assertFalse(row["enumeration_complete"])
            self.assertIsNone(row["maximizer_count"])
            self.assertEqual(row["largest_displayed_lower_bound"], 34)
        self.assertEqual(summary["m8_prediction"]["status"], "heuristic-not-a-bound")

    def test_written_export_is_accepted_by_existing_atlas_loader(self):
        directory = REPO / "results/family1-atlas-current"
        if not (directory / "champions.jsonl").is_file():
            self.skipTest("run presentation dataset generator first")
        records = load_records([directory])
        self.assertEqual(len(records), 33)
        self.assertEqual(sum(record["maximum_certified"] for record in records), 20)
        self.assertTrue(all(record["best_bound_tie"] for record in records))
        self.assertTrue(all(record["upper_bound"] is None for record in records if record["m"] >= 8))
        summary = json.loads((directory / "summary.json").read_text())
        self.assertEqual(len(summary["sizes"]), 20)


if __name__ == "__main__":
    unittest.main()
