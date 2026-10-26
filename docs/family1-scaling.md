# Family 1 search through twenty states

The exhaustive search through six states establishes global maxima for every
rooted accessible class in that range. Extending the supported seed size to
twenty requires separating two computational questions:

1. How can one score a particular larger graph, with rigorous bounds or an
   exact shortest merge length?
2. How can one find promising larger graphs without visiting every graph class?

The larger-graph workflow uses exact canonical graph identities, SAT-based
scoring certificates, and heuristic graph generation. It retains every tied
class among the graphs evaluated. Its candidate-generation coverage does not
establish a global maximum over all twenty-state graphs.

## Why exhaustive graph enumeration does not scale to twenty

An elementary lower bound already gives at least

\[
\left(\frac m2\right)^m
\]

rooted accessible classes with unordered outgoing ports. To prove this, count
pairs consisting of a labeled graph and a directed Hamiltonian cycle contained
in that graph:

- There are `(m-1)!` directed Hamiltonian cycles through a fixed root on `m`
  labeled vertices.
- For a fixed cycle, choose each vertex's other successor arbitrarily from all
  `m` vertices. This gives exactly `m^m` different unordered transition tables
  containing that cycle. The extra successor may equal the cycle successor.
- Any graph with two outgoing ports has at most `2^m` contained directed
  Hamiltonian cycles: choose one successor at each vertex.
- A rooted isomorphism class contains at most `(m-1)!` labeled graphs.

Dividing the pair count by these two upper bounds gives the stated bound.
Every graph counted contains a directed Hamiltonian cycle, so it is accessible
and even strongly connected. Thus restricting to accessible graphs cannot
remove this obstruction.

At `m=20`, the bound is **10^20 graph classes**. Even an idealized billion
complete graph evaluations per second would require over three thousand
years. This bound ignores the cost of scoring each graph. A short list of
maximizers at small sizes does not imply that locating or certifying all
maximizers at larger sizes is easy.

## Exact canonicalization with discovery labels

Root-preserving isomorphism and independent swaps of the two ports can still
be handled exactly at twenty states. Factorial vertex-permutation enumeration
is unnecessary for rooted accessible graphs of this fixed outgoing degree.

Give the root label `0`. Scan source vertices in label order, sorting their two
successor labels. Assign an unseen successor the next unused label. There are
only four cases:

- Both successors are already labeled: their sorted row is fixed.
- Exactly one successor is unseen: its new label is forced.
- Both successors are the same unseen vertex: assign one new label.
- The two successors are distinct and both unseen: branch on which original
  vertex receives the first of the two new labels.

Take the lexicographically least completed table over these branches. Every
accessible rooted graph admits such a discovery labeling. Its least table over
all root-fixing permutations also has this property: at the first skipped
unused label, exchanging it with the newly referenced larger label would
decrease the table at its first differing entry. Therefore restricting to
discovery labelings preserves the true canonical minimum.

Only the last case branches. Each such branch discovers two new vertices, so a
root-to-leaf path has at most `floor((m-1)/2)` binary choices. At twenty states
there are at most **512 completed discovery labelings**, rather than `19!`
vertex permutations. Early lexicographic comparison can reduce the actual
work further. Coincident ports and loops remain valid throughout.

This canonicalization makes deduplication of generated graphs exact. It does
not make the collection of generated graphs exhaustive.

## Fast certified lower bounds

Before asking SAT, the scorer expands endpoint vectors on a deterministic
selection of at most 64 static masks. For `m<=6` this selection contains every
mask. For larger graphs it includes the all-zero and all-one masks, followed
by distinct masks from `std::mt19937(0x46414d31U+m)` reduced to `m` bits.

If every word of length `L` has a different endpoint vector on this subset,
then every such pair also differs in the full family. Thus a collision-free
completed layer proves `H(G)>=L+1`. A collision in the subset only supplies a
candidate; the universal verifier must check it before it supplies an upper
bound. The implementation compares complete projected states after hash hits.
It never treats a sampled collision as a full-family collision.

The default projection depth is 20 with at most `2^20` states per layer.
Explicit budgets permit depth 26 and `2^26` states; at twenty vertices the
largest production layer uses about 4.3 GiB peak memory. The independent scalar
replay uses about 6.5 GiB. Multiple jobs multiply memory requirements. A partial
layer or allocation failure preserves only earlier completed bounds.

A structural shortcut recognizes a simple root path whose prefix rows are
`{root,next}`. If it has `D` distinct vertices, then `H(G)>=D`: for two different
words of length less than `D`, set the static bits along the path so that the
first word advances at every step. The other word resets to the root at its
first disagreement and cannot catch up by the final step. This gives the
twenty-state reset cycle a lower bound of 20 without word enumeration. The
bound is capped to the requested maximum query length plus one in exports.

