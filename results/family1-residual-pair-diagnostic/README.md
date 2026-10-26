# Residual coordinates of the old literal20 pilot pair

The old full-metric pilot retained a length96 pair agreeing on 1,048,075 of
1,048,576 static masks, leaving501 unequal coordinates. This diagnostic proves
that **496 of those coordinates can never merge under any common suffix**.
Only five are individually mergeable; their shortest local suffix distances
are1 (one coordinate),4 (two), and10 (two).

Consequently this particular pair is permanently blocked despite agreement on
every one of the32 permutation coordinates. Any common suffix can add at most
five agreeing coordinates, so agreement cannot exceed1,048,080. The result
concerns this starting pair only; it gives no new upper or lower bound on the
graph's H and does not exclude the graph from consideration.

`literal20-oldpilot.json` comes from independent C++ scalar simulation of all
static masks, followed by complete per-DFA pair BFS for the501 residuals.
The native calculation took0.1941 seconds. Each negative coordinate includes
a closed set of unequal state pairs. Closure under both transitions, inclusion
of the initial pair, and exclusion of every diagonal provide independently
checkable nonmergeability certificates.

There is also a simple structural certificate. Undoing the canonical relabeling
and local port swaps, every one of the496 negative masks is periodic with period10
on the raw circulant states, and its two endpoints differ by10 modulo20. Both
letter maps commute with translation by10 under that mask. Thus antipodal
states remain antipodal after every word. The five mergeable residuals do not
have period10.

`validation.json` pins the original pilot result, raw-family mapping, diagnostic
source/executable and independent validator. The Python validator replays only
the501 residual masks, verifies every closed certificate, recomputes every local
distance by a separate forward BFS, and checks all1,024 period10 masks. It does
not repeat the expensive million-mask word simulation.

```powershell
uv run --no-project python tests/family1_residual_pair_diagnostic_test.py
```

The standalone native source is `tests/Family1ResidualPairDiagnostic.cpp`, built
with the existing MSVC BuildTools environment using `/std:c++20 /O2 /EHsc`.
It has no production Family1 dependencies. Its self-tests cover permanent
permutation mismatch, one-step merging, and a two-step zero-gain plateau.
