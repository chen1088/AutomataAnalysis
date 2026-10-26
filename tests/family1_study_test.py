#!/usr/bin/env python3
"""Standard-library tests for study aggregation and restart orchestration."""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]


def import_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


study = import_path("family1_study", REPO / "scripts/family1_study.py")
reference = import_path("family1_reference", REPO / "tests/family1_reference.py")


def write_run(path, records, *, seed=None, sizes=None):
    path.mkdir(parents=True)
    study.atomic_jsonl(path / "graphs.jsonl", records)
    study.atomic_json(path / "run.json", {"method": "test-fixture"} | ({"seed": seed} if seed is not None else {}))
    study.atomic_json(path / "summary.json", {"sizes": sizes or [], "candidate_traversal_complete": True})


def graph_record(table, lower, upper=None, witness=None, *, legacy=False):
    table = study.canonical_table(table)
    key = "".join(str(target) for row in table for target in row) if legacy else study.fixed_key(table)
    return {"m": len(table), "key": key, "canonical_table": table,
            "status": "exact" if lower == upper else "bounded" if upper else "lower-bound",
            "lower_bound": lower, "upper_bound": upper,
            "merge_length": lower if lower == upper else None, "witness": witness}


def fixtures(root):
    exact_records, summaries = [], []
    for m in (1, 2):
        classes, _ = reference.enumerate_classes(m)
        scores = []
        for table in sorted(classes):
            length, witness = reference.score(table)
            record = graph_record(table, length, length, witness, legacy=True)
            record.pop("upper_bound")  # Existing exhaustive output uses merge_length.
            exact_records.append(record)
            scores.append(length)
        highest = max(scores)
        summaries.append({"m": m, "evaluated": len(classes), "enumeration_complete": True,
                          "scoring_complete": True, "maximum_certified": True,
                          "maximum_merge_length": highest, "maximizer_count": scores.count(highest)})
    exact = root / "exact"
    write_run(exact, exact_records, sizes=summaries)

    # Coincident-port cycle has H=1, and all same-length words are witnesses.
    cycle = [[(s + 1) % 7] * 2 for s in range(7)]
    # These root-accessible graphs have distinct root ports, proving H>=2.
    reset = [[0, (s + 1) % 7] for s in range(7)]
    double_cycle = [[(s + 1) % 7, (s + 2) % 7] for s in range(7)]
    twenty = [[0, (s + 1) % 20] for s in range(20)]
    first = root / "first"
    write_run(first, [graph_record(cycle, 1, 4, ["0000", "1111"]),
                      graph_record(reset, 1), graph_record(double_cycle, 2), graph_record(twenty, 2)], seed=17)
    second = root / "second"
    write_run(second, [graph_record(cycle, 1, 2, ["00", "01"]), graph_record(reset, 2)], seed=29)
    third = root / "third"
    # Port swaps and a root-fixing relabeling must deduplicate exactly.
    table = list(map(list, study.canonical_table(cycle)))
    permutation = [0, 6, 5, 4, 3, 2, 1]
    transformed = [None] * 7
    for old, row in enumerate(table):
        transformed[permutation[old]] = [permutation[row[1]], permutation[row[0]]]
    record = {"m": 7, "canonical_table": transformed, "status": "exact", "lower_bound": 1,
              "upper_bound": 1, "merge_length": 1, "witness": ["0", "1"]}
    write_run(third, [record], seed=31)
    return exact, first, second, third, cycle, reset


