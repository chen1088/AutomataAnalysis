# Certified multi-seed Family 1 finder

`Family1Certified` implements the first certificate baseline specified in
[`shortest_hard_pair_heuristics.tex`](https://github.com/chen1088/Analytic-Methods-for-Transition-Monoid/blob/9b907c005eac6357e667d9b91f40a7cea501d0e4/shortest_hard_pair_heuristics.tex).
It accepts an ordered list of rooted seed tables and targets the union of every
seed's complete Family 1 closure. One shared, distinct, equal-length pair must
collide under every original static mask. This mode has its own budgets and
certificate output; the historical heuristic finders retain their existing modes.

For seed `i`, mask bit `q` swaps the two original ports at state `q`:

\[
\delta_{i,\sigma}(q,a)=\tau^{(i)}_{a\oplus((\sigma\mathbin{\gg}q)\mathbin{\&}1)}(q).
\]

Roots, seed order, table rows, and port order are retained. Each seed may have a
different size, from 1 to 20 states. All `2^m` indexed masks count, including masks
that happen to implement identical transitions. The tool does not close a product
seed or apply fresh masks after processing a prefix.
The CLI accepts horizons and word lengths through 4096. These finite input
limits do not assert a bound on the mathematical shortest hard-pair length.

## Build and first run

The target uses only the C++ standard library. It is included in the existing
dependency-free build:

```sh
cmake -S . -B out/build/heuristics -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build out/build/heuristics --target Family1Certified
```

Supply each seed using the existing two-decimal-digit graph-key encoding, four
digits per row. Repeat `--seed` for the same target family. `--root` applies to
the immediately preceding seed and defaults to zero. For example,
`00010001` encodes rows `(0,1),(0,1)`:

```sh
out/build/heuristics/Family1Certified \
  --seed 00010001 --horizon 2 --out excluded.json
python scripts/family1_check_certificate.py excluded.json
```

That full two-state closure has shortest hard-pair length 3. The completed
length-2 exclusion proves `lower_bound=3`. At horizon 3, the tool can instead
produce a full-family witness and certify an upper bound of 3. A witness alone
does not certify that it is shortest.

Output paths must be new. A completed report embeds the seed tables and roots,
mask convention, indexed observer count, requested query, resource counters,
verified upper witness when available, and lower proof when available.

## Exact selected-observer refinement

The default mode starts from an empty selected observer set, or the explicit
`--observer i:mask` options. For a fixed horizon it explores the paired alphabet
`00,01,10,11` on complete selected endpoint vectors and a separate word-distinctness
flag. Agreement at an observer remains in the state because later unequal inputs
can break it. States are compared exactly; a hash match is not an equality proof.

Each selected collision is replayed by literal scalar transitions over every mask
of every original seed. A failed candidate adds the first separating observer in
seed/mask order. A successful replay supplies a genuine full-family upper witness.
A collision-free selected query excludes that horizon for the full family.

The refinement process is finite if every exact query and verifier finishes:
each failed candidate adds a new original observer. This is not a practical runtime
guarantee. The number of paired states, their endpoint-vector size, and the number
of queries can still be large.

The lower certificate records complete reachable layers for the selected paired
system. The independent Python checker confirms the initial root, all four
successors of every nonterminal state, and absence of a distinct collision in the
final layer. It checks exact endpoint coordinates and seed/mask membership rather
than trusting native status strings or a digest.

## Signature intersections

Use `--signature count` or `--signature first-difference` to compute exact
attainable continuation statistics on small observer projections. Declare a
projection with `--projection i:mask,j:mask`, repeated as needed. If projections
are absent, declared `--observer` options become singleton projections; if both
are absent, all original observers become singleton projections.

The signature vector is `[ones_u,ones_v,first_difference,ones_before_difference]`.
Count mode uses `-1,-1` for its last two coordinates. First-difference positions
are zero-based within the continuation; identical continuations have `-1,-1`.
The last coordinate counts ones in the common continuation prefix before the
first unequal paired move. It is not the count through that move.

The independent checker verifies the signature update on every successor and
derives the accepted terminal signatures. Empty intersection proves exclusion.
A surviving signature is unresolved by that relaxation: different projections may
realize it with different word pairs, so it is never promoted to a word witness.

`--prefix-u` and `--prefix-v` condition a signature query on actual equal-length
prefixes. Each observer replays those prefixes with its original mask, then keeps
that same mask. Continuation signatures exclude prefix statistics, and the
distinctness flag separately records whether the prefixes already differ. Thus
identical continuations are legal after unequal prefixes. A nonempty-prefix
exclusion proves only a remaining completion bound, reported as
`remaining_lower_bound`; it does not raise the global lower endpoint.

## Intervals and budgets

`--upper-u` and `--upper-v` import an incumbent only after complete scalar
verification against the declared family. A pair hard for one seed alone cannot
be imported as a witness for the union.

With a verified upper bound, `--gap Delta` replaces `--horizon` and repeatedly
targets `t=U-Delta-1` while the current gap exceeds `Delta`. Completed exclusion
sets `L=max(L,t+1)`; a verified full-family collision sets `U=t`; unresolved work
changes neither certified endpoint. Exactness means `L=U`.

`--heuristic-expansions N` optionally runs the existing joint finder on the full
declared union before the certificate query. Its lookahead, beam, and maximum
word length are controlled by `--heuristic-k`, `--heuristic-beam`, and
`--heuristic-length`. Every proposed pair still needs the same complete scalar
verification. This can supply the initial upper witness for `--gap`; a bounded
heuristic miss supplies no lower-bound credit.

The defaults and current options are shown by `--help`. The principal caps are
`--states`, `--work`, `--verifier-steps`, `--refinements`, and `--timeout-ms`.
Counters are cumulative across the run, including refinement queries and
signature groups. Timeout zero disables the clock cap; work caps still apply.
These are state/work limits, not a byte-accurate memory cap. Endpoint-vector and
proof-output storage also depends on the selected projection sizes and horizon.
The `work_units` counter charges one selected paired successor or prefix move
in exact/signature queries, one entry when enumerating default projections, and
one original-mask paired transition in the scalar heuristic. Verifier steps
count individual letter transitions separately. Refinement additions are also
counted cumulatively across interval queries. These counters describe work in
each mode; they are not interchangeable runtime estimates.

A cap, interruption, or incomplete table returns `unresolved`. Missing signatures,
discarded search states, and partial layers never supply evidence of absence.
An earlier checked proof and verified incumbent remain valid when later work is
unfinished. If no full-family upper witness has been verified, `upper_bound` stays
null.

The checker accepts `--max-work` and `--max-states` limits. A checker refusal is
reported as incomplete checking, never as a successful certificate. To pin a
self-contained certificate to another supplied input, use `--input FAMILY.json`;
that JSON contains `seeds` with exact `root` and `ports` values, or the report's
`family` object.

## Verification scope

`tests/family1_certified_test.py` uses independent literal word/mask loops and
analytic cases from the handoff: chains with horizon `2r`; the prefix-recorder plus
delayed chain with joint horizon `2r+2`; the two-state last-bit/parity seed with an
input-blind clock; and preservation of mask/state correlation after prefixes. It
also exercises cumulative resource caps, inherited distinctness, order-sensitive
signatures, and rejection of missing proof branches or inflated bounds.

These small checks validate certificate semantics and implementation consistency.
They do not establish a general approximation guarantee or predict the cost of
certifying a small gap on the eight-state `A+B` family. That target has 512 indexed
masks; its input requires one shared upper witness and a lower proof for that same
union before any joint interval can be claimed.

### Initial implementation checks, October 27, 2026

The dependency-free Release build passed all 16 configured CTest tests on Linux
with GCC 13.3. The new CLI suite produced and independently checked 34 reports,
including forged-proof rejection and a refinement limit spanning several interval
queries. Windows/MSVC execution has not been checked for this new target.

For the declared eight-state seeds

```text
A: 01020003040501060003020705060407
B: 01020002030403040506000705070206
```

bounded smoke runs produced the following outcomes. Each report was passed to
the independent Python checker; raw proof layers remain under ignored `out/`.

| Query | Limits | Outcome |
|---|---|---|
| Exact refinement at length 6 | 150,000 states, 1,000,000 work units, 10 seconds | Complete selected-observer exclusion; checked lower endpoint 7 |
| Exact refinement at length 10 | Same limits | State cap; no new lower certificate |
| Joint beam, then length-4 exact query | Joint k=4, beam 16, length cap 100, 80,000 expansions; shared 250,000 states, 50,000,000 work units, 10 seconds | Beam expansion cap with no joint witness; subsequent checked length-4 exclusion |

These checks establish basic operation on the full 512-mask target. The small
new lower certificates are weaker than the previously proved per-seed bounds
that already transfer to the union. The tool does not import those historical
proofs or replace them with its weaker run-local endpoints. No small joint
interval was obtained in these checks.

The historical length-50 pair for A,
`00001101101010101011000111100000011010010011100010` and
`00100011011010101011000111100000011010010011100010`, was also replayed
against B. It fails on 25 of B's 256 masks, starting with numeric mask 15.
It therefore cannot supply the joint upper endpoint.

The current exact producer stores paired reachability layers. In the absence of
state merging these grow as `4^t`; signature states add further statistics. This
is a correctness baseline rather than evidence of efficient certification at the
known eight-state horizons. Better exact-query backends and projection selection
remain performance work; incomplete attempts retain the checked-proof semantics
above.
