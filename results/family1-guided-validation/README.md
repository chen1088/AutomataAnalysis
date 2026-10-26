# Guided coordinate-score validation

Both native MSVC/vcpkg **Release and Debug** passed the independent guided CLI
suite on 2026-10-26. `validation.json` pins binaries, test source, and example
artifacts. Earlier constructor/sampler validation records remain unchanged.

- All 64 rooted classes through size three were checked against scalar static
  mask simulation, including native sampled population counts and independent
  exact full-agreement traces.
- The mathematical reference checked 2,240 pairs and 15,680 suffix traces,
  including monotonicity and permutation-coordinate obstructions.
- `plateau-lookahead0.json` and `plateau-lookahead2.json` both find the shortest
  pair `0111 / 1011`, with full score trace **4,4,8**. The neutral step survives
  even with lookahead disabled.
- `shortest-m3.json` finds `010110 / 100110` at the known three-state maximum
  length six, with full trace **4,5,6,7,8**.
- `sampled-and-full.json` displays the same valid pair using a sampled trace
  **0,0,1 out of 1** and an exact trace **4,4,8 out of 8**. Their denominators
  remain separate and each trace is bound to its own masks.
- `gate-blocked.json` correctly rejects suffix completion of a pair disagreeing
  on two permutation masks. It records UNKNOWN with no new score bound.
- Partial guided checkpoints resume identically to uninterrupted runs, and
  changed prefix/beam/lookahead settings are rejected.

`known-m7-traces.jsonl` independently replays the eight saved certified shortest
seven-state witnesses, splitting each at its longest common suffix. These are
analyses of existing witnesses, not new searches. All eight prefixes pass the
full permutation gate. Seven of the eight saved suffixes contain neutral steps,
with 17 neutral steps in total. This finite collection is not a random sample
of shortest witnesses and does not enumerate all such witnesses.

```powershell
uv run --no-project python tests/family1_guided_cli_test.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe
```

See [the score definition and proofs](../../docs/family1-merge-coordinate-score.md).
