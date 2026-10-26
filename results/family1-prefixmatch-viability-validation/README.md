# Prefix matching and viability validation

The independent generic tests passed in native MSVC **Release and Debug**.

Prefix tests enumerate746 complete binary DFA tables through three states
and compare12,992 actual equal-length collision pairs with a scalar exhaustive
reference. They check fresh tables at every length, full-profile comparisons
under forced hash collisions, common prefixes, heterogeneous roots, depth
diversity, capped collections, empty constraints and deterministic sampled
layers at lengths20 and24. Sampled layers never claim complete enumeration.

Viability tests compare6,626 ordered pairs against separate forward BFS,
including exact local distances and closed negative sets. Caps and cancellation
never produce a negative proof. Generic initial-state and child-state pruning
retain viable siblings.

The native adapter's Release and Debug regressions independently check exported
closed sets and a fixed-coordinate-budget cache fixture. Cached coordinates
still consume the budget; warm uninterrupted and cold resumed runs make the
same branch decisions. Disabling the optional check never prunes.

`validation.json` pins headers, test sources and binaries. It also links the
second blind72-run quality report, its T2-only24-run ablation, the preserved
first benchmark, and the literal20 residual diagnostic. All216 closed-set
proof examples exported by the new primary quality grid were independently
verified. No new global shortest merge-length theorem is claimed.
