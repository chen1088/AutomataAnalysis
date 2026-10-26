"""A newly improved best-of pair must survive without a periodic checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="finder-improvement-", dir=repo / "out") as temporary:
        output = Path(temporary) / "native"
        # Both words have even parity and end in0. They agree in all four
        # static masks of this graph. The first seed succeeds, then the shorter
        # cap excludes this fixed length-three prefix in the remaining seeds.
        command = [str(args.exe.resolve()), "--graph", "00010001", "--mode", "finder", "--length", "8",
                   "--samples", "4", "--window-k", "2", "--beam-width", "4",
                   "--first-prefix", "000", "--second-prefix", "110", "--best-of-seeds",
                   "--checkpoint-every", "1000", "--out", str(output)]
        answer = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert answer.returncode == 0, answer.stderr + answer.stdout
        result = json.loads((output / "result.json").read_text())
        assert result["upper_bound"] == 3 and result["witness"] == ["000", "110"], result
        checkpoint = output / "checkpoints/sample-1.txt"
        assert checkpoint.exists(), "Improvement disappeared between periodic checkpoints"
        assert checkpoint.read_text().splitlines()[2] == "1", "Saved cursor must follow the successful seed"
        assert checkpoint.with_suffix(".txt.sha256").read_text() == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        for mask in range(4):
            states = []
            for word in result["witness"]:
                state = 0
                for symbol in word:
                    state = int(symbol) ^ ((mask >> state) & 1)
                states.append(state)
            assert states[0] == states[1]
        # Remove only this test's completed result. Recovery now depends on the
        # non-periodic saved improvement, rather than the completed JSON result.
        for name in ("result.json", "result.sha256"):
            (output / name).unlink()
        resumed = subprocess.run(command + ["--resume"], capture_output=True, text=True, timeout=30)
        assert resumed.returncode == 0, resumed.stderr + resumed.stdout
        recovered = json.loads((output / "result.json").read_text())
        assert recovered["upper_bound"] == 3 and recovered["witness"] == result["witness"]
        for name in ("result.json", "result.sha256"):
            (output / name).unlink()
        checkpoint.with_suffix(".txt.sha256").write_text("0" * 64)
        rejected = subprocess.run(command + ["--resume"], capture_output=True, text=True, timeout=30)
        assert rejected.returncode != 0, "Corrupted saved improvement was accepted"
    print("Immediate best-of improvement, checkpoint replay, and corruption rejection passed")


if __name__ == "__main__":
    main()
