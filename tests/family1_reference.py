#!/usr/bin/env python3
"""Independent, deliberately simple Family 1 oracle for m <= 3.

This does not reuse the C++ enumerator or scoring algorithm: it enumerates every
ordered labelled transition table, tries every root-fixing permutation, and
simulates every word separately for every static mask at every depth.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


Table = tuple[tuple[int, int], ...]


def accessible(table: Table) -> bool:
    seen = {0}
    pending = [0]
    while pending:
        for state in table[pending.pop()]:
            if state not in seen:
                seen.add(state)
                pending.append(state)
    return len(seen) == len(table)


def canonical(table: Table) -> Table:
    """Try ALL root-fixing relabellings, independently sorting both ports."""
    candidates = []
    for tail in itertools.permutations(range(1, len(table))):
        old_to_new = (0,) + tail
        rows = [None] * len(table)
        for old, pair in enumerate(table):
            rows[old_to_new[old]] = tuple(sorted(old_to_new[t] for t in pair))
        candidates.append(tuple(rows))
    return min(candidates)


def trace(table: Table, mask: int, word: str) -> list[int]:
    state = 0
    visited = [state]
    for character in word:
        # The same mask bit is consulted at every revisit to this state.
        state = table[state][int(character) ^ ((mask >> state) & 1)]
        visited.append(state)
    return visited


def product_state(table: Table, word: str) -> tuple[int, ...]:
    return tuple(trace(table, mask, word)[-1] for mask in range(1 << len(table)))


def score(table: Table, depth_cap: int = 20) -> tuple[int | None, tuple[str, str] | None]:
    for depth in range(1, depth_cap + 1):
        seen = {}  # Intentionally new at each depth: earlier lengths do not count.
        for letters in itertools.product("01", repeat=depth):
            word = "".join(letters)
            state = product_state(table, word)
            if state in seen:
                return depth, (seen[state], word)
            seen[state] = word
    return None, None


def enumerate_classes(m: int) -> tuple[set[Table], int]:
    classes = set()
    labelled_accessible = 0
    for transitions in itertools.product(range(m), repeat=2 * m):
        table = tuple(zip(transitions[::2], transitions[1::2]))
        if accessible(table):
            labelled_accessible += 1
            classes.add(canonical(table))
    return classes, labelled_accessible


def verify_witness(table: Table, length: int, witness: tuple[str, str] | list[str]) -> None:
    first, second = witness
    assert first != second, (table, witness)
    assert len(first) == len(second) == length, (table, length, witness)
    assert set(first + second) <= {"0", "1"}
    assert product_state(table, first) == product_state(table, second), (table, witness)


def self_test() -> None:
    assert score(((0, 0),)) == (1, ("0", "1"))  # Loops and coincident ports.
    assert accessible(((1, 1), (1, 1)))
    assert score(((1, 1), (1, 1)))[0] == 1
    assert not accessible(((0, 0), (1, 1)))
    revisits = ((0, 1), (0, 0))
    assert trace(revisits, 1, "0000") == [0, 1, 0, 1, 0]
    assert trace(revisits, 0, "0000") == [0, 0, 0, 0, 0]
    assert trace(revisits, 3, "0000") == [0, 1, 0, 1, 0]
    assert score(revisits)[0] == 2
    # "0" and "10" reach the same product state, but their different lengths
    # are not a collision. At length 1 the two product states remain distinct.
    assert product_state(revisits, "0") == product_state(revisits, "10")
    assert product_state(revisits, "0") != product_state(revisits, "1")
    # Port swaps and non-root relabellings must preserve the entire class key.
    table = ((1, 2), (0, 2), (1, 1))
    assert canonical(table) == canonical(((2, 1), (2, 0), (1, 1)))
    assert canonical(table) == canonical(((2, 1), (2, 2), (0, 1)))


def read_table(record: dict) -> Table:
    raw = record.get("canonical_table", record.get("table", record.get("transitions")))
    if raw is None:
        raise AssertionError(f"Missing transition table: {record}")
    if raw and isinstance(raw[0], int):
        raw = list(zip(raw[::2], raw[1::2]))
    return tuple(tuple(row) for row in raw)


def compare_export(path: Path, expected: dict[int, dict[Table, int]], allow_partial: bool, maximizers_only: bool = False) -> None:
    records = []
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                item = json.loads(line)
                if "canonical_table" in item or "table" in item or "transitions" in item:
                    records.append(item)
    assert records, f"No graph records in {path}"
    actual: dict[int, dict[Table, int]] = {}
    for record in records:
        table = read_table(record)
        m = record.get("m", len(table))
        if m not in expected:
            continue
        assert accessible(table), record
        assert canonical(table) == table, record
        status = record.get("status")
        length = record.get("merge_length", record.get("H", record.get("length")))
        assert status == "exact", record
        assert length == expected[m][table], record
        witness = record.get("witness")
        if witness is None and "word0" in record and "word1" in record:
            witness = [record["word0"], record["word1"]]
        assert witness is not None, record
        verify_witness(table, length, witness)
        assert table not in actual.setdefault(m, {}), f"Duplicate graph in {path}: {table}"
        actual[m][table] = length
    assert actual, f"No graph records with requested small sizes in {path}"
    if not allow_partial:
        for m, values in actual.items():
            highest = max(expected[m].values())
            wanted = ({t: h for t, h in expected[m].items() if h == highest}
                      if maximizers_only else expected[m])
            assert values == wanted, (
                str(path), m, "class set differs", len(values), len(wanted),
                "missing", sorted(set(wanted) - set(values))[:5],
            )
            assert {t for t, h in values.items() if h == highest} == {
                t for t, h in expected[m].items() if h == highest
            }
    print(f"Verified {sum(map(len, actual.values()))} exported graph scores and witnesses: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-m", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--maximizers", type=Path, action="append", default=[], help="Verify the complete maximum tie collection")
    parser.add_argument("--allow-partial", action="store_true", help="Check records without requiring all classes")
    parser.add_argument("--export", type=Path, help="Write independent exact records as JSONL")
    args = parser.parse_args()
    self_test()
    expected = {}
    export = []
    for m in range(1, args.max_m + 1):
        classes, labelled_count = enumerate_classes(m)
        expected[m] = {}
        for table in sorted(classes):
            length, witness = score(table)
            assert length is not None
            verify_witness(table, length, witness)
            expected[m][table] = length
            export.append({"m": m, "canonical_table": table, "status": "exact", "merge_length": length, "witness": witness})
        highest = max(expected[m].values())
        ties = [table for table, length in expected[m].items() if length == highest]
        print(json.dumps({"m": m, "ordered_labelled_accessible": labelled_count, "rooted_classes": len(classes), "maximum": highest, "maximizers": len(ties)}))
    if args.export:
        with args.export.open("w", encoding="utf-8", newline="\n") as target:
            for record in export:
                target.write(json.dumps(record, separators=(",", ":")) + "\n")
    for path in args.compare:
        compare_export(path, expected, args.allow_partial)
    for path in args.maximizers:
        compare_export(path, expected, args.allow_partial, maximizers_only=True)
    print("Independent static-mask, revisits, loops, coincident-port and equal-length checks passed.")


if __name__ == "__main__":
    main()
