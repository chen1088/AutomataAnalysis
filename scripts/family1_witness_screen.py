#!/usr/bin/env python3
"""Transfer supplied word-pair upper witnesses to candidate Family 1 graphs.

Every source pair is checked on its source graph first. A no-hit candidate is
unresolved: this finite witness catalogue cannot provide a hardness bound.
The simulator is independent of the native graph/search implementation.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
from itertools import product
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                yield number, json.loads(line)


def reference(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return {"path": str(path.resolve()), "sha256": digest.hexdigest()}


def graph(row):
    table = row.get("canonical_table")
    require(isinstance(table, list) and 1 <= len(table) <= 20,
            "canonical_table must contain 1..20 rows")
    m = len(table)
    require(row.get("m", m) == m, "m/table mismatch")
    for ports in table:
        require(isinstance(ports, list) and len(ports) == 2
                and all(type(v) is int and 0 <= v < m for v in ports),
                "invalid transition row")
    key = "".join(f"{v:02d}" for ports in table for v in ports)
    require(row.get("key") == key, "key/table mismatch")
    reached, pending = {0}, [0]
    while pending:
        for target in table[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    require(len(reached) == m, "candidate must be accessible from root 0")
    return table, key


@lru_cache(maxsize=20)
def mask_selectors(m):
    count = 1 << m
    all_masks = (1 << count) - 1
    selectors = []
    for vertex in range(m):
        block = (1 << (1 << vertex)) - 1
        value = 0
        for start in range(1 << vertex, count, 2 << vertex):
            value |= block << start
        selectors.append(value)
    return all_masks, tuple(selectors)


def advance(table, selectors, profile, symbol):
    following = [0] * len(table)
    for state, bits in enumerate(profile):
        if not bits:
            continue
        high = bits & selectors[state]
        low = bits ^ high
        a, b = table[state]
        if symbol:
            following[a] |= high
            following[b] |= low
        else:
            following[a] |= low
            following[b] |= high
    return tuple(following)


def scalar(table, mask, word):
    state = 0
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def verify_pair(table, pair):
    all_masks, selectors = mask_selectors(len(table))
    profiles = []
    for word in pair:
        profile = (all_masks,) + (0,) * (len(table) - 1)
        for symbol in word:
            profile = advance(table, selectors, profile, int(symbol))
        profiles.append(profile)
    return profiles[0] == profiles[1]


def build_trials(pairs):
    """Build one shared word-prefix trie in the supplied canonical pair order."""
    nodes, edges = [(-1, 0)], {}

    def node_for(word):
        at = 0
        for symbol in word:
            edge = at, int(symbol)
            if edge not in edges:
                edges[edge] = len(nodes)
                nodes.append(edge)
            at = edges[edge]
        return at

    return nodes, [(pair, node_for(pair[0]), node_for(pair[1])) for pair in pairs]


def first_matching_pair(table, nodes, trials, prefilter_limit, statistics):
    """Reject only concrete scalar mismatches; completely verify every survivor.

    The prefilter examines masks 0..N-1 in order. It cannot discard a universal
    pair: one mismatching scalar endpoint is already a counterexample. Passing
    this filter alone never accepts a pair or provides a graph hardness bound.
    Scalar and full-family prefix caches are local to this candidate graph.
    """
    m = len(table)
    all_masks, selectors = mask_selectors(m)
    full_cache = [None] * len(nodes)
    full_cache[0] = (all_masks,) + (0,) * (m - 1)
    scalar_caches = {}

    def full_endpoint(at):
        missing = []
        while full_cache[at] is None:
            missing.append(at)
            at = nodes[at][0]
        for child in reversed(missing):
            parent, symbol = nodes[child]
            full_cache[child] = advance(table, selectors, full_cache[parent], symbol)
            statistics["bitset_word_transitions"] += 1
        return full_cache[missing[0]] if missing else full_cache[at]

    def scalar_endpoint(at, mask):
        cache = scalar_caches.get(mask)
        if cache is None:
            cache = [-1] * len(nodes)
            cache[0] = 0
            scalar_caches[mask] = cache
        missing = []
        while cache[at] < 0:
            missing.append(at)
            at = nodes[at][0]
        state = cache[at]
        for child in reversed(missing):
            _, symbol = nodes[child]
            state = table[state][symbol ^ ((mask >> state) & 1)]
            cache[child] = state
            statistics["prefilter_scalar_word_transitions"] += 1
        return state

    for pair, first, second in trials:
        statistics["candidate_pair_trials"] += 1
        mismatch = False
        for mask in range(min(prefilter_limit, 1 << m)):
            statistics["prefilter_scalar_mask_checks"] += 1
            if scalar_endpoint(first, mask) != scalar_endpoint(second, mask):
                statistics["prefilter_rejected_pair_trials"] += 1
                mismatch = True
                break
        if mismatch:
            continue
        statistics["candidate_bitset_mask_checks"] += 1 << m
        if full_endpoint(first) == full_endpoint(second):
            return pair
    return None


def self_check():
    """Check repeated static choices, loops and coincident ports against scalar."""
    tables = [[[0, 0]], [[0, 1], [0, 1]],
              [[1, 2], [1, 0], [0, 2]], [[1, 1], [0, 1]]]
    tables += [[[(vertex + offset) % m, (2 * vertex + offset + 1) % m]
                for vertex in range(m)]
               for m in range(1, 9) for offset in range(3)]
    checks = 0
    for table in tables:
        m = len(table)
        all_masks, selectors = mask_selectors(m)
        words = ["".join(word) for depth in range(5)
                 for word in product("01", repeat=depth)]
        words += ["001101001100101101010001", "11111000001111100000"]
        for word in words:
            profile = (all_masks,) + (0,) * (m - 1)
            for symbol in word:
                profile = advance(table, selectors, profile, int(symbol))
            require(sum(bits.bit_count() for bits in profile) == 1 << m,
                    "self-check lost or duplicated a mask")
            for mask in range(1 << m):
                state = scalar(table, mask, word)
                require((profile[state] >> mask) & 1,
                        "static-mask bitset/scalar self-check failed")
                checks += 1
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--witnesses", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=50)
    parser.add_argument("--prefilter-masks", type=int, default=16,
                        help="First N ascending static masks checked by cached scalar simulation before full replay; 0 disables.")
    args = parser.parse_args()
    require(args.max_length > 0, "--max-length must be positive")
    require(0 <= args.prefilter_masks <= 1 << 20, "--prefilter-masks must be in 0..1048576")
    inputs = [args.candidates, *args.witnesses]
    require(all(args.out.resolve() != path.resolve() for path in inputs),
            "output must not overwrite an input")
    summary_path = args.out.with_suffix(".summary.json")
    require(all(summary_path.resolve() != path.resolve() for path in inputs),
            "summary must not overwrite an input")
    scalar_self_checks = self_check()
    catalogue = {}
    source_pairs_checked = source_mask_checks = 0
    for path in args.witnesses:
        source = reference(path)
        for line, row in rows(path):
            if row.get("witness") is None:
                continue
            table, key = graph(row)
            pair = row["witness"]
            require(isinstance(pair, list) and len(pair) == 2
                    and all(isinstance(word, str) and word
                            and not (set(word) - {"0", "1"}) for word in pair)
                    and len(pair[0]) == len(pair[1]) and pair[0] != pair[1],
                    f"invalid witness in {path}:{line}")
            require(row.get("upper_bound", len(pair[0])) == len(pair[0]),
                    "witness length/upper_bound mismatch")
            require(verify_pair(table, pair), f"invalid source pair in {path}:{line}")
            source_pairs_checked += 1
            source_mask_checks += 1 << len(table)
            if len(pair[0]) <= args.max_length:
                canonical_pair = tuple(sorted(pair))
                catalogue.setdefault(canonical_pair, []).append(
                    {"source": source, "line": line, "source_key": key})
    pairs = sorted(catalogue, key=lambda pair: (len(pair[0]), pair))
    nodes, trials = build_trials(pairs)
    output = []
    seen = set()
    statistics = dict.fromkeys(("candidate_pair_trials", "candidate_bitset_mask_checks",
                               "bitset_word_transitions", "prefilter_scalar_mask_checks",
                               "prefilter_rejected_pair_trials", "prefilter_scalar_word_transitions"), 0)
    scalar_positive_checks = 0
    for _, candidate in rows(args.candidates):
        table, key = graph(candidate)
        require(key not in seen, f"duplicate candidate key: {key}")
        seen.add(key)
        m = len(table)
        found = first_matching_pair(table, nodes, trials, args.prefilter_masks, statistics)
        if found is not None:
            for mask in range(1 << m):
                require(scalar(table, mask, found[0]) == scalar(table, mask, found[1]),
                        f"positive scalar replay failed for {key}")
                scalar_positive_checks += 1
        output.append({"key": key, "m": m, "canonical_table": table,
                       "lower_bound": 1, "upper_bound": len(found[0]) if found else None,
                       "merge_length": None, "witness": list(found) if found else None,
                       "status": "verified-upper" if found else "unresolved",
                       "witness_sources": catalogue[found] if found else [],
                       "verification": {"method": "ascending-mask-scalar-prefilter-and-full-static-mask-bitsets-and-scalar-positive-replay",
                                        "static_masks_verified": (1 << m) if found else 0},
                       "reason": "shortest valid supplied pair" if found else "no supplied pair passed; no hardness inference"})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                 for row in output), encoding="utf-8")
    temporary.replace(args.out)
    summary = {"schema": 1, "method": "independent-witness-transfer",
               "candidates": reference(args.candidates),
               "witness_inputs": [reference(path) for path in args.witnesses],
               "script": reference(Path(__file__)), "output": reference(args.out),
               "max_length": args.max_length, "candidate_count": len(output),
               "verified_upper_count": sum(row["upper_bound"] is not None for row in output),
               "unresolved_count": sum(row["upper_bound"] is None for row in output),
               "source_pairs_checked": source_pairs_checked,
               "source_mask_checks": source_mask_checks,
               "distinct_retained_pairs": len(pairs), **statistics,
               "prefilter_mask_limit": args.prefilter_masks,
               "prefilter_mask_order": "ascending original static mask IDs, starting at zero",
               "prefilter_rule": "reject only on a concrete scalar endpoint mismatch; all survivors receive full-family verification",
               "positive_scalar_mask_checks": scalar_positive_checks,
               "self_check_scalar_mask_checks": scalar_self_checks,
               "global_maximum_claimed": False, "lower_bounds_increased": False}
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["candidate_count", "verified_upper_count", "unresolved_count", "distinct_retained_pairs"]}))


if __name__ == "__main__":
    main()
