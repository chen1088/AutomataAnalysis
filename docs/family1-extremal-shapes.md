# Extremal graph shapes through six states

The complete search through six states gives the following results. A rooted
class identifies vertex relabellings that fix the starting vertex and arbitrary
independent swaps of the two outgoing ports. An unrooted shape also allows the
starting vertex to move.

| Reachable states m | Exact maximum H | Maximizing rooted classes | Unrooted shapes among the maximizers |
|---:|---:|---:|---:|
| 1 | 1 | 1 | 1 |
| 2 | 3 | 1 | 1 |
| 3 | 6 | 2 | 1 |
| 4 | 10 | 1 | 1 |
| 5 | 15 | 5 | 4 |
| 6 | 23 | 2 | 1 |

The [complete-run summary](../results/family1-m1-m6/summary.json) records
exhaustive enumeration and exact scoring for every class through m=6. The
[saved maximizers](../results/family1-m1-m6/maximizers.jsonl) retain all ties.
The independent [shape audit](../results/family1-extremal-shapes.json), generated
by [this script](../tests/family1_extremal_shapes_test.py), tries all m! vertex
permutations for each graph, with separate root-preserving comparisons. It also
checks accessibility, saved witnesses over every static mask, automorphisms,
indegrees and simple directed cycles. This shape audit does not itself repeat
the full scoring run.

Thus m=5 is the only size through six with several maximizing unrooted shapes.
There is currently no proved structural explanation for this multiplicity,
and the observation does not predict later sizes. The four five-state shapes
have different simple-cycle length histograms, confirming that their
differences extend beyond the choice of root. Panels (a) and (c) represent the
same unrooted shape with different roots; both remain in the figures. The
[five-state audit](../results/family1-m5-audit.json) independently verifies all
five shortest merge lengths and all 50 actual TikZ arrows.

## Graph class and coverage

Every vertex has exactly two outgoing ports. Loops, coincident ports and
arbitrary indegrees are allowed. The enumeration requires root accessibility;
it does not require strong connectivity. Removing vertices unreachable from
the root preserves H: their mask bits are never consulted, so varying those
bits only repeats endpoint coordinates. A search at exactly m reachable
vertices is distinct from the cumulative budget of one through m vertices;
each seed is scored separately.

The independent [five-state executable](../tests/Family1IndependentM5.cpp)
uses no production enumerator, canonicalizer or scorer. Each labelled vertex
has 15 unordered successor pairs, giving 15^5 = **759,375** labelled tables.
It checks every table, retains **244,350** accessible ones, and tries all
24 root-fixing vertex permutations for each. This produces **10,398** rooted
classes. It scores every class with full 32-coordinate static-mask endpoint
vectors, using a fresh collision table at each word length and complete vector
equality after hash matches. The
[independent report](../results/family1-m5-independent-global-audit.json) records complete
enumeration and scoring, exact maximum 15, all five maximizers, and equality of
the entire class-to-score map with the production dataset.

Requiring indegree exactly two defines a stricter balanced subclass. It is a
different optimization problem: at m=3 its maximum is **5**, whereas the
unrestricted-indegree maximum above is **6**. At m=5 the balanced subclass
retains three of the five maximizing rooted classes, spanning two unrooted
shapes. See the [balanced-subclass audit](../results/family1-balanced-subclass-audit.json).
Strong connectivity happens to hold for the maximizers through six, but that
finite observation does not justify imposing it on the search.

## Reproduction and limits

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-windows-vcpkg.ps1 -Configuration Release
uv run --no-project python tests\family1_extremal_shapes_test.py
uv run --no-project python tests\family1_m5_isomorphism_test.py
.\out\build\msvc-vcpkg\Release\Family1IndependentM5.exe --reference .\out\family1-m1-m6\graphs.jsonl --out .\out\family1-independent-m5
```

The last command requires the native `Family1IndependentM5` target and the
complete production dataset. It regenerates the ignored independent report
and per-graph results under `out/`. Generate the production dataset using the
[exact-search instructions](family1-search.md). CMake registers the independent
audit with CTest when that dataset exists at configuration time.

**Absolute global optima and complete maximizing collections are established
only through m=6. Sizes 7–20 remain globally unresolved.** A completed
enumeration count, an individual exact score or a certified lower bound at a
larger size does not establish that size's absolute optimum or all its ties.
