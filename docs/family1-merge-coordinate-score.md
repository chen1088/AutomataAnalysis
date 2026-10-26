# Coordinate agreement for a word pair

For one rooted seed graph `G` with `m` vertices, define

```text
S_G(u,v) = #{sigma in {0,1}^m : delta_sigma(0,u)=delta_sigma(0,v)}.
```

The denominator is `2^m`. When `u,v` are distinct words of the same positive
length, `S_G(u,v)=2^m` certifies a Family 1 collision and hence an upper bound
on `H(G)`. Partial agreement is a useful search objective; it is not itself
a merge-length bound or a proof that a graph is extremal.

The score counts mask coordinates, including distinct masks that happen to
define the same realization when ports coincide. This is exactly the specified
Family 1 product. Root-preserving relabeling and independent port swaps only
permute its coordinates, so the full score is invariant under the graph
equivalence used in enumeration.

## Common suffixes preserve agreement

For every common suffix `z`,

```text
S_G(uz,vz) >= S_G(u,v).
```

For a fixed mask, equal current states follow equal transitions under every
subsequent letter. Its contribution to the score can change from zero to one,
but cannot change from one to zero. This uses the static-mask convention: each
state retains the same bit on every revisit. A suffix search can therefore
track newly merged coordinates without losing previously merged ones.

Strictly increasing greedy steps are insufficient. On the accessible graph

```json
[[0,1],[1,2],[0,0]]
```

the pair `01 / 10` agrees on four of eight masks. Appending either `0` or `1`
still gives agreement on exactly four masks. Appending `00` or `11` gives
agreement on all eight. In particular,

```text
01 / 10        : 4/8
010 / 100      : 4/8
0100 / 1000    : 8/8.
```

Independent exhaustive word enumeration gives `H=4` for this seed. Retaining
a neutral first step is necessary to reach this shortest witness. Lookahead
or a beam must therefore retain useful states even when their immediate gain
is zero. A finite lookahead does not prove that a plateau is permanent.

## Permutation coordinates give a necessary gate

Call a mask a permutation mask when both its zero and one transitions are
bijective. Every common suffix is then a bijection at that coordinate. If
`u,v` already end in different states there, no common suffix can merge them.

Consequently, if `U` permutation coordinates disagree, every common suffix
has score at most `2^m-U`. A candidate intended for completion by a common
suffix must already agree on every permutation coordinate. Passing this gate
is necessary; it is not a general proof that a completing suffix exists.

For example, the graph

```json
[[0,1],[0,2],[1,2]]
```

has permutation masks 2 and 5, using the bit of state `s` at position `s`.
Both disagree for `01 / 10`. The initial full score is zero of eight, and no
common suffix can raise it above six of eight. A search may reject this
particular suffix-completion attempt without making any claim about the
graph's score: this graph itself has `H=4` through another pair.

If only sampled permutation masks have been checked, the gate must be labeled
as such. A sampled gate can miss an obstructing coordinate; it cannot turn
an unverified completion into a universal witness.

## Sampled scores and trace labels

For a sampled mask set `M`, use the separate score

```text
S_(G,M)(u,v) = #{sigma in M : delta_sigma(0,u)=delta_sigma(0,v)}.
```

Its denominator is the actual number `|M|`, rather than the requested sample
count or `2^m`. Masks selected deterministically or refined after failures do
not provide an unbiased statistical estimate of the full score. A result of
`64/64 sampled` is different from `2^m/2^m full`.

Every score trace must identify the mask set on which it was measured. If an
all-mask check supplies a counterexample and the sample changes, earlier
trace counts remain attached to their original masks. Reporting those old
counts beside only the final refined mask set would be misleading.

A packed implementation may compute a bitset of matching sampled coordinates
and take its population count. That bitset must contain only active mask bits;
unused positions in a machine word are not extra agreeing masks. Matching
hashes still require complete-state comparison. Universal success requires
an independent replay of the final distinct equal-length pair over all masks.

Neither a sampled miss, an unsuccessful beam, nor a permutation-gate rejection
certifies a new lower bound on `H(G)`. They describe the explored word-pair
search only. Exact lower bounds continue to require exhaustive equal-length
injectivity or another valid certificate.

## Guided search and validation

The native sampler supports a deterministic guided mode with a beam and
lookahead. For example:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Sample.exe --graph 000101020000 --out out\guided-plateau --length 4 --samples 1 --masks 8 --mode guided --beam-width 4 --lookahead 0 --full-agreement
```

`--length` is the maximum word length in guided mode. A pair found earlier
is returned at its actual length, with distinct `requested_length` and
`witness_length` fields. `guided_attempt` reports the sampled objective and
its own mask set. `--full-agreement` additionally computes the exact full
score trace of the retained attempt. It does not turn a failed search into
a lower-bound certificate.

Both native Release and Debug passed the independent guided suite. All 64
rooted classes through size three were checked against scalar endpoints;
2,240 pairs and 15,680 suffix traces supplied independent mathematical checks.
The plateau example succeeds with lookahead zero as well as two, returning
the shortest pair `0111 / 1011` with trace `4,4,8`. A three-state global
maximizer yields `010110 / 100110` at length six, with trace `4,5,6,7,8`.
Partial checkpoints, denominator labels, full permutation gates, and
resume configuration guards were also checked.

The [validation artifacts](../results/family1-guided-validation/README.md)
also replay all eight previously saved shortest seven-state witnesses.
Seven of their chosen common suffixes contain neutral score steps. These
are observations about that saved finite collection, not a frequency claim
or a claim to have enumerated every shortest pair.
