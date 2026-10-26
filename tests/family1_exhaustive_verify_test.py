"""Regression tests for the standalone journal verifier and its proof scope.

The complete three-state fixture comes from independent ordered-table and
word/mask enumeration, not from the production exhaustive runner.
"""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from family1_exhaustive_cli_test import oracle


ROOT = Path(__file__).resolve().parents[1]


def key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def record(table, length, witness, ordinal=0, status="exact"):
    return {
        "m": len(table), "ordinal": ordinal, "key": key(table),
        "canonical_table": list(map(list, table)), "status": status,
        "lower_bound": length if status == "exact" else 1,
        "upper_bound": length, "merge_length": length if status == "exact" else None,
        "witness": list(witness), "reason": "",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path,
                        default=ROOT / "out/build/msvc-vcpkg/Release/Family1ExhaustiveVerify.exe")
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    expected = oracle()
    complete = [record(table, length, witness, ordinal)
                for ordinal, (_, (length, table, witness)) in enumerate(sorted(expected.items()))]
    assert len(complete) == 57
    invocations = 0

    with tempfile.TemporaryDirectory(prefix="family1-journal-verify-", dir=ROOT / "out") as name:
        temporary = Path(name).resolve()
        assert temporary.is_relative_to((ROOT / "out").resolve())

        def run(name, values=None, *, raw=None, states=3, count=None, success=True):
            nonlocal invocations
            invocations += 1
            journal, report = temporary / f"{name}.jsonl", temporary / f"{name}.json"
            if raw is None:
                raw = "".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values)
            journal.write_text(raw, encoding="utf-8", newline="\n")
            before = journal.read_bytes()
            command = [str(executable), "--states", str(states), "--journal", str(journal), "--out", str(report)]
            if count is not None:
                command += ["--expected-count", str(count)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            assert (result.returncode == 0) == success, (name, result.stdout, result.stderr)
            assert journal.read_bytes() == before, "Verifier modified its input journal"
            data = json.loads(report.read_text(encoding="utf-8"))
            assert data["verification_passed"] is success, (name, data)
            # Neither accepted metadata nor a count override supplies lower
            # proofs, individual exact minima, or a complete tie certificate.
            assert data["lower_proofs_checked"] is False
            assert data["maximum_value_certified"] is False
            assert data["maximizing_collection_complete"] is False
            if not success:
                assert data["failure"]
                assert data["enumeration_complete"] is False
                assert data["global_upper_bound_verified"] is None
            return data

        exact = run("complete-exact", complete, count=57)
        assert exact["enumeration_complete"] and exact["records_verified"] == 57
        assert exact["upper_witnesses_verified"] == 57 and exact["global_upper_bound_verified"] == 6
        assert exact["claimed_exact_records"] == 57
        expected_distribution = {str(length): count for length, count in Counter(value[0] for value in expected.values()).items()}
        expected_frontier = sorted(key for key, value in expected.items() if value[0] == 6)
        assert len(expected_frontier) == 2
        assert exact["upper_bound_distribution"] == expected_distribution
        assert exact["keys_at_largest_verified_upper_bound"] == expected_frontier
        assert exact["root_fixed_permutations_checked_per_graph"] == 2
        assert exact["original_static_masks_checked_per_upper_witness"] == 8

        bounded = deepcopy(complete)
        for value in bounded:
            value.update(status="bounded", lower_bound=1, merge_length=None)
        bound = run("complete-bounded", bounded)
        assert bound["enumeration_complete"] and bound["global_upper_bound_verified"] == 6
        assert bound["claimed_exact_records"] == 0 and bound["bounded_records"] == 57
        assert bound["upper_bound_distribution"] == expected_distribution
        assert bound["keys_at_largest_verified_upper_bound"] == expected_frontier

        prefix = run("valid-prefix", complete[:13])
        override = run("prefix-count-override", complete[:13], count=13)
        for data in (prefix, override):
            assert not data["enumeration_complete"] and data["global_upper_bound_verified"] is None
            assert data["burnside_expected_classes"] == 57

        partial = deepcopy(complete)
        partial[0].update(status="depth-capped", lower_bound=1, upper_bound=None, merge_length=None, witness=None)
        partial[1].update(status="incomplete", lower_bound=2, upper_bound=None, merge_length=None, witness=None)
        capped = run("complete-with-unresolved", partial)
        assert capped["enumeration_complete"] and capped["global_upper_bound_verified"] is None
        assert capped["records_without_verified_upper"] == 2
        assert capped["depth_capped_records"] == capped["incomplete_records"] == 1
        assert sum(capped["upper_bound_distribution"].values()) == 55

        # Coincident ports, loops, and original masks that have no effect.
        one = run("one-state", [record(((0, 0),), 1, ("0", "1"))], states=1, count=1)
        assert one["enumeration_complete"] and one["global_upper_bound_verified"] == 1
        functional = tuple((min(state + 1, 6),) * 2 for state in range(7))
        seven = record(functional, 1, ("0", "1"), status="bounded")
        seven["reason"] = "Unicode \u03b1 \U0001f4c4 and escaped newline\n"
        data = run("seven-state-prefix", [seven], states=7, count=1)
        assert data["root_fixed_permutations_checked_per_graph"] == 720
        assert data["original_static_masks_checked_per_upper_witness"] == 128
        assert not data["enumeration_complete"] and data["burnside_expected_classes"] == 4166855

        # This graph actually has H=1. A padded length-31 witness is valid, but
        # its invented lower bound is not. The verifier must retain that lower
        # bound as an explicitly UNCHECKED claim rather than certify H=31.
        false_lower = record(functional, 31, ("0" * 31, "0" * 30 + "1"))
        data = run("false-lower-claim", [false_lower], states=7, count=1)
        assert data["largest_inherited_claimed_lower_bound"] == 31
        assert data["independently_verified_lower_bound_per_graph"] == 1
        assert data["inherited_lower_bound_claims_above_one"] == 1
        assert data["lower_bound_warning"] and data["global_upper_bound_verified"] is None
        assert data["upper_bound_distribution"] == {"31": 1}
        assert data["keys_at_largest_verified_upper_bound"] == [false_lower["key"]]

        wrong = deepcopy(complete)
        wrong[0]["ordinal"] = 1
        run("bad-ordinal", wrong, success=False)
        wrong = deepcopy(complete)
        wrong[0]["key"] = "bad"
        run("bad-key", wrong, success=False)
        wrong = deepcopy(complete)
        wrong[1]["key"] = wrong[0]["key"]
        wrong[1]["canonical_table"] = wrong[0]["canonical_table"]
        run("duplicate-key", wrong, success=False)
        wrong = deepcopy(complete)
        wrong[0], wrong[1] = wrong[1], wrong[0]
        for ordinal, value in enumerate(wrong):
            value["ordinal"] = ordinal
        run("unsorted-keys", wrong, success=False)

        noncanonical = record(((2, 2), (1, 1), (1, 1)), 1, ("0", "1"))
        run("noncanonical-table", [noncanonical], success=False)
        unreachable = record(((0, 0), (1, 1)), 1, ("0", "1"))
        run("inaccessible-table", [unreachable], states=2, success=False)
        invalid_target = deepcopy(complete[0])
        invalid_target["canonical_table"][0][0] = 3
        invalid_target["key"] = key(invalid_target["canonical_table"])
        run("invalid-target", [invalid_target], success=False)

        # For this two-state graph mask 0 separates 000 and 001.
        false_witness = record(((0, 1), (0, 1)), 3, ("000", "001"))
        run("false-upper-witness", [false_witness], states=2, success=False)
        for name, change in (
            ("different-word-lengths", {"witness": ["0", "11"]}),
            ("identical-words", {"witness": ["0", "0"]}),
            ("nonbinary-word", {"witness": ["0", "2"]}),
            ("unknown-status", {"status": "finished"}),
            ("zero-lower", {"lower_bound": 0}),
            ("lower-above-upper", {"lower_bound": 2}),
            ("bounded-no-upper", {"upper_bound": None, "witness": None}),
            ("upper-without-witness", {"witness": None}),
            ("witness-without-upper", {"upper_bound": None}),
            ("nonexact-merge", {"merge_length": 1}),
            ("exact-inconsistent-merge", {"status": "exact", "merge_length": 2}),
            ("wrong-state-count", {"m": 6}),
        ):
            value = deepcopy(seven)
            value.update(change)
            run(name, [value], states=7, success=False)

        serialized = json.dumps(seven, separators=(",", ":"))
        run("duplicate-field", raw=serialized.replace('"m":7', '"m":7,"m":7'), states=7, success=False)
        run("unknown-field", raw=serialized[:-1] + ',"extra":0}', states=7, success=False)
        run("integer-overflow", raw=serialized.replace('"ordinal":0', '"ordinal":18446744073709551616'), states=7, success=False)
        run("leading-zero", raw=serialized.replace('"ordinal":0', '"ordinal":00'), states=7, success=False)
        run("floating-point-integer", raw=serialized.replace('"ordinal":0', '"ordinal":0.0'), states=7, success=False)
        run("bad-unicode-surrogate", raw=serialized.replace('"reason":', '"reason":"\\ud800", "unused":'), states=7, success=False)
        missing = deepcopy(seven)
        del missing["reason"]
        run("missing-field", [missing], states=7, success=False)
        run("torn-json", raw=serialized[:20], states=7, success=False)
        run("trailing-text", raw=serialized + "garbage", states=7, success=False)
        run("wrong-expected-count", complete, count=56, success=False)
        broken_prefix = "".join(json.dumps(value) + "\n" for value in complete[:13]) + '{"m":3'
        data = run("torn-after-prefix", raw=broken_prefix, success=False)
        assert data["records_verified"] == 13 and data["failure_line"] == 14

        # The report path must never be allowed to overwrite the input journal.
        journal = temporary / "same-file.jsonl"
        journal.write_text(serialized + "\n", encoding="utf-8")
        before = hashlib.sha256(journal.read_bytes()).digest()
        aliases = [journal]
        if os.name == "nt":
            aliases.append(journal.with_name(journal.name.upper()))
        for report_path in aliases:
            result = subprocess.run([str(executable), "--states", "7", "--journal", str(journal), "--out", str(report_path)],
                                    cwd=ROOT, capture_output=True, text=True)
            invocations += 1
            assert result.returncode != 0 and "must differ" in result.stderr
            assert hashlib.sha256(journal.read_bytes()).digest() == before

    print(f"PASS: {invocations} standalone journal-verifier cases; independent 57-class oracle, all-mask witnesses, malformed records, and explicitly unchecked false lower claim.")


if __name__ == "__main__":
    main()