## SAT scoring without enumerating all words or masks

For a fixed seed graph, let `C(L)` mean that two distinct words of length `L`
have the same endpoint under every static mask. A common suffix preserves
endpoint equality, so

\[
C(L)\Longrightarrow C(L+1).
\]

Consequently, proving that no collision exists at a single length `L` also
rules out every shorter positive length. This permits queries at selected
lengths rather than expanding every word layer.

The scoring procedure maintains a set `S` of sampled static masks. It uses two
SAT queries with different purposes.

### Candidate query

The candidate solver chooses shared word arrays `u` and `v`, each of length
`L`. It requires that the words are distinct and that their final states agree
for every mask in `S`. The transitions for a particular sampled mask are
ordinary deterministic transitions; all samples use the same word variables.

If this query is **UNSAT**, no universal collision at length `L` exists:
a pair colliding under every mask would also collide under every sampled mask.
Together with monotonicity, this certifies

\[
H(G)\ge L+1.
\]

If it is **SAT**, the model supplies only a candidate word pair. Agreement on a
subset of masks is not yet a collision for Family 1.

### Universal verifier query

For the fixed candidate words, the verifier chooses one static mask `sigma`
and asks whether their final states differ. It uses **the same mask vector**
for both trajectories, with one fixed bit per vertex on every revisit.

If this query is **SAT**, its model is a separating mask. Add that mask to `S`
and repeat the candidate query. This is counterexample refinement: the new
constraint excludes the rejected candidate and possibly many others.

If it is **UNSAT**, no mask separates the fixed words. They are a genuine
universal collision, certifying

\[
H(G)\le L.
\]

If symbolic verification times out while aggregate time remains, direct
simulation over every static mask is an exact fallback. At twenty vertices
there are `2^20` masks; checking one fixed pair needs very little memory.

The verifier's static-mask variables are essential. Choosing a different mask
for each word, or a fresh bit on each visit, would test a different property.

