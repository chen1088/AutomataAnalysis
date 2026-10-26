#!/usr/bin/env python3
"""Export one complete, certified Family 1 maximizing collection as TikZ.

Requires explicit global-value and all-ties completion flags. This presentation
step checks graph identities and every upper witness, while inheriting global
coverage and shortest-length proofs from the supplied certified run.
Compilation and PDF visual inspection are separate steps.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def key_for(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def accessible(table, root=0):
    seen, pending = {root}, [root]
    while pending:
        for target in table[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return len(seen) == len(table)


def rooted_canonical(table, root=0, return_mapping=False):
    """Exact least rooted table by all discovery-order choices.

    First unseen targets take consecutive labels in a least row-sorted table.
    Only two distinct unseen successors permit a choice, consuming two new
    vertices per branch. At m<=20 there are at most 512 complete branches.
    """
    check(accessible(table, root), "canonicalization requires accessibility from the chosen root")
    m = len(table)
    old_to_new, new_to_old = [-1] * m, [None] * m
    old_to_new[root], new_to_old[0] = 0, root
    current, best, best_mapping = [None] * m, None, None

    def visit(row, known):
        nonlocal best, best_mapping
        if row == m:
            candidate = tuple(current)
            mapping = tuple(old_to_new)
            if best is None or (candidate, mapping) < (best, best_mapping):
                best, best_mapping = candidate, mapping
            return
        check(row < known, "accessible discovery stopped before every source was named")
        a, b = table[new_to_old[row]]
        unseen = [target for target in dict.fromkeys((a, b)) if old_to_new[target] < 0]

        def advance(next_known):
            current[row] = tuple(sorted((old_to_new[a], old_to_new[b])))
            if best is None or tuple(current[:row + 1]) <= best[:row + 1]:
                visit(row + 1, next_known)

        if len(unseen) == 2:
            for first, second in (unseen, unseen[::-1]):
                old_to_new[first], old_to_new[second] = known, known + 1
                new_to_old[known], new_to_old[known + 1] = first, second
                advance(known + 2)
                old_to_new[first] = old_to_new[second] = -1
        elif unseen:
            target = unseen[0]
            old_to_new[target], new_to_old[known] = known, target
            advance(known + 1)
            old_to_new[target] = -1
        else:
            advance(known)

    visit(0, 1)
    check(best is not None, "no canonical discovery labelling")
    return (best, best_mapping) if return_mapping else best


def underlying_shape(table):
    # Considering every accessible root gives an isomorphism-invariant key
    # even for graphs that are not strongly connected. Equal keys imply an
    # ordinary graph isomorphism; no rooted member is removed from the export.
    return min(rooted_canonical(table, root, return_mapping=True)
               for root in range(len(table)) if accessible(table, root))


def underlying_shape_key(table):
    return key_for(underlying_shape(table)[0])


def verify_witness(table, length, witness):
    check(isinstance(witness, list) and len(witness) == 2, "missing two-word witness")
    check(witness[0] != witness[1], "witness words must be distinct")
    check(all(isinstance(word, str) and len(word) == length and set(word) <= {"0", "1"}
              for word in witness), "witness words must be binary and have the exact maximum length")
    for mask in range(1 << len(table)):
        endpoints = []
        for word in witness:
            state = 0
            for letter in word:
                state = table[state][int(letter) ^ ((mask >> state) & 1)]
            endpoints.append(state)
        check(endpoints[0] == endpoints[1], f"witness is separated by original static mask {mask}")


def load_certified_collection(directory, states=7):
    """Validate source data without creating output or authoring a drawing."""
    directory = Path(directory).resolve()
    check(type(states) is int and 1 <= states <= 20, "states must lie in 1..20")
    check(directory.is_dir(), "input must be a certified run directory")
    summary_path, records_path = directory / "summary.json", directory / "maximizers.jsonl"
    summary_bytes, records_bytes = summary_path.read_bytes(), records_path.read_bytes()
    supplied = json.loads(summary_bytes.decode("utf-8-sig"))
    if "sizes" in supplied:
        matching = [item for item in supplied["sizes"] if item.get("m") == states]
        check(len(matching) == 1, "summary must identify exactly one entry for the selected size")
        summary = matching[0]
    else:
        summary = supplied
    check(type(summary.get("m")) is int and summary["m"] == states, "summary state count differs from --states")
    certificate_fields = [summary[field] for field in ("maximum_value_certified", "max_value_certified") if field in summary]
    check(bool(certificate_fields) and all(value is True for value in certificate_fields),
          "global maximum is not explicitly certified")
    check(summary.get("maximizing_collection_complete") is True, "complete maximizing collection is not certified")
    maximum, count = summary.get("maximum_merge_length"), summary.get("maximizer_count")
    check(type(maximum) is int and maximum > 0, "certified summary must provide a positive maximum_merge_length")
    check(type(count) is int and count > 0, "certified summary must provide a positive maximizer_count")
    records, keys = [], set()
    for line_number, line in enumerate(records_bytes.decode("utf-8-sig").splitlines(), 1):
        check(bool(line.strip()), f"blank record at maximizers.jsonl:{line_number}")
        record = json.loads(line)
        check(type(record.get("m")) is int and record["m"] == states, f"record {line_number} belongs to another size")
        table = record.get("canonical_table")
        check(isinstance(table, list) and len(table) == states, f"invalid transition table in record {line_number}")
        check(all(isinstance(row, list) and len(row) == 2 and
                  all(type(target) is int and 0 <= target < states for target in row) for row in table),
              f"invalid transition target in record {line_number}")
        check(accessible(table), f"inaccessible graph in record {line_number}")
        table = tuple(tuple(row) for row in table)
        key = key_for(table)
        check(record.get("key") == key, f"fixed-two-digit key does not match table in record {line_number}")
        check(rooted_canonical(table) == table, f"table is not rooted canonical in record {line_number}")
        check(key not in keys, f"duplicate rooted class {key}; duplicates cannot stand in for missing ties")
        keys.add(key)
        check(record.get("status") == "exact" and type(record.get("merge_length")) is int
              and record["merge_length"] == maximum, f"record {line_number} is not an exact maximizer")
        check(all(type(record.get(field, maximum)) is int and record.get(field, maximum) == maximum
                  for field in ("lower_bound", "upper_bound")),
              f"inconsistent exact bounds in record {line_number}")
        verify_witness(table, maximum, record.get("witness"))
        records.append(dict(record, key=key, canonical_table=[list(row) for row in table],
                            lower_bound=maximum, upper_bound=maximum,
                            maximum_value_certified=True, maximizing_collection_complete=True))
    check(len(records) == count, f"summary requires {count} maximizing classes, but export contains {len(records)}")
    records.sort(key=lambda record: record["key"])
    provenance = {
        "summary": {"path": str(summary_path), "sha256": sha256(summary_bytes)},
        "maximizers": {"path": str(records_path), "sha256": sha256(records_bytes)},
        "summary_bytes": summary_bytes,
    }
    return summary, records, provenance


def check_output_directory(output):
    output = Path(output).resolve()
    check(not output.exists() or output.is_dir(), "output exists and is not a directory")
    check(not output.exists() or not any(output.iterdir()), "output directory must be new or empty; existing files are preserved")
    return output


def panel_label(index):
    label = ""
    while index:
        index, digit = divmod(index - 1, 26)
        label = chr(ord("a") + digit) + label
    return label


def plate_document(records, states, maximum, shape_count):
    """A focused portrait plate: two columns and three rows per page."""
    per_page = 4 if 7 <= len(records) <= 8 else 6
    picture_width = "8.2cm" if len(records) <= 4 or per_page == 4 else "6.2cm"
    parts = [r"\documentclass[10pt,a4paper]{article}", r"\usepackage[margin=14mm]{geometry}",
             r"\usepackage{tikz,graphicx}", r"\usetikzlibrary{arrows.meta}",
             r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{0pt}",
             r"\pagestyle{plain}", r"\begin{document}"]
    pages = []
    for start in range(0, len(records), per_page):
        chunk = records[start:start + per_page]
        if start:
            parts.append(r"\clearpage")
        parts += [r"{\Large\bfseries Extremal Family 1 seed graphs}\par\vspace{2mm}",
                  rf"{{\small $m={states}$; $\max_G H(G)={maximum}$. "
                  rf"Complete collection: {len(records)} rooted classes and {shape_count} underlying shapes.}}\par",
                  r"\vspace{1.5mm}{\small Root $0$: double circle. Port $0$: solid; port $1$: dashed. "
                  r"Members of each underlying shape share one vertex embedding.}\par\vspace{3mm}"]
        for offset in range(0, len(chunk), 2):
            parts.append(r"\noindent\hfill")
            for record in chunk[offset:offset + 2]:
                parts += [r"\begin{minipage}[t]{.47\textwidth}\centering",
                          rf"\resizebox{{{picture_width}}}{{!}}{{\input{{{record['snippet']}}}}}\par\smallskip",
                          rf"{{\small ({panel_label(record['index'])}) Rooted class {record['index']}; "
                          rf"underlying shape {record['underlying_shape_index']}.}}\par",
                          r"\end{minipage}\hfill"]
            parts.append(r"\par\vspace{3mm}")
        pages.append({"page": len(pages) + 1, "m": states, "graph_keys": [record["key"] for record in chunk]})
    parts += [r"\end{document}", ""]
    return "\n".join(parts), pages


def generate(directory, output, states=7, port_labels="all"):
    summary, records, provenance = load_certified_collection(directory, states)
    output = check_output_directory(output)
    check(port_labels in ("all", "small", "none"), "invalid port label mode")
    spec = importlib.util.spec_from_file_location("family1_certified_tikz_helper", HERE / "family1_tikz_atlas.py")
    helper = importlib.util.module_from_spec(spec)
    check(spec.loader is not None, "cannot load existing TikZ helper")
    spec.loader.exec_module(helper)

    shape_data = {record["key"]: underlying_shape(record["canonical_table"]) for record in records}
    shape_keys = {key: key_for(value[0]) for key, value in shape_data.items()}
    shapes = {key: index for index, key in enumerate(sorted(set(shape_keys.values())), 1)}
    shape_tables = {key_for(table): table for table, _ in shape_data.values()}
    # Compute exactly one embedding per ordinary shape. Vertex names and the
    # selected root in each drawing retain that member's canonical convention.
    shape_positions = {key: helper.atlas.layout({"m": states, "key": key,
                                               "canonical_table": [list(row) for row in table]})
                       for key, table in shape_tables.items()}
    files, drawings = {}, []
    for index, record in enumerate(records, 1):
        basename = f"m{states:02d}-graph-{index:02d}"
        snippet, standalone = f"snippets/{basename}.tex", f"standalone/{basename}.tex"
        shape_table, mapping = shape_data[record["key"]]
        shape_key = shape_keys[record["key"]]
        check(sorted(mapping) == list(range(states)), "underlying-shape vertex map is not bijective")
        flips = []
        for source, targets in enumerate(record["canonical_table"]):
            mapped = tuple(mapping[target] for target in targets)
            check(tuple(sorted(mapped)) == shape_table[mapping[source]], "underlying-shape map does not preserve successors")
            flips.append(0 if mapped == shape_table[mapping[source]] else 1)
        positions = [shape_positions[shape_key][mapping[state]] for state in range(states)]
        picture, positions = helper.tikz_picture(record, port_labels, positions=positions)
        edges = helper.atlas.edge_geometry(record, positions)
        expected = {(source, port, target) for source, row in enumerate(record["canonical_table"]) for port, target in enumerate(row)}
        check(len(edges) == 2 * states and {(edge["source"], edge["port"], edge["target"]) for edge in edges} == expected,
              f"drawing geometry does not match canonical ports for {record['key']}")
        wrapper = "\n".join([r"\documentclass[border=3mm]{standalone}", r"\usepackage{tikz}",
                              r"\usetikzlibrary{arrows.meta}", r"\begin{document}",
                              rf"\input{{../{snippet}}}", r"\end{document}", ""])
        files[snippet], files[standalone] = picture.encode("utf-8"), wrapper.encode("utf-8")
        drawings.append(dict(record, index=index, snippet=snippet, standalone=standalone,
                             underlying_shape_key=shape_key, underlying_shape_index=shapes[shape_key],
                             old_to_underlying_shape_vertex=list(mapping),
                             port_flip_at_original_state=flips,
                             root_in_underlying_shape_labelling=mapping[0],
                             shared_underlying_embedding=True,
                             positions_svg=positions, edge_geometry=edges,
                             outgoing_ports_verified=2 * states, full_static_masks_witness_verified=1 << states,
                             snippet_sha256=sha256(files[snippet]), standalone_sha256=sha256(files[standalone])))
    text, pages = plate_document(drawings, states, summary["maximum_merge_length"], len(shapes))
    files["plate.tex"] = text.encode("utf-8")
    files["certified-summary.json"] = provenance.pop("summary_bytes")
    files["maximizers.jsonl"] = "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records).encode("utf-8")
    files["README.md"] = f"""# Certified Family 1 extremal graphs

