# Literal circulant family: fixed length 34 queries

The family here is exactly `tau0(i)=(i+1) mod m`,
`tau1(i)=(i+floor(m/3)) mod m`. It is separate from the manuscript variant.
Translations identify every starting vertex, so one rooted graph class per
size covers all roots of this supplied family.

All 13 queries at exact sizes 8 through 20 returned **UNKNOWN**. These queries
supply no new lower or upper bound. They do not settle any global maximum.
The distinct root ports independently give H>=2. Existing exact scores from
`results/family1-circulant-family/`, including H=18 at m=8, remain in force;
the threshold-only intervals in this export do not replace those scores.

Each query had a 10,000 ms aggregate CEGIS budget and a 5,000 ms SAT-call budget,
with four concurrent processes and 64 initial static masks. Actual per-query
times were 5.35--8.47 seconds (81.0 seconds summed per-process elapsed time).
Solver reasons were `timeout` or `canceled`; every such result stays UNKNOWN.

`native-results/` retains all thirteen original native JSON records, including
actual sampled masks. `artifact-manifest.json` pins their hashes and original
locations. `run.json` pins the input dataset, executable, driver, and settings.
`graphs.jsonl` combines the original input metadata with each threshold result;
`summary.json` records all outcomes and completion flags.

The complete native working directories, including their guarded run settings,
are under `out/family1-circulant-threshold34/queries/`. Re-running with `--resume`
passed and left all thirteen native result files byte-for-byte unchanged.

Reproduce with a new empty output directory:

```powershell
uv run --no-project python scripts/family1_circulant_threshold.py --out out/family1-circulant-threshold34-new
```

Resume the existing run with:

```powershell
uv run --no-project python scripts/family1_circulant_threshold.py --resume
```
