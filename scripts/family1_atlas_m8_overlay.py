#!/usr/bin/env python3
"""Add a single checked m8 interval to the existing33-picture atlas inputs."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from family1_layer_certificate import validate_manifest, check_reference
from family1_m8_candidate_figure import KEY, select, verify_upper, reference

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-atlas-m8-update")
    parser.add_argument("--upper", type=Path, default=REPO / "results/family1-m8-fresh-prefix-refinement/records.jsonl")
    parser.add_argument("--lower-report", type=Path, default=REPO / "out/family1-m8-lower34-root-lift/report.json")
    args = parser.parse_args()
    original = REPO / "results/family1-atlas-current/champions.jsonl"
    prior, upper = select(original, KEY), select(args.upper, KEY)
    if prior["canonical_table"] != upper["canonical_table"]:
        raise ValueError("Overlay would change the illustrated graph")
    verify_upper(upper)
    manifest_path = args.lower_report.parent / "certificate-run.json"
    proof = validate_manifest(manifest_path, args.lower_report)
    if proof["key"] != KEY or proof["m"] != 8 or proof["lower_bound"] > upper["upper_bound"]:
        raise ValueError("Overlay proof/upper identity or interval conflict")
    certificate = {field: proof[field] for field in ("method", "depth", "lower_bound", "full_family_injectivity_certified",
                    "expected_representatives", "completed_buckets", "complete_profile_comparisons")}
    certificate.update(report=reference(args.lower_report), run_manifest=reference(manifest_path))
    row = deepcopy(prior)
    row.update(lower_bound=proof["lower_bound"], upper_bound=upper["upper_bound"], witness=upper["witness"],
               status="bounded", merge_length=None, reason="independent-complete-layer-lower-certificate-and-static-mask-upper-witness",
               exact_score_certified=False, global_maximum_certified=False, lower_certificate=certificate,
               upper_certificate={"source": reference(args.upper), "independent_scalar_static_masks_verified": 256})
    args.out.mkdir(parents=True, exist_ok=True)
    evidence = args.out / "evidence"; evidence.mkdir(exist_ok=True)
    shutil.copy2(args.lower_report, evidence / "lower-report.json")
    shutil.copy2(manifest_path, evidence / "certificate-run.json")
    shutil.copy2(args.upper, evidence / "upper-records.jsonl")
    pinned = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    inventory = []
    for field in ("native_executable", "verifier_source", "reference_checker", "validation_log", "native_log", "runner", "certificate_checker", "fingerprint_masks"):
        item = pinned[field]; path = check_reference(item)
        shutil.copy2(path, evidence / path.name)
        inventory.append({"source": item, "local_file": f"evidence/{path.name}"})
    (args.out / "records.jsonl").write_text(json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {"schema": 1, "dataset_kind": "single-graph-certified-interval-overlay", "record_count": 1,
               "sources": {"original_presentation": reference(original), "upper": reference(args.upper),
                           "lower_report": reference(args.lower_report), "lower_run_manifest": reference(manifest_path)},
               "generator": reference(Path(__file__)),
               "sizes": [{"m": 8, "displayed_graphs": 1, "largest_displayed_lower_bound": row["lower_bound"],
                          "global_maximum": None, "maximum_value_certified": False, "maximum_certified": False,
                          "maximizing_collection_complete": False, "enumeration_complete": False}]}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.out / "evidence-inventory.json").write_text(json.dumps({"pinned_lower_evidence": inventory}, indent=2) + "\n", encoding="utf-8")
    (args.out / "validation.json").write_text(json.dumps({"passed": True, "graph_and_construction_unchanged": True,
         "native_lower_manifest_and_all_source_pins_validated": True, "upper_witness_masks_independently_replayed": 256,
         "lower_bound": row["lower_bound"], "upper_bound": row["upper_bound"], "global_maximum_certified": False}, indent=2) + "\n", encoding="utf-8")
    (args.out / "README.md").write_text("""# Single m8 atlas interval overlay

This updates the existing illustrated eight-state root-lift graph to 35 <= H(G) <= 52. The graph, construction, root and layout metadata are unchanged. A complete check of words of length 34 supplies the lower certificate; a distinct pair of 52 symbols is independently replayed over all 256 static masks. The exact graph score and global maximum remain unresolved. No other size receives a new bound.

Use this one-record file together with results/family1-atlas-current/champions.jsonl. The original presentation dataset stays unchanged, including all 20 certified rooted winners through seven states and all thirteen larger examples. Do not substitute the full search corpus: that would change the atlas's selected scope. Checked native evidence and code snapshots are retained under evidence/; evidence-inventory.json maps original pins to these copies.

Recreate this overlay with uv run --no-project python scripts/family1_atlas_m8_overlay.py. Build the atlas using both --input results/family1-atlas-current and --input results/family1-atlas-m8-update/records.jsonl, preserving --overview, --ancestry and --edit-distances settings recorded in the atlas source manifest.
""", encoding="utf-8")
    print(json.dumps({"overlay": str(args.out), "key": KEY, "lower_bound": row["lower_bound"], "upper_bound": row["upper_bound"]}))


if __name__ == "__main__":
    main()
