#!/usr/bin/env python3
"""Verify local closed-set certificates without repeating the million-mask scan."""
from collections import Counter, deque
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def endpoint(table, mask, word, root=0):
    state = root
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def local_bfs(table, mask, first, second):
    queue = deque([((first, second), "")])
    seen = {(first, second)}
    while queue:
        (a, b), word = queue.popleft()
        if a == b:
            return word
        for letter in (0, 1):
            pair = (table[a][letter ^ ((mask >> a) & 1)], table[b][letter ^ ((mask >> b) & 1)])
            if pair not in seen:
                seen.add(pair)
                queue.append((pair, word + str(letter)))
    return None


def reference(path):
    path = Path(path)
    return {"path": path.relative_to(REPO).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    folder = REPO / "results/family1-residual-pair-diagnostic"
    source = folder / "literal20-oldpilot.json"
    result = json.loads(source.read_text())
    m, key = result["m"], result["key"]
    values = [int(key[i:i+2]) for i in range(0, len(key), 2)]
    table = list(zip(values[::2], values[1::2]))
    first, second = result["first_word"], result["second_word"]
    assert first != second and len(first) == len(second) == 96
    family_path = REPO / "results/family1-circulant-family/champions.jsonl"
    family = next(json.loads(line) for line in family_path.read_text().splitlines() if json.loads(line)["m"] == 20)["family"]
    mapping, flips = family["raw_to_canonical_labels"], family["canonical_mask_lift_xor_at_raw_source"]
    inverse = [mapping.index(i) for i in range(m)]
    counts, distances = Counter(), Counter()
    masks = set()
    for record in result["residual_coordinates"]:
        mask, a, b = record["mask"], record["first_state"], record["second_state"]
        assert mask not in masks and 0 <= mask < (1 << m)
        masks.add(mask)
        assert endpoint(table, mask, first) == a != b == endpoint(table, mask, second)
        expected = local_bfs(table, mask, a, b)
        assert record["mergeable"] is (expected is not None)
        if expected is not None:
            assert record["shortest_local_distance"] == len(expected)
            suffix = record["shortest_local_suffix"]
            assert len(suffix) == len(expected)
            assert endpoint(table, mask, suffix, a) == endpoint(table, mask, suffix, b)
            distances[len(expected)] += 1
        else:
            closed = {tuple(pair) for pair in record["closed_unmerged_pair_set"]}
            assert tuple(sorted((a, b))) in closed
            assert len(closed) == record["pair_states_seen"]
            assert all(0 <= x < y < m for x, y in closed)
            for x, y in closed:
                for letter in (0, 1):
                    next_pair = tuple(sorted((table[x][letter ^ ((mask >> x) & 1)], table[y][letter ^ ((mask >> y) & 1)])))
                    assert next_pair in closed
        # Undo both relabeling and local port swaps, then verify an independent
        # analytic obstruction for every negative coordinate.
        raw_mask = [((mask >> mapping[s]) & 1) ^ flips[s] for s in range(m)]
        period10 = all(raw_mask[s] == raw_mask[(s + 10) % m] for s in range(m))
        antipodal = (inverse[a] - inverse[b]) % m == 10
        if expected is None:
            assert period10 and antipodal
        counts[(expected is None, period10, antipodal)] += 1
    assert len(masks) == 501
    assert sum(value for (dead, _, _), value in counts.items() if dead) == 496
    assert distances == {1: 1, 4: 2, 10: 2}

    # Only1024 patterns are needed for an additional independent check of the
    # whole period10 obstruction class; this is not the million-mask scan.
    periodic_residual = set()
    for bits in range(1 << 10):
        mask = sum((((bits >> (s % 10)) & 1) ^ flips[s]) << mapping[s] for s in range(m))
        a, b = endpoint(table, mask, first), endpoint(table, mask, second)
        if a != b:
            assert (inverse[a] - inverse[b]) % m == 10
            periodic_residual.add(mask)
    assert periodic_residual == {record["mask"] for record in result["residual_coordinates"] if not record["mergeable"]}
    validation = {"schema": 1, "passed": True, "diagnostic": reference(source),
                  "independent_test": reference(Path(__file__).resolve()),
                  "native_source": reference(REPO / "tests/Family1ResidualPairDiagnostic.cpp"),
                  "native_executable": reference(REPO / "out/family1-residual-pair-diagnostic/Family1ResidualPairDiagnostic.exe"),
                  "source_family": reference(family_path),
                  "residual_coordinates_checked": 501, "closed_negative_certificates_checked": 496,
                  "all_local_BFS_distances_independently_recomputed": True,
                  "distance_histogram": dict(sorted(distances.items())),
                  "all_negative_coordinates_period10_and_antipodal_in_raw_labels": True,
                  "all_1024_period10_masks_independently_checked": True,
                  "native_all_mask_count": result["masks_enumerated"],
                  "python_million_mask_scan_performed": False,
                  "common_suffix_impossible_for_this_pair": True,
                  "maximum_additional_agreement_upper_bound": 5,
                  "global_H_bound_claimed": False}
    queries = REPO / "out/family1-neighbor-full-metric-8-20-v1/query-results.jsonl"
    old = next(json.loads(line) for line in queries.read_text().splitlines() if json.loads(line)["key"] == key)
    old_path = Path(old["native_result"]["path"])
    validation["source_old_native_result"] = reference(old_path)
    assert validation["source_old_native_result"]["sha256"] == old["native_result"]["sha256"]
    old_attempt = old["native_answer"]["guided_attempt"]
    assert [word + old_attempt["suffix"] for word in old_attempt["initial_words"]] == [first, second]
    (folder / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation))


if __name__ == "__main__":
    main()