def test_aggregation(root):
    exact, first, second, third, cycle, reset = fixtures(root)
    output = root / "study"
    args = study.parse_args(["--out", str(output), "--exact-run", str(exact),
                             "--existing-run", str(first), "--existing-run", str(second), "--existing-run", str(third)])
    summary = study.aggregate(args, [], [])
    assert len(summary["sizes"]) == 20
    assert [item["m"] for item in summary["sizes"]] == list(range(1, 21))
    assert summary["unique_graphs"] == 11  # 7 exhaustive + 3 size7 + 1 size20.
    assert summary["observations"] == 14
    for m in (1, 2):
        item = summary["sizes"][m - 1]
        assert item["global_maximum_certified"] is True
        assert item["global_maximum"] == {1: 1, 2: 3}[m]
    for m in range(3, 21):
        assert summary["sizes"][m - 1]["global_maximum_certified"] is False
        assert summary["sizes"][m - 1]["global_maximum"] is None
    seven = summary["sizes"][6]
    assert seven["unique_graphs"] == 3 and seven["observations"] == 6
    assert seven["source_runs"] == seven["restart_seeds"] == 3
    assert seven["best_known_lower_bound"] == 2 and seven["best_lower_bound_ties"] == 2
    assert seven["best_exact_merge_length"] == 1 and seven["best_exact_ties"] == 1
    assert seven["observed_maximum_certified"] is False and seven["observed_maximum"] is None
    assert seven["unresolved_graphs"] == seven["strong_challengers"] == seven["competitive_cases"] == 2
    assert summary["global_maximum_over_budget_1_to_20"] is None
    assert "not uniform" in summary["generation_description"]
    records = [record for _, record in study.jsonl(output / "graphs.jsonl")]
    selected = next(record for record in records if record["m"] == 7 and record["key"] == study.fixed_key(study.canonical_table(cycle)))
    assert selected["status"] == "exact" and selected["lower_bound"] == selected["upper_bound"] == 1
    assert selected["witness"] == ["0", "1"]
    assert selected["observation_count"] == 3 and len(selected["source_ids"]) == 3
    assert len([record for _, record in study.jsonl(output / "champions.jsonl") if record["m"] == 7]) == 2
    assert len([record for _, record in study.jsonl(output / "challengers.jsonl") if record["m"] == 7]) == 2
    assert len([record for _, record in study.jsonl(output / "best_exact.jsonl") if record["m"] == 7]) == 1
    with (output / "study.csv").open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 20 and rows[6]["global_maximum"] == ""
    before = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    study.aggregate(args, [], [])
    assert before == {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}

    # Contradictory observations must not silently overwrite stronger certificates.
    merged = {}
    table = study.canonical_table(cycle)
    study.merge_record(merged, table, graph_record(cycle, 1, 1, ["0", "1"]), 0, 0)
    try:
        study.merge_record(merged, table, graph_record(cycle, 2), 1, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("contradictory score intervals were accepted")
    # Every accessible ordered small table must agree with an independent full
    # root-fixing permutation canonicalizer, including loops and port swaps.
    for m in (1, 2, 3):
        classes, _ = reference.enumerate_classes(m)
        for candidate in classes:
            assert study.canonical_table(candidate) == reference.canonical(candidate)
    print("Aggregation checks passed: all20rows, exact small coverage, strongest consistent bounds, all ties, unresolved challengers, provenance and deterministic exports.")


def test_orchestration(root):
    root.mkdir(parents=True, exist_ok=True)
    seed_table = [[0, 1], [0, 1]]
    seed_file = root / "warm-seeds.jsonl"
    study.atomic_jsonl(seed_file, [graph_record(seed_table, 3, 3, ["010", "100"], legacy=True)])
    executable = root / "fake-executable"
    executable.write_text("not invoked: subprocess is mocked")
    args = study.parse_args(["--exe", str(executable), "--out", str(root / "orchestrated"),
                             "--restarts", "2", "--candidates", "128", "--jobs", "16",
                             "--timeout-ms", "250", "--solve-timeout-ms", "100", "--projection-masks", "8",
                             "--projection-depth", "18", "--projection-max-states", "262144", "--seeds", str(seed_file)])
    called = []

    def fake_run(command, *, cwd, check):
        assert cwd == study.REPO and check is True
        called.append(command)
        def value(flag): return command[command.index(flag) + 1]
        assert value("--min-m") == "7" and value("--max-m") == "20"
        assert value("--candidates") == "128" and value("--jobs") == "16"
        assert value("--timeout-ms") == "250" and value("--solve-timeout-ms") == "100"
        assert value("--projection-masks") == "8" and value("--projection-depth") == "18"
        assert value("--seeds") == str(seed_file.resolve())
        directory = Path(value("--out")); directory.mkdir(parents=True)
        metadata = study.requested_run_config(args, int(value("--seed")), study.expected_seed_keys(seed_file))
        study.atomic_json(directory / "run.json", metadata)
        study.atomic_json(directory / "summary.json", {"candidate_traversal_complete": True})
        study.atomic_jsonl(directory / "graphs.jsonl", [])
        return subprocess.CompletedProcess(command, 0)

    with patch.object(study.subprocess, "run", side_effect=fake_run):
        directories, commands = study.orchestrate_restarts(args)
        assert len(called) == 2 and len(directories) == 2
        assert commands[0]["seed"] != commands[1]["seed"]
        directories_again, reused = study.orchestrate_restarts(args)
        assert directories_again == directories and len(called) == 2
        assert all(item["reused_completed_run"] is True for item in reused)
        changed = deepcopy(args); changed.timeout_ms = 251
        try:
            study.orchestrate_restarts(changed)
        except ValueError:
            pass
        else:
            raise AssertionError("changed restart budget was accepted")
    print("Orchestration checks passed with mocked subprocesses: independent deterministic seeds, identical per-size budgets, warm seeds, completed-run reuse, changed-budget rejection. No search workload launched.")


def test_global_import(root):
    exact, first, second, third, _, _ = fixtures(root)
    executable = root / "mock-global-verifier"
    executable.write_text("mocked verifier: no native proof claim is made by this unit test")
    proof = {"schema": 1, "method": study.GLOBAL_METHOD, "encoder_version": study.GLOBAL_ENCODER,
             "states": 7, "threshold": 2, "decision": "impossible", "global_upper_bound_certified": True,
             "proven_upper_bound": 2, "learned_pairs": [["00", "01"]]}
    # This is a synthetic UNSAT response to test aggregation semantics. Native
    # synthesis correctness is tested separately; this mocked result is not a
    # real mathematical claim about seven-state graphs.
    proof_path = root / "supplied-proof.json"
    study.atomic_json(proof_path, proof)
    unknown_path = root / "unknown-result.json"
    unknown = dict(proof, states=20, threshold=64, decision="unknown", global_upper_bound_certified=False,
                   proven_upper_bound=None, learned_pairs=[], reason="timeout")
    study.atomic_json(unknown_path, unknown)
    args = study.parse_args(["--out", str(root / "with-proof"), "--exact-run", str(exact),
                             "--existing-run", str(first), "--existing-run", str(second), "--existing-run", str(third),
                             "--global-certificate", str(proof_path), "--global-certificate", str(unknown_path),
                             "--global-exe", str(executable)])
    calls = []

    def fake_replay(command, *, cwd, check):
        assert cwd == study.REPO and check is True
        calls.append(command)
        replay_input = Path(command[command.index("--replay") + 1])
        result = study.load_json(replay_input / "result.json")
        assert result == proof
        output = Path(command[command.index("--out") + 1]); output.mkdir(parents=True)
        study.atomic_json(output / "result.json", result)
        return subprocess.CompletedProcess(command, 0)

    with patch.object(study.subprocess, "run", side_effect=fake_replay):
        summary = study.aggregate(args, [], [])
        assert len(calls) == 1  # UNKNOWN reports never supply a bound or trigger replay.
        seven = summary["sizes"][6]
        assert seven["global_upper_bound"] == seven["global_maximum"] == 2
        assert seven["maximum_value_certified"] is True
        assert seven["maximizing_collection_complete"] is False
        assert seven["strong_challengers"] == 0 and seven["competitive_cases"] == 2
        assert seven["formal_global_status"] == "maximum-value-certified-collection-incomplete"
        twenty = summary["sizes"][19]
        assert twenty["global_upper_bound"] is None and twenty["maximum_value_certified"] is False
        assert twenty["formal_global_status"] == "unresolved"
        assert twenty["formal_attempts"] == 1
        records = [record for _, record in study.jsonl(args.out / "graphs.jsonl") if record["m"] == 7]
        composed = [record for record in records if record["lower_bound"] == 2]
        assert len(composed) == 2
        assert all(record["witness"] is None and record["status"] == "lower-bound" for record in composed)
        assert all(record["effective_status"] == "exact" and record["effective_merge_length"] == 2 for record in composed)
        assert len([record for _, record in study.jsonl(args.out / "best_exact.jsonl") if record["m"] == 7]) == 2
        study.aggregate(args, [], [])
        assert len(calls) == 1  # Binding includes input and verifier hashes.

    no_verifier = deepcopy(args); no_verifier.global_exe = None
    try:
        study.import_global_certificates(no_verifier)
    except ValueError:
        pass
    else:
        raise AssertionError("bare impossible JSON was accepted without a verifier")
    bad = deepcopy(proof); bad["encoder_version"] = "unrecognized-encoder"
    try:
        study.validate_global_report(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("unrecognized proof encoder accepted")
    for encoder in study.GLOBAL_ENCODERS:
        supported = deepcopy(proof); supported["encoder_version"] = encoder
        assert study.validate_global_report(supported) == (proof["states"], proof["threshold"], proof["decision"])
    print("Global import plumbing passed with mocked UNSAT replay: value certification remains separate from all-maximizer completeness; UNKNOWN yields no bound; cache is bound to proof/verifier hashes. No native/global proof is asserted by this unit test.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        test_aggregation(args.work_dir / "aggregation")
        test_orchestration(args.work_dir / "orchestration")
        test_global_import(args.work_dir / "global-import")
    else:
        with tempfile.TemporaryDirectory(prefix="family1-study-test-") as temporary:
            root = Path(temporary)
            test_aggregation(root / "aggregation")
            test_orchestration(root / "orchestration")
            test_global_import(root / "global-import")
    print("Family1 study checks passed.")


if __name__ == "__main__":
    main()
