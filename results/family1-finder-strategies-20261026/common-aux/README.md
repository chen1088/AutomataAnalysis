# Fixed common-suffix auxiliary: negative comparison

All 22 declared graphs were tested twice: the 20 certified winner graphs,
the m7 nonwinner counterexample 0102000304050203000604050003, and the held
m8 graph 01020003040501060003020705060407.

This is an auxiliary restricted search after distinct prefixes. Configured
**COMMON k=8 and COMMON k=12** count common binary suffix symbols; an
unpruned tree has **2^k leaves**, unlike the full-joint finder's 4^k leaves.
It does not cover all four-symbol continuations. The exact prescore uses
**k=N/A** and solves the 12 cases through m6 before any heuristic suffix
search; producing k is recorded accordingly.

| Configured COMMON k | Winners found /20 | Optimal /20 | Within two /20 | Largest positive L−H | Nonwinner counterexample | Held m8 upper |
|---|---:|---:|---:|---:|---|---:|
| 8 | 20 | 14 | 17 | 4 | miss | 53 |
| 12 | 20 | 14 | 16 | 4 | miss | 55 |

The m7 winner lengths in canonical-key order are:

- COMMON k=8: 37,36,34,38,34,36,38,36.
- COMMON k=12: 36,37,34,38,34,36,38,38.

Every m7 winner has exact H=34. Neither configuration improves the new
full-joint calibration portfolio, neither finds the extra nonwinner pair,
and both return a longer m8 pair than its existing verified upper 50.
These results do not justify adding the auxiliary to the default pipeline.

Every parameter was fixed before querying. Both runs use beam 8, distinct
graph-derived prefix pairs 128, prefix depth 20, prefix words 1,048,576 and
common-prefix strata through 8; exact prescore depth 24, full layer cap
16,777,216 and packed payload 256 MiB; conditional exact-tail threshold 8,
50,000 states and depth 80; 2,000,000 expansions per prefix and maximum length 80.
Window and maximum-window are both set to the tested k. Target upper is 0,
all supplied graphs are evaluated, and all clock limits are disabled.
The native executable is deterministic; neither query sees reference scores
or saved reference pair words.

The native legacy finder uses coordinate viability and distance proofs to
prune branches in the restricted common-suffix space. Its retained metric
reports therefore need not contain every leaf. At COMMON k=8, 28 retained
reports are complete and 116 are incomplete; at COMMON k=12, 19 are complete
and 125 incomplete. Additional reports are truncated: 13,213 and 8,565,
respectively. These are retained diagnostics, not full global window counts.
No full-window or full-joint coverage claim is made.

All 42 final positive pairs passed independent scalar replay on every
original static mask: 3,212 pair/mask checks. cases.csv retains every pair,
full D trace, actual/configured k, reference label where available and both
misses. input-cases.csv contains all geometry. The query outputs were sealed
before labels were attached. The analysis adapter was corrected to distinguish
oracle k=0 from configured COMMON k and bounded completed evaluations from
exact scores; it then revalidated the unchanged completed native outputs
without repeating a query. Native-runtime fields are omitted after that
analysis-only replay.

Build the dependency-free Family1Offline target, then run:

    python3 scripts/family1_common_aux_benchmark.py \
      --exe out/build/joint-solid-linux/Family1Offline \
      --out out/common-aux-reproduction

The default geometry sources are the two committed exhaustive winner-table
files. The runner strips them to keys before querying and appends the two
fixed diagnostic keys. Its frozen original binary SHA256 is
95fb3e9e4a7d7fcf301228ad5ac2f41e073bc18692eccc6bb52484e5164be5e9.
Use --resume-native only to revalidate already completed batches; it launches
no search.
