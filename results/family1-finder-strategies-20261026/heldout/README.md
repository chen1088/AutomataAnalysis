# Broader validation of scored seeds

This pool was excluded from selecting the new scored-seed configuration,
apart from two explicitly marked overlaps: all 69 exact m6 near-top graphs
include the two m6 training champions. The other 67 m6 graphs and all 47
m7 nonwinners give 114 strict held-out graphs. The pool is deliberately
enriched near the frontier, not a representative distribution of all graphs.

Every one of the 116 keys ran under both frozen configurations, with no
score, historical pair or time limit passed to search:

| Configuration | Joint k | Beam | Prefix depth / words | Catalogue | Selected |
|---|---:|---:|---|---:|---:|
| Original scored seeds | 4 | 16 | 20 /1,048,576 | 16,384 total | 512 |
| Compact scored seeds | 4 | 16 | 20 /1,048,576 | 4,096 per completed layer | 512 |

Both use permutation-first joint ranking after full-family seed scoring and
a complete exact-word fallback through depth 16 (oracle k=N/A). Seed
catalogues are deterministic bounded heuristics, not all compatible pairs.
Every subsequent joint window includes00,01,10,11. Maximum pair length is80,
with2,000,000 expansions per attempt and no clock limit.

| Configuration | Strict m6 exact /67 | Strict m6 within two /67 | Median / maximum finite gap | m7 misses /47 | m7 verified U≤33 /47 |
|---|---:|---:|---|---:|---:|
| Original | 33 | 56 | 1 /12 | 2 | 24 |
| Compact | 39 | 60 | 0 /12 | 0 | 20 |
| Minimum upper from both | 40 | 61 | 0 /12 | 0 | 24 |

All m6 queries return a pair, but these configurations do not establish a
within-two error on the broader corpus. On m7, the exhaustive certificate
identifies all 47 as nonwinners with H≤33; it does not give their exact H.
The original leaves 21 finite uppers≥34 and two misses. Compact leaves 27
finite uppers≥34. Both together retain 23 finite false-compatible cases.
Misses never become scores, and an upper alone is not a hardness proof.

The complete 232 rows, actual two words, configured/producing k and D traces
are in cases.csv. input-cases.csv preserves every canonical table and marks
the two overlaps. worst-cases.csv preserves all strict m6 cases whose
best scored upper exceeds exact H by more than two. analysis.json compares
the minimum verified uppers while charging both configurations.

Every final positive passed independent all-mask replay:20,608 word-pair/mask
checks. Native inputs and outputs were sealed before target scores were
used. The post-search analysis was rerun after correcting an analysis-only
import; summary.json pins the analysis source separately from the unchanged
frozen query driver. No search result or parameter changed.

Reproduce with a fresh output directory after building the scored-seed
benchmark binary and freezing its sources:

    python3 scripts/family1_scored_seed_heldout.py --out out/scored-heldout-reproduction

The default source and 20 training-key input identify the original local run.
Use --source, --tuned-input and --frozen-source for regenerated paths.
The frozen native driver and source manifest remain under
out/family1-finder-strategies-20261026/scored-seeds/fast-source.
Use --analyze-only to replay and analyze the already sealed native outputs;
it verifies their hashes and launches no search.

Additional canonical-prefix configurations selected after these failures
are documented in ../heldout-prefix. Those are post-hoc development
comparisons, not a new held-out qualification.
