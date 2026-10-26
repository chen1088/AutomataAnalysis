#!/usr/bin/env python3
"""Pin the completed Windows build, independent audits and candidate benchmarks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from family1_record_finder_validation import log_text

REPO = Path(__file__).resolve().parents[1]


def ref(path):
    path = Path(path).resolve()
    return {"path": path.relative_to(REPO).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    output = REPO / "results/family1-edit-candidate-validation"
    output.mkdir(parents=True, exist_ok=True)
    configs = []
    for name in ("Release", "Debug"):
        log = REPO / f"out/ctest-edit-candidates-{name.lower()}.log"
        text = log_text(log)
        if "100% tests passed, 0 tests failed out of 31" not in text:
            raise ValueError(f"Complete {name} suite did not pass")
        configs.append({"configuration": name, "passed": 31, "failed": 0,
                        "log": ref(log),
                        "seconds": float(re.search(r"Total Test time \(real\) =\s*([0-9.]+)", text)[1]),
                        "executables": [ref(REPO / f"out/build/msvc-vcpkg/{name}/{target}.exe")
                                        for target in ("Family1Edit", "Family1Sample")]})
        (output / f"ctest-{name.lower()}.txt").write_text(text, encoding="utf-8")
    sources = ["CMakeLists.txt", "Family1EditSearch.h", "Family1EditSearch.cpp", "family1_edit.cpp",
               "Family1LargeGraph.h", "Family1LargeGraph.cpp", "Family1CliArtifacts.h",
               "scripts/family1_graph_candidate_search.py", "scripts/family1_rank_edit_candidates.py",
               "scripts/family1_edit_candidate_pilot.py", "tests/family1_edit_candidate_cli_test.py",
               "tests/family1_graph_candidate_search_test.py", "tests/family1_rank_edit_candidates_test.py"]
    result = {"schema": 1, "platform": "native Windows x64, MSVC2022, CMake, pinned vcpkg",
              "configurations": configs, "sources": [ref(REPO / source) for source in sources],
              "benchmarks": [ref(REPO / path) for path in (
                  "results/family1-edit-candidate-benchmark/summary.json",
                  "results/family1-edit-candidate-benchmark/independent-audit.json",
                  "results/family1-edit-ranked-candidate-benchmark/summary.json",
                  "results/family1-edit-elimination-benchmark/summary.json",
                  "results/family1-edit-elimination-complete-m7/summary.json")],
              "pilot_resume_log": ref(REPO / "out/family1-edit-candidate-pilot-8-20-resume.log"),
              "coverage": {"complete_tiny_unit_neighborhood_source_classes": 64,
                           "larger_sampled_paths": 256, "larger_primitive_steps": 616,
                           "parent_classes_in_complete_growth_comparison": 288,
                           "generated_shapes_with_complete_root_closure_checks": 4467},
              "limits": "Finite edit pools and heuristic screening do not prove global coverage or new exact scores. Unknown, unselected and time-capped graphs remain exported."}
    (output / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Native edit-candidate validation\n\n"
        "MSVC Release and Debug each passed all31 registered CTests. The complete logs, "
        "source hashes and both native executable hashes are retained here. Independent "
        "checks cover complete tiny unit neighborhoods, larger edit-path replay, all supplied "
        "parents' complete growth sets, accessible-root closure, every-mask witness replay, "
        "candidate-label-independent ranking, all ties and guarded resume. The bounded "
        "8 through20 pilot also passed a no-op resume.\n\n"
        "See [the generation benchmark](../family1-edit-candidate-benchmark/README.md), "
        "[same-pool rankings](../family1-edit-ranked-candidate-benchmark/README.md), and "
        "[complete seven-state pool screening](../family1-edit-elimination-complete-m7/README.md). "
        "These measurements certify no new global maximum above seven states.\n", encoding="utf-8")
    print(json.dumps({"passed": True, "configurations": 2, "tests_each": 31, "output": str(output)}))


if __name__ == "__main__":
    main()
