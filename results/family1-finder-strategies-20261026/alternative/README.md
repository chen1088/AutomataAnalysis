# Alternative searches: deterministic SAT and full-profile cycles

Both methods have **k=N/A**: neither is a joint lookahead window.
They are development experiments on all 20 certified rooted winners through
m=7. Every query receives graph tables only. Reference scores and witness
strings are joined after both complete query sets are sealed.

| Method | Found / 20 | L=H / 20 | Largest positive gap | Found among m=6,7 / 10 |
|---|---:|---:|---:|---:|
| SAT/CEGAR | 10 | 6 | 4 | 0 |
| Full-profile graph / return cycles | 10 | 10 | 0 | 0 |

These methods do not meet the required recovery gate. They should not replace
the stronger rolling/portfolio search. All positives, actual word pairs,
prefix disagreement traces, misses, reference labels and work appear in
[cases.csv](cases.csv); [summary.json](summary.json) pins source/backend/input
hashes and limits. Unsuccessful pilot variants remain local.

## SAT/CEGAR

The solver creates two length-L binary words, requires distinctness and equal
final states on each active static-mask DFA, and searches the whole joint
word-pair space. A safe Family 1 symmetry fixes the first input of the
lexically first word to zero. Each SAT model is replayed on every original
static mask. All failing masks, in numeric order, are added to the formula.
UNSAT for an active mask subset implies UNSAT for the full family; a fixed
work-budget result remains UNKNOWN.

The published configuration uses one-hot state variables, forward transitions
plus redundant inverse-support clauses, and decisions only on input letters.
The other variables are forced by propagation when inputs are fixed.
Initial constraints are all permutation-mask DFAs, or mask zero if none exist.
The universal length schedule is 1,2,4,8,...,80; a positive is tightened using
its own length and the accumulated CNF lower bound. No reference H determines
length selection or stopping. Each length gets fixed budgets of 20,000
conflicts and 5,000,000 propagations; a propagation batch can overshoot its
counter target before the solver checks its budget again.

The local MiniSat 2.2 backend is compiled after removing its RNG implementation
and every RNG call, including random branch selection, random initial activity
and random polarity. This is stronger than fixing a seed. The compiled source
has no drand/irand calls, and every run reports zero random decisions. There
are no clock limits. The build manifest pins the original solver archive,
patched source, wrapper and shared-library hashes.

Binary and one-hot encodings both matched every exact graph score on all 64
rooted accessible classes through m=3: 128 encoding/case checks and 964 final
mask replays. A repeat m=4 query reproduced its full result, witness, mask
sequence and all solver work counters exactly.

Other tested pilots included binary states, all-variable branching, more
per-length work, linear length schedules, and a restricted differing-prefix /
common-tail formula. None produced a competitive m=6,7 result. Restricted
formulas never promote UNSAT to a global hard-pair lower bound.

## Full endpoint-profile graph

The second method explores single-word endpoint vectors across all lengths.
Equal full vectors can merge even when their shortest representative words
have different lengths. This can expose short cycles that same-length
collision enumeration would overlook.

If a prefix p reaches a full profile q, and a and b are return cycles at q
starting with different letters, then p+a+b and p+b+a are distinct equal-length
hard words. The code also checks collisions among all canonical-prefix
extensions in a complete depth group. Full profile equality is checked after
hash lookup; a hash alone is never a state identity.

The published budget is 262,144 stored profiles, 64 deterministic cycle roots,
10,000,000 return-search edges, and maximum output length 80. The graph can be
incomplete and state-capped; this yields no exclusion of unvisited profiles.
A stronger pilot found no return cycles after 4,194,304 profiles on the first
m=6 winner and 2,097,152 profiles on the first m=7 winner. Both stored edge
subgraphs still had only singleton strongly connected components.

All 64 exact small classes through m=3 matched their true optimum under this
method as well. Every final positive passed independent Python scalar replay.
The two complete 20-case matrices required 396 final word-pair/mask checks.

## Reproduction

The profile graph search has no external dependency:

    g++ -O3 -std=c++23 -I . tests/Family1ProfileCyclesBenchmark.cpp \
      Family1LargeGraph.cpp Family1ExactPacked.cpp -o out/profile-cycles
    out/profile-cycles cases.keys 262144 64 10000000 out/profile-cycles.jsonl

Each line of cases.keys is one canonical graph key; the public CSV contains
all 20 keys. The runner never reads reference scores or witness strings.

SAT reproduction needs the MiniSat 2.2 archive vendored in the pinned
python-sat 1.9.dev17 source distribution, not a random-enabled binary:

    python3 -m pip download --no-binary=python-sat --no-deps \
      python-sat==1.9.dev17 --dest out/sat-source

Extract its solvers/minisat22.tar.gz, then run:

    python3 scripts/family1_sat_pair_experiment.py \
      --archive PATH/TO/minisat22.tar.gz --build out/sat-native \
      --cases cases.jsonl --out out/sat-reproduction \
      --encoding onehot --inputs-only --schedule bracket \
      --conflicts 20000 --propagations 5000000

Every cases.jsonl row supplies only key and canonical_table. The script builds
the patched RNG-free backend automatically. Rebuild explicitly with
--rebuild when changing the wrapper. Python and native sources are pinned in
summary.json; complete native traces and source archives stay under
out/family1-finder-strategies-20261026/profile/.
