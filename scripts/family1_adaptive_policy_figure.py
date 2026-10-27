#!/usr/bin/env python3
"""Draw the controlled m7 comparison from its published full-pool audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]


def ref(path):
    path = path.resolve()
    return {"path": path.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "results/family1-adaptiveness-20261026/policy/m7/forced-factorial.csv")
    parser.add_argument("--out", type=Path, default=REPO / "output/figures/family1-adaptiveness/policy.svg")
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.input.open()))
    wanted = [
        "keep-parents/keep-finder",
        "broaden-parents/keep-finder",
        "keep-parents/total-c2-k2+permutation-c2-k4",
        "broaden-parents/total-c2-k2+permutation-c2-k4",
    ]
    selected = [next(row for row in rows if row["initial_pool"] == "winners-fixedroot"
                     and row["action"] == action) for action in wanted]
    assert all(row["forced_factorial"] == "True" and row["m"] == "7" for row in selected)
    labels = ["Baseline\njoint k=2", "Edit only\njoint k=2", "Finder only\njoint k=2 + 4/P", "Both\njoint k=2 + 4/P"]
    colors = ["#75889a", "#21918c", "#e3a449", "#6f5d95"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "family1-adaptive-policy"})
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.5))
    fig.suptitle("m=7: edit coverage and pair-finder quality are different problems", fontsize=15)
    cases = [int(row["unique_candidates"]) for row in selected]
    winners = [int(row["true_winners_in_pool"]) for row in selected]
    misses = [int(row["unresolved"]) for row in selected]
    false = [int(row["reference_cutoff_false_survivors"]) for row in selected]
    nodes = [int(row["expanded_nodes"]) for row in selected]
    panels = [
        (axes[0, 0], winners, "True champions present in candidate pool (of 8)", [f"{n}/8\n{c:,} candidates" for n, c in zip(winners, cases)]),
        (axes[0, 1], [100 * n / c for n, c in zip(misses, cases)], "Queries with no verified pair (%)", [f"{n:,} / {c:,}" for n, c in zip(misses, cases)]),
        (axes[1, 0], false, "Nonchampions surviving the verified-upper cutoff", [f"{n:,}" for n in false]),
        (axes[1, 1], [n / 1e6 for n in nodes], "Finder work (million node expansions)", [f"{n / 1e6:.2f}" for n in nodes]),
    ]
    for ax, values, title, annotations in panels:
        bars = ax.bar(range(4), values, color=colors, width=0.62)
        ax.set_title(title, fontsize=11, loc="left", pad=14)
        ax.set_xticks(range(4), labels, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        for bar, note in zip(bars, annotations):
            ax.annotate(note, (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 5), textcoords="offset points", ha="center", va="bottom", fontsize=9)
        ax.set_ylim(0, max(values) * 1.3)
    axes[0, 0].set_ylim(0, 10.7)
    axes[0, 0].set_yticks([0, 2, 4, 6, 8])
    axes[0, 1].set_ylim(0, 118)
    fig.text(0.06, 0.055,
             "Forced comparisons; the original crowding gate did not fire. All candidates were tested.\n"
             "c=2 (14 planned starts), beam 1, max length 80; refinement retains min upper from k=2/total and k=4/P.\n"
             "Survive iff no pair or upper >= 34 (exhaustive reference k=N/A, used after queries). Work charges both runs.",
             fontsize=9, linespacing=1.6)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.20, hspace=0.45, wspace=0.25)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, metadata={"Date": None}, facecolor="white")
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.preview, dpi=120, facecolor="white")
    plt.close(fig)
    manifest = {"source": ref(args.input), "generator": ref(Path(__file__)), "output": ref(args.out),
                "data": selected, "generation_k": None, "finder_joint_ks": [2, 4],
                "figure_scope": "forced controlled comparison, candidate coverage is not pair-finder success"}
    args.out.with_suffix(".json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "joint_ks": [2, 4], "source_rows": len(selected)}))


if __name__ == "__main__":
    main()