This focused plate contains all {len(records)} certified maximizing rooted
classes with {states} states and H={summary['maximum_merge_length']}.
`plate.tex` uses at most six panels per page. Every rooted class is retained;
underlying-shape indices provide a separate grouping and remove no drawings.
Members of the same underlying shape share vertex positions. Each drawing
keeps its original canonical state numbers and double-circled root 0; the
manifest records the map to the shared shape and its local port swaps.

Each `snippets/*.tex` is a reusable `tikzpicture`. Load `tikz` and
`\\usetikzlibrary{{arrows.meta}}` in the paper, then input the chosen snippet.
The double circle marks root 0; solid/dashed arrows distinguish ports 0/1.
Compile `plate.tex` from this directory. Compile wrappers from `standalone/`:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error plate.tex
Set-Location standalone
pdflatex -interaction=nonstopmode -halt-on-error m{states:02d}-graph-01.tex
```

`source-manifest.json` records original input digests, every canonical table,
witness, drawing digest, geometry and page assignment. `certified-summary.json`
preserves the source summary bytes. The exporter verifies exact metadata,
canonicality and every witness over all original static masks; global coverage
and shortest-length proofs are inherited from the certified input run.
Compilation and visual PDF inspection must be completed separately.
""".encode("utf-8")
    manifest = {
        "schema": 1, "m": states, "maximum_merge_length": summary["maximum_merge_length"],
        "maximum_value_certified": True, "maximizing_collection_complete": True,
        "rooted_class_count": len(drawings), "ordinary_underlying_shape_count": len(shapes),
        "underlying_grouping_method": "Minimum rooted canonical key over every accessible choice of starting vertex; groups ordinary underlying isomorphism classes without removing any rooted class.",
        "underlying_shapes": [{"index": shapes[key], "canonical_key": key,
                               "canonical_table": [list(row) for row in shape_tables[key]],
                               "shared_positions_svg": shape_positions[key],
                               "member_keys": [record["key"] for record in records if shape_keys[record["key"]] == key]}
                              for key in sorted(shapes)],
        "validation": {"rooted_canonical_tables": True, "table_key_agreement": True,
                       "every_upper_witness_checked_over_all_original_static_masks": True,
                       "global_coverage_and_shortest_proofs_inherited_from_certified_run": True,
                       "pdf_compiled": False, "pdf_visually_inspected": False},
        "sources": provenance,
        "layout_sources": [{"path": str(path), "sha256": sha256(path.read_bytes())}
                           for path in (Path(__file__).resolve(), HERE / "family1_tikz_atlas.py", HERE / "family1_graph_atlas.py")],
        "page_count": len(pages), "pages": pages, "port_labels": port_labels, "drawings": drawings,
        "file_sha256": {name: sha256(data) for name, data in sorted(files.items())},
    }
    files["source-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    # All validation/layout work finishes before the destination is changed.
    output = check_output_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as target:
            target.write(data)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Certified run directory with summary.json and maximizers.jsonl")
    parser.add_argument("--out", required=True, type=Path, help="New or empty destination directory")
    parser.add_argument("--states", type=int, default=7)
    parser.add_argument("--port-labels", choices=("all", "small", "none"), default="all")
    parser.add_argument("--validate-only", action="store_true", help="Check certification, tables, witnesses and destination without authoring files")
    args = parser.parse_args(argv)
    try:
        if args.validate_only:
            summary, records, _ = load_certified_collection(args.input, args.states)
            check_output_directory(args.out)
            print(json.dumps({"validated": True, "m": args.states, "maximum": summary["maximum_merge_length"],
                              "rooted_classes": len(records), "files_authored": 0}))
        else:
            manifest = generate(args.input, args.out, args.states, args.port_labels)
            print(json.dumps({"m": args.states, "rooted_classes": manifest["rooted_class_count"],
                              "pages": manifest["page_count"], "out": str(args.out.resolve())}))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"family1_certified_tikz: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
