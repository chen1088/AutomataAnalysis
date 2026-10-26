# Native structured word-pair sampling

Family1Sample samples word pairs for one fixed graph. A verified hit certifies only an upper bound at the requested length. A miss proves no lower bound, and none of these pairs is claimed shortest. The sampler stops at its first verified hit; the requested budget is a maximum.

These Release runs used seed 1088, 64 sampled static masks, and a budget of 10,000 candidates. Complete sampled-state equality is required after hash matches. Every accepted pair is then replayed independently over all masks; a separate Python scalar implementation rechecked all three positive cases (512 masks per word in total).

| Graph | Length | Candidates used | Result | Full masks on accepted pair | Native seconds |
|---|---:|---:|---|---:|---:|
| literal-m7-L34 | 34 | 260 | verified upper witness | 128 | 0.000522 |
| literal-m7-L64 | 64 | 2 | verified upper witness | 128 | 0.000108 |
| literal-m8-L34 | 34 | 10000 | sampling miss; score unresolved | 0 | 0.016951 |
| literal-m8-L64 | 64 | 740 | verified upper witness | 256 | 0.001461 |
| winner-m7-L34 | 34 | 10000 | sampling miss; score unresolved | 0 | 0.014610 |
| winner-m7-L64 | 64 | 10000 | sampling miss; score unresolved | 0 | 0.018201 |
| literal-m20-L128 | 128 | 10000 | sampling miss; score unresolved | 0 | 0.213383 |
| literal-m20-L256 | 256 | 10000 | sampling miss; score unresolved | 0 | 0.594763 |

The literal circulant family is tau0(i)=i+1 and tau1(i)=i+floor(m/3), modulo m. Its independently known exact scores at seven and eight states are 14 and 18, respectively. Thus even a sampler miss at a longer length is not evidence of collision absence. The seven-state maximizing graph used here has certified H=34, but this sampler did not rediscover its shortest pair or a length-64 extension in the chosen finite stream.

## Paired native benchmark

Each case evaluates exactly 10,000 identical deterministic words over the same 64 static masks. The packed engine uses state-membership bitplanes and an eight-letter prefix cache. The scalar engine independently simulates every sampled mask. Both timed segments include word generation and identical profile-hash/checksum work. All complete endpoint profiles and checksums agreed. The packed segment stores profiles; the scalar segment reconstructs and compares them. These are local measurements, not a general speed guarantee.

| Graph | Length | Packed seconds | Scalar seconds | Scalar / packed |
|---|---:|---:|---:|---:|
| benchmark-literal-m7-L34 | 34 | 0.003882 | 0.023715 | 6.11 |
| benchmark-literal-m8-L64 | 64 | 0.007275 | 0.055676 | 7.65 |
| benchmark-winner-m7-L34 | 34 | 0.003919 | 0.023730 | 6.06 |
| benchmark-literal-m20-L128 | 128 | 0.023087 | 0.127405 | 5.52 |

## Reproduce

Use a fresh output directory or append --resume with identical settings. Exact commands and all transition tables, witnesses, hashes, counters, masks and timing data are retained in [summary.json](summary.json). The native source is [family1_sample.cpp](../../family1_sample.cpp).

```powershell
.\out\build\msvc-vcpkg\Release\Family1Sample.exe --graph KEY --out out\sample-fresh --length 34 --samples 10000 --seed 1088 --masks 64 --mode commutator
.\out\build\msvc-vcpkg\Release\Family1Sample.exe --graph KEY --out out\benchmark-fresh --length 34 --samples 10000 --seed 1088 --masks 64 --mode benchmark
```

Native misses and partial runs return decision unknown, lower_bound 1, and no upper bound. The profile mask set can adapt to scalar counterexamples; masks stay static during every word. Checkpoints retain sample position, mask set, counters and random-mode cache word indices. Hash collisions never substitute for complete sampled-state equality.
