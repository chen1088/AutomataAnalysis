"""Small proof-mechanics tests; these are NOT seven-state global certificates.

The real independent CPU checker is used only at depth1 on tiny journals.
The dictionaries used for frontier reconciliation are local control-flow
fixtures and never cause a global summary or maximizing collection export.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/family1_verify_global_certificate.py"
SPEC = importlib.util.spec_from_file_location("family1_certificate_refine_under_test", SCRIPT)
CERT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CERT)
LAYER = ROOT / "out/build/msvc-vcpkg/Release/Family1LayerVerify.exe"
UPPER = ROOT / "out/build/msvc-vcpkg/Release/Family1ExhaustiveVerify.exe"


def key(table):
    return "".join(f"{v:02d}" for row in table for v in row)


def row(table, witness, ordinal, lower=1):
    return {"m": 7, "ordinal": ordinal, "key": key(table), "canonical_table": table,
            "status": "bounded", "lower_bound": lower, "upper_bound": 2,
            "merge_length": None, "witness": witness, "reason": "LOCAL TEST FIXTURE; NOT GLOBAL COVERAGE"}


H1 = [[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [6, 6], [6, 6]]
H1_OTHER = [[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [6, 6], [0, 0]]
H2 = [[1, 2], [3, 3], [3, 3], [4, 5], [6, 6], [6, 6], [0, 0]]


class FrontierRefinementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="LOCAL-NOT-GLOBAL-refinement-", dir=ROOT / "out")
        self.base = Path(self.temporary.name).resolve()
        self.assertTrue(self.base.is_relative_to((ROOT / "out").resolve()))
        self.args = SimpleNamespace(layer_exe=LAYER, lower_threads=1, lower_timeout_ms=1000,
                                    jobs=2, max_total_working_mib=256, refine_frontier=True)

    def tearDown(self):
        self.assertFalse((self.base / "summary.json").exists(), "Unit fixture produced a global certificate")
        self.assertFalse((self.base / "maximizers.jsonl").exists())
        self.temporary.cleanup()

    def journal(self, values, name="input.jsonl"):
        path = self.base / name
        path.write_text("".join(json.dumps(value) + "\n" for value in values))
        return path

    def mixed(self):
        values = [row(H1, ["00", "11"], 0), row(H2, ["00", "01"], 1)]
        self.assertLess(values[0]["key"], values[1]["key"])
        return values

    def test_real_cpu_lower_checks_and_monotone_complete_refinement(self):
        values = self.mixed()
        path = self.journal(values)
        before = path.read_bytes()
        records = CERT.load_frontier_records(path, [r["key"] for r in values], 2, 2)
        outcomes = CERT.execute_frontier_checks(self.args, records, 2, self.base)
        self.assertEqual([r["outcome"] for r in outcomes], ["collision-found", "collision-free"])
        output = self.base / "refined.jsonl"
        checksum, refinements = CERT.write_refined_journal(path, output, records, outcomes, 2, 2)
        self.assertEqual(checksum, CERT.digest(output))
        self.assertEqual(len(refinements), 1)
        actual = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(actual[0]["lower_bound"], values[0]["lower_bound"])
        self.assertEqual((actual[0]["upper_bound"], actual[0]["merge_length"], actual[0]["status"]), (1, 1, "exact"))
        self.assertEqual(actual[1], values[1])
        self.assertEqual(output.read_bytes().splitlines(keepends=True)[1], before.splitlines(keepends=True)[1])
        self.assertEqual(path.read_bytes(), before)
        # Local reconciliation only: this says nothing about all m=7 graphs.
        local = {"global_upper_bound_verified": 2, "keys_at_largest_verified_upper_bound": [values[1]["key"]]}
        self.assertEqual(CERT.surviving_frontier(2, outcomes, local), [values[1]["key"]])
        native = self.base / "native-prefix-audit.json"
        process = subprocess.run([str(UPPER), "--states", "7", "--journal", str(output),
                                  "--expected-count", "2", "--out", str(native)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        audit = json.loads(native.read_text())
        self.assertTrue(audit["verification_passed"])
        self.assertFalse(audit["enumeration_complete"])
        self.assertIsNone(audit["global_upper_bound_verified"])

    def test_all_collision_results_retain_refined_journal_but_refuse_certificate(self):
        tables = sorted([H1, H1_OTHER], key=key)
        values = [row(table, ["00", "11"], ordinal) for ordinal, table in enumerate(tables)]
        source = self.journal(values)
        records = {r["key"]: r for r in values}
        outcomes = CERT.execute_frontier_checks(self.args, records, 2, self.base)
        self.assertTrue(all(r["outcome"] == "collision-found" for r in outcomes))
        destination = self.base / "retained-refined.jsonl"
        CERT.write_refined_journal(source, destination, records, outcomes, 2, 2)
        self.assertTrue(destination.is_file())
        local = {"global_upper_bound_verified": 1, "keys_at_largest_verified_upper_bound": list(records)}
        with self.assertRaisesRegex(RuntimeError, "All initial frontier graphs collided"):
            CERT.surviving_frontier(2, outcomes, local)
        self.assertTrue(destination.is_file())

    def test_false_inherited_lower_is_rejected_not_silently_changed(self):
        value = row(H1, ["00", "11"], 0, lower=2)
        value.update(status="exact", merge_length=2)
        source = self.journal([value])
        outcomes = CERT.execute_frontier_checks(self.args, {value["key"]: value}, 2, self.base)
        self.assertEqual(outcomes[0]["outcome"], "collision-found")
        with self.assertRaisesRegex(RuntimeError, "contradicts inherited lower"):
            CERT.write_refined_journal(source, self.base / "must-not-exist.jsonl",
                                       {value["key"]: value}, outcomes, 2, 1)
        self.assertFalse((self.base / "must-not-exist.jsonl").exists())

    def test_strict_mode_still_rejects_a_loose_frontier(self):
        value = row(H1, ["00", "11"], 0)
        self.args.refine_frontier = False
        with self.assertRaisesRegex(RuntimeError, "not been proved to attain"):
            CERT.execute_frontier_checks(self.args, {value["key"]: value}, 2, self.base)

    def test_refinement_executes_every_initial_key_despite_one_incomplete(self):
        values = self.mixed(); records = {r["key"]: r for r in values}; calls = []
        def fake_run(command, log):
            # Deliberately mocked process metadata for control-flow coverage.
            # No full-journal audit or certificate is created by this test.
            k = command[command.index("--key") + 1]
            calls.append(k)
            report = {"method": CERT.METHOD, "m": 7, "key": k, "depth": 1,
                      "status": "incomplete", "reason": "test timeout", "lower_bound": 1,
                      "upper_bound": None, "witness": None, "generated_representatives": 0}
            Path(command[command.index("--out") + 1]).write_text(json.dumps(report))
        with mock.patch.object(CERT, "run", side_effect=fake_run):
            outcomes = CERT.execute_frontier_checks(self.args, records, 2, self.base)
        self.assertCountEqual(calls, records)
        self.assertTrue(all(r["outcome"] == "incomplete" for r in outcomes))
        source = self.journal(values)
        refined = self.base / "incomplete-but-preserved.jsonl"
        CERT.write_refined_journal(source, refined, records, outcomes, 2, 2)
        self.assertEqual(source.read_bytes(), refined.read_bytes())
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            CERT.surviving_frontier(2, outcomes, {"global_upper_bound_verified": 2,
                                               "keys_at_largest_verified_upper_bound": list(records)})

    def test_collision_metadata_and_full_scalar_witness_are_checked(self):
        value = row(H2, ["00", "01"], 0)
        valid_free = {"method": CERT.METHOD, "m": 7, "key": value["key"], "depth": 1,
                      "status": "collision-free", "reason": "", "lower_bound": 2,
                      "upper_bound": None, "witness": None, "generated_representatives": 1}
        self.assertEqual(CERT.interpret_lower_report(valid_free, value["key"], 2, value, True)["outcome"], "collision-free")
        for change in ({"key": "bad"}, {"m": 6}, {"depth": True}, {"generated_representatives": 0},
                       {"lower_bound": 999}, {"witness": ["0", "1"]}, {"reason": "timeout"}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                CERT.interpret_lower_report(dict(valid_free, **change), value["key"], 2, value, True)
        collision = dict(valid_free, status="collision-found", lower_bound=1, upper_bound=1,
                         witness=["0", "1"])
        with self.assertRaisesRegex(RuntimeError, "static mask"):
            CERT.interpret_lower_report(collision, value["key"], 2, value, True)
        for words in (["0", "0"], ["00", "11"], ["0", "2"]):
            with self.subTest(words=words), self.assertRaises(RuntimeError):
                CERT.interpret_lower_report(dict(collision, witness=words), value["key"], 2, value, True)

    def test_refinement_ids_and_original_snapshot_are_checked(self):
        values = self.mixed(); records = {r["key"]: r for r in values}
        outcome = {"key": values[0]["key"], "outcome": "collision-found", "upper_bound": 1,
                   "witness": ["0", "1"]}
        source = self.journal(values)
        changed = deepcopy(values); changed[0]["reason"] = "modified after original frontier read"
        source.write_text("".join(json.dumps(r) + "\n" for r in changed))
        with self.assertRaisesRegex(RuntimeError, "changed before refinement"):
            CERT.write_refined_journal(source, self.base / "reject-changed.jsonl", records, [outcome], 2, 2)
        self.assertFalse((self.base / "reject-changed.jsonl").exists())
        self.assertFalse((self.base / "reject-changed.jsonl.tmp").exists())

    def test_thread_flag_defaults_and_explicit_parallel_request(self):
        command = CERT.lower_command(self.args, key(H2), 1, 65, self.base / "report.json")
        self.assertNotIn("--threads", command)
        self.args.lower_threads = 8
        command = CERT.lower_command(self.args, key(H2), 1, 65, self.base / "report.json")
        self.assertEqual(command[command.index("--threads") + 1], "8")

    def test_real_parallel_flag_on_tiny_independent_checks(self):
        self.args.lower_threads = 8
        values = self.mixed()
        outcomes = CERT.execute_frontier_checks(self.args, {r["key"]: r for r in values}, 2, self.base)
        self.assertEqual([r["outcome"] for r in outcomes], ["collision-found", "collision-free"])

    def test_full_wrapper_refuses_prefix_with_and_without_refinement(self):
        source = self.journal(self.mixed())
        for mode in ([], ["--refine-frontier"]):
            destination = self.base / ("refine-prefix" if mode else "strict-prefix")
            process = subprocess.run([sys.executable, str(SCRIPT), "--journal", str(source),
                                      "--out", str(destination), "--upper-exe", str(UPPER),
                                      "--layer-exe", str(LAYER), *mode], capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((destination / "summary.json").exists())
            self.assertFalse((destination / "maximizers.jsonl").exists())
            incomplete = json.loads((destination / "incomplete.json").read_text())
            self.assertFalse(incomplete["maximum_value_certified"])
            self.assertFalse(incomplete["maximizing_collection_complete"])
            self.assertFalse(list(destination.glob("lower-*.json")), "Prefix triggered expensive lower checks")

    def test_pins_detect_source_executable_and_code_changes(self):
        journal = self.journal(self.mixed())
        executable, code = self.base / "fake-verifier.bin", self.base / "fake-source.txt"
        executable.write_bytes(b"EXPLICIT LOCAL PIN FIXTURE")
        code.write_text("source version1")
        jhash = CERT.digest(journal); ehash = {str(executable): CERT.digest(executable)}; shash = {str(code): CERT.digest(code)}
        CERT.check_pins(journal, jhash, ehash, shash)
        code.write_text("source version2")
        with self.assertRaisesRegex(RuntimeError, "Verification source changed"):
            CERT.check_pins(journal, jhash, ehash, shash)
        code.write_text("source version1"); executable.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "executable changed"):
            CERT.check_pins(journal, jhash, ehash, shash)

    def test_reconciled_frontier_must_equal_all_fresh_lower_proofs(self):
        outcomes = [{"key": key(H2), "outcome": "collision-free", "lower_bound": 2},
                    {"key": key(H1), "outcome": "collision-found", "upper_bound": 1}]
        for audit in ({"global_upper_bound_verified": 1, "keys_at_largest_verified_upper_bound": [key(H2)]},
                      {"global_upper_bound_verified": 2, "keys_at_largest_verified_upper_bound": [key(H2), key(H1)]}):
            with self.assertRaises(RuntimeError): CERT.surviving_frontier(2, outcomes, audit)


if __name__ == "__main__":
    unittest.main()
