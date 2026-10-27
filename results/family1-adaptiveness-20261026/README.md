# Deterministic adaptiveness benchmark

The [report](../../docs/family1-adaptiveness-report.md) compares edit-only,
finder-only and combined adjustments against the complete exhaustive findings.
Every winner tie is included. Graph generation and exhaustive oracles use
**k=N/A**; finder windows use the joint alphabet 00,01,10,11.

The result supports broader previous-size parent sets before a larger edit
radius, but also exposes serious finder error. At m=7, candidate coverage rises
from 1/8 to 8/8 winners when parents broaden at fixed joint k=2. Refinement
retaining the minimum verified upper from joint k=2/total and
k=4/permutation-first reduces misses on the broader fixed-root pool from
2,934 to 378. Neither adjustment makes the current scores reliable estimates
of shortest length. The count-three crowding gate fails to fire for the
initial fixed-root pool.

## Artifacts

| Artifact | Contents | k |
|---|---|---|
| [edit/coverage.csv](edit/coverage.csv) | All 40 complete-neighborhood coverage comparisons, preserving every true winner tie | N/A |
| [edit/generation-manifest.json](edit/generation-manifest.json) | Twenty sealed pools, complete independent generation checks and source hashes | N/A |
| [evaluation-audit.json](evaluation-audit.json) | Every declared neighborhood member evaluated, exact histograms through m=5 and independent scalar replay | N/A for exact truth; joint 2 for m=6,7 baseline |
| [finder/summary.json](finder/summary.json) | 6,278 fixed-pool queries, numerical error where exact truth exists, misses and work | Joint 2,4,6,8 |
| [finder/true-champion-results.csv](finder/true-champion-results.csv) | Every certified winner query, actual words and prefix traces | Joint 2,4,6,8 |
| [policy/m6/summary.json](policy/m6/summary.json) | All 11,693 six-state pool members | Joint 2 |
| [policy/m7/summary.json](policy/m7/summary.json) | All 13,329 seven-state pool members at each configuration | Joint 2,4 |
| [policy/m7/forced-factorial.csv](policy/m7/forced-factorial.csv) | Controlled edit-only/finder-only/both comparison, all-root and fixed-root views | Joint 2,4 |
| [policy/m7/crowding-gated.csv](policy/m7/crowding-gated.csv) | Actual outcomes when the finite top-band count-three gate controls adjustment | Joint 2,4 |
| [figures](../../output/figures/family1-adaptiveness/README.md) | Coverage, cost and quality charts; actual pair words beside example graphs and D traces | Explicit per figure |

The finder directory contains one complete case CSV per configuration.
The policy directories contain complete records-*.csv shards: every graph,
configuration, finite pair or miss, producing k and work. Every individual
artifact is below 1 MiB. Large native journals, per-attempt traces and binary
snapshots remain in the ignored local out/family1-adaptiveness-20261026 tree.
The public tables preserve actual final strings; source manifests pin the
complete raw journals.

## Reproduction

Start from the repository root. All run outputs must use fresh directories.
The [finder instructions](finder/REPRODUCE.md) build the native executable,
regenerate small exact corpora and run the fixed-pool joint k=2,4,6,8 matrix.
The [policy instructions](policy/REPRODUCE.md) regenerate and score complete
m=6,7 neighborhoods, export every result and reconstruct the policy cells.

For the entire coverage matrix, rather than just m=6,7:

    python3 scripts/family1_adaptive_edit_benchmark.py \
      --out out/adaptive-repro/edit \
      --publish out/adaptive-repro/edit-public \
      --figure out/adaptive-repro/coverage.svg

This includes complete radius 1 for m=2..7 and radius 2 for m=2..5.
No path/candidate cap may be reached. Generation asserts this and independently
compares every pool with complete Python occurrence/path enumeration.

The newly regenerated m=5 exact corpus uses no heuristic window, **k=N/A**:

    out/family1-adaptiveness-reproduction/build/Family1Offline \
      --m 5 --heuristics off --depth 15 \
      --max-layer-states 32768 --memory-mib 256 \
      --per-graph-ms 0 --max-graphs 0 --out out/adaptive-repro/exact-m5

Build Family1Offline as well as Family1Joint in the dependency-free build;
the finder reproduction guide includes the build. The m=5 records SHA256
in this run is 060f9d3e5b5d9fe5ebeb9139b2fb90d0d42930abb01300633112d7baf35cff5d.
All 10,398 rows are exact, the full histogram matches the earlier exhaustive
finding, and the maximum is 15 with five winners.

The cross-experiment audit checks every candidate key against a completed
evaluation and independently replays every final pair through every original
static mask, including multiplicities at coincident ports:

    python3 scripts/family1_adaptiveness_audit.py

Its defaults identify the original local run. For a fresh reproduction,
provide --work, --exact-template, --exact-m5 and --out pointing to the
regenerated corpora; the exact template includes a literal {m} placeholder.
It requires complete exact m=1..4 corpora, complete exact m=5, and the m=6,7
baseline policy records. Changing paths or build provenance changes hashes,
not the required key sets, histograms or deterministic search decisions.

Recreate the policy figure from the public CSV alone:

    python3 scripts/family1_adaptive_policy_figure.py \
      --out out/adaptive-repro/policy.svg

## Verification and limits

The independent cross-experiment audit passed all 40 neighborhood comparisons
over 36,162 distinct evaluated graphs. It scalar-replayed 20,387 final pairs:
1,142,914 word-pair/mask checks and 25,468,194 prefix updates. Separate finder
and policy publications also check every final/improving witness and every
exported row. No evaluated joint window was partial and no expansion budget
was reached.

The seven native/CLI/independent/figure CTests passed. These checks establish
the reported coverage and correctness of positive certificates. The quality
benchmark still fails on known hard graphs: even joint k=8/permutation-first
misses three m=7 winners, and its largest positive error there is 43.
No global m=8 or m=9 result follows.
