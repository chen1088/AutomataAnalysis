# Finder strategy optimization

The [report](../../docs/family1-finder-strategies-report.md) describes the
implemented Family1NearPair pipeline, all tested alternatives and the
remaining failures.

The new default uses exact word layers (k=N/A, depth24, 16,777,216 words,
256 MiB planned payload), then full-D and common-input-distance scored starts
and **joint k=4, beam16**, with a compact-catalogue retry on misses. All 20
certified winners through m=7 are found within one of H; 18 lengths match H.
All 69 saved hard m=6 cases are solved exactly. All 343 saved frontier graphs
receive pairs, and 288 m≤6 rows carry native exact proofs.

The broader quality gate still fails. A seven-state nonwinner returns 43
despite an independently replayed 32-pair; its error is at least 11. The
m8 development check returns 52, worse than the existing verified 50. Neither passing
the winner gate nor returning a valid pair establishes general near-shortest
accuracy.

## Complete evidence

| Directory | Evidence | k |
|---|---|---|
| [near](near/summary.json) | Final frozen binary:20 winners,343 frontier cases and m8 development check; every actual pair, trace, lower/upper claim and work count | Joint4; exact producers N/A |
| [near-full-D](near-full-D/summary.json) | Preserved full-D baseline before adding common-distance seed ranking; all 364 final rows | Joint4; exact producers N/A |
| [near/strategy-comparison.csv](near/strategy-comparison.csv) | Complete canonical-prefix grid and new default | Joint3,4,6 |
| [near/prefix-cases.csv](near/prefix-cases.csv) | All240 native prefix-grid cases, words and D traces | Joint3,4,6 |
| [rolling](rolling/README.md) | Receding horizon, beams, distance metrics, alternate ties and scored-start probes | Explicit per row |
| [refinement](refinement/README.md) | Complete local edit spheres and exhaustive prefix/tail replacements | Edit N/A; binary-prefix12/16; COMMON16/18 |
| [alternative](alternative/README.md) | RNG-free SAT/CEGAR and exact-profile cycle search, including misses | N/A |
| [heldout](heldout/README.md) | Original/compact seed validation on116 cases, with114 strictly outside winner training | Joint4, short exact fallback N/A |
| [heldout-prefix](heldout-prefix/README.md) | Post-hoc canonical-prefix refinement on all116 cases | Joint4 |
| [exact-budget](exact-budget/README.md) | Fixed exact budget on all69 m6 and47 m7 reference cases | N/A |
| [scored-seeds/validation.json](scored-seeds/validation.json) | All742 m≤4 classes and four m8 cases;1,888,160 independently checked seed pairs | N/A, selector validation |
| [final-window-trials](final-window-trials/README.md) | Full21-case k6/k8 trials and unfavorable outcomes | Joint6/B4 and8/B1 |
| [common-aux](common-aux/README.md) | All44 auxiliary runs, actual pairs, misses and pruning telemetry | COMMON8/12 |
| [tail-scored](tail-scored/README.md) | Maximum-first and sum-first common-input-distance seed rankings on all 22 controls | Joint4/B16; common distances only rank seeds |
| [paired figures](../../output/figures/family1-near-calibration/README.md) | Actual words, producing k and every prefix D beside20 winner graphs and the m8 graph | Explicit per figure |

In near/, cases.csv contains all364 final rows:20 calibration,343 frontier
and one m8. Producing k is N/A for exact layers and numeric for joint
producers; configured joint k is always explicit. A graph may occur in more
than one dataset. Native records are retained separately for all three runs.
summary.json distinguishes the passing winner gate from the failing broader
gate and lists counterexamples certified by prior uppers.

All exact labels enter the benchmark analysis after query outputs are sealed.
Only graph tables and fixed parameters reach native queries. Source/binary
fingerprints and complete input keys are pinned. Prior certificates are
replayed independently; their words are never native query hints.

## Reproduce the implemented finder

From the repository root, use fresh output directories:

    cmake -S . -B out/build/near -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build out/build/near -j 6
    ctest --test-dir out/build/near --output-on-failure
    python3 scripts/family1_near_benchmark.py \
      --exe out/build/near/Family1NearPair --out out/near-repro/final-calibration
    python3 scripts/family1_near_benchmark.py \
      --exe out/build/near/Family1NearPair \
      --pool results/family1-neighbor-seeds/near-top.jsonl \
      --exact results/family1-neighbor-seeds/near-top.jsonl \
      --out out/near-repro/final-frontier343
    python3 scripts/family1_near_benchmark.py \
      --exe out/build/near/Family1NearPair \
      --pool results/family1-finder-strategies-20261026/near/records-m8.jsonl \
      --out out/near-repro/final-m8

The last command uses the public m8 record as a geometry source; the runner
strips its witness and scores before forming a query. It does not pass the
known upper 50 or the previously found 52 pair to the finder.

For the prefix-grid ablations, build Family1Joint and run:

    python3 scripts/family1_prefix_strategy_benchmark.py \
      --exe out/build/near/Family1Joint --out out/near-repro/prefix
    python3 scripts/family1_prefix_strategy_benchmark.py \
      --exe out/build/near/Family1Joint --out out/near-repro/prefix-wide \
      --config 4:16:512:permutation --config 4:64:128:permutation \
      --config 3:32:1024:permutation --config 4:8:4096:permutation
    python3 scripts/family1_prefix_strategy_benchmark.py \
      --exe out/build/near/Family1Joint --out out/near-repro/prefix-deep \
      --config 4:16:1024:permutation --config 4:64:128:permutation \
      --prefix-depth 20 --prefix-words 1048576
    python3 scripts/family1_near_publish.py --experiments out/near-repro \
      --out out/near-repro/public --gallery out/near-repro/gallery

The publisher verifies compile-time source fingerprints against the matching
source files and checks every native record/journal hash before drawing.
Other experiment directories have their own source-pinned reproduction
instructions. Full journals, binaries, source snapshots and render previews
stay local under out/family1-finder-strategies-20261026. Every public file is
below1 MiB.

## Verification

The [verification record](verification.json) pins the tested source inventory,
published data, method documents and remaining quality failures.

All 12 CTests pass, including independent full-family replay, complete small
references, whole-window budget refusal, exact-vs-joint producer metadata,
compact fallback, repeat determinism and output/journal integrity. The seed
selector is separately checked against29,944,370 scalar pair-mask coordinates.
Independent forward BFS checks 226,922 common-input pair-mask distances and
4,470 full-mask score aggregates across 745 graphs. The final publisher also
verifies the historical m8 length-50 certificate
independently, without supplying it to search.

Runtime fields are observed local measurements, sometimes collected with
other experiments running. Exact word work, prefix word work and joint node
work remain separate units. A memory limit refers to planned payload, not
total process RSS. Correct certificates and semantic tests do not imply a
near-shortest quality guarantee.
