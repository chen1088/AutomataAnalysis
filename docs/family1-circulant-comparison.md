# Circulant seeds and the quadratic result

The user-specified seed in this search is the literal graph

```text
Q = Z/mZ, root = 0,
tau0(i) = i+1 mod m,
tau1(i) = i+floor(m/3) mod m.
```

The first port ensures accessibility. Every translation is an ordinary graph
automorphism taking one starting vertex to another, so all vertex roots give
the same rooted isomorphism class and the same Family 1 score. One score per
size covers all m starting vertices, with their multiplicity retained.

Complete per-length static-mask calculations give exact scores for sizes one
through eight:

| m | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H of the literal seed | 1 | 3 | 1 | 1 | 1 | 11 | 14 | 18 |

At sizes 3, 4, and 5, the two ports coincide. The distinct one-letter words
therefore merge. This does not by itself refute an asymptotic lower bound,
but the small-size degeneracy must be recorded.

The exact results, witnesses, and complete-layer proofs are exported by
`scripts/family1_circulant_family.py` in `results/family1-circulant-family/`.
Fixed-length native tests at sizes 8 through 20 are a separate evidence source;
timeouts do not strengthen the bound. The graph's score is not a global maximum
unless all other rooted graph classes are independently excluded.

## Difference from the local manuscript

Read-only inspection of the sibling repository's
`family1_chase_recovery.tex`, Section "The proposed fixed-shift graph"
(around line 859), finds the different prescription

```text
r_m = max(1,floor(m/3)),
tau0(i) = i+1 mod m,
tau1(i) = i+1+r_m mod m.
```

Its "Quadratic shortest merge length" theorem (around line 956) concerns
`H_core(R)`, the product over all masks on all cores of sizes `3r`,
`1 <= r <= R`. It proves

```text
1 + sum(phi(d), d=1..R) <= H_core(R)
                         <= 1 + sum(phi(d), d=1..R) + 8R(R+1).
```

The subsequent corollary (around line 1164) gives a quadratic guarantee for
the product of retained seed sizes up to a state budget M. The manuscript
explicitly distinguishes that pool from the Family 1 product of one seed.
These statements do not provide a numerical quadratic lower bound for each
individual literal seed specified above, or prove a quadratic lower bound
for the maximum individual-graph score F(m). Any additional fixed-graph
theorem needs its own proof and finite-size bound before import into this search.

Both the port offset and the quantified product must be matched before using
a theorem as a certificate. No manuscript or dissertation file was edited.
