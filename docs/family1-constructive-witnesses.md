# Constructing merge witnesses for one seed

`Family1Construct` produces an explicit pair of distinct equal-length words
that merge under every static mask of one seed graph. `Family1Sample` looks
for shorter pairs using structured candidates and packed sampled-mask states.
Every accepted sample is then verified independently over all static masks.
Both tools produce upper bounds on the seed's shortest merge length `H(G)`.
They do not certify shortestness or a global maximum over graph classes.

## A deterministic pair

Fix a static mask `sigma`, and write `f_sigma` for its zero-letter function
and `g_sigma` for its one-letter function. The bit at each state is fixed on
every revisit, so these are ordinary functions on the seed's `m` vertices.

Let `a_sigma` and `p_sigma` be the tail length and eventual cycle length of
the orbit of the root under `f_sigma`. Choose

```text
A = max_sigma a_sigma.
```

The state `f_sigma^A(root)` lies on that cycle for every mask. Put
`q_sigma = g_sigma(f_sigma^A(root))`, and let `b_sigma` and `r_sigma` be the
tail length and cycle length of the zero-letter orbit starting at `q_sigma`.
Choose

```text
B = max_sigma b_sigma,
P = lcm({p_sigma : all sigma} union {r_sigma : all sigma}).
```

Then the words

```text
u = 0^(A+P) 1 0^B,
v = 0^A     1 0^(B+P)
```

have the same length `A+B+P+1` and merge for every mask. The initial extra
`P` zeroes return the root orbit to the same cycle state, so both words
reach `q_sigma` immediately after their unique one. After `B` zeroes that
state is on its zero-letter cycle; the final extra `P` zeroes return it to
the same endpoint. This proves equality separately for each fixed mask.

`P` is positive. The unique one occurs at zero-based positions `A+P` and
`A`, respectively, proving that the two words are distinct, including cases
where `A` or `B` is zero. The length bound is therefore a valid positive,
equal-length merge bound.

The construction uses all masks of a single graph. It does not combine
different seeds or seed sizes into a product.

## A generic pair and the role of cycles

Every functional tail has length at most `m-1` and every cycle length is at
most `m`. Thus an immediate construction, without mask enumeration, uses

```text
A = B = m-1,
P = lcm(1,2,...,m).
```

Its word length is `2m-1+lcm(1,...,m)`. This universal bound is generally
loose and does not establish a polynomial bound in `m`. At `m=20`, the
generic period is 232792560 and the word length is 232792599. The graph-specific
routine computes smaller tail and period requirements when possible.

For an accessible seed, the cycle lengths seen in root zero-letter orbits
over all masks are exactly the lengths of the seed's simple directed cycles.
One inclusion is immediate. For the other, take any such cycle and a simple
path from the root to its first entry into that cycle. Choose a static mask
whose zero transition follows that path and the cycle. Their disjointness
before the entry makes the choices consistent. Every suffix cycle is thus
already represented among the prefix cycle lengths, possibly under another
mask. Consequently `P` equals the prefix period; including suffix periods
again is a valid consistency check.

## Native implementation and verification

The native constructor enumerates `2^m` masks, for `1<=m<=20`, computes the
root and post-one functional orbits, and emits three run-length blocks for
each word. Zero-count blocks are retained. It materializes full strings only
when the explicit materialization limit permits them.

After constructing the parameters, a separate scalar verifier evaluates
both endpoints for every mask. It reduces large exponents after detecting
an actual repeated state; it does not expand the words, reuse the constructor's
orbit metadata, or rely on endpoint hashes. The output records the full
transition table, parameters, cycle lengths, mask count, verification status,
and SHA-256 provenance. A successful output certifies the reported upper
bound; `exact_score_certified` remains false.

For example, the two-state global maximizer has `H=3`. Its deterministic
orbit construction gives `A=B=1,P=2`, hence the longer witness of length five.
The structured sampler's first candidate at length three is `010 / 100`,
which is a shortest pair for this graph. A valid construction need not be
a shortest construction.

## Searching shorter structured pairs

The default sampler proposes

```text
p A B z / p B A z
```

