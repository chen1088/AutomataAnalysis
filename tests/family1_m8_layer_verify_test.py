#!/usr/bin/env python3
"""Scalar exhaustive reference for the independent partitioned layer verifier."""
from __future__ import annotations
import argparse
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
EXECUTABLE = REPO / "out/build/msvc-vcpkg/Release/Family1M8LayerVerify.exe"


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def endpoint(table, mask, word):
    state = 0
    for bit in word:
        state = table[state][int(bit) ^ ((mask >> state) & 1)]
    return state


def collision(table, depth, masks=None):
    masks = list(range(1 << len(table))) if masks is None else masks
    seen = {}
    for bits in itertools.product("01", repeat=depth):
        word = "".join(bits)
        profile = tuple(endpoint(table, mask, word) for mask in masks)
        if profile in seen:
            return [seen[profile], word]
        seen[profile] = word
    return None


def accessible(table):
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target); pending.append(target)
    return len(reached) == len(table)


def canonical(table):
    m = len(table)
    values = []
    for tail in itertools.permutations(range(1, m)):
        mapping = (0,) + tail
        rows = [None] * m
        for state, row in enumerate(table):
            rows[mapping[state]] = tuple(sorted(mapping[target] for target in row))
        values.append(tuple(rows))
    return min(values)


class LayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="m8-layer-independent-")
        cls.directory = Path(cls.temp.name)
        cls.counter = 0
        cls.tiny = set()
        for m in range(1, 4):
            for flat in itertools.product(range(m), repeat=2*m):
                table = tuple(zip(flat[::2], flat[1::2]))
                if accessible(table):
                    cls.tiny.add(canonical(table))
        assert len(cls.tiny) == 64

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_native(self, table, depth, extra=(), successful=True):
        type(self).counter += 1
        report = self.directory / f"case-{self.counter}.json"
        command = [str(EXECUTABLE), "--key", key(table), "--depth", str(depth), "--out", str(report),
                   "--max-working-mib", "16", "--prefix-bits", "2", *map(str, extra)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if successful:
            self.assertEqual(process.returncode, 0, process.stderr+process.stdout)
        else:
            self.assertNotEqual(process.returncode, 0)
        self.assertTrue(report.is_file(), process.stdout+process.stderr)
        return json.loads(report.read_text()), command, report

    def check_result(self, table, depth, result, expected, full_proof=True, masks=None):
        masks = list(range(1 << len(table))) if masks is None else masks
        self.assertFalse(result["exact_score_certified"])
        self.assertFalse(result["global_optimality_claim"])
        if expected is None:
            self.assertEqual(result["status"], "collision-free")
            self.assertEqual(result["lower_bound"], depth+1)
            self.assertIsNone(result["upper_bound"])
            self.assertIsNone(result["witness"])
            self.assertEqual(result["phase"], "complete")
            count = 1 << (depth-1)
            self.assertEqual(result["expected_representatives"], count)
            self.assertEqual(result["count_pass_representatives"], count)
            self.assertEqual(result["fill_pass_representatives"], count*result["bucket_count"])
            self.assertEqual(sum(result["bucket_sizes"]), count)
            self.assertEqual(result["completed_buckets"], result["bucket_count"])
            self.assertTrue(result["full_family_injectivity_certified"])
            self.assertEqual(result["full_scalar_hash_replay_records"], result["repeated_hash_records"])
            if result["fingerprint_subset_with_full_replay"]:
                self.assertEqual(result["full_scalar_self_symmetry_checks"], result["self_symmetric_fingerprint_candidates"])
        else:
            expected_status = "collision-found" if full_proof else "projection-collision"
            self.assertEqual(result["status"], expected_status)
            self.assertEqual(result["lower_bound"], 1)
            self.assertEqual(result["upper_bound"], depth if full_proof else None)
            first, second = result["witness"]
            self.assertNotEqual(first, second)
            self.assertEqual(len(first), depth); self.assertEqual(len(second), depth)
            test_masks = range(1 << len(table)) if full_proof else masks
            self.assertTrue(all(endpoint(table, mask, first) == endpoint(table, mask, second) for mask in test_masks))
            self.assertTrue(result["selected_scalar_witness_verified"])
            if full_proof:
                self.assertTrue(result["full_scalar_witness_verified"])
        self.assertEqual(result["reason"], "")

    def test_exhaustive_all64_tiny_graphs_full_layers(self):
        for index, table in enumerate(sorted(self.tiny, key=lambda t: (len(t), t))):
            for depth in range(1, 8):
                expected = collision(table, depth)
                with self.subTest(table=table, depth=depth):
                    result, _, _ = self.run_native(table, depth, ["--threads", 1 if index%2 else 4,
                                                                   "--bucket-bits", (index+depth)%3])
                    self.check_result(table, depth, result, expected)
                if expected is not None:
                    break

    def test_forced_hash_equality_checks_complete_states(self):
        for table in sorted(self.tiny, key=lambda t: (len(t), t)):
            first = next(depth for depth in range(1, 8) if collision(table, depth) is not None)
            depth = max(1, first-1)
            result, _, _ = self.run_native(table, depth, ["--force-hash-collisions", "--threads", "4"])
            self.check_result(table, depth, result, collision(table, depth))

    def test_projected_collision_and_full_replay_are_distinct(self):
        # First fixture has a false cross-orientation projection collision;
        # second has a false self-complement projection collision at word00.
        for table in [((0,1),(0,1)), ((1,2),(0,1),(2,0))]:
            masks = [0, (1 << len(table))-1]
            self.assertIsNone(collision(table, 2))
            self.assertIsNotNone(collision(table, 2, masks))
            text = ",".join(map(str,masks))
            projected, _, _ = self.run_native(table, 2, ["--mask-list", text, "--force-hash-collisions"])
            self.check_result(table, 2, projected, collision(table, 2, masks), False, masks)
            full, _, _ = self.run_native(table, 2, ["--fingerprint-masks", text, "--force-hash-collisions", "--threads", "4"])
            self.check_result(table, 2, full, None, True, masks)
        self.assertGreater(full["self_symmetric_fingerprint_candidates"], 0)

    def test_eight_state_partial_bit_blocks_and_random_full_reference(self):
        table = tuple(((s+1)%8, (s+3)%8) for s in range(8))
        expected = collision(table, 4)
        for count in [2,6,64,66,128,130,192,254,256]:
            half = list(range(count//2))
            masks = sorted(half+[x^255 for x in half])
            result, _, _ = self.run_native(table, 4, ["--fingerprint-masks", ",".join(map(str,masks)),
                                                    "--force-hash-collisions", "--threads", "4"])
            self.check_result(table, 4, result, expected, True, masks)
        rng = random.Random(1088)
        for m in [4,5,6,7,8]:
            for _ in range(3):
                while True:
                    candidate = tuple((rng.randrange(m),rng.randrange(m)) for _ in range(m))
                    if accessible(candidate):
                        break
                expected = collision(candidate, 4)
                result, _, _ = self.run_native(candidate, 4, ["--threads", "4", "--bucket-bits", "2"])
                self.check_result(candidate, 4, result, expected)

    def test_guards_no_false_lower_bounds_and_early_self_collision(self):
        table = ((0,1),(0,1))
        for extra in [["--mask-list","0"], ["--mask-list","0,0,3"], ["--mask-list", ""],
                      ["--depth","4294967297"], ["--threads","4294967297"],
                      ["--bucket-bits","4294967297"], ["--max-working-mib","1"]]:
            result, _, _ = self.run_native(table, 2, extra, successful=False)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["lower_bound"], 1)
            self.assertIsNone(result["upper_bound"])
            self.assertFalse(result["full_family_injectivity_certified"])
        result, command, report = self.run_native(((0,0),), 36, ["--threads", "4"])
        self.check_result(((0,0),), 36, result, ["0"*36, "1"*36])
        self.assertLess(result["count_pass_representatives"], 1000)
        saved = report.read_bytes()
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
        self.assertEqual(report.read_bytes(),saved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--exe", type=Path)
    args, remaining = parser.parse_known_args()
    if args.exe:
        EXECUTABLE = args.exe.resolve()
    unittest.main(argv=[sys.argv[0],*remaining])
