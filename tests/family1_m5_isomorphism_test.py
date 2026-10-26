#!/usr/bin/env python3
"""Independently audit the five saved m=5 maximizers and their TikZ arrows.

This uses all 5! vertex bijections, sorted successor pairs for independent
port swaps, and ordinary 32-coordinate state tuples for exact scoring. It
does not import the C++ search, its bitplanes, or its canonicalizer.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re


Table = tuple[tuple[int, int], ...]
REPO = Path(__file__).resolve().parents[1]


def direct_endpoint(table: Table, word: str, root: int = 0) -> tuple[int, ...]:
    endpoints = []
    for mask in range(1 << len(table)):
        state = root
        for letter in word:
            state = table[state][int(letter) ^ ((mask >> state) & 1)]
        endpoints.append(state)
    return tuple(endpoints)


def exact_score(table: Table, root: int = 0, cap: int = 15) -> dict:
    """Enumerate every word at each depth until the first equal-length merge.

    Reusing a prefix endpoint saves simulation time, but every endpoint is a
    complete vector over ALL static masks. Python tuple keys compare all
    coordinates on a hash match. The dictionary is new at every depth.
    """
    masks = range(1 << len(table))
    frontier = [tuple(root for _ in masks)]
    checked = []
    for depth in range(1, cap + 1):
        seen: dict[tuple[int, ...], int] = {}
        following = []
        for prefix_index, parent in enumerate(frontier):
            for letter in (0, 1):
                word_index = 2 * prefix_index + letter
                child = tuple(
                    table[state][letter ^ ((mask >> state) & 1)]
                    for mask, state in enumerate(parent)
                )
                # A separately written whole-word simulator checks the prefix
                # recurrence for every word through depth 7.
                word = format(word_index, f"0{depth}b")
                if depth <= 7:
                    assert child == direct_endpoint(table, word, root)
                if child in seen:
                    witness = [format(seen[child], f"0{depth}b"), word]
                    assert witness[0] != witness[1]
                    assert direct_endpoint(table, witness[0], root) == direct_endpoint(table, witness[1], root)
                    return {
                        "status": "exact", "merge_length": depth,
                        "witness": witness,
                        "collision_free_layers": checked,
                        "colliding_layer_words_examined": word_index + 1,
                        "full_mask_coordinates": len(parent),
                    }
                seen[child] = word_index
                following.append(child)
        assert len(seen) == 1 << depth
        checked.append({"length": depth, "words": len(seen), "distinct_vectors": len(seen)})
        frontier = following
    return {"status": "depth-capped", "lower_bound": cap + 1, "collision_free_layers": checked}


def isomorphisms(first: Table, second: Table, root_fixed: bool) -> list[dict]:
    found = []
    for permutation in itertools.permutations(range(len(first))):
        if root_fixed and permutation[0] != 0:
            continue
        if all(
            sorted(permutation[target] for target in row) == sorted(second[permutation[source]])
            for source, row in enumerate(first)
        ):
            flips = []
            for source, row in enumerate(first):
                transformed = tuple(permutation[target] for target in row)
                flips.append(0 if transformed == second[permutation[source]] else 1)
            found.append({"old_to_new": permutation, "port_flip_at_old_source": flips})
    return found


def rooted_canonical(table: Table) -> Table:
    candidates = []
    for tail in itertools.permutations(range(1, len(table))):
        permutation = (0,) + tail
        rows = [None] * len(table)
        for state, pair in enumerate(table):
            rows[permutation[state]] = tuple(sorted(permutation[target] for target in pair))
        candidates.append(tuple(rows))
    return min(candidates)


def audit_tikz(path: Path, table: Table) -> dict:
    original = path.read_text(encoding="utf-8-sig")
    # Ignore all comments. In particular the '% edge ...' annotations provide
    # no evidence here: the actual draw command supplies source, port, target.
    source = re.sub(r"(?m)%.*$", "", original)
    commands = re.findall(r"\\draw\b[^;]*;", source, flags=re.S)
    edges = {}
    for command in commands:
        style = re.search(r"\\draw\[f1m5 port (zero|one)\]", command)
        assert style, (str(path), command)
        port = 0 if style.group(1) == "zero" else 1
        nodes = re.findall(r"\(q(\d+)\)", command)
        assert len(nodes) == 2, (str(path), command)
        old, target = map(int, nodes)
        labels = re.findall(r"\{\$\s*([01])\s*\$\}", command)
        assert labels == [str(port)], (str(path), command)
        assert (old, port) not in edges, (str(path), old, port)
        edges[old, port] = target
    assert edges == {(s, p): table[s][p] for s in range(len(table)) for p in (0, 1)}, str(path)
    nodes = re.findall(r"\\node\[f1m5 (root|vertex)\]\s*\(q(\d+)\)[^;]*\{\$\s*(\d+)\s*\$\};", source)
    assert len(nodes) == len(table), str(path)
    assert sorted(int(node) for _, node, _ in nodes) == list(range(len(table)))
    assert all(node == label for _, node, label in nodes)
    assert [(int(node)) for style, node, _ in nodes if style == "root"] == [0]
    assert re.search(r"f1m5 root/\.style=\{[^}]*\bdouble\b", source)
    for style in ("zero", "one"):
        assert re.search(r"f1m5 port " + style + r"/\.style=\{->,", source)
    return {
        "file": str(path.relative_to(REPO)).replace("\\", "/"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "actual_draw_commands_verified": len(edges), "root": 0,
        "node_labels_verified": len(nodes),
    }


def self_test() -> None:
    assert exact_score(((0, 0),))["merge_length"] == 1
    revisits = ((0, 1), (0, 0))
    assert direct_endpoint(revisits, "0") == direct_endpoint(revisits, "10")
    assert direct_endpoint(revisits, "0") != direct_endpoint(revisits, "1")
    assert exact_score(revisits)["merge_length"] == 2
    # A static mask sends 0000 alternately 0->1->0->1->0 when bit 0 is 1.
    assert direct_endpoint(revisits, "0000")[1] == 0
    assert direct_endpoint(revisits, "000")[1] == 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPO / "results/family1-m5-audit.json")
    args = parser.parse_args()
    self_test()
    manifest_path = REPO / "figures/family1-m5/source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    records_path = REPO / manifest["source"]
    records = {record["key"]: record for record in
               (json.loads(line) for line in records_path.read_text(encoding="utf-8-sig").splitlines())
               if record["m"] == 5}
    panels = manifest["graphs"]
    assert len(panels) == len(records) == 5
    tables = {panel["panel"]: tuple(tuple(row) for row in panel["canonical_table"]) for panel in panels}
    pair_audits = []
    groups: list[list[str]] = []
    for label in tables:
        for group in groups:
            if isomorphisms(tables[group[0]], tables[label], False):
                group.append(label)
                break
        else:
            groups.append([label])
    for first, second in itertools.combinations(tables, 2):
        rooted = isomorphisms(tables[first], tables[second], True)
        unrooted = isomorphisms(tables[first], tables[second], False)
        assert not rooted, (first, second, rooted)
        pair_audits.append({"first": first, "second": second,
                            "root_preserving_isomorphisms": rooted,
                            "ordinary_isomorphisms_with_port_swaps": unrooted})
    assert groups == [["a", "c"], ["b"], ["d"], ["e"]], groups
    panel_audits = []
    for panel in panels:
        label = panel["panel"]
        table = tables[label]
        assert rooted_canonical(table) == table
        record = records[panel["canonical_key"]]
        assert panel["canonical_key"] == "".join(str(target) for row in table for target in row)
        assert tuple(tuple(row) for row in record["canonical_table"]) == table
        assert record["status"] == "exact" and record["merge_length"] == panel["merge_length"] == 15
        figure = audit_tikz(manifest_path.parent / panel["file"], table)
        score = exact_score(table)
        assert score["status"] == "exact" and score["merge_length"] == 15
        witness = record["witness"]
        assert len(witness[0]) == len(witness[1]) == 15 and witness[0] != witness[1]
        assert direct_endpoint(table, witness[0]) == direct_endpoint(table, witness[1])
        panel_audits.append({"panel": label, "canonical_key": panel["canonical_key"],
                             "canonical_table": table, "figure": figure,
                             "rooted_canonical_table_independently_verified": True,
                             "independent_score": score, "saved_witness_verified": True})
        print(f"Panel {label}: all 10 actual TikZ arrows and exact H=15 verified", flush=True)
    root_scores = []
    for root in range(5):
        score = exact_score(tables["a"], root=root)
        assert score["status"] == "exact"
        root_scores.append({"root_in_panel_a_labelling": root, **score})
        print(f"Underlying graph (a), root {root}: H={score['merge_length']}", flush=True)
    report = {
        "scope": "Five saved m=5 rooted maximizers and their actual TikZ source arrows",
        "methods": {
            "isomorphism": "All 120 vertex bijections per pair; successor pairs compared as multisets, allowing independent port swaps. Root-preserving checks require image(0)=0.",
            "score": "Enumerate all binary words at each length using exact 32-coordinate endpoint tuples. Fresh collision dictionary per length. No collision through 14; an equal-length collision at 15. Whole-word direct static-mask simulation independently checks every word through 7 and both collision witnesses.",
            "figure": "Strip comments and parse each actual draw command, verifying source, target, port style and port label; check all node labels and the double root marker.",
        },
        "limitations": "This audits the five supplied classes and their scores. It does not independently re-enumerate all 10398 five-state rooted classes or prove that no omitted class exceeds 15.",
        "rooted_class_count": len(tables), "ordinary_unrooted_class_count": len(groups),
        "ordinary_unrooted_groups": groups, "pairwise_isomorphism_audits": pair_audits,
        "a_c_root_obstruction": "Panel a has a self-loop at its root 0; panel c has no self-loop at its root 0. This invariant rules out root-preserving isomorphism. The ordinary isomorphism sends a vertex 2 to c root 0, so c uses root 2 in a's labelling.",
        "panels": panel_audits, "all_root_scores_of_panel_a_underlying_graph": root_scores,
        "total_actual_tikz_arrows_verified": sum(panel["figure"]["actual_draw_commands_verified"] for panel in panel_audits),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: 5 rooted classes, 4 ordinary classes, 50 TikZ arrows, five independent H=15 proofs. Report: {args.report}")


if __name__ == "__main__":
    main()
