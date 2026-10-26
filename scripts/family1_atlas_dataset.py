#!/usr/bin/env python3
"""Assemble the current proof-aware 1..20 drawing dataset, without running a search.

Keep all certified rooted maximizers through seven states. At each larger exact
size, provide an accessible graph with a rigorous projection lower bound. These
larger graphs are examples, not claims about global optimality or all maximizers.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from family1_certified_tikz import rooted_canonical
from family1_study import compact, fixed_key, jsonl, validate_table


REPO = Path(__file__).resolve().parents[1]
MAXIMA = (1, 3, 6, 10, 15, 23, 34)
ROOTED_COUNTS = (1, 1, 2, 1, 5, 2, 8)
SHAPE_COUNTS = (1, 1, 1, 1, 4, 1, 4)
BASE_TABLE = ((0, 1), (2, 3), (2, 3), (4, 5), (0, 6), (4, 6), (1, 5))
BASE_KEY = fixed_key(BASE_TABLE)


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def reference(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": file_hash(path)}


def endpoint(table, mask, word):
    """Ordinary scalar simulation with one fixed mask bit at every vertex."""
    state = 0
    for symbol in word:
        state = table[state][int(symbol) ^ ((mask >> state) & 1)]
    return state


def extension(m):
    if not 8 <= m <= 20:
        raise ValueError("extension requires 8..20 exact reachable states")
    raw = [list(row) for row in BASE_TABLE]
    raw[0] = [7, 1]
    raw.extend([[state + 1, 1] for state in range(7, m - 1)])
    raw.append([0, 1])
    validate_table(raw)
    canonical, old_to_new = rooted_canonical(raw, return_mapping=True)
    raw_projection = list(range(7)) + [0] * (m - 7)
    projection, mask_xor = [None] * m, [None] * m
    for old, row in enumerate(raw):
        new = old_to_new[old]
        mapped_row = tuple(old_to_new[target] for target in row)
        projection[new] = raw_projection[old]
        mask_xor[new] = int(mapped_row != canonical[new])
        if mapped_row[:: -1 if mask_xor[new] else 1] != canonical[new]:
            raise AssertionError("canonicalization is not a local port swap")
    for state, row in enumerate(canonical):
        for port, target in enumerate(row):
            if projection[target] != BASE_TABLE[projection[state]][port ^ mask_xor[state]]:
                raise AssertionError("canonical static-mask projection identity failed")
    return {
        "m": m, "key": fixed_key(canonical),
        "canonical_table": [list(row) for row in canonical],
        "status": "incomplete", "merge_length": None,
        "lower_bound": 34, "upper_bound": None, "witness": None,
        "reason": "constructive-static-mask-projection-bound; score-and-global-maximum-unresolved",
        "construction": {
            "name": "expand-base-root-loop-into-cycle-with-second-ports-to-state-1",
            "base_m": 7, "base_key": BASE_KEY, "base_lower_bound": 34,
            "raw_table": raw,
            "raw_projection_to_base": raw_projection,
            "raw_to_canonical_labels": list(old_to_new),
            "canonical_projection_to_base": projection,
            "canonical_mask_lift_xor": mask_xor,
            "mask_lift_formula": "sigma_new[s] = sigma_base[projection[s]] XOR mask_lift_xor[s]",
            "projection_identity": "projection[tau_new[p][s]] = tau_base[p XOR mask_lift_xor[s]][projection[s]]",
            "all_vertices_accessible": True,
        },
    }


def certified_records(small_path, seven_path):
    records, provenance = [], []
    for path in (Path(small_path), Path(seven_path)):
        summary_path = path.parent / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        source_ref = reference(path)
        summary_ref = reference(summary_path)
        provenance.append({"records": source_ref, "summary": summary_ref})
        for _, raw in jsonl(path):
            m = raw.get("m")
            if type(m) is not int or not 1 <= m <= 7:
                raise ValueError("unexpected size in certified maximizers export")
            cert = summary if summary.get("m") == m else next(
                (item for item in summary.get("sizes", []) if item.get("m") == m), {})
            proved = cert.get("maximum_certified") is True or cert.get("maximum_value_certified") is True
            complete = cert.get("maximizing_collection_complete") is True or (
                cert.get("enumeration_complete") is True and cert.get("scoring_complete") is True
                and cert.get("maximum_certified") is True)
            global_value = next((cert[field] for field in ("global_maximum", "maximum_merge_length", "maximum_value")
                                 if type(cert.get(field)) is int), None)
            if (not proved or not complete or cert.get("maximizer_count") != ROOTED_COUNTS[m - 1]
                    or global_value != MAXIMA[m - 1]):
                raise ValueError(f"missing complete global certificate for m={m}")
            table = validate_table(raw["canonical_table"])
            if len(table) != m or rooted_canonical(table) != table:
                raise ValueError("source table is not rooted canonical")
            if raw.get("status") != "exact" or raw.get("merge_length") != MAXIMA[m - 1]:
                raise ValueError("source does not have the certified exact maximum")
            witness = raw.get("witness")
            if (not isinstance(witness, list) or len(witness) != 2 or witness[0] == witness[1]
                    or any(len(word) != MAXIMA[m - 1] or set(word) - {"0", "1"} for word in witness)):
                raise ValueError("invalid source witness")
            for mask in range(1 << m):
                if endpoint(table, mask, witness[0]) != endpoint(table, mask, witness[1]):
                    raise ValueError("source witness fails a static mask")
            record = deepcopy(raw)
            record.update({"key": fixed_key(table), "source_key": raw["key"],
                           "upper_bound": raw["merge_length"], "lower_bound": raw["merge_length"],
                           "source_certificate": {"records": source_ref, "summary": summary_ref}})
            records.append(record)
    counts = Counter(record["m"] for record in records)
    if [counts[m] for m in range(1, 8)] != list(ROOTED_COUNTS):
        raise ValueError("certified exports do not contain the expected complete collections")
    if len({(record["m"], record["key"]) for record in records}) != len(records):
        raise ValueError("duplicate rooted class in certified exports")
    base = next((record for record in records if record["m"] == 7 and record["key"] == BASE_KEY), None)
    if base is None or tuple(map(tuple, base["canonical_table"])) != BASE_TABLE:
        raise ValueError("projection base is absent from certified maximizers")
    return sorted(records, key=lambda record: (record["m"], record["key"])), provenance


def build_dataset(small_path, seven_path):
    records, provenance = certified_records(small_path, seven_path)
    records.extend(extension(m) for m in range(8, 21))
    sizes = []
    for m in range(1, 21):
        exact = m <= 7
        sizes.append({
            "m": m, "scope": "exactly-m-root-reachable-states", "enumeration_complete": exact,
            "maximum_value_certified": exact, "maximum_certified": exact,
            "global_maximum": MAXIMA[m - 1] if exact else None,
            "maximum_merge_length": MAXIMA[m - 1] if exact else None,
            "maximizing_collection_complete": exact,
            "maximizer_count": ROOTED_COUNTS[m - 1] if exact else None,
            "ordinary_shape_count": SHAPE_COUNTS[m - 1] if exact else None,
            "displayed_graphs": ROOTED_COUNTS[m - 1] if exact else 1,
            "largest_displayed_lower_bound": MAXIMA[m - 1] if exact else 34,
            "status": "global-maximum-and-all-rooted-ties-certified" if exact else "constructive-lower-bound; global-maximum-unresolved",
            "coverage_source": provenance[0 if m <= 6 else 1] if exact else None,
        })
    summary = {
        "schema": 1, "dataset_kind": "selected-presentation-data-not-a-search-journal",
        "record_count": len(records), "min_m": 1, "max_m": 20,
        "graph_model": {"root": 0, "outgoing_ports_per_state": 2, "loops_allowed": True,
                        "coincident_ports_allowed": True, "indegree_restriction": None,
                        "strong_connectivity_required": False,
                        "equivalence": "root-preserving vertex relabeling and independent local port swaps",
                        "each_seed_scored_separately": True},
        "scope": "All rooted maximizers for exact sizes 1..7; one constructive lower-bound example per exact size 8..20.",
        "sources": provenance, "generator": reference(Path(__file__)),
        "larger_examples": {"method": "static-mask-projection-to-certified-seven-state-base",
                            "base_key": BASE_KEY, "lower_bound": 34,
                            "individual_exact_scores_known": False,
                            "enumeration_complete": False,
                            "global_maxima_known": False,
                            "complete_maximizing_collections_known": False},
        "historical_observations": {
            **reference(REPO / "results/family1-through20/larger-graph-observations.jsonl"),
            "note": "Historical larger classes remain unresolved and are preserved separately; a lower displayed bound does not exclude a challenger."
        },
        "m8_prediction": {"point_guess": 48, "informal_range": [40, 55],
                          "status": "heuristic-not-a-bound",
                          "rationale": "Continue increments 5,8,11 by14; 34+14=48.",
                          "statistical_confidence_claim": False},
        "sizes": sizes,
    }
    return records, summary


README = r"""# Current Family 1 atlas data, exact sizes 1 through 20

