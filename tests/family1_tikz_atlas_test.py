#!/usr/bin/env python3
"""Verify reusable TikZ edges, honest captions, all ties, and atlas pagination."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("family1_tikz_atlas", REPO / "scripts/family1_tikz_atlas.py")
tikz = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tikz)


def write_fixture(directory):
    directory.mkdir(parents=True)
    records = []
    for m in range(1, 21):
        table = [[(state + 1) % m] * 2 for state in range(m)]
        records.append({"m": m, "canonical_table": table, "key": tikz.key_for(table),
                        "status": "exact", "lower_bound": 1, "upper_bound": 1,
                        "merge_length": 1, "witness": ["0", "1"]})
    # Seven different size20 tables share only the certified lower bound H>=1.
    # More than six must create a continuation page rather than lose a tie.
    for offset in range(1, 7):
        table = [[(state + 1) % 20, (state + offset + 1) % 20] for state in range(20)]
        records.append({"m": 20, "canonical_table": table, "key": tikz.key_for(table),
                        "status": "lower-bound", "lower_bound": 1, "upper_bound": None,
                        "merge_length": None, "witness": None})
    (directory / "champions.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    (directory / "summary.json").write_text(json.dumps({"sizes": [
        {"m": 1, "maximum_value_certified": True, "maximizing_collection_complete": True,
         "global_maximum": 1, "best_lower_bound_ties": 1},
        {"m": 20, "maximum_value_certified": False, "maximizing_collection_complete": False,
         "global_maximum": None, "best_lower_bound_ties": 7}]}), encoding="utf-8")
    return records


def test_geometry():
    edge = {"kind": "quadratic", "points": [(0, 0), (2, 4), (6, 0)]}
    cubic = tikz.cubic_points(edge)
    for t in (0, .1, .5, .85, 1):
        for axis in (0, 1):
            quadratic_value = (1 - t) ** 2 * edge["points"][0][axis] + 2 * (1 - t) * t * edge["points"][1][axis] + t ** 2 * edge["points"][2][axis]
            cubic_value = sum(point[axis] * weight for point, weight in zip(cubic, ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3)))
            assert math.isclose(quadratic_value, cubic_value, abs_tol=1e-12)


def exercise(root, pdflatex=None):
    fixture = root / "input"
    expected = write_fixture(fixture)
    output = root / "atlas"
    manifest = tikz.generate([fixture], output, manual_directory=None, max_panels=6)
    assert manifest["graphs"] == len(expected) == 26
    assert manifest["page_count"] == 21
    assert [page["m"] for page in manifest["pages"]] == list(range(1, 21)) + [20]
    all_keys = [key for page in manifest["pages"] for key in page["graph_keys"]]
    assert len(all_keys) == len(expected)
    assert manifest["sizes"][0]["maximum_value_certified"] is True
    assert manifest["sizes"][19]["maximum_value_certified"] is False
    for drawing in manifest["drawings"]:
        text = (output / drawing["snippet"]).read_text(encoding="utf-8")
        edges = [tuple(map(int, edge)) for edge in re.findall(r"^% edge (\d+) (\d+) (\d+)\s*$", text, re.MULTILINE)]
        wanted = {(source, port, target) for source, row in enumerate(drawing["canonical_table"]) for port, target in enumerate(row)}
        assert len(edges) == drawing["m"] * 2 and set(edges) == wanted
        assert len(re.findall(r"^% state \d+$", text, re.MULTILINE)) == drawing["m"]
        assert r"double,double distance" in text and "dash pattern" in text
        assert text.count(".. controls") == 2 * drawing["m"]
        assert text.count(r"\node[f1atlas label]") == (2 * drawing["m"] if drawing["m"] <= 6 else 0)
        assert "loop above left" not in text and "loop above right" not in text
        assert "Global maximum" not in text and "H(G)" not in text
        assert (output / drawing["standalone"]).is_file()
    document = (output / "atlas.tex").read_text()
    assert document.count(r"\clearpage") == 20
    assert "The global maximum remains unresolved." in document
    assert "The maximum merge length is proved to be $1$" in document
    assert "snippets/" in document and "(a)" in document
    assert "key=" not in document
    for record in (expected[0], expected[19]):
        variants = {mode: tikz.tikz_picture(record, mode)[0] for mode in ("all", "small", "none")}
        draw_lines = lambda text: [line for line in text.splitlines() if line.startswith(r"\draw") or line.startswith("% edge") or line.startswith("% state")]
        assert draw_lines(variants["all"]) == draw_lines(variants["small"]) == draw_lines(variants["none"])
        assert variants["all"].count(r"\node[f1atlas label]") == 2 * record["m"]
        assert r"\node[f1atlas label]" not in variants["none"]
    # Manual pictures are copied, verified by their ten outgoing-port comments,
    # and left unchanged in their original repository directory.
    manual_directory = REPO / "figures/family1-m5"
    if (manual_directory / "source-manifest.json").is_file():
        hashes = {path.name: tikz.digest(path) for path in manual_directory.glob("*.tex")}
        manuals = tikz.manual_map(manual_directory)
        assert len(manuals) == 5
        assert hashes == {path.name: tikz.digest(path) for path in manual_directory.glob("*.tex")}
    if pdflatex is not None:
        source = output / "standalone/m20-graph-01.tex"
        result = subprocess.run([str(pdflatex), "-interaction=nonstopmode", "-halt-on-error", source.name],
                                cwd=source.parent, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, (result.stdout[-8000:], result.stderr)
        assert source.with_suffix(".pdf").is_file()
        assert "Overfull" not in source.with_suffix(".log").read_text(errors="replace")
        print(f"Native pdfLaTeX compiled a20-state standalone graph: {source.with_suffix('.pdf')}")
    print("TikZ source checks passed: exact node/port preservation, Bézier conversion, double root, grayscale ports, certificate-aware captions, all ties, 20sizes and continuation pages.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--pdflatex", type=Path)
    args = parser.parse_args()
    test_geometry()
    if args.work_dir:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        exercise(args.work_dir.resolve(), args.pdflatex.resolve() if args.pdflatex else None)
    else:
        with tempfile.TemporaryDirectory(prefix="family1-tikz-") as temporary:
            exercise(Path(temporary), args.pdflatex.resolve() if args.pdflatex else None)
    current = REPO / "results/family1-atlas-current"
    ancestry = REPO / "results/family1-ancestry-through7/summary.json"
    if current.is_dir() and ancestry.is_file():
        with tempfile.TemporaryDirectory(prefix="family1-atlas-current-") as temporary:
            output = Path(temporary)
            manifest = tikz.generate([current], output, REPO / "figures/family1-m5", 6, "small",
                                     REPO / "figures/family1-m7", True, ancestry,
                                     REPO / "results/family1-edit-distance-through7/summary.json")
            assert manifest["graphs"] == 33 and manifest["page_count"] == 24
            seven = [page for page in manifest["pages"] if page.get("m") == 7]
            assert [len(page["graph_keys"]) for page in seven] == [4, 4]
            assert [row["displayed_graphs"] for row in manifest["sizes"][:7]] == [1, 1, 2, 1, 5, 2, 8]
            assert all(row["maximizing_collection_complete"] for row in manifest["sizes"][:7])
            assert all(not row["maximum_value_certified"] for row in manifest["sizes"][7:])
            document = (output / "atlas.tex").read_text()
            assert "$3,3,3,1,3,3,3,3$" in document and "$1,2$" in document
            assert "no chain of maximizing rooted graphs" in document
            for drawing in manifest["drawings"]:
                if drawing["m"] in (5, 7):
                    original = Path(drawing["layout_source"]["source"])
                    assert tikz.digest(original) == drawing["layout_source"]["sha256"]
                    assert (output / drawing["snippet"]).read_text() == original.read_text(encoding="utf-8-sig")
                if drawing["m"] >= 8:
                    assert drawing["lower_bound"] == 34 and drawing["upper_bound"] is None
                    assert drawing["construction"]["all_vertices_accessible"]
                    positions = tikz.construction_positions(drawing)
                    assert len(positions) == drawing["m"] and len(set(positions)) == drawing["m"]
                text = (output / drawing["snippet"]).read_text()
                edges = [tuple(map(int, edge)) for edge in re.findall(r"^% edge (\d+) (\d+) (\d+)\s*$", text, re.MULTILINE)]
                assert sorted(edges) == sorted((s, p, t) for s, row in enumerate(drawing["canonical_table"]) for p, t in enumerate(row))
            print("Current atlas: all20 certified winners,13 constructive bounds, exact tables, preserved m5/m7 drawings, all consecutive-size ancestry, balanced4+4 pagination verified.")


if __name__ == "__main__":
    main()
