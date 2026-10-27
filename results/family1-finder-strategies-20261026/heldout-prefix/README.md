# Post-hoc canonical-prefix development comparison

These two fixed configurations test every member of the same116-case pool
after the scored-seed failures were inspected. The 114 originally held-out
identities are still flagged, but this comparison is development validation,
not a new independent holdout.

| Configuration | Joint k | Beam | Canonical prefix pairs | Prefix depth / words |
|---|---:|---:|---:|---|
| canonical-deep | 4 | 64 | 128 | 20 /1,048,576 |
| canonical-wide | 4 | 16 | 512 | 16 /65,536 |

Both use permutation-first ranking, the mandatory empty-root attempt plus
the deterministic bounded prefix catalogue, common-prefix strata through 8,
maximum length 80 and2,000,000 expansions per attempt. There are no clock
limits or random choices. Each window enumerates all 4^4=256 leaves over
00,01,10,11. Every one of the 116 candidates ran under both configurations.

| Configuration | Originally held-out m6 exact /67 | Within two /67 | m6 misses | Maximum finite gap | m7 misses /47 | m7 U≤33 exclusions /47 |
|---|---:|---:|---:|---:|---:|---:|
| canonical-deep | 36 | 55 | 1 | 17 | 3 | 26 |
| canonical-wide | 37 | 57 | 0 | 11 | 1 | 21 |
| Minimum of both scored and both canonical configurations | 48 | 62 | 0 | 11 | 0 | 30 |

The four-way portfolio still leaves 17 m7 finite uppers≥34, and at least one
returned upper exceeds a separately verified historical upper by 12.
Therefore the broader data continue to reject a universal within-two claim.
Refinement always retains the minimum previously verified upper and charges
the work from every queried configuration.

cases.csv contains all 232 new rows, actual pair strings, k and full D traces.
input-cases.csv contains every table and overlap flag. The native CLI also
preserves full per-attempt reports and improvement journals in the ignored
local directory out/family1-finder-strategies-20261026/heldout-prefix.
Every final positive was independently scalar-replayed on all original masks.

Reproduce after regenerating the original 116-case pool:

    python3 scripts/family1_scored_seed_heldout_prefix.py \
      --pool out/scored-heldout-reproduction \
      --out out/canonical-prefix-reproduction

The source executable is --exe; the runner freezes it before querying.
All outputs are sealed before the reference scores are read.