This is a selected presentation dataset, not a complete search journal. It
contains every certified rooted maximizing class through seven states, and one
explicit lower-bound example at each larger exact size. No larger maximum or
complete larger maximizing collection is asserted.

| m | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Certified global maximum | 1 | 3 | 6 | 10 | 15 | 23 | 34 |
| All rooted maximizing classes | 1 | 1 | 2 | 1 | 5 | 2 | 8 |
| Ordinary shapes, root ignored for comparison only | 1 | 1 | 1 | 1 | 4 | 1 | 4 |

Each exact size 8 through 20 has a constructive graph with **H >= 34**. Its
individual exact score and the global maximum remain unresolved. The 33 records
are not evidence of exhaustive coverage at larger sizes. Historical observations
in `results/family1-through20/` remain unchanged; lower certified bounds do not
rule out unresolved challengers.

## Larger-size construction and lower-bound proof

Use the certified seven-state maximizer

```json
[[0,1],[2,3],[2,3],[4,5],[0,6],[4,6],[1,5]]
```

For m >= 8, replace the root's port-0 loop by the cycle
`0 -> 7 -> 8 -> ... -> m-1 -> 0`; each new vertex has its other port to state 1.
Keep the six other old rows. Every added vertex is reachable from root 0, and
all seven old vertices remain reachable, so the seed has exactly m reachable
states. All vertices still have two outgoing ports. Its indegrees need not be
two, consistent with the unrestricted search model.

