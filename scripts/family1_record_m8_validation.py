#!/usr/bin/env python3
"""Record real native checks and rejection of altered mathematical evidence."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from family1_layer_certificate import reference, validate_manifest, validate_report

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-run", type=Path, default=REPO / "out/family1-m8-lower34-root-lift")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ctests", type=int, default=34)
    parser.add_argument("--log-prefix", default="out/ctest-m8-adaptive")
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Use a fresh output directory")
    manifest_path, report_path = args.proof_run / "certificate-run.json", args.proof_run / "report.json"
    proof = validate_manifest(manifest_path, report_path)
    mutations = {
        "capped_status": lambda p: p.update(status="incomplete"),
        "timeout_reason": lambda p: p.update(reason="timeout"),
        "unfinished_phase": lambda p: p.update(phase="fill-bucket-1"),
        "unrecognized_method": lambda p: p.update(method="sampled-no-collision"),
        "missing_representative": lambda p: p.update(count_pass_representatives=p["count_pass_representatives"]-1),
        "incomplete_bucket_fill": lambda p: p.update(fill_pass_representatives=p["fill_pass_representatives"]-1),
        "unfinished_bucket": lambda p: p.update(completed_buckets=p["completed_buckets"]-1),
        "incomplete_hash_replay": lambda p: p.update(full_scalar_hash_replay_records=0),
        "missing_replay_group": lambda p: p.update(repeated_hash_groups=0),
        "wrong_full_mask_claim": lambda p: p.update(full_mask_family=True),
        "unchecked_self_orbit": lambda p: p.update(self_symmetric_fingerprint_candidates=1,
                                                      full_scalar_self_symmetry_checks=0),
        "wrong_graph_binding": lambda p: p.update(key="00010001", m=2),
    }
    negatives = []
    for name, mutate in mutations.items():
        altered = copy.deepcopy(proof)
        mutate(altered)
        try:
            validate_report(altered, proof["key"])
        except (ValueError, KeyError, TypeError) as error:
            negatives.append({"case": name, "rejected": True, "reason": str(error)})
        else:
            raise AssertionError(f"Invalid evidence accepted: {name}")
    original_manifest = json.loads(manifest_path.read_text())
    manifest_mutations = {
        "changed_native_command": lambda m: m["native_command"].__setitem__(2, "00010001"),
        "changed_report_hash": lambda m: m["report"].update(sha256="0" * 64),
        "changed_runner_pin": lambda m: m["runner"].update(sha256="0" * 64),
        "changed_verifier_source": lambda m: m["verifier_source"].update(sha256="0" * 64),
        "changed_fingerprint_coordinates": lambda m: m["fingerprint_masks"].update(sha256="0" * 64),
        "changed_reference_invocation": lambda m: m["validation_command"].__setitem__(1, "unrelated.py"),
    }
    with tempfile.TemporaryDirectory(prefix="m8-certificate-audit-", dir=REPO / "out") as directory:
        path = Path(directory) / "altered-manifest.json"
        for name, mutate in manifest_mutations.items():
            altered = copy.deepcopy(original_manifest)
            mutate(altered)
            path.write_text(json.dumps(altered), encoding="utf-8")
            try:
                validate_manifest(path, report_path)
            except (ValueError, KeyError, TypeError) as error:
                negatives.append({"case": name, "rejected": True, "reason": str(error)})
            else:
                raise AssertionError(f"Altered invocation accepted: {name}")
    builds = []
    for configuration in ("release", "debug"):
        path = REPO / f"{args.log_prefix}-{configuration}.log"
        content = path.read_text(encoding="utf-8-sig")
        if f"100% tests passed, 0 tests failed out of {args.ctests}" not in content:
            raise ValueError(f"Incomplete native validation: {configuration}")
        builds.append({"configuration": configuration, "ctests": args.ctests, "passed": args.ctests, "log": reference(path),
                       "executable": reference(REPO / f"out/build/msvc-vcpkg/{configuration.title()}/Family1M8LayerVerify.exe")})
    result = {"schema": 1, "both_native_configurations_passed": True, "builds": builds,
        "accepted_complete_lower_certificate": reference(manifest_path), "negative_evidence_checks": negatives,
        "all_negative_cases_rejected": True,
        "sources": [reference(REPO / name) for name in ["CMakeLists.txt", "tests/Family1M8LayerVerify.cpp",
            "tests/family1_m8_layer_verify_test.py", "scripts/family1_layer_certificate.py",
            "scripts/family1_run_m8_layer.py", "scripts/family1_publish_m8_search.py",
            "scripts/family1_record_m8_validation.py", "family1_sample.cpp",
            "tests/family1_finder_improvement_checkpoint_test.py", "scripts/family1_adaptive_candidate_search.py",
            "tests/family1_adaptive_candidate_search_test.py", "scripts/family1_estimate_merge_lengths.py",
            "scripts/family1_adaptive_edit_search.py"]]}
    args.out.mkdir(parents=True, exist_ok=True)
    snapshots = args.out / "sources-used"
    snapshots.mkdir()
    for item in result["sources"]:
        original = Path(item["path"])
        destination = snapshots / original.name
        shutil.copy2(original, destination)
        item.update(original_path=str(original), path=str(destination.resolve()))
    (args.out / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"native_configurations": 2, "ctests_each": args.ctests, "altered_reports_rejected": len(negatives)}, indent=2))


if __name__ == "__main__":
    main()
