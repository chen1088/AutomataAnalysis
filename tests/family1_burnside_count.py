"""Independent exact counts of accessible rooted unordered-port digraphs.

Burnside over root-fixing permutations; no production enumerator is imported.
Every vertex has two outgoing ports and indegree is unrestricted.
"""
import argparse
from collections import Counter
from fractions import Fraction
from functools import cache
from itertools import combinations_with_replacement, permutations, product
import json
from math import comb, factorial, prod
from pathlib import Path


def partitions(n, minimum=1):
    if n == 0:
        yield ()
    for first in range(minimum, n + 1):
        for rest in partitions(n - first, first):
            yield (first,) + rest


def pair_choices(cycles, length):
    fixed = sum(d for d in cycles if length % d == 0)
    fixed_twice = sum(d for d in cycles if (2 * length) % d == 0)
    return fixed * (fixed + 1) // 2 + (fixed_twice - fixed) // 2


@cache
def fixed_accessible(other_cycles):
    """Fixed accessible tables for cycle type (distinguished root 1, *others)."""
    cycles = (1,) + other_cycles
    choices = {d: pair_choices(cycles, d) for d in set(cycles)}
    all_tables = prod(choices[d] for d in cycles)
    counts = Counter(other_cycles)
    lengths = sorted(counts)
    inaccessible = 0
    # The reachable set is permutation-invariant and contains the root.
    # Choose which other whole cycles belong to it; its complement's rows may
    # target ANY vertex and have the original full-permutation choice counts.
    for selected in product(*(range(counts[d] + 1) for d in lengths)):
        if all(b == counts[d] for d, b in zip(lengths, selected)):
            continue
        inside = tuple(d for d, b in zip(lengths, selected) for _ in range(b))
        multiplicity = prod(comb(counts[d], b) for d, b in zip(lengths, selected))
        outside = prod(choices[d] ** (counts[d] - b) for d, b in zip(lengths, selected))
        inaccessible += multiplicity * fixed_accessible(inside) * outside
    return all_tables - inaccessible


def rooted_classes(m):
    total = Fraction(0)
    rows = []
    for cycles in partitions(m - 1):
        z = prod(d ** a * factorial(a) for d, a in Counter(cycles).items())
        fixed = fixed_accessible(cycles)
        total += Fraction(fixed, z)
        rows.append({"nonroot_cycle_lengths": cycles, "centralizer_order": z,
                     "fixed_accessible_tables": fixed})
    assert total.denominator == 1
    return total.numerator, rows


def brute_check():
    # Exhaust all labelled unordered-port tables and all root-fixed vertex
    # permutations through four states, independently checking each fixed set.
    for m in range(1, 5):
        pairs = list(combinations_with_replacement(range(m), 2))
        maps = [(0,) + p for p in permutations(range(1, m))]
        counts = [0] * len(maps)
        for table in product(pairs, repeat=m):
            seen = {0}
            while True:
                after = seen | {v for s in seen for v in table[s]}
                if after == seen:
                    break
                seen = after
            if len(seen) != m:
                continue
            for i, p in enumerate(maps):
                if all(tuple(sorted(p[v] for v in table[s])) == table[p[s]] for s in range(m)):
                    counts[i] += 1
        for p, actual in zip(maps, counts):
            unseen = set(range(1, m))
            cycles = []
            while unseen:
                s = min(unseen)
                length = 0
                while s in unseen:
                    unseen.remove(s)
                    s = p[s]
                    length += 1
                cycles.append(length)
            expected = fixed_accessible(tuple(sorted(cycles)))
            assert actual == expected, (m, p, actual, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-m", type=int, default=7)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--skip-brute", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_m <= 20:
        parser.error("--max-m must be in 1..20")
    if not args.skip_brute:
        brute_check()
    known = [1, 6, 57, 678, 10398, 192181, 4166855]
    sizes = []
    for m in range(1, args.max_m + 1):
        count, terms = rooted_classes(m)
        if m <= len(known):
            assert count == known[m - 1], (m, count)
        sizes.append({"m": m, "rooted_classes": count, "burnside_terms": terms})
        print(f"m={m}: {count} accessible rooted classes")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        report = {"method": "independent-root-fixed-Burnside-reachable-set-recurrence",
                  "indegree_restriction": None, "loops_and_coincident_ports": True,
                  "brute_fixed_set_check_through_m": None if args.skip_brute else 4,
                  "sizes": sizes}
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
