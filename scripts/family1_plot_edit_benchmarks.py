#!/usr/bin/env python3
"""Create publication PNG/SVG figures from sealed edit/ranking/filter results.

uv run --no-project --with matplotlib python scripts/family1_plot_edit_benchmarks.py
All completeness statements concern the indicated local growth neighborhoods.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

REPO = Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREEN, GRAY = "#0072B2", "#D55E00", "#009E73", "#6B7280"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "svg.fonttype": "none", "svg.hashsalt": "family1-edit-benchmark-v1",
                     "axes.titleweight": "normal", "savefig.facecolor": "white"})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    try:
        label = path.relative_to(REPO).as_posix()
    except ValueError:
        label = str(path)
    return {"path": label, "sha256": sha(path)}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def pinned_path(item):
    path = Path(item["path"])
    if not path.is_absolute():
        path = REPO / path
    if sha(path) != item["sha256"]:
        raise ValueError(f"source hash mismatch: {path}")
    return path


def one(values, context):
    if len(values) != 1:
        raise ValueError(f"expected one {context}, found {len(values)}")
    return values[0]


def collect_data():
    generation_file = REPO / "results/family1-edit-candidate-benchmark/observations.jsonl"
    seal_file = REPO / "results/family1-edit-candidate-benchmark/generation-seal.json"
    ranking_file = REPO / "results/family1-edit-ranked-candidate-benchmark/observations.jsonl"
    filter_summary = REPO / "results/family1-edit-elimination-complete-m7/summary.json"
    filter_analysis = REPO / "results/family1-edit-elimination-complete-m7/analysis.json"
    observations, seal, ranked = jsonl(generation_file), read(seal_file), jsonl(ranking_file)
    sources = [ref(path) for path in (generation_file, seal_file, ranking_file, filter_summary, filter_analysis)]
    full = []
    for m in range(2, 8):
        for roots in (False, True):
            run = one([row for row in seal["generations"] if row["m"] == m and row["pool"] == "winners"
                       and row["radius"] == 1 and row["seed"] == 1088 and row["root_closure"] == roots], "complete winner growth")
            if not run["native_summary"]["enumeration_complete"]:
                raise ValueError("winner-parent growth run is capped")
            observation = one([row for row in observations if row["run_id"] == run["run_id"] and row["nominal_budget"] == 2048], "winner full-prefix metric")
            metric = observation["edit"]
            if metric["actual_candidates"] != run["native_summary"]["candidate_count"]:
                raise ValueError("winner-parent prefix does not cover the full local set")
            full.append({"m": m, "parents": "winners", "all_roots": roots,
                         "hits": metric["winner_rooted_hits"], "total": metric["winner_rooted_total"],
                         "actual_candidates": metric["actual_candidates"], "run_id": run["run_id"], "local_complete": True})
        observation = one([row for row in observations if row["m"] == m and row["pool"] == "near2"
                           and row["nominal_budget"] == "all_generated"], "complete near-top observation")
        run = one([row for row in seal["generations"] if row["run_id"] == observation["run_id"]], "complete near-top generation")
        if not run["native_summary"]["enumeration_complete"]:
            raise ValueError("near-top complete-growth source is capped")
        candidate_file = pinned_path(run["candidate_file"])
        sources.append(ref(candidate_file))
        candidates = jsonl(candidate_file)
        direct = {row["key"] for row in candidates if row.get("path_ids")}
        known_winners = set(observation["edit"]["winner_keys_found"])
        if len(candidates) != observation["edit"]["actual_candidates"] or len(direct) != run["native_summary"]["root_fixed_candidate_count"]:
            raise ValueError("complete growth direct/root-closure counts disagree")
        total = observation["edit"]["winner_rooted_total"]
        full.extend([{"m": m, "parents": "near2", "all_roots": False, "hits": len(direct & known_winners),
                      "total": total, "actual_candidates": len(direct), "run_id": run["run_id"], "local_complete": True},
                     {"m": m, "parents": "near2", "all_roots": True, "hits": len(known_winners),
                      "total": total, "actual_candidates": len(candidates), "run_id": run["run_id"], "local_complete": True}])
    selected = [row for row in ranked if row["m"] == 7 and row["pool"] == "near2" and row["radius"] == 1
                and row["root_closure"] and row["complete_growth_run"] is False]
    curves = []
    for strategy in ("discovery", "structural", "parent-strata"):
        for budget in (32, 128, 512, 2048):
            rows = [row for row in selected if row["strategy"] == strategy and row["nominal_budget"] == budget]
            if len(rows) != 3 or {row["seed"] for row in rows} != {1088, 2027, 65537}:
                raise ValueError("ranked curve must retain every seed and exclude complete-growth extras")
            curves.append({"strategy": strategy, "nominal_budget": budget, "seeds": [
                {"seed": row["seed"], "hits": row["metrics"]["winner_rooted_hits"],
                 "total": row["metrics"]["winner_rooted_total"], "actual_candidates": row["metrics"]["actual_candidates"]}
                for row in sorted(rows, key=lambda row: row["seed"])]})
    random_rows = [row for row in observations if row["m"] == 7 and row["pool"] == "near2" and row["radius"] == 1
                   and row["root_closure"] and "complete-growth" not in row["run_id"]]
    for budget in (32, 128, 512, 2048):
        rows = [row for row in random_rows if row["nominal_budget"] == budget]
        if len(rows) != 3:
            raise ValueError("matched random baseline missing a seed")
        curves.append({"strategy": "matched-random", "nominal_budget": budget, "seeds": [
            {"seed": row["seed"], "hits": row["fair_random"]["winner_rooted_hits"],
             "total": row["fair_random"]["winner_rooted_total"], "actual_candidates": row["fair_random"]["actual_candidates"]}
            for row in sorted(rows, key=lambda row: row["seed"])]})
    elimination = read(filter_summary)
    analysis = one([row for row in read(filter_analysis)["per_size"] if row["m"] == 7], "m7 filter analysis")
    counts = {"total": elimination["query_count"], "certified_weaker": analysis["eliminated"],
              "unresolved_nonwinners": analysis["unresolved_nonwinners"], "known_winners": analysis["unresolved_winners"],
              "false_eliminations": elimination["false_eliminations"]}
    if counts["total"] != sum(counts[key] for key in ("certified_weaker", "unresolved_nonwinners", "known_winners")):
        raise ValueError("filter partition does not sum to the pool")
    return {"schema": 1, "sources": sources, "full_local_growth": full, "budgeted_m7_rankings": curves,
            "full_m7_filter": counts, "global_graph_enumeration_claimed": False,
            "ranking_truth_loaded_only_after_seal": True,
            "random_sampling": "uniform labelled port tables, accessibility rejection, rooted-class deduplication; not uniform graph classes"}


def save(fig, output, stem):
    fig.savefig(output / f"{stem}.png", dpi=240, bbox_inches="tight", metadata={"Software": "Family1 sealed benchmark plotting"})
    fig.savefig(output / f"{stem}.svg", bbox_inches="tight", metadata={"Date": None, "Creator": "Family1 sealed benchmark plotting"})
    plt.close(fig)


def plot_growth(data, output):
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    fig.subplots_adjust(left=.10, right=.97, bottom=.28, top=.73)
    definitions = [("winners", False, BLUE, "s", "--", "Winner parents · fixed root"),
                   ("winners", True, BLUE, "o", "-", "Winner parents · all accessible roots"),
                   ("near2", False, ORANGE, "s", "--", "Near-top parents · fixed root"),
                   ("near2", True, ORANGE, "o", "-", "Near-top parents · all accessible roots")]
    denominators = {}
    for parents, roots, color, marker, style, label in definitions:
        rows = sorted((row for row in data["full_local_growth"] if row["parents"] == parents and row["all_roots"] == roots), key=lambda row: row["m"])
        x, y = [row["m"] for row in rows], [row["hits"] / row["total"] for row in rows]
        denominators.update({row["m"]: row["total"] for row in rows})
        ax.plot(x, y, style, color=color, marker=marker, linewidth=1.8, markersize=6,
                markerfacecolor="white" if not roots else color, label=label)
        for row, value in zip(rows, y):
            if 0 < value < 1:
                offset = (0, 10) if parents == "near2" else (0, -17 if not roots else 10)
                ax.annotate(f"{row['hits']}/{row['total']}", (row["m"], value), xytext=offset,
                            textcoords="offset points", ha="center", color=color, fontsize=9)
    ax.set(xlim=(1.8, 7.2), ylim=(-.07, 1.08), ylabel="Known maximizing rooted classes recovered")
    ax.set_xticks(range(2, 8), [f"{m}\nN={denominators[m]}" for m in range(2, 8)])
    ax.set_xlabel("Number of states m (N = total known maximizing rooted classes)", labelpad=8)
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="y", alpha=.2)
    fig.suptitle("Winner recall in complete local growth neighborhoods", y=.98, fontsize=14)
    fig.text(.5, .92, "One routing insertion from previous-size seeds; near-top means score gap ≤ 2", ha="center", fontsize=10)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.53, .865), ncol=2, frameon=False, fontsize=9)
    fig.text(.10, .075, "Fixed-root near-top counts come from direct path IDs in the same complete root-closed pools.", fontsize=8.8, color=GRAY)
    fig.text(.10, .035, "Completeness is local to these growth neighborhoods; it is not global graph coverage.", fontsize=8.8, color=GRAY)
    save(fig, output, "complete-local-growth-recall")


def span(values):
    return str(min(values)) if min(values) == max(values) else f"{min(values)}–{max(values)}"


def plot_rankings(data, output):
    fig, ax = plt.subplots(figsize=(8.4, 6.4))
    fig.subplots_adjust(left=.17, right=.96, top=.74, bottom=.39)
    budgets = [32, 128, 512, 2048]
    x = np.arange(4)
    definitions = [("discovery", BLUE, "o", "Native discovery"), ("structural", ORANGE, "s", "Structural"),
                   ("parent-strata", GREEN, "D", "Parent strata"), ("matched-random", GRAY, "x", "Matched labelled random")]
    table_rows, table_labels = [], []
    for strategy, color, marker, label in definitions:
        rows = [one([row for row in data["budgeted_m7_rankings"] if row["strategy"] == strategy and row["nominal_budget"] == budget], "ranking budget") for budget in budgets]
        values = np.array([[seed["hits"] / seed["total"] for seed in row["seeds"]] for row in rows])
        means = values.mean(axis=1)
        line = "--" if strategy == "matched-random" else "-"
        ax.plot(x, means, line, color=color, marker=marker, label=label, linewidth=1.8, markersize=6,
                markerfacecolor="white" if strategy == "discovery" else color, zorder=4 if strategy == "discovery" else 3)
        ax.fill_between(x, values.min(axis=1), values.max(axis=1), color=color, alpha=.12, linewidth=0)
        table_rows.append([span([seed["actual_candidates"] for seed in row["seeds"]]) for row in rows])
        table_labels.append(label)
        if strategy in ("structural", "parent-strata"):
            final_hits = [seed["hits"] for seed in rows[-1]["seeds"]]
            ax.annotate(f"{span(final_hits)}/8", (3, means[-1]), xytext=(-7, 8 if strategy == "parent-strata" else -18),
                        textcoords="offset points", ha="right", color=color, fontsize=9)
    ax.set(xlim=(-.12, 3.13), ylim=(-.04, 1.06), ylabel="Known maximizing rooted classes recovered")
    ax.set_xticks(x, [str(value) for value in budgets])
    ax.set_xlabel("")
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="y", alpha=.2)
    ax.text(0, -.27, "Actual classes at each nominal budget (whole final shape block; range over seeds)", transform=ax.transAxes,
            fontsize=8.5, color=GRAY)
    table = ax.table(cellText=table_rows, rowLabels=table_labels, colLabels=list(map(str, budgets)),
                     cellLoc="center", rowLoc="left", bbox=[0, -.79, 1, .44])
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#D9DDE2")
        cell.set_linewidth(.5)
        if row == 0:
            cell.set_facecolor("#F1F4F7")
    fig.suptitle("Seven-state recall under a fixed generation budget", y=.98, fontsize=14)
    fig.text(.5, .925, "Same near-top, radius-1, root-closed pools; complete-growth extras excluded", ha="center", fontsize=10)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.53, .875), ncol=2, frameon=False, fontsize=9)
    fig.text(.17, .065, "Lines: mean of three sealed seeds. Shading: minimum–maximum, not a confidence interval.", fontsize=8.5, color=GRAY)
    fig.text(.17, .035, "Random prefixes match native-prefix counts; their separate whole-block overshoot is shown.", fontsize=8.5, color=GRAY)
    save(fig, output, "budgeted-m7-ranking-recall")


def plot_filter(data, output):
    counts = data["full_m7_filter"]
    total = counts["total"]
    weaker, missed, winners = (counts[key] for key in ("certified_weaker", "unresolved_nonwinners", "known_winners"))
    surviving = missed + winners
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    fig.subplots_adjust(left=.10, right=.96, bottom=.22, top=.77)
    left = 0
    for value, color in ((weaker, BLUE), (missed, ORANGE), (winners, GREEN)):
        ax.barh(1, value / total, left=left, height=.42, color=color, edgecolor="white", linewidth=.4)
        left += value / total
    ax.barh(0, missed / surviving, height=.42, color=ORANGE, edgecolor="white", linewidth=.4)
    ax.barh(0, winners / surviving, left=missed / surviving, height=.42, color=GREEN, edgecolor="white", linewidth=.4)
    ax.text(0, 1.34, f"{total:,} graphs — complete local pool", fontsize=11)
    ax.text((weaker / total) / 2, 1, f"{weaker:,} certified H ≤ 33\n{100 * weaker / total:.2f}% of the pool", ha="center", va="center", color="white", fontsize=11)
    ax.annotate(f"{surviving:,} not eliminated", xy=((1 + weaker / total) / 2, 1.08), xytext=(.72, 1.48),
                arrowprops={"arrowstyle": "-", "color": GRAY, "lw": .8}, ha="center", fontsize=10, color=GRAY)
    ax.text(0, .34, f"{surviving:,} survivors — conditional zoom", fontsize=11)
    ax.text((missed / surviving) / 2, 0, f"{missed:,} nonmaximizers\nunresolved by this filter", ha="center", va="center", color="white", fontsize=11)
    ax.annotate(f"{winners} known maximizers\n(retrospective labels)", xy=(1 - winners / surviving / 2, -.04), xytext=(.76, -.55),
                arrowprops={"arrowstyle": "-", "color": GREEN, "lw": .9}, ha="center", va="center", color=GREEN, fontsize=10)
    ax.set(xlim=(-.01, 1.015), ylim=(-.8, 1.7))
    ax.axis("off")
    fig.suptitle("Certified elimination in the complete local seven-state pool", y=.98, fontsize=14)
    fig.text(.5, .915, "Short-witness search at length ≤ 33; 128 prefix seeds per graph", ha="center", fontsize=10)
    fig.text(.10, .085, "Ground-truth labels were applied after sealing generation, ranking and query plans.", fontsize=8.8, color=GRAY)
    fig.text(.10, .045, "A filter miss supplies no new lower bound. Graphs outside this local pool are not excluded.", fontsize=8.8, color=GRAY)
    save(fig, output, "complete-m7-elimination")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "output/figures/family1-edit-candidates")
    parser.add_argument("--data", type=Path, help="Reuse a previously frozen plot-data.json without raw candidate files.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = read(args.data) if args.data else collect_data()
    data_path = args.out / "plot-data.json"
    data_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    plot_growth(data, args.out)
    plot_rankings(data, args.out)
    plot_filter(data, args.out)
    images = sorted(args.out.glob("*.png")) + sorted(args.out.glob("*.svg"))
    for path in args.out.glob("*.svg"):
        ET.parse(path)
    manifest = {"schema": 1, "script": ref(Path(__file__)), "data": ref(data_path), "sources": data["sources"],
                "artifacts": [ref(path) for path in images], "all_svg_xml_validated": True,
                "matplotlib_version": matplotlib.__version__, "python_version": platform.python_version(),
                "all_completeness_claims_are_local": True, "retrospective_truth_labels_explicit": True}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figures": len(images) // 2, "artifacts": len(images), "out": str(args.out), "svg_valid": True}))


if __name__ == "__main__":
    main()
