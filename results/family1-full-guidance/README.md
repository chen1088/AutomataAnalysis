# Full-mask guidance for common suffixes

The optional header `Family1FullGuidance.h` uses the exact `2^m`-mask agreement
count as its beam objective at **every expansion and lookahead node**. It does
not guide on a small sample and then only rescore the final path.

The shared context and active-coordinate pruning come from
`Family1PairAgreement.h`. Both common letters are expanded. Neutral bridges
are retained, deterministic seed-based ties favor diverse parents/last bits,
and a neutral branch receives a reserved slot when beam width permits.
Lookahead is bounded to zero or one additional letter. A node-expansion budget
and optional interruption flag bound work. A miss supplies no lower bound.

## API

```cpp
auto context = std::make_shared<family1::PairAgreementContext>(graph);
auto result = family1::full_suffix_beam(
    context, u, v, max_suffix, 4, 1, 1088, nullptr, 10000);
```

`result.score_trace` contains the initial exact agreement count and one count
for each returned suffix letter. `mask_count` is always `2^m`. A positive
`permutation_mismatch_count` blocks every common-suffix continuation of this
prefix pair. Arbitrary indegrees are supported; an unbalanced seed has no
coloring with both letter maps bijective, and is still guided over every mask.

If `all_merged` is true, the sampler still independently replays the accepted
word pair with ordinary scalar transitions under all static masks. The helper
returns no shortest-score or global-optimum claim.

## Independent native validation

The standalone MSVC/O2 audit passed all 64 rooted classes through m=3, with
256 full-guidance searches. Every returned trace was checked by a separate
ordinary-state simulator over **all** masks. The H=4 plateau fixture retained
its neutral step, with exact trace `[4,4,8]` at denominator8, for both
lookahead0 and lookahead1. Expansion limits, interruption, and seeded
reproducibility passed.

The literal circulant has `tau0(i)=i+1 modm` and
`tau1(i)=i+floor(m/3) modm`.

| Case | Exact terminal agreement | Permutation mismatches | Outcome |
|---|---:|---:|---|
| m7, prefix pair 01 / 10 | 128/128 | 0 | A 25-letter common suffix was found |
| m20, prefix pair 01 / 10 | 262144/1048576 | 16 | Every common suffix is blocked |
| m20, prefix pair 0^5 1^5 / 1^5 0^5 | 1043502/1048576 | 0 | 5074 coordinates remain after 30 letters |

The last search used beam4/lookahead1, evaluated 674 nodes, and took about
0.982 seconds on this machine. Every intermediate trace entry was independently
checked by scalar simulation of all 1,048,576 masks. This is a bounded search
miss, not evidence excluding other suffixes or prefix pairs. The m7 constructed
pair has length27; the previously certified exact H=14 remains the stronger
score result.

`validation.json` pins the header/test sources and records the tested cases.
`release-test.log` retains native output. No main CMake or previous executable
was changed by this standalone audit. The sampler author integrates the helper
behind `--full-guidance` and performs a separate final scalar witness check.

To reproduce the standalone audit from an x64 Native Tools command prompt at
the repository root:

```bat
cl /nologo /O2 /EHsc /std:c++20 /I. tests\Family1FullGuidanceVerify.cpp Family1LargeGraph.cpp /Fe:out\Family1FullGuidanceVerify.exe /Fo:out\
out\Family1FullGuidanceVerify.exe
```