Map each old vertex i to i and every new vertex to 0. Before canonicalization
this projection pi commutes with each outgoing port:

`pi(tau_new(s,p)) = tau_base(pi(s),p)`.

For any static base mask sigma, give each new state the bit of the base state
to which it projects. Induction on word length gives projection of the new
trajectory equal to the base trajectory, including every revisit. If two
distinct equal-length words collided in the new graph under every static mask,
they would collide in the base graph under every static base mask. Therefore
`H(new) >= H(base) = 34`. This argument proves only a lower bound.

The exported transition tables are exactly rooted canonical, allowing local
port swaps. The construction metadata retains the raw table, its raw projection,
the old-to-canonical label map, and the local port flips. In canonical labels,
write `pi[s]` for `canonical_projection_to_base[s]` and `k[s]` for
`canonical_mask_lift_xor[s]`. The checked identity is

`pi[tau_new(s,p)] = tau_base(pi[s], p XOR k[s])`.

Lift each base mask by the **fixed** assignment
`sigma_new[s] = sigma_base[pi[s]] XOR k[s]`. The transition projection then
commutes for both input symbols. This absorbs canonicalization's port swaps and
retains the same proof.

## Files and validation

- `champions.jsonl`: all 20 certified small rooted winners and 13 constructive
  larger examples, in deterministic size/key order. The filename is accepted by
  the atlas tools; it does not claim optimality for the larger examples.
- `summary.json`: per-size proof flags, complete collection counts where known,
  source SHA-256 digests, and an explicitly speculative m=8 extrapolation.
- `validation.json`: all source upper witnesses independently replayed over all
  static masks; all thirteen accessible constructions and projection identities
  checked. Global coverage and base lower proofs are inherited from the pinned
  source certificates, not recomputed by this presentation generator.

The m=8 point guess 48 and informal range 40--55 are heuristics, not proved
bounds or statistical confidence intervals. Continuing the latest increments
5,8,11 by 14 gives 34+14=48. These few values do not settle quadratic versus
cubic extremal growth.

Reproduce from the repository root:

```powershell
uv run --no-project python scripts/family1_atlas_dataset.py
uv run --no-project python tests/family1_atlas_dataset_test.py
```
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small", type=Path, default=REPO / "results/family1-m1-m6/maximizers.jsonl")
    parser.add_argument("--seven", type=Path, default=REPO / "results/family1-m7/maximizers.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-atlas-current")
    args = parser.parse_args()
    records, summary = build_dataset(args.small, args.seven)
    args.out.mkdir(parents=True, exist_ok=True)
    records_path = args.out / "champions.jsonl"
    records_path.write_text("".join(compact(record) + "\n" for record in records), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.out / "README.md").write_text(README, encoding="utf-8")
    validation = {
        "schema": 1, "records": reference(records_path),
        "source_exact_witness_count": sum(record["m"] <= 7 for record in records),
        "source_exact_upper_witnesses_all_static_masks_verified": True,
        "source_exact_rooted_canonical_tables_verified": True,
        "construction_sizes": list(range(8, 21)),
        "construction_exact_reachable_sizes_verified": True,
        "construction_canonical_projection_identities_verified": True,
        "global_coverage_and_lower_certificates": "inherited-from-pinned-source-certificates; not-rerun-here",
        "larger_graph_scoring_performed": False,
        "larger_global_search_performed": False,
    }
    (args.out / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(compact({"output": str(args.out), "records": len(records),
                   "certified_rooted_winners_through_seven": 20,
                   "constructive_lower_bound_examples_eight_through_twenty": 13}))


if __name__ == "__main__":
    main()
