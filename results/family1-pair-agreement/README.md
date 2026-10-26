# Exact progress over every static mask

`Family1PairAgreement.h` is optional and header-only. It computes

`S(u,v) = #{sigma : delta_sigma(0,u) = delta_sigma(0,v)}`

for every one of the `2^m` static masks, with `m<=20`. A common appended letter
cannot decrease S: coordinates that already agree remain equal under the same
deterministic transition. Merged coordinates can therefore be discarded while
tracking the remaining complete endpoint states exactly.

Both outgoing ports are retained. Loops, coincident ports, and arbitrary
indegrees are supported. The context separately identifies masks for which both
letter maps are permutations. If any seed vertex has indegree different from
two, this set is empty; the graph is still evaluated over all masks. A mismatch
on a permutation coordinate is permanent under every common suffix and gives a
rigorous rejection of that prefix pair for common-suffix continuation.

No hashes are used for endpoint equality. At m=20, the paired active payload
is about 5.19 MiB, with a shared 128 KiB permutation-mask context. The completed
pair releases its endpoint planes. Accepted collisions must still receive the
caller's independent scalar all-mask replay.

## API

```cpp
#include "Family1PairAgreement.h"

auto context = std::make_shared<family1::PairAgreementContext>(graph);
family1::ExactPairAgreement pair(context, u, v);
auto score = pair.merged_count();
auto total = pair.mask_count();
auto blocked = pair.permutation_mismatch_count();
auto next = pair.append_common(false); // common input0
// For a textual suffix character c, use append_common(c == '1').
```

`u` and `v` must be distinct binary words of the same length. Copies share the
immutable context and own their paired endpoint planes. Optional audit methods
expose agreement for one mask and the two states for an unmerged coordinate.

## Independent validation

Both native MSVC Release and Debug passed:

- All 64 rooted isomorphism classes through m=3, independently enumerated by
  labeled tables and factorial root-fixing permutations.
- Five distinct word pairs per class (320 pairs), with complete scalar counts,
  permutation-mask classification, every common-suffix step, both copy branches,
  static revisits, loops, coincident ports, and arbitrary indegrees.
- Three m=20 cases: balanced circulant, an unbounded-indegree reset seed, and
  a coincident-port cycle. Full scalar counts were checked on all 1,048,576
  masks at the initial and final pair; another 256 selected scalar states were
  checked after every suffix letter.
- The three permutation-mask totals were 32, 0, and 1,048,576. Final exact
  agreement counts were 815340, 958908, and 1048576.
- Invalid inputs were rejected; the common-suffix count never decreased and
  permutation mismatches remained invariant.

The `*-validation.json` files pin source hashes; the corresponding logs retain
native output. `manifest.json` pins these artifacts. Production CMake files and
previous executable files were not changed for this header audit.

Reproduce without changing the main project build:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File tests/run-family1-pair-agreement.ps1 -Configuration Release
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File tests/run-family1-pair-agreement.ps1 -Configuration Debug
```
