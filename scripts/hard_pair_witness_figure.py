#!/usr/bin/env python3
"""Render a verified hard pair, its full disagreement trace, and search parameters.

Family 1 records use every original static mask, including coincident-port
multiplicity. Generic benchmark records use the saved fixture's DFA family.
This renderer performs scalar verification; it launches no search.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
from html import escape
import hashlib
import json
import math
from pathlib import Path
import textwrap

import family1_graph_atlas as atlas


ALPHABET = ["00", "01", "10", "11"]
METRIC = "D(i) = number of family DFAs whose endpoints after u[:i] and v[:i] differ"


def reference(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def checked_table(table):
    if not isinstance(table, list) or not table or any(
            not isinstance(ports, list) or len(ports) != 2
            or any(type(target) is not int or not 0 <= target < len(table) for target in ports)
            for ports in table):
        raise ValueError("Invalid binary DFA table")
    return table


def search_parameters(row):
    """Do not mistake a refinement's completed_k for the witness-producing k."""
    supplied = row.get("search_parameters", {})
    joint = row.get("alphabet", supplied.get("alphabet")) == ALPHABET
    explicit_kind = row.get("window_kind", supplied.get("window_kind"))
    kind = explicit_kind or ("joint-pair" if joint else "common-suffix-historical")
    result = {"k": row.get("k", supplied.get("k")), "window_kind": kind,
              "alphabet": ALPHABET if joint else supplied.get("alphabet", ["00", "11"]),
              "producer_k_known": row.get("k", supplied.get("k")) is not None}
    aliases = {"beam_width": ("beam_width", "beam"),
               "diagonal_width": ("diagonal_width", "diagonal_beam"),
               "unequal_width": ("unequal_width", "unequal_beam"),
               "prefix_pairs": ("prefix_pairs",), "prefix_depth": ("prefix_depth",),
               "prefix_words": ("prefix_words",), "common_prefix_depth": ("common_prefix_depth",),
               "max_length": ("max_length",), "expansion_cap": ("expansion_cap", "max_expansions"),
               "target_upper": ("target_upper",), "deterministic": ("deterministic",),
               "bootstrap_depth": ("bootstrap_depth",), "bootstrap_width": ("bootstrap_width",),
               "startup_policy": ("startup_policy",), "advance_policy": ("advance_policy",)}
    for target, names in aliases.items():
        result[target] = next((source[name] for source in (row, supplied)
                               for name in names if name in source), None)
    for field in ("winning_attempt", "divergence_common_prefix_depth", "divergence_start_count",
                  "first_greedy_depth", "window_advance", "candidate_selection", "startup",
                  "common_depth", "score", "ranking", "priority_coordinate_count", "greedy_advance",
                  "max_length", "expanded_nodes", "complete_windows", "expansion_limit_reached",
                  "length_limit_reached", "prefix_pair_capped", "prefix_word_capped"):
        if field in row:
            result[field] = row[field]
    if "completed_k" in row or "max_attempted_k" in row:
        result["separate_refinement_completed_k"] = row.get("completed_k")
        result["separate_refinement_max_attempted_k"] = row.get("max_attempted_k")
        result["provenance_note"] = "Refinement k values do not identify the producer of this imported witness."
    return result


def parameter_label(parameters):
    k = parameters["k"]
    k_text = str(k) if k is not None else "not applicable" if parameters["window_kind"] == "exact-oracle" else "unknown"
    parts = [f"k={k_text}", parameters["window_kind"]]
    for field, label in (("beam_width", "B"), ("diagonal_width", "diagonal"),
                         ("unequal_width", "unequal"), ("prefix_pairs", "prefix starts"),
                         ("common_prefix_depth", "common-prefix depth"),
                         ("bootstrap_depth", "bootstrap depth"), ("bootstrap_width", "bootstrap width")):
        if parameters.get(field) is not None:
            if field == "common_prefix_depth" and not parameters.get("prefix_pairs"):
                continue
            parts.append(f"{label}={parameters[field]}")
    startup = parameters.get("startup")
    if isinstance(startup, dict):
        parts.append("startup=" + str(startup.get("mode", "unknown")))
        if "common_depth" in startup:
            parts.append("c=" + str(startup["common_depth"]))
    elif parameters.get("startup_policy"):
        parts.append("startup=" + str(parameters["startup_policy"]))
    elif isinstance(startup, str):
        parts.append("startup=" + startup)
        if startup == "divergence" and parameters.get("common_depth") is not None:
            parts.append("c=" + str(parameters["common_depth"]))
    if parameters.get("score") or parameters.get("ranking"):
        score = str(parameters.get("score", parameters.get("ranking")))
        parts.append("score=" + score + (" (experimental)" if "permutation" in score else ""))
    return "; ".join(parts)


