#!/usr/bin/env python3
"""Export the supplied circulant seed family, with independently checked scores.

Literal family: tau0(i)=i+1, tau1(i)=i+floor(m/3), modulo m.
One rooted class is retained at each exact size 1..20; all vertex roots are
isomorphic by translation. No numerical asymptotic lower bound is assumed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from family1_certified_tikz import rooted_canonical
from family1_study import REPO, compact, file_hash, fixed_key, validate_table


def formula_table(m, variant="literal"):
    if not 1 <= m <= 20:
        raise ValueError("expected an exact size in 1..20")
    if variant not in ("literal", "manuscript"):
        raise ValueError("unknown circulant variant")
    jump = m // 3 if variant == "literal" else 1 + max(1, m // 3)
    return tuple(((state + 1) % m, (state + jump) % m) for state in range(m))


def endpoint(table, mask, word, root=0):
    state = root
    for letter in word:
        state = table[state][int(letter) ^ ((mask >> state) & 1)]
    return state


def verify_witness(table, witness, all_roots=False):
    assert len(witness) == 2 and witness[0] != witness[1]
    assert len(witness[0]) == len(witness[1]) > 0
    assert all(not (set(word) - {"0", "1"}) for word in witness)
    for root in range(len(table)) if all_roots else (0,):
        for mask in range(1 << len(table)):
            assert endpoint(table, mask, witness[0], root) == endpoint(table, mask, witness[1], root)


def exact_layers(table, depth_cap):
    """Straightforward complete vectors, with a fresh collision table per length.

    Every coordinate is a fixed static mask. Bytes equality checks full states;
    Python dictionary hashing is only a lookup accelerator. Equal endpoints at
    earlier lengths are deliberately not used to prune this layer.
    """
    table = validate_table(table)
    m, masks = len(table), 1 << len(table)
    transitions = [[[table[state][letter ^ ((mask >> state) & 1)] for state in range(m)]
                    for mask in range(masks)] for letter in (0, 1)]
    layer, completed = {bytes(masks): 0}, []
    for depth in range(1, depth_cap + 1):
        next_layer = {}
        for vector, prefix in layer.items():
            for letter in (0, 1):
                successor = bytes(transitions[letter][mask][state] for mask, state in enumerate(vector))
                word = 2 * prefix + letter
                previous = next_layer.get(successor)
                if previous is not None:
                    witness = [format(previous, f"0{depth}b"), format(word, f"0{depth}b")]
                    verify_witness(table, witness)
                    return {"status": "exact", "merge_length": depth, "lower_bound": depth,
                            "upper_bound": depth, "witness": witness,
                            "completed_injective_layers": completed, "all_static_masks": masks,
                            "first_collision_depth": depth, "collision_layer_complete": False}
                next_layer[successor] = word
        assert len(next_layer) == 1 << depth
        digest = hashlib.sha256()
        for vector in next_layer:  # Lexicographic word order in injective layers.
            digest.update(vector)
        completed.append({"depth": depth, "word_count": 1 << depth,
                          "distinct_complete_product_states": len(next_layer),
                          "vectors_sha256_in_word_order": digest.hexdigest(), "complete": True})
        layer = next_layer
    return {"status": "depth-capped", "merge_length": None, "lower_bound": depth_cap + 1,
            "upper_bound": None, "witness": None, "completed_injective_layers": completed,
            "all_static_masks": masks, "first_collision_depth": None}


def canonical_metadata(raw):
    canonical, mapping = rooted_canonical(raw, return_mapping=True)
    flips = []
    for old, row in enumerate(raw):
        mapped = tuple(mapping[target] for target in row)
        flip = int(mapped != canonical[mapping[old]])
        assert mapped[:: -1 if flip else 1] == canonical[mapping[old]]
        flips.append(flip)
    translations = []
    for root in range(len(raw)):
        translation = tuple((state - root) % len(raw) for state in range(len(raw)))
        assert translation[root] == 0
        for source, row in enumerate(raw):
            for port, target in enumerate(row):
                assert translation[target] == raw[translation[source]][port]
        rooted, _ = rooted_canonical(raw, root=root, return_mapping=True)
        assert rooted == canonical
        translations.append({"root": root, "old_to_root_zero_labels": translation})
    return canonical, {"raw_table": raw, "raw_to_canonical_labels": mapping,
                       "canonical_mask_lift_xor_at_raw_source": flips,
                       "mask_lift_formula": "sigma_canonical[mapping[s]]=sigma_raw[s] XOR port_flip[s]",
                       "root_translations_to_root_zero": translations,
                       "vertex_root_multiplicity": len(raw), "distinct_rooted_class_count": 1,
                       "all_roots_accessible": True, "translations_preserve_ordered_ports": True}


def source_records(small_path, seven_path, wanted):
    small = {}
    with small_path.open(encoding="utf-8-sig") as source:
        for line in source:
            record = json.loads(line)
            m = record["m"]
            if m in wanted and fixed_key(record["canonical_table"]) == wanted[m]:
                if m in small:
                    raise ValueError("duplicate small source class")
                small[m] = record
    if set(small) != set(range(1, 7)):
        raise ValueError("missing exact small source record")
    seven, digest = None, hashlib.sha256()
    needle = wanted[7].encode("ascii")
    with seven_path.open("rb") as source:
        for line in source:
            digest.update(line)
            if needle not in line:
                continue
            record = json.loads(line)
            if record.get("m") == 7 and record.get("key") == wanted[7]:
                if seven is not None:
                    raise ValueError("duplicate seven-state source class")
                seven = record
    if seven is None:
        raise ValueError("missing seven-state source class")
    return small, seven, digest.hexdigest()


def run(args):
    tables, metadata = {}, {}
    for m in range(1, 21):
        raw = formula_table(m, args.variant)
        validate_table(raw)
        tables[m], metadata[m] = canonical_metadata(raw)
    wanted = {m: fixed_key(tables[m]) for m in range(1, 8)}
    small, seven, seven_hash = source_records(args.small_journal, args.seven_journal, wanted)
    records, layers = [], {}
    for m in range(1, 21):
        table, raw = tables[m], formula_table(m, args.variant)
        distinct = raw[0][0] != raw[0][1]
        result = {"status": "incomplete", "merge_length": None, "lower_bound": 2 if distinct else 1,
                  "upper_bound": None, "witness": None}
        proof = {"method": "distinct-root-ports-exclude-length-one" if distinct else "coincident-root-ports",
                 "asymptotic_numeric_lower_bound_used": False}
        if m <= 6:
            prior = small[m]
            if prior["status"] != "exact":
                raise ValueError("small source score is not exact")
            verify_witness(table, prior["witness"])
            computed = exact_layers(table, prior["merge_length"])
            assert computed["merge_length"] == prior["merge_length"]
            result.update({field: computed[field] for field in result})
            proof = {"method": "exact-small-journal-independently-recomputed", "source_ordinal": prior["ordinal"]}
            layers[str(m)] = computed
        elif m == 7:
            assert tuple(map(tuple, seven["canonical_table"])) == table
            result["lower_bound"] = max(result["lower_bound"], seven["lower_bound"])
            result["upper_bound"] = seven["upper_bound"]
            result["witness"] = seven["witness"]
            result["status"] = "bounded"
            verify_witness(table, seven["witness"])
            proof = {"method": "certified-refined-journal-interval", "source_ordinal": seven["ordinal"],
                     "prior_interval": {"lower_bound": seven["lower_bound"], "upper_bound": seven["upper_bound"],
                                        "witness": seven["witness"]}}
        if 7 <= m <= args.exact_through:
            computed = exact_layers(table, args.depth_cap)
            layers[str(m)] = computed
            if computed["status"] == "exact":
                result.update({field: computed[field] for field in result})
                proof["method"] = "independent-complete-per-length-product-vectors"
            else:
                result["lower_bound"] = max(result["lower_bound"], computed["lower_bound"])
                result["status"] = "depth-capped"
        if result["witness"] is not None:
            verify_witness(table, result["witness"])
            verify_witness(raw, result["witness"], all_roots=True)
        if result["upper_bound"] is not None:
            assert result["lower_bound"] <= result["upper_bound"]
        if result["merge_length"] is not None:
            assert result["lower_bound"] == result["upper_bound"] == result["merge_length"]
        jump = m // 3 if args.variant == "literal" else 1 + max(1, m // 3)
        records.append({"m": m, "key": fixed_key(table), "canonical_table": table,
                        **result, "reason": proof["method"], "score_proof": proof,
                        "family": {"name": "supplied-circulant" if args.variant == "literal" else "manuscript-reference-circulant",
                                   "variant": args.variant, "root": 0,
                                   "tau0_formula": "(i+1) mod m",
                                   "tau1_formula": "(i+floor(m/3)) mod m" if args.variant == "literal" else "(i+1+max(1,floor(m/3))) mod m",
                                   "raw_second_step": jump, **metadata[m]},
                        "global_maximum_certified": False, "maximizing_collection_complete": False})
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "champions.jsonl").write_text("".join(compact(record) + "\n" for record in records), encoding="utf-8")
    (args.output / "layers.json").write_text(json.dumps(layers, indent=2) + "\n", encoding="utf-8")
    summary = {"schema": 1, "dataset_kind": "one-supplied-circulant-class-per-exact-size-not-global-champions",
               "variant": args.variant, "min_m": 1, "max_m": 20, "records": 20,
               "all_roots_translation_equivalent": True, "indegree_restriction_used_for_search": None,
               "global_enumeration_performed": False, "global_maxima_claimed": False,
               "numeric_asymptotic_lower_bound_imported": False,
               "quadratic_family_context": "The initial quadratic-family discussion involves different formulas and a cumulative product. No fixed-graph quadratic H theorem or numerical bound is asserted by this export.",
               "manuscript_reference_caution": "The manuscript variant has a different second step; a theorem for a cumulative product over seed sizes is not transferred to fixed-graph H.",
               "generator": {"path": "scripts/family1_circulant_family.py", "sha256": file_hash(Path(__file__)),
                             "exact_through": args.exact_through, "depth_cap": args.depth_cap},
               "sizes": [{"m": record["m"], "key": record["key"], "status": record["status"],
                          "merge_length": record["merge_length"], "lower_bound": record["lower_bound"],
                          "upper_bound": record["upper_bound"], "vertex_root_multiplicity": record["m"],
                          "distinct_rooted_classes": 1, "global_maximum_certified": False,
                          "maximizing_collection_complete": False} for record in records],
               "sources": {str(args.small_journal.relative_to(REPO)): {"sha256": file_hash(args.small_journal)},
                           str(args.seven_journal.relative_to(REPO)): {"sha256": seven_hash}},
               "validation": {"all_raw_formula_tables_verified": True, "all_root_translations_verified": True,
                              "all_canonical_vertex_maps_and_port_swaps_verified": True,
                              "all_available_witnesses_all_static_masks_all_raw_roots_verified": True,
                              "small_exact_scores_independently_recomputed": True,
                              "complete_vectors_used_for_matching_hashes": True}}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Circulant Family 1 seeds", "",
             f"Variant: `{args.variant}`. Each exact size 1–20 contributes one rooted class; all vertex roots are equivalent by translation. `champions.jsonl` is a candidate-input filename, not a claim that these graphs are global maximizers.", "",
             "The raw formula, ordered transition table, canonical vertex permutation, port swaps, and every root translation are retained in each record. Local mask bits remain fixed on revisits. All saved upper witnesses were replayed for every static mask and every raw root.", "",
             "| m | Lower bound | Upper bound | Status |",
             "|---:|---:|---:|---|"]
    for record in records:
        lines.append(f"| {record['m']} | {record['lower_bound']} | {record['upper_bound'] if record['upper_bound'] is not None else 'unknown'} | {record['status']} |")
    lines.extend(["", "Exact scores through six were checked against the complete small-case journal and independently recomputed. Any further exact scores use fresh complete equal-length product-vector layers, with layer counts and SHA-256 checksums in `layers.json`. The seven-state source interval is also retained separately.", "",
                  "The literal supplied formula is tau0(i)=(i+1) mod m, tau1(i)=(i+floor(m/3)) mod m. Its ports coincide for m=1,3,4,5, so those scores are exactly one. No numeric quadratic bound is invented from an asymptotic claim. The separately labeled manuscript variant uses tau1(i)=(i+1+max(1,floor(m/3))) mod m; a cumulative-product theorem for that family does not imply a quadratic lower bound on this fixed-graph score.", "",
                  "```powershell", "uv run --no-project python scripts/family1_circulant_family.py" +
                  (" --variant manuscript --exact-through 8 --depth-cap 18" if args.variant == "manuscript" else ""),
                  "uv run --no-project python tests/family1_circulant_family_test.py", "```", ""])
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(compact({"variant": args.variant, "records": 20, "output": str(args.output),
                   "exact_scores": {record["m"]: record["merge_length"] for record in records if record["status"] == "exact"}}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("literal", "manuscript"), default="literal")
    parser.add_argument("--small-journal", type=Path, default=REPO / "out/family1-m1-m6/graphs.jsonl")
    parser.add_argument("--seven-journal", type=Path, default=REPO / "out/family1-m7-global-certificate-v3/refined-checkpoint.jsonl")
    parser.add_argument("--exact-through", type=int, choices=(6, 7, 8), default=8)
    parser.add_argument("--depth-cap", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.depth_cap < 1:
        parser.error("depth cap must be positive")
    if args.output is None:
        args.output = REPO / ("results/family1-circulant-family" if args.variant == "literal" else "results/family1-circulant-manuscript-reference")
    run(args)


if __name__ == "__main__":
    main()
