#!/usr/bin/env python3
"""Independently audit a small saved Family 1 global-upper-bound certificate.

uv run --with pycosat python tests/family1_global_cnf_test.py --cnf m3.cnf --pairs m3-pairs.json

PicoSAT independently solves the exported DIMACS formula. A separate ordinary
Python check exhausts EVERY ordered labeled root-accessible graph through m=3
and checks that the learned word pairs cover it. This is independent of Z3,
the synthesis graph encoding, canonicalization, and symbolic state simulation.
This produces an independently checked finite cover; it is not a DRAT checker.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def read_dimacs(path: Path) -> tuple[int, list[list[int]]]:
    header = None
    clauses, clause = [], []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p"):
            fields = line.split()
            if header is not None or len(fields) != 4 or fields[:2] != ["p", "cnf"]:
                raise ValueError(f"Invalid DIMACS header at {line_number}")
            header = tuple(map(int, fields[2:]))
            continue
        if header is None:
            raise ValueError("DIMACS clauses precede header")
        for token in line.split():
            literal = int(token)
            if literal:
                if abs(literal) > header[0]:
                    raise ValueError("DIMACS literal exceeds declared variable count")
                clause.append(literal)
            else:
                clauses.append(clause)
                clause = []
    if header is None or clause or len(clauses) != header[1]:
        raise ValueError("DIMACS clause count/termination mismatch")
    return header[0], clauses


def accessible(table: tuple[tuple[int, int], ...]) -> bool:
    reached = {0}
    pending = [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return len(reached) == len(table)


def endpoint(table: tuple[tuple[int, int], ...], mask: int, word: str) -> int:
    state = 0
    for character in word:
        state = table[state][int(character) ^ ((mask >> state) & 1)]
    return state


def universal(table: tuple[tuple[int, int], ...], pair: list[str]) -> bool:
    return all(endpoint(table, mask, pair[0]) == endpoint(table, mask, pair[1]) for mask in range(1 << len(table)))


def check_cover(m: int, threshold: int, pairs: list[list[str]]) -> dict:
    if type(m) is not int or not 1 <= m <= 3:
        raise ValueError("Independent ordered-table audit supports m=1..3")
    if type(threshold) is not int or threshold < 1:
        raise ValueError("Positive threshold required")
    for pair in pairs:
        if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                or any(not isinstance(word, str) or set(word) - {"0", "1"} for word in pair)
                or not 1 <= len(pair[0]) == len(pair[1]) <= threshold):
            raise ValueError("Invalid learned word pair")
    if not pairs:
        raise ValueError("Empty pair collection cannot cover any valid graph")
    counts = [0] * len(pairs)
    covered = 0
    for transitions in itertools.product(range(m), repeat=2 * m):
        table = tuple(zip(transitions[::2], transitions[1::2]))
        if not accessible(table):
            continue
        matches = [index for index, pair in enumerate(pairs) if universal(table, pair)]
        if not matches:
            raise AssertionError(f"Learned pairs do not cover accessible graph {table}")
        for index in matches:
            counts[index] += 1
        covered += 1
    expected = {1: 1, 2: 12, 3: 432}
    assert covered == expected[m], (m, covered, expected[m])
    return {"m": m, "global_upper_bound": threshold, "ordered_labeled_accessible_graphs": covered,
            "learned_pairs": len(pairs), "graphs_covered_by_each_pair": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cnf", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True, help="JSON object with m/states, threshold, learned_pairs")
    parser.add_argument("--proplimit", type=int, default=100000000, help="PicoSAT propagation limit; UNKNOWN is a failed check")
    arguments = parser.parse_args()
    variables, clauses = read_dimacs(arguments.cnf)
    try:
        import pycosat
    except ImportError as error:
        raise RuntimeError("Install optional independent checker with uv run --with pycosat python ...") from error
    answer = pycosat.solve(clauses, vars=variables, prop_limit=arguments.proplimit)
    if answer != "UNSAT":
        raise AssertionError(f"Independent PicoSAT result is {answer}, not UNSAT")
    evidence = json.loads(arguments.pairs.read_text(encoding="utf-8-sig"))
    report = check_cover(evidence.get("m", evidence.get("states")), evidence["threshold"], evidence["learned_pairs"])
    report.update({"cnf_variables": variables, "cnf_clauses": len(clauses), "independent_solver": "PicoSAT via pycosat " + pycosat.__version__,
                   "cnf_result": "UNSAT", "finite_graph_cover_verified": True, "drat_trace_checked": False})
    print(json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    main()
