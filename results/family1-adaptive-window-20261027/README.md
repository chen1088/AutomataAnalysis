# Variance-adaptive hard-pair search

The [method and results](../../docs/family1-adaptive-window-report.md) evaluate
the proposed variance-based choice of joint lookahead k. All experiments are
deterministic, use 00,01,10,11, and disable the exact oracle. Beam width is 16.
All supplied graphs are tested under every declared configuration. No
reference length or saved pair enters a native query.

The evidence supports one-symbol rolling advancement on the broader suite,
but has not established a quality advantage from the variance threshold.
The finder still has substantial errors and misses outside the winner suite.

The [final verification record](verification.json) pins the tested sources,
all five publications, method documents and remaining quality limits.

| Evidence | Scope | Configured joint k |
|---|---|---|
| [Pilot](pilot-64/README.md) | All 20 certified winners × 11 configurations; 64 starts per ranking | Fixed 2/4/5; adaptive 2..5, 2..6, 4..6 |
| [Stronger calibration](calibration-512/README.md) | All 20 winners × five configurations; 512 starts per ranking | Fixed 4; adaptive 2..5, 2..6, 4..6 |
| [Broader frontier](frontier-64/README.md) | All 343 saved graphs × three configurations; 64 starts per ranking | Fixed 4; adaptive 2..5 |
| [Shallow calibration control](shallow-calibration-512/README.md) | All 20 winners, fixed rolling control; 512 starts per ranking | 2 |
| [Shallow frontier control](shallow-frontier-64/README.md) | All 343 saved graphs, fixed rolling control; 64 starts per ranking | 2 |
| [Small variance counterexamples](variance-counterexamples.json) | Two three-state graphs, every joint leaf and every original mask | 2 |

Each published run includes all actual word pairs and D traces in cases.csv,
configured bounds and winning k sequences, all-attempt k/work histograms,
and winning-path decision/moment tables. Large moment tables are split into
files below 1 MiB. A producing k of N/A means the bounded seed catalogue
already contained the returned pair. A match to reference H remains separate
from a native minimum proof.

Detailed moments are from the winning attempt's ancestry. They are not a
sample of every failed attempt. All-attempt work includes refused-growth
pilots, rejected seeds and losing beam branches. Expansion-budget refusal
and length-limit exhaustion are distinct. Historical certificates preserve
the certificate floor but never receive credit as new finder results.

## Reproduction

Build the standalone dependency-free targets:

    cmake -S . -B out/build/adaptive-window -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build out/build/adaptive-window -j 4
    ctest --test-dir out/build/adaptive-window --output-on-failure

Run and publish the complete predeclared pilot in fresh directories:

    python3 scripts/family1_adaptive_window_benchmark.py \
      --exe out/build/adaptive-window/Family1AdaptiveWindowBenchmark \
      --out out/adaptive-window-repro/pilot-64 --starts 64 --jobs 4
    python3 scripts/family1_adaptive_window_report.py \
      --work out/adaptive-window-repro/pilot-64 \
      --out out/adaptive-window-repro/public-pilot \
      --figures out/adaptive-window-repro/figures-pilot

For the broader matched stress test, supply the entire saved pool:

    python3 scripts/family1_adaptive_window_benchmark.py \
      --exe out/build/adaptive-window/Family1AdaptiveWindowBenchmark \
      --pool results/family1-neighbor-seeds/near-top.jsonl \
      --out out/adaptive-window-repro/frontier-64 --starts 64 --jobs 4 \
      --config block4:fixed-block:4:4:16:0:1:block \
      --config rolling4:fixed-roll:4:4:16:0:1:first \
      --config variance-low:total-roll:2:5:16:1000:1:first

All native files are sealed before reference labels are joined. The publisher
independently scalar-replays every final and improvement pair, checks winning
parent metrics, reconstructs moment arithmetic from full sparse D histograms,
and verifies source, executable, configuration and journal hashes.
Independent native tests separately compare complete leaf populations against
scalar word enumeration, including all four symbols and original-mask weights.

The 20-winner suite was used for development; the saved frontier overlaps it.
These results establish no universal near-shortest error bound and do not
repeat the full exhaustive graph search through m=7.
