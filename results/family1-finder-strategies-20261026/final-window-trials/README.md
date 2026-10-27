# Deeper joint windows after scored seeding

These final development trials keep the original deterministic scored-prefix
catalogue and test **joint k=8, beam 1** and **joint k=6, beam 4**. They include
all 20 certified winners through m=7 plus one explicitly post hoc m=7
nonwinner on which production previously returned upper 45.

The query input contains only 21 canonical graph keys. Both complete query
files were sealed before reference labels were loaded. All final positive
pairs and every D prefix score passed independent replay on every original
static mask: **2,956 pair/mask checks**.

| Joint configuration | Winners found / 20 | L=H / 20 | Within two / 20 | Largest winner gap | Joint nodes |
|---|---:|---:|---:|---:|---:|
| k=8, beam 1 | 20 | 13 | 19 | 3 | 971,767,468 |
| k=6, beam 4 | 20 | 16 | 18 | 4 | 250,389,808 |

The m=7 winner lengths in canonical key order are:

- **Joint k=8/B1:** 36,36,35,35,36,37,35,34.
- **Joint k=6/B4:** 36,37,34,38,34,36,34,34.
- **Exact reference, k=N/A:** 34 for each.

Neither trial improves any winner over the production joint k=4/beam16
scored-seed result. Replacing that result would regress five winner cases at
k=8 and three at k=6. Earlier verified uppers must be retained.

The post hoc nonwinner key is 0102000304050203000604050003. It has certified
H≤33 from the complete m=7 finding; its individual exact H is not supplied.
Joint k=8 still returns 45, at least 12 above H. Joint k=6 returns a valid
44-pair, improving the previous upper by one but still at least 11 above H.
This new pair is worth retaining as a certificate. Neither window treatment
establishes the required near-shortest accuracy.

## Fixed configuration and provenance

Both trials use prefix depth20, complete word layers of at most 1,048,576
words, a global compatible catalogue of 16,384 pairs, 512 full-D scored
starts, permutation-priority ranking, maximum pair length80, no diagonal or
unequal beam, and 2,000,000 nodes per joint attempt. Every evaluated window
uses all 4^k leaves over 00,01,10,11. There is no random choice or time cap.
The theoretical per-attempt work bounds are 873,800 nodes for k=8/B1 and
305,760 for k=6/B4, so the configured expansion cap cannot bind.

The complete exact-word-layer phase uses depth24, at most 2^24 words per
layer and 256 MiB array payload. It finds all twelve winners through m=6
exactly before joint search. These witnesses have producing **k=N/A**,
separate from configured joint k. The raw experimental binary records only
configured k, so [cases.csv](cases.csv) adds an explicit producing-k column.
The m=7 cases proceed to joint search.

The frozen original benchmark executable SHA256 is
cb05d4b79c83ccb32f7efc55ebab500c39e06fe14839ee9732bf84c3b706e665,
matching its original source manifest. This is the original global catalogue,
not the newer compact per-layer catalogue. Source snapshots, raw final JSONL
files, the independent audit source, and the frozen executable remain under
out/family1-finder-strategies-20261026/final-window-trials/.

[cases.csv](cases.csv) preserves every case, actual words, full D trace,
reference or known upper, exact-word work and joint-node/window work.
[summary.json](summary.json), [run.json](run.json) and
[query-audit.json](query-audit.json) pin the complete files, configuration,
input and native/source provenance. The comparison is post hoc development
evidence rather than an independent held-out benchmark.

The versioned benchmark retains the original catalogue branch when no final
fast argument is supplied. Build it and use the 21 keys in the CSV:

    g++ -O3 -std=c++23 -I . tests/Family1ScoredSeedBenchmark.cpp \
      Family1LargeGraph.cpp Family1ExactPacked.cpp -o out/Family1ScoredSeedBenchmark

    out/Family1ScoredSeedBenchmark keys-21.txt 8 1 20 1048576 16384 512 24
    out/Family1ScoredSeedBenchmark keys-21.txt 6 4 20 1048576 16384 512 24

The fresh binary fingerprint may differ from the frozen measured binary.
No reference score or witness string is passed to either query command.
