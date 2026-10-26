# Complete-mask individual scoring

`Family1ExactPacked.h/.cpp` implements `family1::score_packed` for individual
graphs with 1–20 vertices. It complements the symbolic solver; it does not
enumerate graph classes or certify a global maximum by itself.

Every static mask is represented. A bit at vertex `s` is omitted only if
`tau0[s] == tau1[s]`: changing that bit changes no transition on any visit.
If `k` bits remain, a product state uses
`max(1, ceil(log2(m))) * ceil(2^k / 64)` 64-bit planes. In particular,
seven noncoincident vertices use six planes, and eight use twelve.

## Exact collision detection

Each positive word length receives a fresh collision table. Hash matches are
checked against every bit of the complete packed state. A collision at another
length has no effect on the score. Parents are expanded in descending binary
word order: the parent at index `i/2` is still intact when child `i` is computed.
The overlapping root entry uses a scratch buffer. Fixed-size profile chunks
avoid allocating a second layer or reallocating the previous layer.

By default `quotient_complements = true`. For a word `w`, let `bar(w)` complement
every letter, and let `T` complement every retained static-mask coordinate.
Then `profile(bar(w)) = T(profile(w))`, because
`(1-x) XOR (1-sigma[s]) = x XOR sigma[s]` on every visit. Consequently it suffices
to store words beginning with `0`. At each length the algorithm checks:

- `A == T(A)`, giving a word and its distinct complement;
- `A == B`, giving two stored words;
- `A == T(B)`, giving a stored word and the complement of the other word.

The table hashes `min(hash(A), hash(T(A)))`, with complete-state comparisons in
both orientations. Thus all words are accounted for. `T` reverses the block
order within each state-bit plane and reverses the 64 bits of each block. For
fewer than 64 coordinates, the reversed bits are shifted into the valid range.
The quotient halves profile and hash-index storage. It does not identify
different graph classes or different starting states.

## Limits and result meaning

`PackedLimits` controls depth, full word-layer size, array-payload memory,
elapsed time and interruption. The maximum layer size refers to **all**
`2^depth` words, including derived complements. The depth limit is 31. The
memory limit includes destination tables, profile chunks, pointer arrays, hash
indices and both scratch buffers; allocator and runtime overhead are excluded.
It is checked before allocating each new payload. No large vector
reallocation creates an uncounted transient layer.

- `exact`: `merge_length == lower_bound` is the least positive collision length;
  the two witness words are distinct and have that length.
- `depth-capped`: every layer through the requested depth was completed without
  a collision, so `H >= depth + 1`; no exact score or witness is reported.
- `incomplete`: a state, byte, time, allocation or interruption limit stopped
  the computation. Only fully completed earlier layers contribute a lower
  bound. A partial layer cannot certify a new lower bound.

`profiles_evaluated` counts physically expanded profiles. `evaluated_words`
also counts the complement words whose complete profiles were derived by `T`.
These counters differ by a factor of two when quotienting is enabled.

Example API use:

```cpp
#include "Family1ExactPacked.h"

auto graph = family1::LargeGraph::from_key("0001020304050406020605060001");
family1::PackedLimits limits;
limits.depth = 24;
limits.max_layer_states = 1ULL << 24;
limits.max_working_bytes = 2ULL << 30;
limits.timeout_ms = 30000;
auto result = family1::score_packed(graph, limits);
// Inspect result.status before interpreting result.merge_length.
```

The global synthesis CLI uses this exact backend for candidate graphs with at
least seven states. Its resource options are
`--candidate-max-layer-states` and `--candidate-max-working-mib`. An individual
candidate timeout cannot establish a global upper bound.

## Validation on 25 October 2026

The native MSVC Release regression passed. The project's Debug and Release
CTest runs also passed all eight registered tests, including
`family1-exact-packed`. The packed regression checks:

- all 746 ordered transition tables with 1–3 vertices against an independent
  scalar implementation using full mask vectors and a new map at each length;
- quotienting enabled and disabled, forced hash collisions, deterministic
  witnesses, loops, static-mask revisits, and resource/interruption limits;
- an independently exhaustively scored five-state example with `H=15`, crossing
  multiple profile chunks;
- both previously exhaustively certified six-state maximizers, reproducing
  `H=23` with quotienting enabled and disabled and independently simulating each
  witness over all 64 original masks;
- full-mask endpoint calculations at sizes 7, 8, 10 and 20, including 20-bit
  masks and state labels 16–19;
- scorer-level complement comparisons spanning multiple 64-mask blocks,
  including a padded two-state example with all `2^20` masks retained and
  independently replayed witnesses;
- removal of coincident-port bits and expansion back to original mask indices.

Rebuild and run the focused test using the existing Windows setup:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-windows-vcpkg.ps1 -Configuration Release
& 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\ctest.exe' --test-dir out\build\msvc-vcpkg -C Release -R '^family1-exact-packed$' --output-on-failure
```

The same commands with `Debug` reproduce the Debug build and test.

### Local diagnostic computations

The following are individual-graph diagnostics, not global certificates. Their
small UTF-8 JSON records and ignored benchmark helpers are under
`out/family1-packed-check/`. No figure or maximizing-graph collection was
changed by these computations.

| Graph key | Result | Array payload peak | Time |
|---|---:|---:|---:|
| `000102030304020500010405` | exact `H=23`, quotient | 134,226,256 bytes | 1.067 s |
| `010200030405020300010405` | exact `H=23`, quotient | 134,226,256 bytes | 0.695 s |
| `0001020304050405020605060001` | exact `H=23`, no quotient | 469,795,536 bytes | 1.362 s |
| `0001020304050406020605060001` | incomplete, `H>=29` | 15,032,910,592 bytes | 90.000 s |

All exact witnesses in these records were independently simulated over every
original static mask. The last run completed all layers through 28, then
timed out during length 29. It supplies no upper bound or exact merge length.
Earlier depth-capped and timed-out records for this graph are retained without
relabeling them as exact.

Two additional existing-solver probes encoded **all 128 masks** of that last
graph upfront. Lengths 40 and 36 both returned `unknown` after approximately
30 seconds. Neither query established an upper bound, lower bound or witness.
The records are `m7-second-sat-length40.json` and
`m7-second-sat-length36.json`.

These diagnostics improve an individual lower bound and validate the new
classifier. They do not settle the absolute optimum, or the complete collection
of maximizing rooted graphs, for sizes 7–20.
