#!/usr/bin/env python3
"""Publish the complete new-finder calibration, broader audit and paired figures."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

import family1_near_benchmark as audit
import hard_pair_witness_figure as drawing

REPO = Path(__file__).resolve().parents[1]


def ref(path):
    path = path.resolve()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def check_run(folder):
    summary = json.loads((folder / "summary.json").read_text())
    seal = json.loads((folder / "query-seal.json").read_text())
    rows = audit.rows(folder / "records.jsonl")
    assert ref(folder / "records.jsonl")["sha256"] == summary["records"]["sha256"] == seal["records"]["sha256"]
    assert len(rows) == summary["cases"] and seal["all_cases_queried"]
    checks = sum(audit.replay(row) for row in rows if row["upper_bound"] is not None)
    return rows, summary, checks


def comparison(experiments, calibration, calibration_rows, truth):
    values, raw_rows = [], []
    for name in ["prefix", "prefix-wide", "prefix-deep"]:
        folder = experiments / name
        summary = json.loads((folder / "summary.json").read_text())
        manifest = json.loads((folder / "manifest.json").read_text())
        native_rows = audit.rows(folder / "records.jsonl")
        for item in summary["analysis"]:
            selected = [row for row in native_rows if row["strategy"] == item["configuration"]["id"]]
            values.append({"source": name, "strategy": item["configuration"]["id"],
                           "joint_k": item["configuration"]["k"], "beam": item["configuration"]["beam"],
                           "prefix_depth": manifest["fixed"]["prefix_depth"],
                           "prefix_pairs": item["configuration"]["prefix_pairs"], "cases": item["cases"],
                           "seed_ranking": "canonical",
                           "found": item["found"], "matches_H": item["exact"], "within_two": item["within_two"],
                           "within_one": sum(row["upper_bound"] is not None
                               and row["upper_bound"] - truth[row["m"], row["key"]] <= 1 for row in selected),
                           "maximum_gap": item["max_gap"], "joint_nodes": item["nodes"]})
        for row in native_rows:
            if row["upper_bound"] is not None:
                trace = drawing.scalar_trace(row["witness"], drawing.family1_family(row["canonical_table"]))
                assert trace == row["witness_metric_trace"]
            raw_rows.append({"experiment": name, "strategy": row["strategy"], "m": row["m"], "key": row["key"],
                             "k": row["k"], "beam": row["beam_width"], "upper": row["upper_bound"],
                             "first": row["witness"][0] if row["upper_bound"] is not None else "",
                             "second": row["witness"][1] if row["upper_bound"] is not None else "",
                             "D_trace": json.dumps(row["witness_metric_trace"], separators=(",", ":")),
                             "joint_nodes": row["expanded_nodes"]})
    ranking = calibration.get("seed_ranking", "full")
    strategy = {"full": "exact24 + full-D scored seeds", "portfolio": "exact24 + full-D/common-distance portfolio",
                "common-max": "exact24 + common maximum distance", "common-sum": "exact24 + common sum distance"}[ranking]
    values.append({"source": "final-calibration", "strategy": strategy,
                   "joint_k": calibration["configured_joint_k"], "beam": 16, "prefix_depth": 20, "prefix_pairs": 512,
                   "seed_ranking": ranking,
                   "cases": calibration["cases"], "found": calibration["found"],
                   "matches_H": calibration["optimal_pairs"], "within_two": calibration["within_two"],
                   "within_one": sum(row["upper_bound"] is not None
                       and row["upper_bound"] - truth[row["m"], row["key"]] <= 1 for row in calibration_rows),
                   "maximum_gap": calibration["maximum_gap_if_found"], "joint_nodes": calibration["expanded_nodes"]})
    return values, raw_rows


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def chart(out, values):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    selected = [
        next(row for row in values if row["strategy"] == "k4-b1-permutation-p128" and row["source"] == "prefix"),
        next(row for row in values if row["strategy"] == "k4-b4-permutation-p1024" and row["source"] == "prefix"),
        next(row for row in values if row["strategy"] == "k4-b64-permutation-p128" and row["source"] == "prefix-wide"),
        values[-1],
    ]
    labels = ["Canonical starts\nk=4, B=1, 128 starts", "Canonical starts\nk=4, B=4, 1,024 starts",
              "Canonical starts\nk=4, B=64, 128 starts", "New hybrid\nk=4, B=16, 512/ranking"]
    plt.rcParams["svg.hashsalt"] = "family1-near-calibration"
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    for offset, field, label, color in [(-0.25, "found", "Pair found", "#8a9baa"),
                                        (0, "within_one", "L <= H+1", "#258c89"),
                                        (0.25, "matches_H", "L = H", "#66558c")]:
        ax.bar([i + offset for i in range(4)], [row[field] for row in selected], width=0.23, label=label, color=color)
    ax.set_xticks(range(4), labels, fontsize=9)
    ax.set_ylim(0, 22); ax.set_yticks([0, 5, 10, 15, 20]); ax.set_ylabel("Certified winner cases (20 total)")
    ax.set_title("Deterministic Family 1 winner calibration through m=7", loc="left", pad=14)
    ax.legend(loc="upper center", ncol=3, frameon=False)
    ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="y", alpha=0.18); ax.set_axisbelow(True)
    fig.text(0.08, 0.04, "Every result stores both words and full D traces. New hybrid exact fallback: depth 24, 256 MiB, k=N/A.\n"
             "Development calibration is not a universal error bound; m=7 outliers remain, and m=8 does not improve the prior upper.", fontsize=9)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.22)
    fig.savefig(out / "quality.svg", metadata={"Date": None}, facecolor="white")
    fig.savefig(out / "quality-preview.png", dpi=120, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiments", type=Path, default=REPO / "out/family1-finder-strategies-20261026")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-finder-strategies-20261026/near")
    parser.add_argument("--gallery", type=Path, default=REPO / "output/figures/family1-near-calibration")
    parser.add_argument("--suffix", default="", help="Production directory suffix, e.g. -portfolio")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True); args.gallery.mkdir(parents=True, exist_ok=True)
    truth, prior_uppers = {}, {}
    truth_paths = [REPO / "results/family1-m1-m6/maximizers.jsonl", REPO / "results/family1-m7/maximizers.jsonl",
                   REPO / "results/family1-neighbor-seeds/near-top.jsonl"]
    prior_reference_checks = 0
    for path in truth_paths:
        for row in audit.rows(path):
            identity = len(row["canonical_table"]), audit.key(row["canonical_table"])
            if row["status"] == "exact":
                if identity in truth: assert truth[identity] == row["merge_length"]
                truth[identity] = row["merge_length"]
            prior_uppers[identity] = row.get("upper_bound", row.get("merge_length"))
            if row.get("witness"):
                drawing.scalar_trace(row["witness"], drawing.family1_family(row["canonical_table"]))
                assert len(row["witness"][0]) == prior_uppers[identity]
                prior_reference_checks += 1 << identity[0]
    production = {name: args.experiments / (name + args.suffix)
                  for name in ["final-calibration", "final-frontier343", "final-m8", "final-native"]}
    calibration, calibration_summary, cchecks = check_run(production["final-calibration"])
    frontier, frontier_summary, fchecks = check_run(production["final-frontier343"])
    m8, m8_summary, mchecks = check_run(production["final-m8"])
    assert len(calibration) == 20 and len(frontier) == 343 and len(m8) == 1
    old_certificate_path = REPO / "results/family1-adaptive-search-final/records.jsonl"
    old_certificate = next(row for row in audit.rows(old_certificate_path)
                           if audit.key(row["canonical_table"]) == m8[0]["key"])
    assert old_certificate["upper_bound"] == 50
    drawing.scalar_trace(old_certificate["witness"], drawing.family1_family(old_certificate["canonical_table"]))
    native_source = production["final-native"] / "source-inventory.json"
    if not native_source.exists():
        source_files = ["family1_near.cpp", "Family1NearPair.h", "Family1ScoredSeeds.h", "Family1JointPair.h",
                        "Family1JointSeeds.h", "HardPairJointFinder.h", "HardPairPrefixSeeds.h",
                        "Family1ExactPacked.h", "Family1ExactPacked.cpp", "Family1LargeGraph.h",
                        "Family1LargeGraph.cpp", "Family1PairAgreement.h", "Family1CliArtifacts.h",
                        "Family1TailScoredSeeds.h", "HardPairViability.h"]
        manifest = json.loads((production["final-calibration"] / "manifest.json").read_text())
        executable = Path(manifest["executable"]["path"])
        assert ref(executable)["sha256"] == manifest["executable"]["sha256"]
        current = {"executable_sha256": manifest["executable"]["sha256"],
                   "sources": [{"path": name, "sha256": ref(REPO / name)["sha256"]} for name in source_files]}
        actual = json.loads(next((production["final-calibration"] / "batches").glob("*/run.json")).read_text())
        expected = hashlib.sha256("".join(item["sha256"] + "\n" for item in current["sources"]).encode()).hexdigest()
        assert actual["source_sha256"] == expected, "rebuild the matching versioned sources before publishing"
        save(native_source, current)
    inventory = json.loads(native_source.read_text())
    fingerprint = hashlib.sha256("".join(item["sha256"] + "\n" for item in inventory["sources"]).encode()).hexdigest()
    for folder in ["final-calibration", "final-frontier343", "final-m8"]:
        for runfile in (production[folder] / "batches").glob("*/run.json"):
            native = json.loads(runfile.read_text())
            assert native["source_sha256"] == fingerprint and native["executable_sha256"] == inventory["executable_sha256"]
    rows_out = []
    for name, rows in [("calibration", calibration), ("frontier", frontier), ("m8", m8)]:
        shutil.copy2(production[f"final-{name if name != 'frontier' else 'frontier343'}"] / "records.jsonl",
                     args.out / f"records-{name}.jsonl")
        for row in rows:
            identity = row["m"], row["key"]
            h, prior, upper = truth.get(identity), prior_uppers.get(identity, 50 if name == "m8" else None), row["upper_bound"]
            if h is not None:
                assert row["lower_bound"] <= h and (upper is None or upper >= h)
                if row["exact"]: assert upper == h
            rows_out.append({"dataset": name, "m": row["m"], "key": row["key"],
                             "configured_joint_k": row["configured_joint_k"], "producing_k": row["k"] if row["k"] is not None else "N/A",
                             "producer": row["producer"], "lower": row["lower_bound"], "upper": upper,
                             "minimality_certified": row["minimality_certified"], "reference_H": h, "prior_verified_upper": prior,
                             "gap_if_H_known": upper - h if upper is not None and h is not None else None,
                             "excess_over_prior_upper": upper - prior if upper is not None and prior is not None else None,
                             "first": row["witness"][0] if upper is not None else "", "second": row["witness"][1] if upper is not None else "",
                             "D_trace": json.dumps(row["witness_metric_trace"], separators=(",", ":")),
                             "joint_nodes": row["expanded_nodes"], "exact_words": row["exact_evaluated_words"],
                             "prefix_words": row["prefix_words_evaluated"], "compact_retry": row["retried_compact"]})
    write_csv(args.out / "cases.csv", rows_out)
    compare, prefix_rows = comparison(args.experiments, calibration_summary, calibration, truth)
    write_csv(args.out / "strategy-comparison.csv", compare); write_csv(args.out / "prefix-cases.csv", prefix_rows)
    save(args.out / "summary.json", {"calibration": calibration_summary, "frontier": frontier_summary, "m8": m8_summary,
         "native_exact_frontier_graphs": sum(row["exact"] for row in frontier),
         "frontier_compact_retries": sum(row["retried_compact"] for row in frontier),
         "m7_nonwinner_reference_cutoff_exclusions": sum(row["m"] == 7 and (7, row["key"]) not in
             {(r["m"], r["key"]) for r in calibration} and row["upper_bound"] is not None and row["upper_bound"] <= 33 for row in frontier),
         "winner_within_two_gate_passed": calibration_summary["all_exact_reference_cases_within_two"],
         "winner_within_one_gate_passed": all(row["upper_bound"] is not None
             and row["upper_bound"] <= truth[row["m"], row["key"]] + 1 for row in calibration),
         "broader_within_two_gate_passed": False,
         "frontier_proven_error_above_two": [{"key": row["key"], "returned_upper": row["upper_bound"],
             "prior_verified_upper": prior_uppers[row["m"], row["key"]],
             "error_lower_bound": row["upper_bound"] - prior_uppers[row["m"], row["key"]]}
             for row in frontier if row["upper_bound"] is not None
             and row["upper_bound"] > prior_uppers[row["m"], row["key"]] + 2],
         "m8_error_at_least": m8[0]["upper_bound"] - 50 if m8[0]["upper_bound"] is not None else None,
         "universal_error_bound_certified": False})
    save(args.out / "run.json", {"calibration": ref(production["final-calibration"] / "manifest.json"),
         "frontier": ref(production["final-frontier343"] / "manifest.json"), "m8": ref(production["final-m8"] / "manifest.json"),
         "compile_source_inventory": inventory, "compile_source_fingerprint": fingerprint,
         "publisher": ref(Path(__file__)), "truth_sources": [ref(path) for path in truth_paths],
         "m8_prior_certificate": ref(old_certificate_path), "m8_prior_producing_k": "unknown, historical common suffix"})
    figure_inputs = []
    for row in calibration + m8:
        row = dict(row); identity = row["m"], row["key"]
        if identity in truth:
            row.update(reference_H=truth[identity], gap=row["upper_bound"] - truth[identity],
                       reference_source=[ref(path) for path in truth_paths[:2]])
        else: row.update(reference_upper=50, gap_to_known_upper=row["upper_bound"] - 50,
                         reference_source=ref(old_certificate_path), reference_producing_k="unknown, historical common suffix")
        figure_inputs.append(row)
    source = args.gallery / "figure-inputs.json"; save(source, figure_inputs)
    lines = ["# Paired-word calibration figures", "",
             "All actual pairs are independently scalar-replayed. Joint k=4, B=16; exact-layer producers have k=N/A.",
             "The fallback depth is 24, word-layer cap 16,777,216 and array-payload cap 256 MiB.",
             "A match to the exhaustive reference and the native minimum-proof flag remain separate.", "",
             "| m | Key | Producing k | L | Reference | Pair and D trace |", "|---:|---|---|---:|---|---|"]
    for row in figure_inputs:
        record = drawing.witness_record(row); record["source"] = drawing.reference(source)
        record["source_native_minimality_certified"] = row["minimality_certified"]
        record["source_native_lower_bound"] = row["lower_bound"]
        record["source_native_producer"] = row["producer"]
        if row["producer"] == "exact-word-layers":
            record["configured_joint_parameters"] = {
                "k": row["configured_joint_k"], "window_kind": "joint-pair",
                "alphabet": ["00", "01", "10", "11"],
                **{field: row[field] for field in (
                    "beam_width", "diagonal_width", "unequal_width", "max_length",
                    "expansion_cap", "score", "seed_ranking", "selected_pairs") if field in row}}
            record["search_parameters"] = {
                "k": None, "window_kind": "exact-oracle", "alphabet": ["0", "1"],
                "producer_k_known": False, "deterministic": True,
                "exact_depth": row["exact_depth"], "exact_max_words": row["exact_max_words"],
                "exact_memory_bytes": row["exact_memory_bytes"]}
        record["generator"] = drawing.reference(Path(drawing.__file__))
        record["graph_geometry_source"] = drawing.reference(Path(drawing.atlas.__file__))
        folder = args.gallery / f"m{row['m']}-{row['key']}"; folder.mkdir(exist_ok=True)
        save(folder / "witness.json", record)
        (folder / "witness.svg").write_text(drawing.figure_svg(record, [row["canonical_table"]]))
        htext = f"H={row['reference_H']}" if "reference_H" in row else "prior verified upper=50; H unknown"
        lines.append(f"| {row['m']} | {row['key']} | {'N/A' if row['k'] is None else row['k']} | {row['upper_bound']} | {htext} | [figure]({folder.name}/witness.svg) |")
    (args.gallery / "README.md").write_text("\n".join(lines) + "\n")
    chart(args.gallery, compare)
    shutil.move(str(args.gallery / "quality-preview.png"), args.experiments / "quality-preview.png")
    artifacts = sorted(path for path in args.out.iterdir() if path.is_file() and path.name != "validation.json")
    for path in artifacts: assert path.stat().st_size <= 1048576
    save(args.out / "validation.json", {"passed": True, "final_pairs_replayed": len(calibration) + len(frontier) + len(m8),
         "independent_final_mask_replays": cchecks + fchecks + mchecks, "compile_fingerprints_checked": True,
         "m8_prior_certificate_independent_mask_replays": 256,
         "prior_reference_independent_mask_replays": prior_reference_checks,
         "positive_figures": len(figure_inputs), "all_public_files_under_1MiB": True, "files": [ref(path) for path in artifacts]})
    print(json.dumps({"published": str(args.out), "paired_figures": len(figure_inputs),
                      "calibration_within_one": sum(row["upper_bound"] is not None
                          and row["upper_bound"] <= truth[row["m"], row["key"]] + 1 for row in calibration),
                      "frontier_found": frontier_summary["found"], "frontier_cases": frontier_summary["cases"]}))


if __name__ == "__main__":
    main()
