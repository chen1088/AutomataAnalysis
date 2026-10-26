# Current Family 1 atlas data, exact sizes 1 through 20

This is a selected presentation dataset, not a complete search journal. It
contains every certified rooted maximizing class through seven states, and one
explicit lower-bound example at each larger exact size. No larger maximum or
complete larger maximizing collection is asserted.

| m | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Certified global maximum | 1 | 3 | 6 | 10 | 15 | 23 | 34 |
| All rooted maximizing classes | 1 | 1 | 2 | 1 | 5 | 2 | 8 |
| Ordinary shapes, root ignored for comparison only | 1 | 1 | 1 | 1 | 4 | 1 | 4 |

Each exact size 8 through 20 has a constructive graph with **H >= 34**. Its
individual exact score and the global maximum remain unresolved. The 33 records
are not evidence of exhaustive coverage at larger sizes. Historical observations
in `results/family1-through20/` remain unchanged; lower certified bounds do not
rule out unresolved challengers.

## Larger-size construction and lower-bound proof

Use the certified seven-state maximizer

```json
[[0,1],[2,3],[2,3],[4,5],[0,6],[4,6],[1,5]]
```

For m >= 8, replace the root's port-0 loop by the cycle
`0 -> 7 -> 8 -> ... -> m-1 -> 0`; each new vertex has its other port to state 1.
Keep the six other old rows. Every added vertex is reachable from root 0, and
all seven old vertices remain reachable, so the seed has exactly m reachable
states. All vertices still have two outgoing ports. Its indegrees need not be
two, consistent with the unrestricted search model.

Map each old vertex i to i and every new vertex to 0. Before canonicalization
this projection pi commutes with each outgoing port:

`pi(tau_new(s,p)) = tau_base(pi(s),p)`.

For any static base mask sigma, give each new state the bit of the base state
to which it projects. Induction on word length gives projection of the new
trajectory equal to the base trajectory, including every revisit. If two
distinct equal-length words collided in the new graph under every static mask,
they would collide in the base graph under every static base mask. Therefore
`H(new) >= H(base) = 34`. This argument proves only a lower bound.

The exported transition tables are exactly rooted canonical, allowing local
port swaps. The construction metadata retains the raw table, its raw projection,
the old-to-canonical label map, and the local port flips. In canonical labels,
write `pi[s]` for `canonical_projection_to_base[s]` and `k[s]` for
`canonical_mask_lift_xor[s]`. The checked identity is

`pi[tau_new(s,p)] = tau_base(pi[s], p XOR k[s])`.

Lift each base mask by the **fixed** assignment
`sigma_new[s] = sigma_base[pi[s]] XOR k[s]`. The transition projection then
commutes for both input symbols. This absorbs canonicalization's port swaps and
retains the same proof.

## Files and validation

- `champions.jsonl`: all 20 certified small rooted winners and 13 constructive
  larger examples, in deterministic size/key order. The filename is accepted by
  the atlas tools; it does not claim optimality for the larger examples.
- `summary.json`: per-size proof flags, complete collection counts where known,
  source SHA-256 digests, and an explicitly speculative m=8 extrapolation.
- `validation.json`: all source upper witnesses independently replayed over all
  static masks; all thirteen accessible constructions and projection identities
  checked. Global coverage and base lower proofs are inherited from the pinned
  source certificates, not recomputed by this presentation generator.

The m=8 point guess 48 and informal range 40--55 are heuristics, not proved
bounds or statistical confidence intervals. Continuing the latest increments
5,8,11 by 14 gives 34+14=48. These few values do not settle quadratic versus
cubic extremal growth.

Reproduce from the repository root:

```powershell
uv run --no-project python scripts/family1_atlas_dataset.py
uv run --no-project python tests/family1_atlas_dataset_test.py
```
