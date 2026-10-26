"""Acceptance checks for the independent partitioned layer verifier's reports."""
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": checksum, "bytes": path.stat().st_size}


def check_reference(item):
    actual = reference(item["path"])
    require(actual["sha256"] == item["sha256"], f"Certificate evidence changed: {item['path']}")
    return Path(item["path"])


def validate_report(proof, key=None):
    require(proof.get("method") in {"independent-partitioned-complement-orbit-layer-v1",
                                     "independent-partitioned-complement-orbit-layer-v2"},
            "Unrecognized independent verifier method")
    require(proof.get("schema") == 1 and proof.get("status") == "collision-free"
            and proof.get("reason") == "" and proof.get("phase") == "complete"
            and proof.get("full_family_injectivity_certified") is True,
            "Layer verifier did not complete an injectivity proof")
    m, depth = proof["m"], proof["depth"]
    require(type(m) is int and 1 <= m <= 8 and type(depth) is int and 1 <= depth <= 36,
            "Invalid layer dimensions")
    graph_key = proof["key"]
    require(isinstance(graph_key, str) and len(graph_key) == 4 * m
            and graph_key.isdecimal() and (key is None or key == graph_key), "Layer graph binding failed")
    require(all(int(graph_key[i:i+2]) < m for i in range(0, len(graph_key), 2)), "Invalid graph target")
    expected = 1 << (depth - 1)
    bits, buckets = proof["bucket_bits"], proof["bucket_count"]
    require(type(bits) is int and 0 <= bits <= 12 and buckets == 1 << bits,
            "Invalid hash partition")
    require(proof["lower_bound"] == depth + 1 and proof["upper_bound"] is None and proof["witness"] is None,
            "Injectivity proof has inconsistent bounds/witness")
    require(proof["expected_representatives"] == expected and proof["count_pass_representatives"] == expected
            and proof["fill_pass_representatives"] == expected * buckets
            and proof["completed_buckets"] == buckets, "Incomplete representative coverage")
    sizes = proof["bucket_sizes"]
    require(len(sizes) == buckets and all(type(n) is int and n >= 0 for n in sizes)
            and sum(sizes) == expected, "Hash buckets do not partition every representative")
    replay = proof["replay_pass_representatives"]
    require(type(replay) is int and replay % expected == 0 and 0 <= replay <= expected * buckets,
            "Incomplete repeated-hash replay traversal")
    groups, repeated = proof["repeated_hash_groups"], proof["repeated_hash_records"]
    require(type(groups) is int and type(repeated) is int and 0 <= 2 * groups <= repeated <= expected,
            "Invalid repeated-hash accounting")
    require((groups == 0) == (repeated == 0), "Repeated fingerprints have no replay group")
    require((groups == 0 and replay == 0) or (groups > 0 and expected <= replay <= expected * groups),
            "Repeated hashes were not completely replayed")
    masks = proof["selected_masks"]
    require(isinstance(masks, list) and masks == sorted(set(masks)) and masks
            and all(type(mask) is int and 0 <= mask < (1 << m) for mask in masks)
            and len(masks) == proof["selected_mask_count"], "Invalid fingerprint mask coordinates")
    require(proof["complement_closed_masks"] is True
            and all((mask ^ ((1 << m) - 1)) in masks for mask in masks), "Mask complement quotient invalid")
    require(proof["full_mask_family"] == (len(masks) == (1 << m)), "Incorrect full-family flag")
    require(proof["full_scalar_hash_replay_records"] == repeated,
            "Repeated fingerprints were not replayed as complete states")
    if proof["fingerprint_subset_with_full_replay"] and not proof["full_mask_family"]:
        require(proof["full_scalar_self_symmetry_checks"] == proof["self_symmetric_fingerprint_candidates"],
                "Projected self-symmetries were not checked against complete states")
    return proof


def validate_manifest(path, report_path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    require(manifest.get("method") == "pinned-native-independent-layer-run-v1"
            and manifest.get("native_exit_code") == 0 and manifest.get("validation_exit_code") == 0
            and manifest.get("validated_before_search") is True and manifest.get("completed") is True,
            "Layer run has no successful pinned validation")
    report = check_reference(manifest["report"])
    require(report.resolve() == Path(report_path).resolve(), "Manifest belongs to another report")
    for name in ("native_executable", "verifier_source", "reference_checker", "validation_log", "native_log",
                 "runner", "certificate_checker"):
        check_reference(manifest[name])
    if "fingerprint_masks" in manifest:
        check_reference(manifest["fingerprint_masks"])
    proof = validate_report(json.loads(report.read_text(encoding="utf-8-sig")), manifest["graph_key"])
    require(manifest["requested_depth"] == proof["depth"], "Depth differs from pinned invocation")
    command = [manifest["native_executable"]["path"], "--key", proof["key"], "--depth", str(proof["depth"]),
               "--threads", str(proof["threads"]), "--bucket-bits", str(proof["bucket_bits"]),
               "--max-working-mib", str(proof["max_working_mib"]), "--timeout-ms", str(proof["timeout_ms"]),
               "--out", str(report)]
    if "fingerprint_masks" in manifest:
        command += ["--fingerprint-mask-file", manifest["fingerprint_masks"]["path"]]
        mask_text = Path(manifest["fingerprint_masks"]["path"]).read_text().replace(",", " ").replace(";", " ")
        require(sorted(map(int, mask_text.split())) == proof["selected_masks"]
                and proof["fingerprint_subset_with_full_replay"] is True,
                "Fingerprint mask snapshot differs from the validated coordinates")
    else:
        require(proof["full_mask_family"] is True, "Default run did not cover all masks")
    require(manifest["native_command"] == command, "Report differs from the pinned native invocation")
    validation_command = manifest["validation_command"]
    require(isinstance(validation_command, list) and len(validation_command) == 4
            and validation_command[1:] == [manifest["reference_checker"]["path"], "--exe",
                                           manifest["native_executable"]["path"]],
            "Reference test invocation differs from its pinned artifacts")
    return proof
