#!/usr/bin/env python3
"""Exercise Family1Search checkpointing, certificates, and deterministic exports.

Usage: uv run --no-project python tests/family1_cli_test.py --exe PATH/Family1Search.exe
No Python packages or testing framework are required.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as source:
        return [json.loads(line) for line in source if line.strip()]


def read_run(directory: Path) -> tuple[list[dict], dict]:
    records = read_jsonl(directory / "graphs.jsonl")
    with (directory / "summary.json").open(encoding="utf-8-sig") as source:
        summary = json.load(source)
    keys = [(record["m"], record["key"]) for record in records]
    assert len(keys) == len(set(keys)), f"Duplicate exported graph classes: {directory}"
    assert keys == sorted(keys), f"Nondeterministic graph ordering: {directory}"
    for m in {record["m"] for record in records}:
        ordinals = [record["ordinal"] for record in records if record["m"] == m]
        assert ordinals == list(range(len(ordinals))), (directory, m, ordinals)
    return records, summary


def semantic_summary(summary: dict) -> dict:
    fields = ("m", "evaluated", "enumeration_complete", "scoring_complete",
              "maximum_certified", "maximum_merge_length", "best_exact_merge_length",
              "maximizer_count")
    return {
        "sizes": [{field: item[field] for field in fields} for item in summary["sizes"]],
        "cumulative": {field: summary["cumulative"][field]
                       for field in fields if field in summary["cumulative"]},
    }


def semantic_records(records: list[dict]) -> list[dict]:
    # Exact scores remain valid when resumed with different search limits.
    # Those original limits are useful provenance, but do not change the result.
    return [{field: value for field, value in record.items()
             if field not in {"depth", "max_layer_states"}} for record in records]


def assert_finished(directory: Path) -> tuple[list[dict], dict]:
    records, summary = read_run(directory)
    expected = {1: (1, 1, 1), 2: (6, 3, 1), 3: (57, 6, 2)}
    assert len(records) == 64, (directory, len(records))
    for item in summary["sizes"]:
        count, maximum, ties = expected[item["m"]]
        assert item["evaluated"] == count, item
        assert item["enumeration_complete"] is True, item
        assert item["scoring_complete"] is True, item
        assert item["maximum_certified"] is True, item
        assert item["maximum_merge_length"] == maximum, item
        assert item["best_exact_merge_length"] == maximum, item
        assert item["maximizer_count"] == ties, item
    assert all(record["status"] == "exact" for record in records)
    maximizers = read_jsonl(directory / "maximizers.jsonl")
    expected_keys = {(record["m"], record["key"]) for record in records
                     if record["merge_length"] == expected[record["m"]][1]}
    actual_keys = [(record["m"], record["key"]) for record in maximizers]
    assert len(actual_keys) == len(set(actual_keys)), directory
    assert set(actual_keys) == expected_keys, (directory, actual_keys, expected_keys)
    return records, summary


def assert_unfinished_scores(directory: Path, expected_status: str) -> None:
    records, summary = read_run(directory)
    assert any(record["status"] == expected_status for record in records), directory
    for record in records:
        if record["status"] != "exact":
            assert record["merge_length"] is None, record
            assert record["witness"] is None, record
            assert record["lower_bound"] >= 1, record
            if record["status"] == "depth-capped":
                assert record["lower_bound"] == 3, record  # Depth 2 fully searched.
    unfinished = [item for item in summary["sizes"] if item["m"] >= 2]
    assert unfinished
    for item in unfinished:
        assert item["enumeration_complete"] is True, item
        assert item["scoring_complete"] is False, item
        assert item["maximum_certified"] is False, item
        assert item["maximum_merge_length"] is None, item
    assert summary["cumulative"]["maximum_certified"] is False, summary


def exercise(executable: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    def run(name: str, *extra: str, success: bool = True, sizes: tuple[int, int] = (1, 3)) -> Path:
        directory = root / name
        command = [str(executable), "--min-m", str(sizes[0]), "--max-m", str(sizes[1]),
                   "--out", str(directory)]
        if "--depth" not in extra:
            command += ["--depth", "24"]
        command += extra
        result = subprocess.run(command, text=True, capture_output=True, timeout=120)
        if success:
            assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
        else:
            assert result.returncode != 0, (command, "mismatched resume configuration was accepted")
        return directory

    fresh = run("fresh", "--dot")
    expected_records, expected_summary = assert_finished(fresh)
    assert list(fresh.rglob("*.dot")), "--dot generated no graph drawing exports"
    print("Fresh run: all 64 rooted classes, exact scores and all maximum ties exported.")

    def assert_matches_fresh(directory: Path) -> None:
        records, summary = assert_finished(directory)
        assert semantic_records(records) == semantic_records(expected_records), f"Resumed graph export differs from fresh run: {directory}"
        assert semantic_summary(summary) == semantic_summary(expected_summary), directory
        assert semantic_records(read_jsonl(directory / "maximizers.jsonl")) == semantic_records(read_jsonl(fresh / "maximizers.jsonl")), directory

    stopped = run("stopped", "--limit-graphs", "3")
    stopped_records, stopped_summary = read_run(stopped)
    assert len(stopped_records) == 3, stopped_records
    assert any(not item["enumeration_complete"] for item in stopped_summary["sizes"]), stopped_summary
    assert stopped_summary["cumulative"]["maximum_certified"] is False, stopped_summary
    run("stopped", "--resume")
    assert_matches_fresh(stopped)
    print("Limited run resumed to byte-equivalent semantic records and complete maxima.")

    capped = run("capped", "--depth", "2")
    assert_unfinished_scores(capped, "depth-capped")
    cap_journal_count = len(read_jsonl(capped / "checkpoint.jsonl"))
    run("capped", "--resume")
    assert_matches_fresh(capped)
    assert len(read_jsonl(capped / "checkpoint.jsonl")) > cap_journal_count, capped
    print("Depth cap preserved lower bounds; larger-depth resume replaced unfinished scores.")

    limited = run("resource-limited", "--max-layer-states", "1")
    assert_unfinished_scores(limited, "incomplete")
    run("resource-limited", "--resume")
    assert_matches_fresh(limited)
    print("Resource-limited scores stayed incomplete; larger-budget resume completed them.")

    torn = run("torn", "--limit-graphs", "3")
    with (torn / "checkpoint.jsonl").open("ab") as target:
        target.write(b'{"m":2,"key":"torn-final-record')
    run("torn", "--resume")
    assert_matches_fresh(torn)
    read_jsonl(torn / "checkpoint.jsonl")
    print("Torn final checkpoint line recovered without losing completed graph evaluations.")

    corrupted = run("noncanonical-checkpoint", "--limit-graphs", "7")
    canonical_record = next(record for record in read_jsonl(corrupted / "checkpoint.jsonl")
                            if record["m"] == 2 and record["key"] == "0100")
    noncanonical_record = dict(canonical_record)
    noncanonical_record.update(key="1000", canonical_table=[[1, 0], [0, 0]], ordinal=6)
    # This is a COMPLETE, well-formed, accessible record with an exact witness.
    # Its independently swapped ports describe a duplicate graph class. A
    # limited resume must reject it before exports could count a seventh m=2
    # class; recovery rules for torn final writes must not hide the corruption.
    with (corrupted / "checkpoint.jsonl").open("a", encoding="utf-8", newline="\n") as target:
        target.write(json.dumps(noncanonical_record, separators=(",", ":")) + "\n")
    corrupted_before = {path.name: path.read_bytes() for path in corrupted.iterdir() if path.is_file()}
    run("noncanonical-checkpoint", "--resume", "--limit-graphs", "1", success=False)
    corrupted_after = {path.name: path.read_bytes() for path in corrupted.iterdir() if path.is_file()}
    assert corrupted_after == corrupted_before, "Rejected noncanonical checkpoint modified run files"
    print("Complete noncanonical checkpoint rejected before a limited resume could export false coverage.")

    checkpoint_before = (fresh / "checkpoint.jsonl").read_bytes()
    graphs_before = (fresh / "graphs.jsonl").read_bytes()
    run("fresh", "--resume", success=False, sizes=(2, 3))
    assert (fresh / "checkpoint.jsonl").read_bytes() == checkpoint_before
    assert (fresh / "graphs.jsonl").read_bytes() == graphs_before
    print("Mismatched size configuration rejected without modifying prior results.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path, help="Preserve test runs here; use a fresh directory")
    args = parser.parse_args()
    executable = args.exe.resolve()
    assert executable.is_file(), executable
    if args.work_dir:
        exercise(executable, args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="family1-cli-") as temporary:
            exercise(executable, Path(temporary))
    print("Family1 CLI integration checks passed.")


if __name__ == "__main__":
    main()