def window_label(record):
    parameters = record["search_parameters"]
    attempt = parameters.get("winning_attempt", {})
    parts = [f"First difference: depth {record['first_difference_position']}"]
    if attempt.get("initial_length") is not None:
        parts.append(f"initial depth {attempt['initial_length']}")
    if attempt.get("first_greedy_depth") == 0:
        parts.append("startup success before greedy windows")
    elif attempt.get("first_greedy_depth") is not None:
        parts.append(f"first window ends at depth {attempt['first_greedy_depth']}")
    advance = parameters.get("greedy_advance", parameters.get("advance_policy"))
    if advance:
        parts.append("advance: " + str(advance))
    return "; ".join(parts) + "."


def scalar_trace(pair, family):
    if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
            or any(not isinstance(word, str) or not word or set(word) - {"0", "1"} for word in pair)
            or len(pair[0]) != len(pair[1])):
        raise ValueError("Witness must contain two distinct, nonempty, equal-length binary words")
    if not family:
        raise ValueError("Cannot verify an empty DFA family")
    endpoints = []
    for dfa in family:
        table = checked_table(dfa.get("table", dfa.get("canonical_table")))
        root = dfa.get("root", dfa.get("start", 0))
        if type(root) is not int or not 0 <= root < len(table):
            raise ValueError("Invalid DFA root")
        endpoints.append([table, root, root])
    trace = [0]
    for a, b in zip(*pair):
        for entry in endpoints:
            table, left, right = entry
            entry[1] = table[left][int(a)]
            entry[2] = table[right][int(b)]
        trace.append(sum(left != right for _, left, right in endpoints))
    if trace[-1] != 0:
        raise ValueError("Witness fails scalar replay on the complete DFA family")
    return trace


def family1_family(table):
    checked_table(table)
    return [{"root": 0, "table": [[ports[(bit ^ ((mask >> state) & 1))]
                                  for bit in range(2)] for state, ports in enumerate(table)]}
            for mask in range(1 << len(table))]


def witness_record(row, family=None, fixture=None):
    pair = row.get("witness", row.get("verified_finder_witness"))
    table = row.get("canonical_table")
    if family is None:
        if table is None:
            raise ValueError("Generic records require a saved fixture family")
        family = family1_family(table)
        counting = "all original 2^m static masks; coincident-port duplicates retain multiplicity"
    else:
        counting = "one coordinate per saved fixture DFA entry"
    trace = scalar_trace(pair, family)
    if row.get("family_size", len(family)) != len(family):
        raise ValueError("Saved family size differs from the supplied complete fixture")
    supplied_trace = row.get("witness_metric_trace", row.get("verified_d_trace"))
    if supplied_trace is not None and supplied_trace != trace:
        raise ValueError("Saved witness metric trace differs from independent scalar replay")
    length = len(pair[0])
    if row.get("upper_bound", length) != length:
        raise ValueError("Upper bound and witness length disagree")
    result = {"schema": 1, "id": row.get("id", row.get("key")), "m": row.get("m"),
              "key": row.get("key"), "canonical_table": table, "witness": pair,
              "first": pair[0], "second": pair[1], "length": length,
              "first_difference_position": next(i + 1 for i, (a, b) in enumerate(zip(*pair)) if a != b),
              "status": "verified-upper", "minimality_certified": False,
              "metric_definition": METRIC, "metric_counting": counting,
              "family_size": len(family), "search_parameters": search_parameters(row),
              "verification": {"method": "independent-scalar-complete-family-prefix-replay",
                               "dfa_count": len(family), "passed": True, "D_empty": 0, "D_final": trace[-1]},
              "trace": [{"length": i, "differing": value, "synchronized": len(family) - value}
                        for i, value in enumerate(trace)], "fixture": fixture}
    if "winning_attempt" not in result["search_parameters"]:
        attempts = row.get("attempts", [])
        attempt = next((item for item in attempts if item.get("witness") == pair), None) if isinstance(attempts, list) else None
        if attempt:
            result["search_parameters"]["winning_attempt"] = {key: attempt[key] for key in
                ("common_prefix", "orientation", "first_difference_depth", "first_greedy_depth") if key in attempt}
    if row.get("first_difference_position", result["first_difference_position"]) != result["first_difference_position"]:
        raise ValueError("Saved first-difference position disagrees with the witness")
    if "coordinate_weight_policy" in row:
        result["source_coordinate_weight_policy"] = row["coordinate_weight_policy"]
    # Exact shortestness belongs to a separately checked benchmark oracle.
    for field in ("reference_H", "reference_source", "reference_upper", "gap_to_known_upper", "gap", "ratio", "oracle"):
        if field in row:
            result[field] = row[field]
    return result


