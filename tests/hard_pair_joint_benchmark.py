#!/usr/bin/env python3
"""Reproducible heterogeneous-DFA and Family1-closure calibration.

Normal runs consume saved fixture tables and use no random generator. Only
--regenerate-fixtures invokes random.Random, and stores every resulting table
and its seed. Neither reference answers nor witness strings enter the native
finder. All misses, caps and gaps survive in records.jsonl and summary.json.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
import tempfile
import time


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = REPO / "tests/data/hard_pair_joint_fixtures.json"
SEED = 0x20261026


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dfa_key(dfa):
    return dfa["root"], tuple(map(tuple, dfa["table"]))


def distinct_family(dfas):
    return [{"root": root, "table": [list(row) for row in table]}
            for root, table in sorted({dfa_key(dfa) for dfa in dfas})]


def closure(bases):
    """All fixed per-state port swaps, with exact rooted table deduplication."""
    members = []
    for base in bases:
        for bits in product((0, 1), repeat=len(base["table"])):
            members.append({"root": base["root"], "table":
                            [row[:: -1 if bit else 1] for row, bit in zip(base["table"], bits)]})
    return distinct_family(members)


def validate_dfa(dfa):
    n = len(dfa["table"])
    assert n and type(dfa["root"]) is int and 0 <= dfa["root"] < n, dfa
    assert all(len(row) == 2 and all(type(t) is int and 0 <= t < n for t in row)
               for row in dfa["table"]), dfa


def validate_case(case):
    for dfa in case["bases"] + case["family"]:
        validate_dfa(dfa)
    assert case["family"] == distinct_family(case["family"]), case["id"]
    assert case["family_size"] == len(case["family"]), case["id"]
    if case["kind"] in ("family1-closure", "union-family1-closures", "certified-family1", "heldout-family1"):
        assert case["family"] == closure(case["bases"]), case["id"]
        # Verify actual closure under each local generator independently of the
        # all-mask construction. Coincident ports are allowed and deduplicated.
        members = {dfa_key(dfa) for dfa in case["family"]}
        for dfa in case["family"]:
            for state in range(len(dfa["table"])):
                table = [row[:] for row in dfa["table"]]
                table[state].reverse()
                assert (dfa["root"], tuple(map(tuple, table))) in members, case["id"]


def make_case(name, kind, bases, **metadata):
    family = closure(bases) if kind in ("family1-closure", "union-family1-closures") else distinct_family(bases)
    case = {"id": name, "kind": kind, "bases": bases, "family": family,
            "family_size": len(family), **metadata}
    if "closure" in kind:
        case["closure"] = {"complete": True, "static_per_state_swaps": True,
                           "masks_before_dedup": sum(1 << len(dfa["table"]) for dfa in bases),
                           "equivalence": "exact-root-and-transition-table", "generator_closure_verified": True}
    validate_case(case)
    return case


def generate_fixtures(path):
    import random  # Fixture generation only. Not imported in a normal run.
    rng = random.Random(SEED)
    specs = [
        ("common-prefix-essential", "arbitrary-family", [{"root": 0, "table": [[1, 2], [1, 1], [2, 2]]}],
         {"expected_H": 2, "expected_shortest_common_prefix_positive": True}),
        ("common-prefix-essential-closure", "family1-closure", [{"root": 0, "table": [[1, 2], [1, 1], [2, 2]]}],
         {"expected_H": 2, "expected_shortest_common_prefix_positive": True}),
        ("unary-coincident-ports", "arbitrary-family", [{"root": 1, "table": [[1, 1], [2, 2], [0, 0]]}],
         {"expected_H": 1}),
        ("permutation-cycle", "arbitrary-family", [{"root": 2, "table": [[1, 2], [2, 0], [0, 1]]}],
         {"expected_H": 2}),
        ("permutation-only-heterogeneous", "arbitrary-family", [
            {"root": 1, "table": [[1, 0], [0, 1]]},
            {"root": 2, "table": [[1, 2], [2, 0], [0, 1]]}], {"expected_H": 2}),
        ("agreement-can-be-lost", "family1-closure", [{"root": 0, "table": [[0, 1], [0, 1]]}],
         {"expected_H": 3}),
        ("coincident-mask-dedup", "union-family1-closures", [
            {"root": 1, "table": [[0, 0], [0, 2], [1, 1]]},
            {"root": 1, "table": [[0, 0], [2, 0], [1, 1]]}], {}),
    ]
    cases = [make_case(name, kind, bases, generation="hand-constructed", **extra)
             for name, kind, bases, extra in specs]
    for i in range(12):
        bases = []
        for j in range(2 + i % 2):
            # Deterministically fixed sizes force heterogeneous families.
            n = 2 + (i + j) % 4
            bases.append({"root": rng.randrange(n),
                          "table": [[rng.randrange(n), rng.randrange(n)] for _ in range(n)]})
        cases.append(make_case(f"generated-arbitrary-{i:02d}", "arbitrary-family", bases,
                               generation="pseudo-random-fixture-only", generation_index=i))
        cases.append(make_case(f"generated-closure-union-{i:02d}", "union-family1-closures", bases,
                               generation="pseudo-random-fixture-only", generation_index=i))
    value = {"schema": 1, "generation": {"seed": SEED, "generator": "Python random.Random MT19937",
             "randomness_used_for": "fixture tables only; searches are deterministic",
             "complete_tables_saved": True}, "cases": cases}
    dump(path, value)
    return value


def certified_cases():
    cases = []
    source = REPO / "results/family1-atlas-current/champions.jsonl"
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        row = json.loads(line)
        if row["m"] > 7:
            continue
        base = {"root": 0, "table": row["canonical_table"]}
        # The witness and answer are intentionally not part of the native input.
        case = make_case(f"family1-m{row['m']}-{row['key']}", "family1-closure", [base],
                         m=row["m"], key=row["key"], reference_H=row["merge_length"],
                         reference_source={"path": str(source.relative_to(REPO)), "sha256": digest(source),
                                           "certificate": row["source_certificate"]})
        case["kind"] = "certified-family1"
        cases.append(case)
    assert Counter(case["m"] for case in cases) == {1: 1, 2: 1, 3: 2, 4: 1, 5: 5, 6: 2, 7: 8}
    return cases


def heldout_cases():
    # This is a held-out upper certificate, not a known shortest answer.
    key = "01020003040501060003020705060407"
    table = [[int(key[4 * i:4 * i + 2]), int(key[4 * i + 2:4 * i + 4])] for i in range(8)]
    case = make_case(f"heldout-m8-{key}", "family1-closure", [{"root": 0, "table": table}],
                     m=8, key=key, reference_upper=50,
                     reference_upper_source="results/family1-m8-joint-audit-20261026/README.md")
    case["kind"] = "heldout-family1"
    return [case]


def endpoint(dfa, word):
    at = dfa["root"]
    for bit in word:
        at = dfa["table"][at][int(bit)]
    return at


def verify_pair(case, pair):
    assert pair[0] != pair[1] and len(pair[0]) == len(pair[1])
    assert all(set(word) <= {"0", "1"} for word in pair)
    assert all(endpoint(dfa, pair[0]) == endpoint(dfa, pair[1]) for dfa in case["family"])
    return [sum(endpoint(dfa, pair[0][:i]) != endpoint(dfa, pair[1][:i])
                for dfa in case["family"]) for i in range(len(pair[0]) + 1)]


def native_input(case):
    lines = [str(len(case["family"]))]
    for dfa in case["family"]:
        lines.append(f"{len(dfa['table'])} {dfa['root']}")
        lines.extend(f"{a} {b}" for a, b in dfa["table"])
    return "\n".join(lines) + "\n"


def summarize(rows):
    groups = []
    for kind, k in sorted({(r["kind"], r["k"]) for r in rows}):
        chosen = [r for r in rows if (r["kind"], r["k"]) == (kind, k)]
        comparable = [r for r in chosen if r["reference_H"] is not None]
        successes = [r for r in comparable if r["upper_bound"] is not None]
        groups.append({"kind": kind, "k": k, "cases": len(chosen),
                       "found": sum(r["upper_bound"] is not None for r in chosen),
                       "reference_H_known": len(comparable), "comparable_found": len(successes),
                       "exact_hits": sum(r["gap"] == 0 for r in successes),
                       "max_observed_gap": max((r["gap"] for r in successes), default=None),
                       "max_observed_ratio": max((r["ratio"] for r in successes), default=None),
                       "miss_ids": [r["id"] for r in chosen if r["upper_bound"] is None],
                       "expansion_capped": sum(r["expansion_limit_reached"] for r in chosen),
                       "seconds": sum(r["seconds"] for r in chosen),
                       "expanded_nodes": sum(r["expanded_nodes"] for r in chosen)})
    return {"schema": 1, "deterministic_search": True, "alphabet": ["00", "01", "10", "11"],
            "global_near_shortest_error_bound_claimed": False, "records": len(rows), "groups": groups}


def run(args):
    fixtures = json.loads(args.fixtures.read_text())
    cases = fixtures["cases"] + ([] if args.no_certified else certified_cases())
    if args.include_m8:
        cases += heldout_cases()
    if args.case:
        cases = [case for case in cases if any(text in case["id"] for text in args.case)]
    assert cases
    for case in cases:
        validate_case(case)
    args.out.mkdir(parents=True, exist_ok=False)
    dump(args.out / "fixtures.json", {**fixtures, "cases": cases})
    config = {"k": args.k, "beam": args.beam, "diagonal_beam": args.diagonal,
              "unequal_beam": args.unequal, "max_length": args.max_length,
              "ranking": "permutation-D,total-D,lex" if args.prioritize_permutation else "total-D,lex",
              "startup_common_depth": args.startup_common_depth,
              "coordinate_weight_policy": "one-per-distinct-rooted-DFA-table",
              "expansion_cap": args.expansions, "oracle_cap": args.oracle_cap,
              "oracle_depth": args.oracle_depth, "search_randomness": False,
              "fixtures_sha256": digest(args.out / "fixtures.json"),
              "executable": str(args.exe.resolve()), "executable_sha256": digest(args.exe),
              "source_sha256": {str(path.relative_to(REPO)): digest(path) for path in
                                (REPO / "HardPairJointFinder.h", Path(__file__),
                                 REPO / "tests/HardPairJointBenchmark.cpp")}}
    if args.source_snapshot:
        config["compiled_source_snapshot"] = str(args.source_snapshot)
        config["compiled_source_sha256"] = {name: digest(args.source_snapshot / name)
                                             for name in ("HardPairJointFinder.h", "HardPairJointBenchmark.cpp")}
    dump(args.out / "run.json", config)
    rows = []
    with tempfile.TemporaryDirectory(prefix="hard-pair-joint-benchmark-") as work:
        target = Path(work) / "family.txt"
        with (args.out / "records.jsonl").open("w", encoding="utf-8") as stream:
            for case in cases:
                target.write_text(native_input(case))
                command = [str(args.exe.resolve()), "--input", str(target), "--k", args.k,
                           "--beam", str(args.beam), "--diagonal", str(args.diagonal),
                           "--unequal", str(args.unequal), "--max-length", str(args.max_length),
                           "--expansions", str(args.expansions), "--oracle-depth", str(args.oracle_depth),
                           "--oracle-cap", str(args.oracle_cap)]
                if args.startup_common_depth is not None:
                    command += ["--startup-common-depth", str(args.startup_common_depth)]
                command += ["--prioritize-permutation", str(int(args.prioritize_permutation))]
                completed = subprocess.run(command, text=True, capture_output=True, timeout=args.timeout)
                assert completed.returncode == 0, (case["id"], completed.stdout, completed.stderr)
                for line in completed.stdout.splitlines():
                    row = json.loads(line)
                    assert row["k"] in list(map(int, args.k.split(",")))
                    assert row["family_size"] == len(case["family"])
                    expected_permutations = sum(all(sorted(ports[bit] for ports in dfa["table"])
                                                    == list(range(len(dfa["table"]))) for bit in (0, 1))
                                                for dfa in case["family"])
                    assert row["permutation_coordinate_count"] == expected_permutations
                    oracle = row["oracle"]
                    if oracle["witness"] is not None:
                        verify_pair(case, oracle["witness"])
                    if "expected_H" in case:
                        assert oracle["H"] == case["expected_H"], (case["id"], oracle)
                    if case.get("expected_shortest_common_prefix_positive"):
                        assert oracle["witness"][0][0] == oracle["witness"][1][0], case["id"]
                    if oracle["exact"] and case.get("reference_H") is not None:
                        assert oracle["H"] == case["reference_H"], (case["id"], oracle)
                    reference_H = case.get("reference_H", oracle["H"])
                    row.update({"id": case["id"], "kind": case["kind"],
                                "alphabet": ["00", "01", "10", "11"], "search_randomness": False,
                                "fixture_reference": {"path": "fixtures.json", "case_id": case["id"]},
                                "reference_H": reference_H,
                                "reference_source": case.get("reference_source", "independent-scalar-oracle")})
                    upper = row["upper_bound"]
                    row["gap"] = upper - reference_H if upper is not None and reference_H is not None else None
                    row["ratio"] = upper / reference_H if upper is not None and reference_H is not None else None
                    row["verified_d_trace"] = verify_pair(case, row["witness"]) if upper is not None else None
                    for attempt in row["attempts"]:
                        if attempt["witness"] is not None:
                            attempt["verified_d_trace"] = verify_pair(case, attempt["witness"])
                        expected_greedy = attempt["first_difference_depth"] + row["k"]
                        if attempt["first_greedy_depth"] and args.startup_common_depth is not None:
                            assert attempt["first_greedy_depth"] == min(expected_greedy, row["max_length"])
                        prefix, orientation = attempt["common_prefix"], attempt["orientation"]
                        initial = (prefix + orientation[0], prefix + orientation[1]) if orientation else ("", "")
                        assert attempt["initial_D"] == sum(endpoint(dfa, initial[0]) != endpoint(dfa, initial[1])
                                                           for dfa in case["family"])
                    if args.startup_common_depth is not None:
                        expected_starts = {("".join(word), orientation)
                                           for depth in range(args.startup_common_depth + 1)
                                           for word in product("01", repeat=depth) for orientation in ("01", "10")}
                        actual_starts = [(a["common_prefix"], a["orientation"]) for a in row["attempts"]]
                        assert set(actual_starts) == expected_starts and len(actual_starts) == len(expected_starts)
                    if case.get("reference_upper") is not None:
                        row["reference_upper"] = case["reference_upper"]
                        row["reference_upper_source"] = case["reference_upper_source"]
                        row["gap_to_known_upper"] = upper - case["reference_upper"] if upper is not None else None
                    if reference_H is not None and upper is not None:
                        assert upper >= reference_H
                    rows.append(row)
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                    stream.flush()
                print(f"{case['id']}: " + ", ".join(
                    f"k={r['k']} L={r['upper_bound']} H={r['reference_H']} gap={r['gap']}"
                    for r in rows if r["id"] == case["id"]), flush=True)
    summary = summarize(rows)
    dump(args.out / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--self-test", action="store_true",
                        help="run fast native fixture checks in an automatically removed temporary directory")
    parser.add_argument("--source-snapshot", type=Path)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--regenerate-fixtures", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-certified", action="store_true")
    parser.add_argument("--include-m8", action="store_true")
    parser.add_argument("--case", action="append")
    parser.add_argument("--k", default="2,4,6")
    parser.add_argument("--beam", type=int, default=1)
    parser.add_argument("--diagonal", type=int, default=1)
    parser.add_argument("--unequal", type=int, default=0)
    parser.add_argument("--startup-common-depth", type=int)
    parser.add_argument("--prioritize-permutation", action="store_true")
    parser.add_argument("--max-length", type=int, default=48)
    parser.add_argument("--expansions", type=int, default=500000)
    parser.add_argument("--oracle-depth", type=int, default=40)
    parser.add_argument("--oracle-cap", type=int, default=150000)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if args.regenerate_fixtures:
        generate_fixtures(args.fixtures)
    if args.self_test:
        assert args.exe is not None, "--exe is required with --self-test"
        args.no_certified, args.include_m8 = True, False
        args.k, args.max_length, args.expansions = "2,4", 16, 100000
        with tempfile.TemporaryDirectory(prefix="hard-pair-joint-self-test-") as work:
            args.out = Path(work) / "root"
            rows = run(args)
            assert len(rows) == 62
            args.startup_common_depth, args.k = 2, "2"
            args.out = Path(work) / "startup-c2"
            rows = run(args)
            assert len(rows) == 31 and all(len(row["attempts"]) == 14 for row in rows)
            assert all(row["upper_bound"] == 2 for row in rows if row["id"].startswith("common-prefix-essential"))
            args.startup_common_depth, args.case = 0, ["common-prefix-essential"]
            args.out = Path(work) / "startup-c0"
            rows = run(args)
            assert len(rows) == 2 and all(row["upper_bound"] is None for row in rows)
        print("passed scalar full-family smoke checks at joint k=2,4; startup checks at joint k=2")
        return
    if args.exe:
        assert args.out is not None, "--out is required with --exe"
        run(args)
    else:
        fixtures = json.loads(args.fixtures.read_text())
        for case in fixtures["cases"]:
            validate_case(case)
        print(f"validated {len(fixtures['cases'])} complete fixture families; k=N/A (no search)")


if __name__ == "__main__":
    main()
