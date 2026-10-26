#!/usr/bin/env python3
"""Independent exhaustive small-word checks for both circulant formulas."""
import itertools
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_circulant_family import endpoint, exact_layers, formula_table, verify_witness


def scalar_reference(table, limit):
    """Restart every word from the root and simulate every static mask."""
    m = len(table)
    for n in range(1, limit + 1):
        seen = {}
        for word in itertools.product((0, 1), repeat=n):
            vector = []
            for mask in range(1 << m):
                state = 0
                for letter in word:
                    state = table[state][letter ^ ((mask >> state) & 1)]
                vector.append(state)
            vector = tuple(vector)
            if vector in seen:
                return n
            seen[vector] = word
    return None


class CirculantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datasets = {}
        for variant, directory in (("literal", "family1-circulant-family"),
                                   ("manuscript", "family1-circulant-manuscript-reference")):
            path = REPO / "results" / directory / "champions.jsonl"
            if path.is_file():
                cls.datasets[variant] = [json.loads(line) for line in path.read_text().splitlines()]

    def test_static_masks_and_cross_length_revisits(self):
        table = formula_table(2)
        self.assertEqual(endpoint(table, 0, "00"), 0)  # Empty-state revisit is not a collision proof.
        self.assertEqual(endpoint(table, 1, "010"), 0)  # Root's swap bit stays fixed on both visits.
        result = exact_layers(table, 3)
        self.assertEqual(result["merge_length"], 3)
        self.assertEqual([layer["distinct_complete_product_states"] for layer in result["completed_injective_layers"]], [2, 4])

    def test_coincident_ports_and_exact_small_scores_independently(self):
        expected = {"literal": [1, 3, 1, 1, 1, 11], "manuscript": [1, 3, 4, 7, 10, 11]}
        for variant, values in expected.items():
            for m, score in enumerate(values, 1):
                with self.subTest(variant=variant, m=m):
                    self.assertEqual(scalar_reference(formula_table(m, variant), score), score)
                    self.assertEqual(exact_layers(formula_table(m, variant), score)["merge_length"], score)

    def test_all_twenty_raw_formulas_maps_and_root_translations(self):
        self.assertEqual(set(self.datasets), {"literal", "manuscript"})
        for variant, records in self.datasets.items():
            self.assertEqual([record["m"] for record in records], list(range(1, 21)))
            for record in records:
                m, family = record["m"], record["family"]
                raw = formula_table(m, variant)
                self.assertEqual(tuple(map(tuple, family["raw_table"])), raw)
                mapping = family["raw_to_canonical_labels"]
                self.assertEqual(mapping[0], 0)
                self.assertEqual(sorted(mapping), list(range(m)))
                for old, row in enumerate(raw):
                    mapped = tuple(mapping[target] for target in row)
                    flip = family["canonical_mask_lift_xor_at_raw_source"][old]
                    self.assertEqual(mapped[::-1 if flip else 1], tuple(record["canonical_table"][mapping[old]]))
                self.assertEqual(family["vertex_root_multiplicity"], m)
                self.assertEqual(family["distinct_rooted_class_count"], 1)
                for translation in family["root_translations_to_root_zero"]:
                    labels = translation["old_to_root_zero_labels"]
                    self.assertEqual(labels[translation["root"]], 0)
                    for source, row in enumerate(raw):
                        self.assertEqual(tuple(labels[target] for target in row), raw[labels[source]])

    def test_saved_witnesses_all_masks_all_roots_and_known_scores(self):
        expected = {"literal": [1, 3, 1, 1, 1, 11, 14, 18],
                    "manuscript": [1, 3, 4, 7, 10, 11, 13, 13]}
        for variant, records in self.datasets.items():
            self.assertEqual([record["merge_length"] for record in records[:8]], expected[variant])
            for record in records[:8]:
                verify_witness(record["canonical_table"], record["witness"])
                verify_witness(record["family"]["raw_table"], record["witness"], all_roots=True)
            for record in records[8:]:
                self.assertEqual(record["status"], "incomplete")
                self.assertEqual(record["lower_bound"], 2)
                self.assertIsNone(record["upper_bound"])
                self.assertIsNone(record["merge_length"])


if __name__ == "__main__":
    unittest.main()