@lru_cache(maxsize=256)
def graph_geometry(ports):
    table = [list(row) for row in ports]
    record = {"m": len(table), "key": "".join(f"{v:02d}" for p in table for v in p), "canonical_table": table}
    positions = atlas.layout(record)
    return positions, atlas.edge_geometry(record, positions)


def graph_parts(table, x_offset=0, y_offset=0, width=420, height=365, starts=(0,)):
    """Reuse the established atlas geometry; all edges remain solid/unlabelled."""
    positions, edges = graph_geometry(tuple(tuple(row) for row in table))
    sx, sy = width / atlas.WIDTH, height / atlas.HEIGHT
    def point(value):
        return f"{x_offset + value[0] * sx:.3f},{y_offset + value[1] * sy:.3f}"
    parts = []
    for edge in edges:
        command = "C" if edge["kind"] == "cubic" else "Q"
        path = "M " + point(edge["points"][0]) + " " + command + " " + " ".join(point(p) for p in edge["points"][1:])
        parts.append(f'<path data-source="{edge["source"]}" data-port="{edge["port"]}" data-target="{edge["target"]}" d="{path}" fill="none" stroke="#111" stroke-width="1.3" marker-end="url(#arrow)"/>')
    for state, position in enumerate(positions):
        x, y = x_offset + position[0] * sx, y_offset + position[1] * sy
        parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="12" fill="white" stroke="#111"/>')
        if state in starts:
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="9.5" fill="none" stroke="#111"/>')
        parts.append(f'<text x="{x:.3f}" y="{y + 4:.3f}" text-anchor="middle" font-size="11">{state}</text>')
    return parts


