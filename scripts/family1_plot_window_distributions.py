#!/usr/bin/env python3
"""Plot complete finite common-window gain distributions and audit native data.

Reproduce with uv run --with matplotlib python scripts/family1_plot_window_distributions.py.
Add --native-exe PATH to refresh native comparisons and the m=20 distribution.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[1]
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#009E73"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
    "axes.spines.right": False, "svg.fonttype": "none", "axes.titleweight": "normal",
    "savefig.facecolor": "white",
})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def display_path(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def fixed_key(table):
    return "".join(f"{target:02d}" for row in table for target in row)


def pointwise_distribution(table, words, windows):
    """Independent exhaustive integer-state simulation, one array lane per mask."""
    table = np.asarray(table, dtype=np.uint8)
    masks = np.arange(1 << len(table), dtype=np.uint32)

    def run(word, state=None):
        state = np.zeros(len(masks), dtype=np.uint8) if state is None else state.copy()
        for symbol in word:
            port = int(symbol) ^ ((masks >> state) & 1)
            state = table[state, port]
        return state

    left, right = map(run, words)
    initial = int(np.count_nonzero(left == right))
    scores = [int(np.count_nonzero(run(window, left) == run(window, right))) for window in windows]
    return initial, scores


def refresh_native(args, cases):
    args.native_out.mkdir(parents=True, exist_ok=True)
    definitions = [case for case in cases if case["window_k"] <= 6]
    family = {row["m"]: row for row in jsonl(REPO / "results/family1-circulant-family/champions.jsonl")}
    definitions.append({
        "label": "m20-literal-core-5-5-k4", "m": 20, "canonical_table": family[20]["canonical_table"],
        "initial_words": ["0000011111", "1111100000"], "window_k": 4, "common_suffix_stage": 0,
    })
    results = []
    for case in definitions:
        directory = args.native_out / case["label"]
        command = [str(args.native_exe), "--graph", fixed_key(case["canonical_table"]),
                   "--out", str(directory), "--mode", "distribution",
                   "--first-prefix", case["initial_words"][0], "--second-prefix", case["initial_words"][1],
                   "--window-k", str(case["window_k"])]
        if (directory / "run.json").exists():
            command.append("--resume")
        process = subprocess.run(command, cwd=REPO, text=True, capture_output=True, timeout=180)
        if process.returncode:
            raise RuntimeError(f"{case['label']}: {process.stderr}")
        result_path = directory / "result.json"
        native = json.loads(result_path.read_text(encoding="utf-8-sig"))
        distribution = native["window_distribution"]
        ordered = sorted(distribution["windows"], key=lambda row: row["window"])
        windows = [row["window"] for row in ordered]
        assert distribution["complete"] and len(windows) == 1 << case["window_k"]
        assert len(set(windows)) == len(windows)
        assert all(len(word) == case["window_k"] and not set(word) - {"0", "1"} for word in windows)
        initial, scores = pointwise_distribution(case["canonical_table"], case["initial_words"], windows)
        assert distribution["mask_count"] == 1 << case["m"]
        assert distribution["initial_remaining"] == (1 << case["m"]) - initial
        assert [row["merged_count"] for row in ordered] == scores
        drops = [score - initial for score in scores]
        assert [row["drop"] for row in ordered] == drops
        histogram = Counter(drops)
        assert {row["drop"]: row["count"] for row in distribution["histogram"]} == histogram
        if "drop_vector" in case:
            assert dict(zip(windows, drops)) == dict(zip(case["windows"], case["drop_vector"]))
            for native_field, reference_field in (("min_drop", "min"), ("max_drop", "max"),
                                                  ("mean_drop", "mean"), ("median_drop", "median"),
                                                  ("stddev_drop", "population_stddev")):
                assert math.isclose(distribution[native_field], case["drop_stats"][reference_field], rel_tol=1e-11, abs_tol=1e-11)
        permutation_masks = []
        for mask in native.get("permutation_masks") or []:
            for symbol in (0, 1):
                targets = [case["canonical_table"][state][symbol ^ ((mask >> state) & 1)] for state in range(case["m"])]
                assert len(set(targets)) == case["m"]
            permutation_masks.append(mask)
        if case["m"] <= 7:
            expected = [mask for mask in range(1 << case["m"])
                        if all(len({case["canonical_table"][state][symbol ^ ((mask >> state) & 1)]
                                    for state in range(case["m"])}) == case["m"] for symbol in (0, 1))]
            assert permutation_masks == expected
        assert native["permutation_mask_count"] == len(permutation_masks)
        results.append({
            "label": case["label"], "m": case["m"], "initial_words": case["initial_words"],
            "window_k": case["window_k"], "initial_S": initial, "total_masks": 1 << case["m"],
            "remaining_coordinates": distribution["initial_remaining"],
            "windows": windows, "drop_vector": drops, "scores_after": scores,
            "normalized_drop_vector": [drop / distribution["initial_remaining"] for drop in drops] if distribution["initial_remaining"] else None,
            "independent_pointwise_all_mask_comparison_passed": True,
            "saved_scalar_reference_comparison_passed": "drop_vector" in case,
            "native_result": native,
            "artifact": {"path": display_path(result_path), "sha256": sha(result_path)},
            "command": command,
        })
        print(f"Native audit: {case['label']}, {1 << case['m']} masks, {len(windows)} windows", flush=True)
    report = {
        "schema": 1, "native_executable": {"path": display_path(args.native_exe), "sha256": sha(args.native_exe)},
        "generator": {"path": display_path(__file__), "sha256": sha(__file__)},
        "reference_cases": {"path": display_path(args.cases), "sha256": sha(args.cases)},
        "cases": results, "all_pointwise_comparisons_passed": True,
        "saved_reference_cases_compared": sum(case["saved_scalar_reference_comparison_passed"] for case in results),
        "native_window_limit": 6, "scalar_only_extra_case": "m7-class1-stage0-k8",
        "scope": "Exact finite endpoint-agreement distributions; no graph score lower bound or generic concentration claim.",
    }
    args.native_report.parent.mkdir(parents=True, exist_ok=True)
    args.native_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def save(figure, args, name, manifest):
    figure.savefig(args.out / f"{name}.png", dpi=220, bbox_inches="tight")
    figure.savefig(args.out / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(figure)
    for suffix in ("png", "svg"):
        path = args.out / f"{name}.{suffix}"
        manifest["artifacts"].append({"path": display_path(path), "sha256": sha(path)})


def ecdf(axis, values, label, color):
    values, counts = np.unique(np.asarray(values), return_counts=True)
    cumulative = np.cumsum(counts) / counts.sum()
    axis.step(np.r_[0, values, 1], np.r_[0, cumulative, 1], where="post", label=label, color=color, lw=1.8)


def plots(args, cases, native):
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": 1, "script_sha256": sha(__file__), "source_sha256": sha(args.cases), "artifacts": []}
    if native:
        manifest["native_report"] = {"path": display_path(args.native_report), "sha256": sha(args.native_report)}
    seven = [case for case in cases if case["m"] == 7 and case["window_k"] == 4]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6.8), sharex=True, sharey=True, layout="constrained")
    for index, axis in enumerate(axes.flat, 1):
        group = [case for case in seven if case["label"].startswith(f"m7-class{index}-")]
        early, late = min(group, key=lambda case: case["common_suffix_stage"]), max(group, key=lambda case: case["common_suffix_stage"])
        for case, color in ((early, BLUE), (late, ORANGE)):
            ecdf(axis, case["normalized_drop_vector"],
                 f"t={case['common_suffix_stage']}, R={case['remaining_coordinates']}", color)
        axis.set(xlim=(0, 1), ylim=(0, 1.02), title=f"({chr(96 + index)})  ordinal {early['ordinal']}")
        axis.set_xticks([0, .25, .5, .75, 1])
        axis.grid(alpha=.18)
        axis.legend(loc="lower right", fontsize=8, frameon=True, facecolor="white", framealpha=.9)
    fig.supxlabel(r"Gain as a fraction of currently unequal coordinates, $\Delta/R$")
    fig.supylabel("Fraction of windows with gain at most x")
    fig.suptitle("Exact four-letter gain distributions across seven-state maximizers\nAll 128 static masks and all 16 windows; stages follow saved common suffixes", fontsize=13)
    save(fig, args, "m7-early-late-ecdf", manifest)

    stages = [0, 8, 16, 24]
    means = np.full((8, 4), np.nan)
    zeros = means.copy()
    remaining = np.full((8, 4), -1)
    for case in seven:
        row = int(case["label"].split("-")[1].removeprefix("class")) - 1
        column = stages.index(case["common_suffix_stage"])
        means[row, column] = case["normalized_drop_stats"]["mean"]
        zeros[row, column] = case["drop_stats"]["zero_count"] / case["window_count"]
        remaining[row, column] = case["remaining_coordinates"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.4), layout="constrained")
    for axis, array, title, cmap in zip(axes, (means, zeros), ("Mean normalized gain", "Fraction of zero-gain windows"), ("Blues", "Oranges")):
        colormap = plt.get_cmap(cmap).copy()
        colormap.set_bad("#eeeeee")
        image = axis.imshow(array, vmin=0, vmax=1, cmap=colormap, aspect="auto")
        axis.set(xticks=range(4), xticklabels=stages, yticks=range(8), yticklabels=[f"({chr(97 + index)})" for index in range(8)],
                 xlabel="Letters appended along the saved suffix", title=title)
        for row in range(8):
            for column in range(4):
                value = array[row, column]
                text = "—" if np.isnan(value) else f"{value:.3f}" + (f"\nR={remaining[row, column]}" if array is means else "")
                axis.text(column, row, text, ha="center", va="center", fontsize=8,
                          color="white" if not np.isnan(value) and value > .63 else "#17252a")
        fig.colorbar(image, ax=axis, shrink=.9, pad=.025)
    fig.suptitle("Family and stage dependence of exact four-letter gains", fontsize=13)
    save(fig, args, "m7-stage-summaries", manifest)

    plateau = [next(case for case in cases if case["label"] == f"plateau-k{k}") for k in (1, 2, 4)]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.5), sharey=True, layout="constrained")
    for axis, case, color in zip(axes, plateau, (BLUE, ORANGE, GREEN)):
        counts = [sum(value == target for value in case["normalized_drop_vector"]) for target in (0, 1)]
        fractions = np.asarray(counts) / case["window_count"]
        axis.bar([0, 1], fractions, width=.58, color=color)
        for x, count, fraction in zip((0, 1), counts, fractions):
            axis.text(x, fraction + .025, f"{count}/{case['window_count']}", ha="center", va="bottom")
        axis.set(xticks=[0, 1], xticklabels=["No new agreement", "All remaining agree"], ylim=(0, 1.13), title=f"k={case['window_k']}")
        axis.tick_params(axis="x", labelsize=8)
        axis.grid(axis="y", alpha=.18)
    axes[0].set_ylabel("Fraction of all windows")
    fig.suptitle(r"Neutral first steps can be necessary: $(u,v)=(01,10)$, $S=4/8$", fontsize=13)
    save(fig, args, "neutral-plateau", manifest)

    if native:
        case = next(case for case in native["cases"] if case["m"] == 20)
        fig, axis = plt.subplots(figsize=(10.5, 4), layout="constrained")
        axis.bar(range(len(case["windows"])), case["normalized_drop_vector"], color=BLUE, width=.72)
        axis.set(xticks=range(len(case["windows"])), xticklabels=case["windows"],
                 xlabel="Common four-letter window", ylabel=r"Normalized gain, $\Delta/R$")
        axis.tick_params(axis="x", rotation=45, labelsize=8)
        axis.grid(axis="y", alpha=.18)
        fig.suptitle(r"Literal twenty-state circulant, $(u,v)=(0^5 1^5,1^5 0^5)$"
                     + f"\nAll 1,048,576 masks; initial S={case['initial_S']:,}, R={case['remaining_coordinates']:,}", fontsize=12)
        save(fig, args, "m20-literal-all-windows", manifest)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.out), "artifacts": len(manifest["artifacts"])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO / "results/family1-window-distributions/cases.jsonl")
    parser.add_argument("--out", type=Path, default=REPO / "output/figures/family1-window-distributions")
    parser.add_argument("--native-exe", type=Path)
    parser.add_argument("--native-out", type=Path, default=REPO / "out/family1-window-native-v2")
    parser.add_argument("--native-report", type=Path, default=REPO / "results/family1-window-distributions/native-v2.json")
    args = parser.parse_args()
    for name in ("cases", "out", "native_exe", "native_out", "native_report"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    cases = jsonl(args.cases)
    for case in cases:
        assert len(case["windows"]) == len(case["drop_vector"]) == 1 << case["window_k"]
        assert sum(case["drop_histogram"].values()) == case["window_count"]
        assert all(0 <= value <= case["remaining_coordinates"] for value in case["drop_vector"])
    native = refresh_native(args, cases) if args.native_exe else (
        json.loads(args.native_report.read_text()) if args.native_report.exists() else None)
    plots(args, cases, native)


if __name__ == "__main__":
    main()
