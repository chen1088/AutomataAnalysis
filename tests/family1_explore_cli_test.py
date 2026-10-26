#!/usr/bin/env python3
"""Exercise the real symbolic Family 1 CLI without claiming exhaustive coverage.

Usage: uv run --no-project python tests/family1_explore_cli_test.py --exe PATH
An optional --work-dir preserves small verification runs in a fresh directory.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


REFERENCE_PATH = Path(__file__).with_name("family1_reference.py")
spec = importlib.util.spec_from_file_location("family1_reference", REFERENCE_PATH)
reference = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(reference)


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]


def fixed_key(table) -> str:
    return "".join(f"{target:02d}" for row in table for target in row)


def identity(record: dict) -> tuple[int, str]:
    return record["m"], record["key"]


def semantic(records: list[dict]) -> list[dict]:
    return [{key: value for key, value in record.items() if key != "seconds"} for record in records]


def assert_small_run(directory: Path) -> tuple[list[dict], dict]:
    records = jsonl(directory / "graphs.jsonl")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8-sig"))
    keys = [identity(record) for record in records]
    assert keys == sorted(keys) and len(keys) == len(set(keys)), directory
    assert len(records) == 15, (directory, len(records))  # 1 + 6 + 8 candidates.
    by_size = {m: [record for record in records if record["m"] == m] for m in (1, 2, 3)}
    assert [len(by_size[m]) for m in (1, 2, 3)] == [1, 6, 8]
    for record in records:
        table = tuple(map(tuple, record["canonical_table"]))
        assert reference.accessible(table) and reference.canonical(table) == table, record
        assert record["key"] == fixed_key(table), record
        length, _ = reference.score(table)
        assert record["status"] == "exact", record
        assert record["merge_length"] == record["lower_bound"] == record["upper_bound"] == length, record
        assert 1 <= record["projection_lower_bound"] <= record["lower_bound"], record
        reference.verify_witness(table, length, record["witness"])
    # Even complete scores in the heuristic candidate pool do not establish a
    # maximum over every graph. These fields must stay false/null throughout.
    for item in [summary, *summary["sizes"]]:
        assert item["enumeration_complete"] is False, item
        assert item["maximum_certified"] is False, item
        assert item["global_maximum"] is None, item
    assert summary["candidate_traversal_complete"] is True, summary
    assert [item["m"] for item in summary["sizes"]] == [1, 2, 3], summary
    lower_ties, exact_ties, possible = [], [], []
    for item in summary["sizes"]:
        m = item["m"]
        highest = max(record["merge_length"] for record in by_size[m])
        expected = [record for record in by_size[m] if record["merge_length"] == highest]
        assert highest == {1: 1, 2: 3, 3: 6}[m], item
        assert len(expected) == {1: 1, 2: 1, 3: 2}[m], item
        assert item["evaluated"] == item["exact"] == len(by_size[m]), item
        assert item["largest_certified_lower_bound"] == item["best_exact_merge_length"] == highest, item
        assert item["best_lower_bound_count"] == item["best_exact_count"] == len(expected), item
        lower_ties.extend(expected)
        exact_ties.extend(expected)
        possible.extend(expected)
    assert jsonl(directory / "best_lower_bound.jsonl") == sorted(lower_ties, key=identity)
    assert jsonl(directory / "best_exact.jsonl") == sorted(exact_ties, key=identity)
    assert jsonl(directory / "potential_best.jsonl") == sorted(possible, key=identity)
    return records, summary


def file_snapshot(directory: Path) -> dict[str, bytes]:
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def exercise(executable: Path, root: Path, all_masks: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)

    def run(name: str, *extra: str, success: bool = True, single: str | None = None):
        command = [str(executable), "--out", str(root / name), "--candidates", "8", "--beam", "1",
                   "--timeout-ms", "2000", "--solve-timeout-ms", "1000", "--max-length", "8",
                   "--projection-depth", "8", "--projection-max-states", "256"]
        command += ["--graph", single] if single else ["--min-m", "1", "--max-m", "3"]
        result = subprocess.run(command + list(extra), text=True, capture_output=True, timeout=120)
        assert (result.returncode == 0) == success, (command, extra, result.returncode, result.stdout, result.stderr)
        return root / name

    fresh = run("fresh", "--dot")
    expected_records, expected_summary = assert_small_run(fresh)
    assert len(list((fresh / "dot").glob("*.dot"))) == 4
    # Beam=1 still retains BOTH m=3 maximizing classes in all result exports.
    assert len([record for record in jsonl(fresh / "best_exact.jsonl") if record["m"] == 3]) == 2
    print("Real SAT CLI: all 15 small candidates match independent exhaustive scores; every best tie retained with beam=1.")

    def matches(directory: Path):
        records, summary = assert_small_run(directory)
        assert semantic(records) == semantic(expected_records), directory
        assert summary == expected_summary, directory
        for name in ("best_lower_bound.jsonl", "best_exact.jsonl", "potential_best.jsonl"):
            assert semantic(jsonl(directory / name)) == semantic(jsonl(fresh / name)), (directory, name)

    limited = run("limited", "--limit-graphs", "7")
    assert len(jsonl(limited / "graphs.jsonl")) == 7
    assert json.loads((limited / "summary.json").read_text())["candidate_traversal_complete"] is False
    run("limited", "--resume")
    matches(limited)
    run("limited", "--resume")
    matches(limited)
    print("Limited and completed resumes reproduce the full candidate collection and bounds.")

    parallel = run("parallel", "--jobs", "2", "--dot")
    matches(parallel)
    assert [identity(record) for record in jsonl(parallel / "checkpoint.jsonl")] == [identity(record) for record in expected_records]
    assert "jobs" not in json.loads((fresh / "run.json").read_text())
    assert json.loads((parallel / "run.json").read_text())["jobs"] == 2
    parallel_limited = run("parallel-limited", "--jobs", "2", "--limit-graphs", "4")
    assert len(jsonl(parallel_limited / "graphs.jsonl")) == 4
    assert len(jsonl(parallel_limited / "checkpoint.jsonl")) == 4
    # This stops in a partially filled batch: one m=1 result, a pair at m=2,
    # then exactly one remaining launch before the limit is reached.
    run("parallel-limited", "--jobs", "2", "--resume")
    matches(parallel_limited)
    before = file_snapshot(parallel)
    run("parallel", "--resume", "--jobs", "1", success=False)
    assert file_snapshot(parallel) == before
    print("Jobs=2 preserves pool-order results and all ties; partial-batch limits/resume and jobs-config rejection passed.")

    parallel_sat = run("parallel-sat", "--jobs", "2", "--projection-depth", "0")
    sat_records, _ = assert_small_run(parallel_sat)
    assert any(record["queries"] > 0 for record in sat_records), "parallel SAT path was not exercised"
    assert [identity(record) for record in sat_records] == [identity(record) for record in expected_records]
    print("Jobs=2 with projection disabled independently verifies concurrent SAT solver contexts on all small candidates.")

    torn = run("torn", "--limit-graphs", "7")
    with (torn / "checkpoint.jsonl").open("ab") as target:
        target.write(b'{"m":3,"key":"partial')
    run("torn", "--resume")
    matches(torn)
    jsonl(torn / "checkpoint.jsonl")
    print("Torn final journal recovery preserves completed graph results.")

    before = file_snapshot(fresh)
    run("fresh", "--resume", "--beam", "2", success=False)
    assert file_snapshot(fresh) == before

    corrupt = run("noncanonical", "--limit-graphs", "7")
    raw = (corrupt / "checkpoint.jsonl").read_text(encoding="utf-8")
    original = next(line for line in raw.splitlines() if '"key":"00010000"' in line)
    forged = original.replace('"key":"00010000"', '"key":"01000000"').replace(
        '"canonical_table":[[0,1],[0,0]]', '"canonical_table":[[1,0],[0,0]]')
    assert original != forged
    with (corrupt / "checkpoint.jsonl").open("a", encoding="utf-8", newline="\n") as target:
        target.write(forged + "\n")
    before = file_snapshot(corrupt)
    run("noncanonical", "--resume", "--limit-graphs", "1", success=False)
    assert file_snapshot(corrupt) == before
    print("Incompatible config and complete noncanonical journal records are rejected without modifying files.")

    capped = run("capped", "--max-length", "1", "--projection-depth", "1")
    capped_records = jsonl(capped / "graphs.jsonl")
    assert any(record["status"] != "exact" for record in capped_records)
    for record in capped_records:
        table = tuple(map(tuple, record["canonical_table"]))
        length, _ = reference.score(table)
        assert record["lower_bound"] <= length, record
        if record["status"] != "exact":
            assert record["merge_length"] is None and record["upper_bound"] is None and record["witness"] is None, record
        else:
            assert record["merge_length"] == length, record
    expected_lower, expected_exact, expected_possible = [], [], []
    for m in (1, 2, 3):
        sized = [record for record in capped_records if record["m"] == m]
        largest_lower = max(record["lower_bound"] for record in sized)
        known_exact = [record for record in sized if record["status"] == "exact"]
        largest_exact = max((record["merge_length"] for record in known_exact), default=0)
        expected_lower.extend(record for record in sized if record["lower_bound"] == largest_lower)
        expected_exact.extend(record for record in known_exact if record["merge_length"] == largest_exact)
        expected_possible.extend(record for record in sized if record["upper_bound"] is None or record["upper_bound"] >= largest_lower)
    assert jsonl(capped / "best_lower_bound.jsonl") == sorted(expected_lower, key=identity)
    assert jsonl(capped / "best_exact.jsonl") == sorted(expected_exact, key=identity)
    assert jsonl(capped / "potential_best.jsonl") == sorted(expected_possible, key=identity)
    capped_snapshot = semantic(capped_records)
    run("capped", "--resume", "--max-length", "1", "--projection-depth", "1")
    assert semantic(jsonl(capped / "graphs.jsonl")) == capped_snapshot
    capped_summary = json.loads((capped / "summary.json").read_text())
    assert capped_summary["maximum_certified"] is False and capped_summary["global_maximum"] is None
    print("Length-capped runs export certified lower bounds and every potential/best tie without exact-score claims.")

    cycle = [[(state + 1) % 20] * 2 for state in range(20)]
    single = run("single20", "--dot", single=fixed_key(cycle))
    record, = jsonl(single / "graphs.jsonl")
    assert record["m"] == 20 and record["status"] == "exact", record
    assert record["merge_length"] == record["lower_bound"] == record["upper_bound"] == 1, record
    assert record["witness"][0] != record["witness"][1]
    assert all(len(word) == 1 and set(word) <= {"0", "1"} for word in record["witness"])
    table = record["canonical_table"]
    if all_masks:
        for mask in range(1 << 20):
            first = table[0][int(record["witness"][0]) ^ (mask & 1)]
            second = table[0][int(record["witness"][1]) ^ (mask & 1)]
            assert first == second, mask
    single_summary = json.loads((single / "summary.json").read_text())
    assert single_summary["maximum_certified"] is False and single_summary["global_maximum"] is None
    run("single20", "--resume", single=fixed_key(cycle))
    print("Single 20-state coincident-port cycle: exact H=1, witness checked against all 1,048,576 static masks.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    if args.work_dir:
        exercise(executable, args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-explore-cli-") as temporary:
            exercise(executable, Path(temporary))
    print("Family1Explore CLI integration checks passed.")


if __name__ == "__main__":
    main()
