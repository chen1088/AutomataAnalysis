"""Small independent fixtures for the positive upper-witness journal applicator.

The 57-class fixture comes from exhaustive ordered m=3 tables and ordinary
word/mask simulation. Expected-count overrides here are explicitly not m=7
coverage certificates.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from family1_exhaustive_cli_test import oracle


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/family1_apply_upper_witnesses.py"
SPEC = importlib.util.spec_from_file_location("family1_upper_applicator", SCRIPT)
APPLY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = APPLY
SPEC.loader.exec_module(APPLY)


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def make_record(table, lower, upper, witness, ordinal=0):
    return {"m": len(table), "ordinal": ordinal, "key": key(table),
            "canonical_table": list(map(list, table)), "status": "bounded",
            "lower_bound": lower, "upper_bound": upper, "merge_length": None,
            "witness": list(witness) if witness is not None else None, "reason": "preserve-existing-evidence"}


def proposal(record, upper, witness, **extra):
    return dict(m=record["m"], ordinal=record["ordinal"], key=record["key"],
                upper_bound=upper, witness=list(witness), **extra)


class UpperApplicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.truth = sorted(oracle().values(), key=lambda item: key(item[1]))
        assert len(cls.truth) == 57
        cls.complete = [make_record(table, 1, length + 2, [word + "00" for word in witness], ordinal)
                        for ordinal, (length, table, witness) in enumerate(cls.truth)]

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="upper-apply-test-", dir=ROOT / "out")
        self.base = Path(self.temporary.name).resolve()
        self.assertTrue(self.base.is_relative_to((ROOT / "out").resolve()))

    def tearDown(self):
        self.temporary.cleanup()

    def files(self, records, proposals, name="case", *, raw_base=None, raw_proposals=None):
        folder = self.base / name
        folder.mkdir()
        journal, sparse, destination = folder / "base.jsonl", folder / "upper.jsonl", folder / "output"
        journal.write_text(raw_base if raw_base is not None else "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        sparse.write_text(raw_proposals if raw_proposals is not None else "".join(json.dumps(r) + "\n" for r in proposals), encoding="utf-8")
        return journal, sparse, destination

    def run_apply(self, records, proposals, name="case", expected=None, **options):
        journal, sparse, destination = self.files(records, proposals, name, **options)
        before = {path: path.read_bytes() for path in (journal, sparse)}
        result = APPLY.apply_upper_witnesses(journal, sparse, destination, len(records) if expected is None else expected)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, "Applicator changed an input")
        output = [json.loads(line) for line in (destination / "checkpoint.jsonl").read_text(encoding="utf-8-sig").splitlines()]
        self.assertFalse(result["maximum_value_certified"])
        self.assertFalse(result["maximizing_collection_complete"])
        self.assertFalse(result["enumeration_complete"])
        self.assertFalse(result["full_seven_state_journal_count"])
        self.assertEqual(result["checkpoint_sha256"], hashlib.sha256((destination / "checkpoint.jsonl").read_bytes()).hexdigest())
        self.assertEqual((destination / "sparse-upper-witnesses.jsonl").read_bytes(), sparse.read_bytes())
        provenance = json.loads((destination / "provenance.json").read_text())
        self.assertEqual(provenance["sources"]["journal"]["sha256"], hashlib.sha256(before[journal]).hexdigest())
        self.assertEqual(provenance["sources"]["witnesses"]["sha256"], hashlib.sha256(before[sparse]).hexdigest())
        return result, output, destination

    def rejection(self, records, proposals, name, *, expected=None, **options):
        journal, sparse, destination = self.files(records, proposals, name, **options)
        before = {path: path.read_bytes() for path in (journal, sparse)}
        with self.assertRaises((ValueError, TypeError, KeyError)):
            APPLY.apply_upper_witnesses(journal, sparse, destination, len(records) if expected is None else expected)
        self.assertFalse(destination.exists(), "Failed application published an output")
        self.assertFalse(list(destination.parent.glob(".output.tmp-*")), "Failed application left staging files")
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_complete_independent_57_class_fixture(self):
        rows = deepcopy(self.complete)
        selected = [0, 7, 13, 25, 38, 50, 56]
        pairs = []
        for index in selected:
            length, _, witness = self.truth[index]
            if index == 13:
                rows[index]["lower_bound"] = length
            pairs.append(proposal(rows[index], length, witness,
                                  canonical_table=rows[index]["canonical_table"],
                                  status="exact", lower_bound=999999))
        result, output, destination = self.run_apply(rows, pairs, "complete")
        self.assertEqual(result["records_processed"], 57)
        self.assertEqual(result["upper_bounds_improved"], len(selected))
        self.assertEqual(result["proposals_verified"], len(selected))
        self.assertEqual(result["records_preserved_byte_for_byte"], 57 - len(selected))
        original_lines = (destination.parent / "base.jsonl").read_bytes().splitlines(keepends=True)
        output_lines = (destination / "checkpoint.jsonl").read_bytes().splitlines(keepends=True)
        for index, (old, new) in enumerate(zip(rows, output)):
            self.assertEqual(new["ordinal"], index)
            self.assertEqual(new["key"], old["key"])
            self.assertEqual(new["canonical_table"], old["canonical_table"])
            self.assertEqual(new["lower_bound"], old["lower_bound"])
            if index not in selected:
                self.assertEqual(new, old)
                self.assertEqual(output_lines[index], original_lines[index])
            else:
                self.assertEqual(new["upper_bound"], self.truth[index][0])
                self.assertEqual(new["status"], "exact" if new["lower_bound"] == new["upper_bound"] else "bounded")
                self.assertLess(new["lower_bound"], 999999, "Trusted an extra proposed lower claim")

    def test_seven_state_loops_coincident_ports_and_exact_normalization(self):
        table = tuple((min(s + 1, 6),) * 2 for s in range(7))
        row = make_record(table, 1, 4, ("0000", "1111"))
        result, output, _ = self.run_apply([row], [proposal(row, 1, ("0", "1"))], "seven")
        self.assertEqual(result["original_static_masks_checked_per_proposal"], 128)
        self.assertEqual(output[0]["status"], "exact")
        self.assertEqual(output[0]["merge_length"], 1)

    def test_static_revisits_and_all_masks(self):
        row = make_record(((0, 1), (0, 1)), 1, 5, ("01000", "10000"))
        _, output, _ = self.run_apply([row], [proposal(row, 3, ("010", "100"))], "static-valid")
        self.assertEqual(output[0]["upper_bound"], 3)
        # Mask0 agrees on00/10; mask1 separates them after a root revisit.
        self.rejection([row], [proposal(row, 2, ("00", "10"))], "static-counterexample")

    def test_equal_and_weaker_proposals(self):
        row = make_record(((0, 0),), 1, 3, ("000", "111"))
        result, output, _ = self.run_apply([row], [proposal(row, 3, ("010", "101"))], "equal")
        self.assertEqual(result["equal_upper_witnesses_replaced"], 1)
        self.assertEqual(output[0]["witness"], ["010", "101"])
        result, output, _ = self.run_apply([row], [proposal(row, 4, ("0000", "1111"))], "weaker")
        self.assertEqual(result["weaker_verified_proposals_ignored"], 1)
        self.assertEqual(result["records_updated"], 0)
        self.assertEqual(output[0], row)
        # Even a proposal that will be ignored must pass all-mask verification.
        two = make_record(((0, 1), (0, 1)), 1, 3, ("010", "100"))
        self.rejection([two], [proposal(two, 4, ("0000", "0001"))], "weaker-but-false")

    def test_empty_sparse_and_existing_empty_output(self):
        row = make_record(((0, 0),), 1, 1, ("0", "1"))
        result, output, _ = self.run_apply([row], [], "empty")
        self.assertEqual(result["proposals_verified"], 0)
        self.assertEqual(output, [row])
        journal, sparse, destination = self.files([row], [], "empty-destination")
        destination.mkdir()
        APPLY.apply_upper_witnesses(journal, sparse, destination, 1)
        self.assertTrue((destination / "checkpoint.jsonl").is_file())

    def test_bad_proposals(self):
        row = make_record(((0, 1), (0, 1)), 1, 5, ("01000", "10000"))
        good = proposal(row, 3, ("010", "100"))
        changes = [
            ("wrong-m", {"m": 3}), ("wrong-key", {"key": "00010000"}),
            ("negative-ordinal", {"ordinal": -1}), ("bool-ordinal", {"ordinal": False}),
            ("out-of-range", {"ordinal": 1}), ("zero-upper", {"upper_bound": 0}),
            ("bool-upper", {"upper_bound": True}), ("float-upper", {"upper_bound": 3.0}),
            ("different-lengths", {"witness": ["01", "100"]}),
            ("identical-words", {"witness": ["010", "010"]}),
            ("nonbinary", {"witness": ["012", "100"]}),
            ("false-witness", {"witness": ["000", "001"]}),
            ("different-table", {"canonical_table": [[0, 1], [0, 0]]}),
        ]
        for name, change in changes:
            with self.subTest(name=name):
                bad = dict(good, **change)
                self.rejection([row], [bad], name)
        self.rejection([row], [good, good], "duplicate-proposal")
        missing = dict(good); del missing["ordinal"]
        self.rejection([row], [missing], "missing-proposal-field")
        raw = json.dumps(good).replace('"ordinal": 0', '"ordinal": 0, "ordinal": 0') + "\n"
        self.rejection([row], [], "duplicate-json-field", raw_proposals=raw)
        self.rejection([row], [], "torn-proposal", raw_proposals=json.dumps(good)[:30])
        above = deepcopy(row); above["lower_bound"] = 4
        self.rejection([above], [good], "below-inherited-lower")

    def test_base_identity_count_and_order_failures(self):
        self.rejection(self.complete[:56], [], "truncated-base", expected=57)
        self.rejection(self.complete, [], "too-many-base", expected=56)
        for name, change in [("ordinal-gap", {"ordinal": 1}), ("table-key", {"key": "bad"}),
                             ("target-range", {"canonical_table": [[0, 3], [1, 2], [0, 1]]}),
                             ("status", {"status": "finished"})]:
            bad = deepcopy(self.complete[:1]); bad[0].update(change)
            self.rejection(bad, [], name)
        bad = deepcopy(self.complete[:2]); bad[1] = dict(bad[0], ordinal=1)
        self.rejection(bad, [], "duplicate-base-key")
        bad = deepcopy(self.complete[:2]); bad.reverse()
        for index, record in enumerate(bad): record["ordinal"] = index
        self.rejection(bad, [], "unsorted-base")
        unreachable = make_record(((0, 0), (1, 1)), 1, 1, ("0", "1"))
        self.rejection([unreachable], [], "unreachable-base")
        self.rejection(self.complete[:1], [], "torn-base", raw_base=json.dumps(self.complete[0])[:20])
        # A key not in the source cannot be manufactured by giving its ordinal.
        wrong = proposal(self.complete[1], self.truth[1][0], self.truth[1][2]); wrong["ordinal"] = 0
        self.rejection(self.complete, [wrong], "missing-graph")

    def test_output_and_input_aliases_preserve_sources(self):
        row = make_record(((0, 0),), 1, 1, ("0", "1"))
        journal, sparse, destination = self.files([row], [], "aliases")
        before = journal.read_bytes()
        for output in (journal, sparse):
            with self.assertRaises(ValueError): APPLY.apply_upper_witnesses(journal, sparse, output, 1)
        with self.assertRaises(ValueError): APPLY.apply_upper_witnesses(journal, journal, destination, 1)
        alias = journal.with_name("hardlink.jsonl")
        os.link(journal, alias)
        with self.assertRaises(ValueError): APPLY.apply_upper_witnesses(journal, alias, destination, 1)
        destination.mkdir(); sentinel = destination / "keep.txt"; sentinel.write_text("keep")
        with self.assertRaises(ValueError): APPLY.apply_upper_witnesses(journal, sparse, destination, 1)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(journal.read_bytes(), before)

    def test_source_mutation_rejected_before_atomic_publication(self):
        row = make_record(((0, 0),), 1, 1, ("0", "1"))
        journal, sparse, destination = self.files([row], [], "mutation")
        original_check = APPLY.assert_sources_unchanged
        def mutate_then_check(hashes):
            journal.write_bytes(journal.read_bytes() + b" ")
            original_check(hashes)
        with mock.patch.object(APPLY, "assert_sources_unchanged", side_effect=mutate_then_check):
            with self.assertRaisesRegex(ValueError, "SHA256 changed"):
                APPLY.apply_upper_witnesses(journal, sparse, destination, 1)
        self.assertFalse(destination.exists())
        self.assertFalse(list(destination.parent.glob(".output.tmp-*")))

    def test_failed_publication_leaves_no_partial_files(self):
        row = make_record(((0, 0),), 1, 1, ("0", "1"))
        journal, sparse, destination = self.files([row], [], "publication-failure")
        destination.mkdir()
        with mock.patch.object(APPLY.os, "replace", side_effect=OSError("simulated publish failure")):
            with self.assertRaises(OSError): APPLY.apply_upper_witnesses(journal, sparse, destination, 1)
        self.assertTrue(destination.is_dir())
        self.assertFalse(list(destination.iterdir()))
        self.assertFalse(list(destination.parent.glob(".output.tmp-*")))

    def test_cli_smoke(self):
        row = make_record(((0, 0),), 1, 2, ("00", "11"))
        journal, sparse, destination = self.files([row], [proposal(row, 1, ("0", "1"))], "cli")
        result = subprocess.run([sys.executable, str(SCRIPT), "--journal", str(journal),
                                 "--witnesses", str(sparse), "--out", str(destination), "--expected-count", "1"],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("remain uncertified", result.stdout)
        summary = json.loads((destination / "summary.json").read_text())
        self.assertFalse(summary["full_seven_state_journal_count"])


if __name__ == "__main__":
    unittest.main()