with noncommuting blocks `A,B`, so the proposed words are distinct and have
equal length. The common prefix state is reused while evaluating the two
orders of the blocks. Random and mixed modes also compare different words
with the same sampled endpoint profile.

A packed profile represents complete states for up to 64 fixed masks, using
one membership bitset per graph state. A transition splits the bits at each
state according to those masks' fixed bits and routes the subsets through
the two ports. Revisiting a state uses the same bits. Prefix caching avoids
replaying shared prefixes.

Hashes locate possible profile matches. Matching hashes must also have
identical complete packed profiles. A sampled match then triggers an
independent ordinary scalar replay for every one of the graph's `2^m` masks.
Only a pair passing this full check is accepted. A separating mask can
refine the sampled set, after which cached profiles are rebuilt.

A miss, a partial run, or a failed projected candidate does not certify
injectivity at the requested length. Such results keep lower bound one,
unknown upper bound, and no witness. Even when a pair is accepted, it only
proves `H(G)<=length`; no statement about all shortest pairs or global graph
coverage follows.

The seed, candidate index, sampled masks, and cache word indices make
restarts deterministic. Completed results require their intact hashes and
the identical configuration. Partial checkpoints resume the same candidate
sequence; a changed graph, seed, or sampling budget is rejected.

## Reproduce

Use the existing Windows MSVC/vcpkg build. From the repository root:

```powershell
$constructExe = '.\out\build\msvc-vcpkg\Release\Family1Construct.exe'
$sampleExe = '.\out\build\msvc-vcpkg\Release\Family1Sample.exe'
& $constructExe --graph 00010001 --out out\construct-m2 --materialize-limit 100
& $sampleExe --graph 00010001 --out out\sample-m2 --length 3 --samples 10000 --mode commutator
```

The two-state key denotes `[[0,1],[0,1]]`. Graph keys use two decimal digits
per target, in source-state and port order. New runs require empty output
directories. Repeat the exact command with `--resume` to reuse a completed
result. Add `--limit-samples N` to pause a sampler after at most `N` more
candidates, then resume with `--limit-samples 0` to finish the original budget.

Independent integration checks:

```powershell
uv run --no-project python tests/family1_construct_cli_test.py --exe $constructExe
uv run --no-project python tests/family1_sample_cli_test.py --exe $sampleExe
```

The references enumerate all 64 rooted accessible classes through three
states by exhaustive transition tables and factorial root-preserving
canonicalization. They independently check every returned compressed pair,
every static mask, exact orbit parameters, loops, coincident ports, revisits,
forced hash collisions, false projected hits, and resume integrity. Sample
acceptances at sizes four through six are also replayed over all masks.

Both Release CLI suites passed on 2026-10-26. The
[portable validation record](../results/family1-native-witness-validation/validation.json)
pins the native executables, test sources, commands, and checks.

## Performance measurements

The test tools offer reproducible measurements on fixed workloads:

```powershell
uv run --no-project python tests/family1_construct_cli_test.py --exe $constructExe --work-dir out\construct-validation-benchmark --benchmark-m 16 --benchmark-repeats 3
uv run --no-project python tests/family1_sample_cli_test.py --exe $sampleExe --work-dir out\sample-validation-benchmark --benchmark
```

The constructor comparison computes the same parameters and checks the same
universal pair over all masks in Python and C++. Its native timing includes
process startup and output I/O, while the Python timing omits output I/O.
The algorithms are independently implemented, so an observed ratio describes
these two end-to-end implementations, not a language-only speed ratio.

The sampler benchmark compares packed and scalar native kernels on exactly
10,000 deterministic length-64 words and the same 64 sampled masks. Complete
profiles must agree. Candidate hit frequency is excluded from this comparison;
sampling success is not used as a substitute for timing a fixed workload.

On the recorded size16 constructor workload, all 65,536 masks were processed
and independently verified. Three repeats gave a Python median of 0.62084
seconds and a native whole-invocation median of 0.013159 seconds, an observed
ratio of 47.18. Both produced `A=12,B=12,P=48`, giving a witness of length73.
The complete repetitions and executable hash are retained in
[the benchmark record](../results/family1-native-witness-validation/constructor-benchmark.json).
