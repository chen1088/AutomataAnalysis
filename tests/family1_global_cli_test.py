"""Exercise global-proof CLI scheduling, cross-size seeds, and clean replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path,
                        default=Path("out/build/msvc-vcpkg/Release/Family1GlobalCheck.exe"))
    args = parser.parse_args()
    executable = args.exe.resolve()
    base = Path("out/global-resume-audit/cli-tests")
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as temporary:
        root = Path(temporary)

        def run(name: str, *options: str, success: bool = True) -> tuple[dict, Path]:
            destination = root / name
            process = subprocess.run([str(executable), "--out", str(destination), *options],
                                     text=True, capture_output=True, timeout=60, check=False)
            assert (process.returncode == 0) == success, process.stdout + process.stderr
            result = json.loads((destination / "result.json").read_text()) if success else {}
            return result, destination

        proof, source = run("proof", "--states", "3", "--threshold", "6")
        assert proof["decision"] == "impossible" and proof["proven_upper_bound"] == 6
        assert proof["postponed_models"] == 0
        replay, replay_dir = run("replay", "--replay", str(source))
        assert replay["decision"] == "impossible"
        assert (source / "graph-space.cnf").read_bytes() == (replay_dir / "graph-space.cnf").read_bytes()
        proof_v2, source_v2 = run("proof-v2", "--states", "3", "--threshold", "6", "--discovery-labels")
        assert proof_v2["decision"] == "impossible" and proof_v2["encoder_version"].endswith("-v2")
        replay_v2, replay_v2_dir = run("replay-v2", "--replay", str(source_v2))
        assert replay_v2["encoder_version"] == proof_v2["encoder_version"]
        assert (source_v2 / "graph-space.cnf").read_bytes() == (replay_v2_dir / "graph-space.cnf").read_bytes()
        resumed_v2, _ = run("resume-v2", "--resume", str(source_v2))
        assert resumed_v2["encoder_version"] == proof_v2["encoder_version"] and resumed_v2["candidates_checked"] == 0
        resumed_v1, _ = run("resume-v1", "--resume", str(source), "--discovery-labels")
        assert resumed_v1["encoder_version"] == proof["encoder_version"] and resumed_v1["candidates_checked"] == 0

        seeded, _ = run("seeded", "--states", "2", "--threshold", "2",
                        "--seed-pairs", str(source), "--seed-pairs", str(source))
        assert seeded["states"] == 2 and seeded["threshold"] == 2
        assert seeded["decision"] == "challenger" and seeded["challenger_lower_bound"] == 3
        assert len(seeded["seed_pair_sources"]) == 2
        first, second = seeded["seed_pair_sources"]
        assert first["states"] == 3 and first["threshold"] == 6
        assert first["skipped_long_pairs"] > 0 and second["imported_pairs"] == 0
        assert second["duplicate_pairs"] == first["imported_pairs"]
        assert sum(first[field] for field in ("imported_pairs", "skipped_long_pairs", "duplicate_pairs")) == len(proof["learned_pairs"])
        assert all(1 <= len(pair[0]) == len(pair[1]) <= 2 for pair in seeded["learned_pairs"])
        seeded_v2, _ = run("seeded-v2", "--states", "2", "--threshold", "2", "--discovery-labels",
                           "--seed-pairs", str(source), "--seed-pairs", str(source_v2))
        assert seeded_v2["encoder_version"].endswith("-v2") and seeded_v2["decision"] == "challenger"

        postponed, postponed_dir = run("postponed", "--states", "2", "--threshold", "3",
                                       "--candidate-max-layer-states", "1", "--max-postponed-models", "32")
        assert postponed["decision"] == "unknown" and not postponed["global_upper_bound_certified"]
        assert postponed["postponed_models"] > 1 and postponed["postponed_candidates"]
        assert postponed["reason"] == "postponed-candidates-remain"
        assert not (postponed_dir / "graph-space.cnf").exists()
        run("forbidden", "--replay", str(source), "--seed-pairs", str(source), success=False)
    print("Global CLI scheduling, seed filtering, and certificate replay passed")


if __name__ == "__main__":
    main()
