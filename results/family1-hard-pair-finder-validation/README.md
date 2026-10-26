# Native finder validation

Both Windows MSVC/vcpkg configurations passed all 28 registered CTests. The complete test logs and pinned executable/source hashes are retained here. Tests include independent exhaustive tiny families, heterogeneous DFA sizes/roots, forced hash collisions, static revisits, complete gain distributions, exact conditional BFS, negative mergeability certificates, budgets and deterministic resume. Three twenty-state cases check the full metric against scalar simulation over all 1,048,576 masks each.

Quality results are separate: see [the blind version comparison](../family1-finder-prefixmatch-version-benchmark/README.md) and [the module documentation](../../docs/hard-pair-finder.md). No global optimum for sizes 8 through 20 is certified.
