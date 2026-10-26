#!/usr/bin/env python3
"""Check a completed Family1Search export and independently simulate witnesses.

This checks exported coverage against the known class counts and maximum
scores. It does not independently certify the absence of shorter collisions;
use family1_reference.py for an independent exhaustive scoring check at m<=3.
By default every maximizing witness is simulated for every static mask. Add
--all-witnesses to perform that simulation for every evaluated graph.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


CLASS_COUNTS = {1: 1, 2: 6, 3: 57, 4: 678, 5: 10398, 6: 192181}
MAXIMUM_LENGTHS = {1: 1, 2: 3, 3: 6, 4: 10, 5: 15, 6: 23}
MAXIMIZER_COUNTS = {1: 1, 2: 1, 3: 2, 4: 1, 5: 5, 6: 2}


def jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as source:
        for line_number, line in enumerate(source, 1):
            if line.strip():
                yield line_number, json.loads(line)


def identity(record: dict) -> tuple[int, str]:
    return record["m"], record["key"]


def witness_format(record: dict) -> None:
    witness = record["witness"]
    assert isinstance(witness, list) and len(witness) == 2, record
    first, second = witness
    assert isinstance(first, str) and isinstance(second, str), record
    assert first != second, record
    assert len(first) == len(second) == record["merge_length"], record
    assert set(first + second) <= {"0", "1"}, record


def simulate_witness(record: dict) -> None:
    """Ordinary integer states and direct XOR transitions; no bit-plane code."""
    witness_format(record)
    table = record["canonical_table"]
    first, second = (tuple(map(int, word)) for word in record["witness"])
    letters = tuple(zip(first, second))
    for mask in range(1 << record["m"]):
        state_first = state_second = 0
        for input_first, input_second in letters:
            state_first = table[state_first][input_first ^ ((mask >> state_first) & 1)]
            state_second = table[state_second][input_second ^ ((mask >> state_second) & 1)]
        assert state_first == state_second, (identity(record), mask, record["witness"])


def verify_collection(path: Path, expected: list[dict]) -> None:
    actual = [record for _, record in jsonl(path)]
    actual_keys = [identity(record) for record in actual]
    assert actual_keys == sorted(actual_keys), (path, "export order")
    assert len(actual_keys) == len(set(actual_keys)), (path, "duplicate graph")
    expected = sorted(expected, key=identity)
    assert actual == expected, (
        path, "wrong graph collection", actual_keys, [identity(record) for record in expected]
    )


def verify_summary(item: dict, *, m: int, count: int, maximum: int, ties: int) -> None:
    assert item["m"] == m, item
    assert item["evaluated"] == item["exact"] == count, item
    assert item["depth_capped"] == item["incomplete"] == 0, item
    assert item["enumeration_complete"] is True, item
    assert item["scoring_complete"] is True, item
    assert item["maximum_certified"] is True, item
    assert item["maximum_merge_length"] == item["best_exact_merge_length"] == maximum, item
    assert item["maximizer_count"] == item["best_exact_count"] == ties, item


def verify_run(directory: Path, all_witnesses: bool) -> None:
    with (directory / "summary.json").open(encoding="utf-8-sig") as source:
        summary = json.load(source)
    min_m, max_m = summary["min_m"], summary["max_m"]
    assert 1 <= min_m <= max_m <= 6, summary
    sizes = list(range(min_m, max_m + 1))
    assert [item["m"] for item in summary["sizes"]] == sizes, summary
    distributions = {m: Counter() for m in sizes}
    best_lengths = {m: 0 for m in sizes}
    best_records = {m: [] for m in sizes}
    next_ordinals = {m: 0 for m in sizes}
    previous_key = None
    simulated = 0
    for line_number, record in jsonl(directory / "graphs.jsonl"):
        m, key = identity(record)
        assert m in distributions, (line_number, m)
        assert previous_key is None or previous_key < (m, key), (line_number, "duplicate or unordered graph")
        previous_key = (m, key)
        assert record["ordinal"] == next_ordinals[m], (line_number, record)
        next_ordinals[m] += 1
        table = record["canonical_table"]
        assert len(table) == m and all(len(row) == 2 for row in table), record
        assert all(0 <= first <= second < m for first, second in table), record
        assert key == "".join(str(target) for row in table for target in row), record
        reached = {0}
        pending = [0]
        while pending:
            for state in table[pending.pop()]:
                if state not in reached:
                    reached.add(state)
                    pending.append(state)
        assert len(reached) == m, record
        assert record["status"] == "exact", record
        length = record["merge_length"]
        assert isinstance(length, int) and 1 <= length <= record["depth"], record
        assert record["lower_bound"] == length, record
        witness_format(record)
        distributions[m][length] += 1
        if length > best_lengths[m]:
            best_lengths[m] = length
            best_records[m] = []
        if length == best_lengths[m]:
            best_records[m].append(record)
        if all_witnesses:
            simulate_witness(record)
            simulated += 1
    for item in summary["sizes"]:
        m = item["m"]
        assert next_ordinals[m] == CLASS_COUNTS[m], (m, next_ordinals[m], CLASS_COUNTS[m])
        assert best_lengths[m] == MAXIMUM_LENGTHS[m], (m, best_lengths[m])
        assert len(best_records[m]) == MAXIMIZER_COUNTS[m], (m, len(best_records[m]))
        verify_summary(item, m=m, count=CLASS_COUNTS[m], maximum=MAXIMUM_LENGTHS[m], ties=MAXIMIZER_COUNTS[m])
        print(json.dumps({"m": m, "classes": next_ordinals[m], "maximum": best_lengths[m],
                          "maximizers": len(best_records[m]),
                          "score_distribution": dict(sorted(distributions[m].items()))}, separators=(",", ":")))
    maxima = [record for m in sizes for record in best_records[m]]
    verify_collection(directory / "maximizers.jsonl", maxima)
    verify_collection(directory / "best_exact.jsonl", maxima)
    cumulative_maximum = max(best_lengths.values())
    cumulative_maxima = [record for record in maxima if record["merge_length"] == cumulative_maximum]
    cumulative = summary["cumulative"]
    assert cumulative["min_m"] == min_m and cumulative["max_m"] == max_m, cumulative
    expected_scope = "size-budget-1-through-max-m" if min_m == 1 else "selected-size-range"
    assert cumulative["scope"] == expected_scope, cumulative
    verify_summary(cumulative, m=0, count=sum(next_ordinals.values()),
                   maximum=cumulative_maximum, ties=len(cumulative_maxima))
    verify_collection(directory / "cumulative_maximizers.jsonl", cumulative_maxima)
    if not all_witnesses:
        for record in maxima:
            simulate_witness(record)
            simulated += 1
    print(f"Verified complete exports and {simulated} witness pairs by direct simulation over every static mask.")
    print("Score minimality is independently cross-checked only where family1_reference.py is also run.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--all-witnesses", action="store_true", help="Directly simulate every graph's witness pair")
    args = parser.parse_args()
    verify_run(args.run_directory, args.all_witnesses)


if __name__ == "__main__":
    main()
