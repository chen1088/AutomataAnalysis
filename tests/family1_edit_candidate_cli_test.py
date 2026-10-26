#!/usr/bin/env python3
"""Independent complete tiny-neighborhood and edit-certificate CLI checks."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from family1_edit_distance import neighbors
from family1_study import canonical_table, fixed_key

EXECUTABLE = REPO / "out/build/msvc-vcpkg/Release/Family1Edit.exe"


def accessible(table):
    m = len(table)
    assert m and all(len(row) == 2 and all(type(x) is int and 0 <= x < m for x in row) for row in table)
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target); pending.append(target)
    return len(reached) == m


def factorial_canonical(table):
    m = len(table)
    best = None
    for tail in itertools.permutations(range(1, m)):
        mapping = (0,) + tail
        rows = [None] * m
        for source, row in enumerate(table):
            rows[mapping[source]] = tuple(sorted(mapping[target] for target in row))
        candidate = tuple(rows)
        if best is None or candidate < best:
            best = candidate
    return best


def all_roots(table):
    result = set()
    for root in range(len(table)):
        order = [root] + [s for s in range(len(table)) if s != root]
        mapping = {old: new for new, old in enumerate(order)}
        raw = tuple(tuple(mapping[t] for t in table[s]) for s in order)
        if accessible(raw):
            result.add(fixed_key(factorial_canonical(raw)))
    return result


def verify_step(step, factorial=True):
    before = tuple(map(tuple, step["before_table"]))
    after = tuple(map(tuple, step["after_table"]))
    expected = tuple(map(tuple, step["raw_after_edit"]))
    assert accessible(before) and accessible(after) and accessible(expected)
    assert fixed_key(before) == step["before_key"] and fixed_key(after) == step["after_key"]
    canonical = factorial_canonical if factorial else canonical_table
    assert canonical(before) == before and canonical(after) == after
    operation = step["operation"]
    raw = list(map(list, before))
    kind = operation["kind"]
    edges = operation["edges"]
    assert len({(e["source"], e["port"]) for e in edges}) == len(edges)
    for edge in edges:
        assert before[edge["source"]][edge["port"]] == edge["target"]
    if kind == "retarget":
        assert len(edges) == 1
        edge = edges[0]
        assert edge["target"] != operation["new_target"]
        raw[edge["source"]][edge["port"]] = operation["new_target"]
    elif kind in {"insert-two-edges", "insert-loop"}:
        vertex = len(before)
        assert operation["vertex"] == vertex
        assert len(edges) == (2 if kind == "insert-two-edges" else 1)
        targets = [edge["target"] for edge in edges]
        expected_outgoing = targets if kind == "insert-two-edges" else targets + [vertex]
        assert sorted(operation["outgoing"]) == sorted(expected_outgoing)
        for edge in edges:
            raw[edge["source"]][edge["port"]] = vertex
        raw.append(operation["outgoing"])
        indegrees = [sum(target == state for row in raw for target in row) for state in range(vertex+1)]
        old_degrees = [sum(target == state for row in before for target in row) for state in range(vertex)]
        assert indegrees[:-1] == old_degrees and indegrees[-1] == 2
    elif kind in {"smooth-two-edges", "smooth-loop"}:
        vertex = operation["vertex"]
        assert 0 < vertex < len(before)
        incoming = {(s, p) for s, row in enumerate(before) if s != vertex for p, t in enumerate(row) if t == vertex}
        outgoing = {p for p, t in enumerate(before[vertex]) if t != vertex}
        assert {(e["source"], e["port"]) for e in edges} == incoming
        assert set(operation["outgoing_ports"]) == outgoing
        assert len(edges) == len(outgoing) == (2 if kind == "smooth-two-edges" else 1)
        assert tuple(operation["outgoing"]) == before[vertex]
        for edge, port in zip(edges, operation["outgoing_ports"]):
            raw[edge["source"]][edge["port"]] = before[vertex][port]
        retained = [s for s in range(len(before)) if s != vertex]
        mapping = {old: new for new, old in enumerate(retained)}
        raw = [[mapping[t] for t in raw[s]] for s in retained]
    else:
        raise AssertionError("Unknown edit kind")
    assert tuple(map(tuple, raw)) == expected
    assert canonical(expected) == after


def verify_path(path, factorial=True):
    current = tuple(map(tuple, path["source_table"]))
    assert accessible(current) and fixed_key(current) == path["parent_key"]
    assert len(path["steps"]) == path["distance_upper_bound"]
    for step in path["steps"]:
        assert current == tuple(map(tuple, step["before_table"]))
        verify_step(step, factorial)
        current = tuple(map(tuple, step["after_table"]))
    assert current == tuple(map(tuple, path["endpoint_table"]))
    assert fixed_key(current) == path["endpoint_key"]


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class NativeEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="family1-edit-independent-")
        cls.directory = Path(cls.temporary.name)
        cls.counter = 0
        cls.tiny = {}
        for m in range(1, 4):
            for values in itertools.product(range(m), repeat=2*m):
                table = tuple(zip(values[::2], values[1::2]))
                if accessible(table):
                    canonical = factorial_canonical(table)
                    cls.tiny[fixed_key(canonical)] = canonical
        assert len(cls.tiny) == 64

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_native(self, table, target, radius=1, closure=False, paths=100000, candidates=100000, seed=1088):
        type(self).counter += 1
        directory = self.directory / str(self.counter)
        command = [str(EXECUTABLE), "--graph", fixed_key(table), "--target-m", str(target),
                   "--radius", str(radius), "--max-paths", str(paths), "--max-candidates", str(candidates),
                   "--seed", str(seed), "--out", str(directory)]
        if closure:
            command += ["--root-closure"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        for name, suffix in [("run", ".json"), ("summary", ".json"), ("candidates", ".jsonl"), ("paths", ".jsonl")]:
            data = (directory / (name+suffix)).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), (directory / (name+".sha256")).read_text().strip())
        return directory, command, json.loads((directory / "summary.json").read_text()), rows(directory / "candidates.jsonl"), rows(directory / "paths.jsonl")

    def test_complete_all_tiny_unit_neighborhoods(self):
        for source_key, table in sorted(self.tiny.items()):
            reference = neighbors(table)
            for target in range(max(1, len(table)-1), len(table)+2):
                with self.subTest(source=source_key, target=target):
                    _, _, summary, candidates, paths = self.run_native(table, target)
                    expected = {key for key, edge in reference.items() if len(edge["after"]) == target}
                    if target == len(table):
                        expected.add(source_key)  # Radius balls include distance zero.
                    self.assertEqual({r["key"] for r in candidates}, expected)
                    self.assertEqual(len(candidates), len(expected))
                    self.assertTrue(summary["enumeration_complete"])
                    for path in paths:
                        verify_path(path)
                    for candidate in candidates:
                        self.assertEqual(factorial_canonical(candidate["canonical_table"]), tuple(map(tuple, candidate["canonical_table"])))
                        self.assertIsNotNone(candidate["rooted_edit_distance_upper_bound"])
                        self.assertLessEqual(candidate["rooted_edit_distance_upper_bound"], 1)

    def test_accessible_root_closure_and_root_distance_labels(self):
        for table in [((0, 0),), ((1, 1), (1, 1)), ((0, 1), (2, 2), (0, 1))]:
            reference = neighbors(table)
            target = len(table)+1
            expected = set()
            for edge in reference.values():
                if len(edge["after"]) == target:
                    expected.update(all_roots(edge["after"]))
            _, _, summary, candidates, paths = self.run_native(table, target, closure=True)
            self.assertEqual({r["key"] for r in candidates}, expected)
            self.assertTrue(summary["enumeration_complete"])
            direct = {p["endpoint_key"] for p in paths if len(p["endpoint_table"]) == target}
            path_by_id = {p["path_id"]: p for p in paths}
            for candidate in candidates:
                self.assertTrue(candidate["shape_roots_complete"])
                self.assertEqual(candidate["rooted_edit_distance_upper_bound"] is not None, candidate["key"] in direct)
                for origin in candidate["root_metadata"]:
                    endpoint = path_by_id[origin["path_id"]]["endpoint_table"]
                    self.assertIn(candidate["key"], all_roots(endpoint))
                    if origin["root_fixed_path"]:
                        self.assertEqual(origin["endpoint_key"], candidate["key"])

    def test_caps_determinism_resume_and_integrity(self):
        table = ((0, 1), (2, 2), (0, 1))
        directory, command, summary, candidates, paths = self.run_native(table, 4, radius=3, paths=12, candidates=3, closure=True)
        self.assertFalse(summary["enumeration_complete"])
        self.assertTrue(summary["path_capped"] or summary["candidate_capped"])
        for path in paths:
            verify_path(path)
        before = {name: (directory/name).read_bytes() for name in ["run.json", "summary.json", "candidates.jsonl", "paths.jsonl"]}
        resumed = subprocess.run(command+["--resume"], capture_output=True, text=True)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(before, {name: (directory/name).read_bytes() for name in before})
        changed = command[:]
        changed[changed.index("--seed")+1] = "2027"
        self.assertNotEqual(subprocess.run(changed+["--resume"], capture_output=True).returncode, 0)
        (directory/"candidates.jsonl").write_bytes(before["candidates.jsonl"]+b" ")
        self.assertNotEqual(subprocess.run(command+["--resume"], capture_output=True).returncode, 0)

    def test_size20_representation_cap_is_not_global_exclusion(self):
        table = tuple((state+1, state+1) for state in range(18)) + ((18, 18),)
        _, _, summary, _, paths = self.run_native(table, 20, radius=3, paths=2, candidates=2)
        self.assertTrue(summary["representation_capped"])
        self.assertEqual(summary["intermediate_size_cap"], 20)
        self.assertFalse(summary["enumeration_complete"])
        for path in paths:
            verify_path(path, factorial=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--exe", type=Path)
    args, remaining = parser.parse_known_args()
    if args.exe:
        EXECUTABLE = args.exe.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
