# Complete local refinement ablations

These operators start from pairs actually found by deterministic search.
They receive no exhaustive scores or reference word pairs. All success
claims are independently replayed on every original static-mask DFA.
Local optimality is not a proof of global shortestness.

The [older input](older-seed-input/input-cases.csv) contains all 20 certified
winner graphs, with pairs found at joint k=4, beam 4, permutation-first ranking,
1,024 canonical prefix seeds, prefix depth 16 and 65,536 prefix words.
The [closer input](closest-input/input-cases.csv) is a frozen minimum-upper
portfolio of actually found pairs; its producing joint k values are 3,4,6.
The latter already has15 optimal pairs and all 20 within two of exact H.
These are development cases used for strategy selection.

| Local operator | Refinement k | Older pairs improved /20 | Optimal after refinement /20 | Candidate evaluations |
|---|---|---:|---:|---:|
| One through three arbitrary deletions | N/A | 0 | 11 | 18,464 |
| Deletions, one substitution and contiguous-block changes | N/A | 0 | 11 | 242,130 |
| Deletions plus substitutions, total budget 4 | N/A | 1 | 12 | 3,599,667 |
| Exhaustive common-tail replacement | Common-suffix16 | 3 | 13 | 25,077,640 |
| Exhaustive prefix replacement | Binary-prefix16 | 1 | 12 | 25,393,448 |

The older pairs start with 11 optimal and 17 within two. No listed operator
reaches all 20 within two. On the closer frozen input, the complete budget 4
edit operator evaluates2,491,739 words and improves none; common-tail k=18
tests65,120,999 continuations and improves none. Those stronger starting
pairs remain 15 optimal and 20 within two. Adding these local searches to
that portfolio therefore adds measured work without improving this corpus.

Each arbitrary-deletion neighborhood fixes the number d of removed
positions and unites all resulting words from both input words. All full
endpoint-profile collisions within the union are tested, including collisions
within either original side. The mixed operator also tests zero or one
substitution after d≤2 deletions, and every contiguous deleted block followed
by zero or one substitution. The budget 4 operator tests d=1..4 deletions
and at most 4−d substitutions; insertions are outside this declared family.
A shortening restarts the local process from the new pair. Each evaluated
fixed-length neighborhood is generated and tested completely.

Common-tail replacement keeps each distinct prefix pair and enumerates every
common binary continuation of lengths 0 through the configured k, truncated
only so the result must be shorter. Its alphabet is00,11 and k has2^k leaves.
It is a restricted local move after a full-joint pair, not a four-symbol
finder. Prefix replacement keeps either original suffix at each cut and
enumerates every binary replacement prefix of every improving length up to
k. It tests complete full-profile collisions among both suffix families
at equal total length. Its k counts binary prefix symbols, not joint steps.

Every started neighborhood completes even after finding a positive.
Fixed catalogue/work bounds are checked before evaluating a neighborhood;
no neighborhood was refused or partially evaluated in these two final runs.
The native self-test checks 1,522 deletion catalogues against independent
subset enumeration and two semantic graphs, including a graph whose common
prefix cannot be cancelled.

Source: Family1PairRefine.h, tests/Family1PairRefineBenchmark.cpp,
scripts/family1_pair_refine_benchmark.py. The runner snapshots and compiles
the exact sources, seals all native outputs, then attaches exhaustive labels.
Raw outputs and complete local-positive traces remain under
out/family1-finder-strategies-20261026/refine/final-prefix and final-closest.

Reproduce with a saved actual found-pair file and a fresh output directory:

    python3 scripts/family1_pair_refine_benchmark.py \
      --input found-pairs.jsonl --out out/refinement-reproduction \
      --modes deletion mixed edits4 tail16 prefix16

Each input row needs a canonical key, producing joint k and actual witness.
Use --strategy to select an exact strategy field from a multi-strategy file.
The public cases.csv files retain every output pair, producing/refinement k,
full disagreement trace, work and miss-free local status; input-cases.csv
retains every actual input pair and its source hash.