def figure_svg(record, tables):
    parameters = record["search_parameters"]
    shown = tables[:4]
    columns = min(2, len(shown))
    rows = math.ceil(len(shown) / columns) if columns else 0
    graph_height = 310 * rows
    word_chunks = [textwrap.wrap(word, width=100) for word in record["witness"]]
    word_height = 24 * sum(map(len, word_chunks))
    parameter_lines = textwrap.wrap(parameter_label(parameters), width=120)
    header_extra = 22 * (len(parameter_lines) - 1)
    reference_line = None
    if type(record.get("reference_H")) is int:
        reference_line = f"Reference shortest H={record['reference_H']}; gap L-H={record['length'] - record['reference_H']}; reference k=N/A."
        header_extra += 22
    height = 390 + graph_height + word_height + header_extra
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img">',
             '<title>Verified hard pair and disagreement trace</title>',
             f'<metadata>{escape(json.dumps(record, separators=(",", ":")))}</metadata>',
             '<defs><marker id="arrow" markerWidth="7" markerHeight="6" refX="6" refY="3" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L6,3 L0,6 Z" fill="#111"/></marker></defs>',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g font-family="Arial,sans-serif" fill="#111">']
    def text(x, y, value, size=15, mono=False):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}"' + (' font-family="monospace"' if mono else '') + f'>{escape(str(value))}</text>')
    text(35, 35, f"Verified pair length {record['length']} — search upper bound", 23)
    for index, line in enumerate(parameter_lines):
        text(35, 63 + index * 22, line, 14)
    count_y = 87 + 22 * (len(parameter_lines) - 1)
    text(35, count_y, f"{record['family_size']} DFA coordinates independently replayed; D(empty)=0; D(final)=0.", 14)
    if reference_line:
        text(35, count_y + 22, reference_line, 14)
    for index, item in enumerate(shown):
        table = item.get("table", item.get("canonical_table")) if isinstance(item, dict) else item
        root = item.get("root", 0) if isinstance(item, dict) else 0
        col, row = index % columns, index // columns
        parts += graph_parts(table, 35 + col * 480, 95 + header_extra + row * 310, width=460, height=310, starts=(root,))
    y = 110 + graph_height + header_extra
    text(35, y, f"Graph drawings: {len(shown)} of {len(tables)} saved base DFA(s); roots are double circles; arrows unlabelled.", 13)
    y += 30
    for label, chunks in zip(("u", "v"), word_chunks):
        for index, chunk in enumerate(chunks):
            text(35, y, (label + " = " if index == 0 else "    ") + chunk, 14, True)
            y += 24
    y += 8
    text(35, y, "D(i): number of DFAs with different endpoints after i joint symbols", 15)
    plot_y = y + 30
    maximum = max(1, record["family_size"])
    points = [(60 + 880 * entry["length"] / record["length"], plot_y + 125 * (1 - entry["differing"] / maximum)) for entry in record["trace"]]
    parts.append(f'<path d="M60,{plot_y} V{plot_y + 125} H940" fill="none" stroke="#888"/>')
    parts.append('<polyline points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in points) + '" fill="none" stroke="#1b5d8c" stroke-width="2"/>')
    text(35, plot_y + 5, maximum, 11); text(43, plot_y + 129, 0, 11)
    text(56, plot_y + 146, 0, 11); text(925, plot_y + 146, record["length"], 11)
    text(35, plot_y + 175, window_label(record), 13)
    text(35, plot_y + 197, "Agreements may be lost under 01 or 10. Complete search parameters and prefix scores are in witness.json.", 13)
    parts += ["</g></svg>"]
    return "\n".join(parts) + "\n"


def load_rows(path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return value if isinstance(value, list) else [value]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON or JSONL result records")
    parser.add_argument("--fixtures", type=Path, help="Saved generic benchmark fixtures.json")
    parser.add_argument("--case", help="Generic fixture/result id, or Family 1 graph key")
    parser.add_argument("--k", type=int, help="Select one producing k; never changes the result's parameters")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = [row for row in load_rows(args.input) if (args.case is None or row.get("id", row.get("key")) == args.case)
            and (args.k is None or row.get("k") == args.k)]
    if len(rows) != 1:
        raise ValueError(f"Select exactly one result with --case/--k; matched {len(rows)}")
    row, family, fixture = rows[0], None, None
    tables = [row["canonical_table"]] if row.get("canonical_table") else []
    if args.fixtures:
        cases = json.loads(args.fixtures.read_text())["cases"]
        case = next(item for item in cases if item["id"] == row["id"])
        family, tables = case["family"], case.get("bases", case["family"])
        fixture = {"source": reference(args.fixtures), "case_id": case["id"]}
    record = witness_record(row, family, fixture)
    record["source"] = reference(args.input)
    record["generator"] = reference(Path(__file__))
    record["graph_geometry_source"] = reference(Path(atlas.__file__))
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Use a fresh figure directory")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "witness.json").write_text(json.dumps(record, indent=2) + "\n")
    (args.out / "witness.svg").write_text(figure_svg(record, tables))
    (args.out / "README.md").write_text(f"Verified upper witness of length {record['length']}; shortestness is unproved.\n\n"
        + parameter_label(record["search_parameters"]) + ".\n\n"
        + f"u = `{record['first']}`\n\nv = `{record['second']}`\n\n"
        + window_label(record) + "\n\n"
        + f"Scalar verification replayed all {record['family_size']} saved DFA coordinates. "
        + "witness.json retains every prefix score and the source/search parameters.\n")
    print(json.dumps({"out": str(args.out), "length": record["length"], "k": record["search_parameters"]["k"],
                      "window_kind": record["search_parameters"]["window_kind"], "verified_dfas": record["family_size"]}))


if __name__ == "__main__":
    main()
