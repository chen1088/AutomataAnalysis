#!/usr/bin/env python3
"""Snapshot, independently test, and run the native eight-state layer verifier."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from family1_layer_certificate import reference, check_reference, validate_manifest, validate_report

REPO = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1M8LayerVerify.exe")
    parser.add_argument("--checker", type=Path, default=REPO / "tests/family1_m8_layer_verify_test.py")
    parser.add_argument("--key", required=True)
    parser.add_argument("--depth", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=24)
    parser.add_argument("--bucket-bits", type=int, default=1)
    parser.add_argument("--memory-mib", type=int, default=40000)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--fingerprint-mask-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.out = args.out.resolve()
    if args.out.exists() and any(args.out.iterdir()):
        if not args.resume:
            raise ValueError("Use fresh output or --resume a completed pinned proof")
        manifest = args.out / "certificate-run.json"
        report = validate_manifest(manifest, args.out / "report.json")
        if report["key"] != args.key or report["depth"] != args.depth:
            raise ValueError("Resume key/depth differs")
        if (report["threads"], report["bucket_bits"], report["max_working_mib"], report["timeout_ms"]) != (
                args.threads, args.bucket_bits, args.memory_mib, args.timeout_seconds * 1000):
            raise ValueError("Resume resource/partition settings differ")
        saved = json.loads(manifest.read_text())
        if bool(args.fingerprint_mask_file) != ("fingerprint_masks" in saved):
            raise ValueError("Resume fingerprint mode differs")
        if args.fingerprint_mask_file and reference(args.fingerprint_mask_file)["sha256"] != saved["fingerprint_masks"]["sha256"]:
            raise ValueError("Resume fingerprint coordinates differ")
        print(json.dumps(report, indent=2))
        return
    if not (1 <= args.depth <= 36 and 1 <= args.threads <= 64 and 0 <= args.bucket_bits <= 12
            and args.memory_mib >= 1 and args.timeout_seconds >= 1):
        raise ValueError("Invalid depth/thread/partition/resource settings")
    args.out.mkdir(parents=True, exist_ok=True)
    files = {"native_executable": args.exe.resolve(),
             "verifier_source": REPO / "tests/Family1M8LayerVerify.cpp",
             "reference_checker": args.checker.resolve(), "runner": Path(__file__).resolve(),
             "certificate_checker": REPO / "scripts/family1_layer_certificate.py"}
    snapshots = args.out / "snapshots"
    snapshots.mkdir()
    pins = {}
    for name, path in files.items():
        destination = snapshots / path.name
        before = reference(path)
        shutil.copy2(path, destination)
        if reference(destination)["sha256"] != before["sha256"]:
            raise ValueError("Snapshot changed during copy")
        pins[name] = reference(destination)
    native = Path(pins["native_executable"]["path"])
    checker = Path(pins["reference_checker"]["path"])
    report_path = args.out / "report.json"
    command = [str(native), "--key", args.key, "--depth", str(args.depth), "--threads", str(args.threads),
               "--bucket-bits", str(args.bucket_bits), "--max-working-mib", str(args.memory_mib),
               "--timeout-ms", str(args.timeout_seconds * 1000), "--out", str(report_path)]
    if args.fingerprint_mask_file:
        destination = snapshots / "fingerprint-masks.txt"
        shutil.copy2(args.fingerprint_mask_file, destination)
        pins["fingerprint_masks"] = reference(destination)
        command += ["--fingerprint-mask-file", str(destination)]
    write(args.out / "invocation.json", {"command": command, "pins": pins})
    started = time.perf_counter()
    validation_log, native_log = args.out / "reference-check.log", args.out / "native.log"
    validation_command = [sys.executable, str(checker), "--exe", str(native)]
    with validation_log.open("w", encoding="utf-8") as log:
        validation = subprocess.run(validation_command,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180)
    if validation.returncode:
        raise ValueError(f"Independent reference tests failed; see {validation_log}")
    for item in pins.values():
        check_reference(item)
    print("Independent scalar reference checks passed; starting pinned layer run.", flush=True)
    with native_log.open("w", encoding="utf-8") as log:
        native_run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=args.timeout_seconds + 120)
    for item in pins.values():
        check_reference(item)
    manifest = {"schema": 1, "method": "pinned-native-independent-layer-run-v1", **pins,
        "graph_key": args.key, "requested_depth": args.depth, "native_command": command,
        "validation_command": validation_command,
        "validation_exit_code": validation.returncode, "native_exit_code": native_run.returncode,
        "validated_before_search": True, "completed": native_run.returncode == 0,
        "report": reference(report_path), "validation_log": reference(validation_log),
        "native_log": reference(native_log), "wall_seconds": time.perf_counter() - started}
    write(args.out / "certificate-run.json", manifest)
    proof = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if proof["status"] == "collision-free":
        validate_report(proof, args.key)
        validate_manifest(args.out / "certificate-run.json", report_path)
    print(json.dumps(proof, indent=2))
    if native_run.returncode:
        raise SystemExit(native_run.returncode)


if __name__ == "__main__":
    main()
