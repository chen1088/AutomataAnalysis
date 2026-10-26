#!/usr/bin/env python3
"""Record the completed native Windows finder validation, with source hashes."""
from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]


def reference(path):
    return {"path": path.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def log_text(path):
    data = path.read_bytes()
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-log", type=Path, default=REPO / "out/ctest-release-final.log")
    parser.add_argument("--debug-log", type=Path, default=REPO / "out/ctest-debug-final.log")
    parser.add_argument("--out", type=Path, default=REPO / "results/family1-hard-pair-finder-validation")
    args = parser.parse_args()
    configurations = []
    for name in ("Release", "Debug"):
        log = args.release_log.resolve() if name == "Release" else args.debug_log.resolve()
        text = log_text(log)
        if "100% tests passed, 0 tests failed out of 28" not in text:
            raise ValueError(f"the complete 28-test {name} suite has not passed")
        configurations.append({"configuration": name, "passed": 28, "failed": 0,
                               "log": reference(log),
                               "seconds": float(re.search(r"Total Test time \(real\) =\s*([0-9.]+)", text)[1]),
                               "finder_executable": reference(REPO / f"out/build/msvc-vcpkg/{name}/Family1Sample.exe")})
    files = ["HardPairFinder.h", "HardPairPrefixSeeds.h", "HardPairViability.h",
             "Family1PairAgreement.h", "Family1FullGuidance.h", "family1_sample.cpp", "CMakeLists.txt",
             "tests/HardPairFinderIndependent.cpp", "tests/HardPairPrefixSeedsIndependent.cpp",
             "tests/HardPairViabilityIndependent.cpp", "tests/Family1PairAgreementVerify.cpp",
             "tests/family1_finder_cli_test.py", "tests/family1_viability_cli_test.py"]
    result = {"schema": 1, "platform": "native Windows x64, MSVC 2022, CMake, pinned vcpkg",
              "configurations": configurations, "source_files": [reference(REPO / path) for path in files],
              "independent_checks": {
                  "rooted_accessible_classes_m_le_3": 64, "conditional_BFS_comparisons": 1263,
                  "forced_hash_cases": 48, "complete_window_distributions": 128,
                  "explicit_binary_DFAs_for_prefix_and_viability_checks": 746,
                  "prefix_reference_pairs": 12992, "viability_ordered_pairs": 6626,
                  "heterogeneous_state_counts": [2, 3, 5],
                  "full_metric_m20_masks_per_case": 1048576,
                  "caps_resume_static_revisits_and_common_prefixes_checked": True},
              "limits": "A shortest conditional tail is not a shortest whole pair. Sampling misses do not prove lower bounds. Global maxima above seven states remain unproved."}
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for item in configurations:
        source = REPO / item["log"]["path"]
        (output / f"ctest-{item['configuration'].lower()}.txt").write_text(log_text(source), encoding="utf-8")
    (output / "README.md").write_text(
        "# Native finder validation\n\n"
        "Both Windows MSVC/vcpkg configurations passed all 28 registered CTests. "
        "The complete test logs and pinned executable/source hashes are retained here. "
        "Tests include independent exhaustive tiny families, heterogeneous DFA sizes/roots, "
        "forced hash collisions, static revisits, complete gain distributions, exact conditional "
        "BFS, negative mergeability certificates, budgets and deterministic resume. "
        "Three twenty-state cases check the full metric against scalar simulation over "
        "all 1,048,576 masks each.\n\n"
        "Quality results are separate: see [the blind version comparison]"
        "(../family1-finder-prefixmatch-version-benchmark/README.md) and "
        "[the module documentation](../../docs/hard-pair-finder.md). "
        "No global optimum for sizes 8 through 20 is certified.\n", encoding="utf-8")
    print(json.dumps({"passed": True, "configurations": 2, "tests_each": 28, "output": str(output)}))


if __name__ == "__main__":
    main()
