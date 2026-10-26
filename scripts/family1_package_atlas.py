#!/usr/bin/env python3
"""Package reusable TikZ, all tables, and the accompanying edit certificates."""
from __future__ import annotations

import json
import argparse
from pathlib import Path
import zipfile


REPO = Path(__file__).resolve().parents[1]


def individual_pdfs(repo, legacy_rooted=False):
    if legacy_rooted:
        directories = [repo / "output/pdf/family1-atlas/individual"]
    else:
        # Keep earlier compiled plates available, but prefer a fresh build from
        # build-family1-atlas.ps1 -Individual when both directories exist.
        directories = [repo / "output/pdf/family1-grouped-atlas/standalone",
                       repo / "output/pdf/family1-atlas/grouped-individual"]
    by_name = {}
    for directory in directories:
        for path in sorted(directory.glob("*.pdf")):
            by_name[path.name] = path
    return [by_name[name] for name in sorted(by_name)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-rooted", action="store_true", help="Package the preserved 33-drawing rooted presentation")
    parser.add_argument("--output", type=Path, default=REPO / "output/pdf/family1-atlas/family1-atlas-tikz.zip",
                        help="Destination ZIP; compiled picture inputs are still read from the repository output directories")
    args = parser.parse_args()
    source = REPO / ("figures/family1-atlas" if args.legacy_rooted else "figures/family1-grouped-atlas")
    output = args.output
    manifest = json.loads((source / "source-manifest.json").read_text())
    entries = {str(path.relative_to(source)).replace("\\", "/"): path
               for path in source.rglob("*") if path.is_file() and path.suffix in (".tex", ".json", ".jsonl", ".md")}
    folders = ("family1-atlas-current", "family1-atlas-m8-update", "family1-ancestry-through7", "family1-edit-distance-through7",
               "family1-edit-priority", "family1-circulant-family", "family1-circulant-manuscript-reference") if args.legacy_rooted else (
               "family1-grouped-atlas", "family1-m8-estimates")
    for folder in folders:
        directory = REPO / "results" / folder
        for path in directory.rglob("*"):
            if path.is_file():
                entries[f"data/{folder}/{path.relative_to(directory).as_posix()}"] = path
    entries["data/historical-larger-graph-observations.jsonl"] = REPO / "results/family1-through20/larger-graph-observations.jsonl"
    entries["docs/family1-graph-edits.md"] = REPO / "docs/family1-graph-edits.md"
    entries["docs/family1-atlas.md"] = REPO / "docs/family1-atlas.md"
    if not args.legacy_rooted:
        entries["docs/family1-grouped-atlas.md"] = REPO / "docs/family1-grouped-atlas.md"
        entries["README.md"] = REPO / "results/family1-grouped-atlas/README.md"
    for name in ("family1-edit-priority.md", "family1-neighbor-search.md", "family1-circulant-comparison.md"):
        entries[f"docs/{name}"] = REPO / "docs" / name
    for path in individual_pdfs(REPO, args.legacy_rooted):
        entries[f"individual-pdf/{path.name}"] = path
    candidate = REPO / ("output/pdf/family1-m8-search" if args.legacy_rooted else "output/pdf/family1-m8-active-best")
    for path in sorted(candidate.glob("*")):
        if path.is_file() and path.suffix.lower() in (".pdf", ".tex", ".json", ".md"):
            entries[f"m8-candidate/{path.name}"] = path
    expected_graphs, expected_pages = (33, 24) if args.legacy_rooted else (26, 21)
    if len(manifest["drawings"]) != expected_graphs or manifest["page_count"] != expected_pages:
        raise ValueError("unexpected current atlas scope")
    if not args.legacy_rooted:
        assert manifest["certified_rooted_classes"] == 20 and manifest["certified_ordinary_shapes"] == 13
        assert manifest["all_edges_solid"] and manifest["port_labels"] == "none"
    for path in entries.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, path in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
        assert "atlas.tex" in package.namelist()
        assert sum(name.startswith("snippets/") for name in package.namelist()) == expected_graphs
    print(json.dumps({"zip": str(output), "files": len(entries), "bytes": output.stat().st_size}))


if __name__ == "__main__":
    main()