The implementation uses the [Z3 solver](https://github.com/Z3Prover/z3).
No claim about exactness depends on how quickly the solver succeeds: the
logical meanings of SAT, UNSAT, and an unfinished query remain distinct.

## Bounds, exact scores, and time limits

Maintain a certified interval

\[
\mathrm{lower}\le H(G)\le\mathrm{upper},
\]

where the upper bound is absent until a universally verified witness exists.
Start with `lower=1`. A candidate UNSAT result at length `L` raises the lower
bound to at least `L+1`. A verifier UNSAT result at length `L` supplies a witness
and lowers the upper bound to at most `L`.

Queries can use increasing trial lengths to find an upper bound and then
binary search the remaining interval. Masks discovered at one length remain
valid samples at every other length. Equality of the bounds certifies the exact
shortest merge length. A witness at length `L` by itself proves an upper bound;
it does not prove that `L` is shortest.

A solver timeout, interrupted refinement, iteration limit, or resource failure
provides no new SAT/UNSAT conclusion. Preserve only bounds established by
completed queries. A run may therefore finish with a certified lower bound, or
a nontrivial interval, while the exact score remains unknown. Scoring limits
and reasons for incomplete work belong in the exported record.

This procedure can avoid explicitly storing `2^m` mask coordinates and `2^L`
word states. It remains an exact algorithm with potentially difficult queries;
there is no guarantee that it will determine every twenty-state graph's exact
score within a practical budget.

Safe word symmetries include swapping the two candidate words and complementing
both words. The latter permutes the full family's masks by complementing every
vertex bit. A common prefix cannot generally be removed: after it, different
mask coordinates may be in different vertices. In particular, requiring the
two words to differ in their first symbol can discard valid collisions.

## Generating and comparing larger candidates

The exploration workflow grows known seeds, mutates transitions, and uses
random starts. One useful growth operation preserves accessibility by
construction. Choose an old edge `s -> b`, replace it by `s -> new`, and give
the new vertex successors `{b,c}` for any old or new vertex `c`. Any old
reachability path can replace `s -> b` by `s -> new -> b`; the new vertex is
also reachable. This operation does not guarantee that the merge length
increases.

Canonicalize each generated seed before scoring and deduplicate by its full
canonical table. The random generator, candidate order, and journal commit
order are deterministic. Wall-clock solver limits can change bounds and parent
selection between fresh runs on different workloads or machines. Resume reuses
recorded scores and parent choices. A bounded candidate collection, local
mutation search, or beam search covers a restricted collection; none proves
that another graph class cannot have a larger score.

Keep the following conclusions separate:

- An exact score belongs to a particular graph.
- A best exact score among evaluated graphs is an incumbent, not a global
  maximum over all graphs of that size.
- Every distinct evaluated graph tied at that best exact score must be retained.
- Unresolved evaluated graphs can still have a larger score. Their lower and
  upper bounds must remain visible alongside exact incumbents.
- A graph whose certified lower bound exceeds the incumbent already proves
  that the incumbent cannot be the best evaluated graph, even when its own
  exact score is unknown.

The generated records and summaries should identify the candidate-generation
method, random seed, scoring budgets, and graph coverage as nonexhaustive.
The separate exhaustive results through six remain unchanged.

## A possible future global proof method

A second counterexample-refinement loop could synthesize the graph itself.
For each collected word pair, require the variable graph to separate that pair
under some static mask. Reject a proposed graph by finding a universal
collision of length at most `L`, then add the corresponding separation
requirement. If the graph-synthesis query eventually becomes UNSAT, it proves
that no graph in its encoded scope has `H(G)>L`. Proving the optimum would
still leave enumeration of every maximizing class, with suitable blocking and
isomorphism handling.

This global synthesis method is now implemented by `Family1GlobalCheck`.
It has independently reproduced global upper bounds through four states.
Larger attempts remain unresolved; see
[the global-certificate documentation](family1-global-certificates.md).

## Commands and measured results

Build using the existing Windows script; the pinned manifest now also installs
Z3 5.1.0. Native MSVC/vcpkg Debug and Release builds passed.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-windows-vcpkg.ps1 -Configuration Release
.\out\build\msvc-vcpkg\Release\Family1Explore.exe --out out\family1-explore-new --min-m 7 --max-m 20 --candidates 16 --jobs 4 --dot
```

`--candidates` bounds the generated collection at each size, while `--beam`
chooses parents for the next size. Beam selection never truncates exported
ties. `--jobs 1..32` evaluates independent graphs concurrently using independent
solver contexts, committing results in candidate order. A new run requires an
empty directory. Resume uses the same command and settings with `--resume`;
`--limit-graphs N` supplies a reproducible stopping point. Generation and scoring
settings are fixed in `run.json`; to rescore a graph with a larger budget use
its key with `--graph` in a new directory.

Each run exports `graphs.jsonl`, all best lower-bound ties in
`best_lower_bound.jsonl`, all best exact-score ties in `best_exact.jsonl`, and
all still-possible best graphs in `potential_best.jsonl`. Bounds on unresolved
graphs remain visible. `summary.json` always marks graph coverage as heuristic
and global maxima as unproved, including single-graph runs. Optional DOT files
cover all best exact and lower-bound ties.

Measured runs evaluated 56 candidates across sizes 7 through 20 and eight
additional twenty-state candidates. All eight additional candidates have
certified `H>=25`. One was tested further through depth 26 and has **`H>=27`**,
with no exact score or witness upper bound established. The snapshot preserves
all evaluated graphs and all observed ties in
[the larger-search results](../results/family1-through20/README.md).

The stronger twenty-state bound can be reproduced and independently replayed:

```powershell
$key = '01020304030506070008090910111012060613141516000211170812111800080112001316191013'
.\out\build\msvc-vcpkg\Release\Family1Explore.exe --out out\family1-twenty-proof --graph $key --max-length 26 --projection-depth 26 --projection-max-states 67108864 --timeout-ms 90000 --dot
.\out\build\msvc-vcpkg\Release\Family1ProjectionVerify.exe --graph $key --depth 26
```

The production proof completed in about 26 seconds on the local machine. The
independent verifier represents every coordinate as an ordinary byte state,
uses direct per-mask XOR transitions, and compares complete endpoint vectors;
it does not call the production bitplane, SAT, or graph-canonicalization code.

Validation commands:

```powershell
ctest --test-dir out\build\msvc-vcpkg -C Release --output-on-failure
ctest --test-dir out\build\msvc-vcpkg -C Debug --output-on-failure
uv run --no-project python tests\family1_explore_cli_test.py --exe out\build\msvc-vcpkg\Release\Family1Explore.exe
uv run --no-project python tests\family1_explore_cli_test.py --exe out\build\msvc-vcpkg\Debug\Family1Explore.exe
```

The original five registered CTest tests passed in both configurations; the
additional global-synthesis regression also validates whole-graph proofs and
replay. Symbolic queries
were independently checked on every one of the 64 classes through three
states. Canonicalization matched full permutation enumeration through four
states and 3,200 transformed twenty-state graphs. The CLI tests cover ties with
beam one, parallel SAT contexts, ordered partial batches, resume, torn and
invalid checkpoints, and a twenty-state witness checked over all 1,048,576
masks. The original exhaustive search and generating-function programs remain
available. Linux/WSL builds were not run. No exhaustive coverage, exact global
maximum, or complete global maximizing collection through twenty is claimed.
