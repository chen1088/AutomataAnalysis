# Complete-pool scoring and policy audit

Generation and exhaustive reference labels use **k=N/A**. All finder runs use the complete joint alphabet `00,01,10,11`: **joint k=2** has 16 leaves per full window; **joint k=4** has 256. Each run uses all common prefixes through depth 2, both first differences (14 planned starts), beam 1, diagonal/unequal beams 0, maximum length 80 and a fixed 2,000,000-node cap per attempt. There are no random choices or clock limits. Every supplied graph is tested.

The m6 campaign tests all 11,693 distinct graphs in the union of the complete radius1 pools at joint k=2, total disagreement score. The m7 campaign tests all 13,329 union members independently at joint k=2/total, k=4/total and k=4/permutation-first. A larger window and permutation-first score are experimental finder treatments.

From the repository root, use fresh output directories:

```bash
cmake -S . -B out/build/adaptive-repro -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build out/build/adaptive-repro --target Family1Joint -j 4

python3 scripts/family1_adaptive_edit_benchmark.py \
  --sizes 6 7 --radius2-max-m 0 \
  --out out/family1-adaptive-repro/edit \
  --publish out/family1-adaptive-repro/edit-public \
  --figure out/family1-adaptive-repro/edit-coverage.svg

python3 scripts/family1_adaptive_policy_benchmark.py \
  --m 6 --edit out/family1-adaptive-repro/edit/sealed-pools \
  --exe out/build/adaptive-repro/Family1Joint \
  --configs total:2 --batch 32 --jobs 4 \
  --out out/family1-adaptive-repro/policy/m6

python3 scripts/family1_adaptive_policy_benchmark.py \
  --m 7 --edit out/family1-adaptive-repro/edit/sealed-pools \
  --exe out/build/adaptive-repro/Family1Joint \
  --configs total:2 total:4 permutation:4 --batch 32 --jobs 4 \
  --out out/family1-adaptive-repro/policy/m7

python3 scripts/family1_adaptive_policy_publish.py \
  --source out/family1-adaptive-repro/policy/m6 \
  --out out/family1-adaptive-repro/published/m6
python3 scripts/family1_adaptive_policy_publish.py \
  --source out/family1-adaptive-repro/policy/m7 \
  --out out/family1-adaptive-repro/published/m7
```

The scorer validates the generation seals and strips scores, historical pairs and ordinals from query inputs. Only canonical tables and the fixed configuration reach the native finder. It seals all scoring outputs before loading the complete exhaustive champion lists. Each final and improving positive is replayed independently in Python over every original static-mask DFA, with its full prefix disagreement trace checked against the native trace. Complete windows and all supplied keys are checked. No run in this publication hit an expansion cap or used a partial window; length/beam limits remain heuristic restrictions.

Each `m6`/`m7` publication contains:

- `records-*.csv`: every candidate and configuration, actual pair strings, verified upper, joint k and node/window work. Empty upper/string cells mean unresolved, never an inferred large score. Shape and pool columns preserve the four controlled candidate sets.
- `summary.json`: root-fixed/all-root and previous-winner/previous-near-top comparisons. Exhaustive m7 truth supports champion membership and nonwinner H≤33, without supplying every nonwinner's exact H.
- `forced-factorial.csv`: deliberate edit-only, finder-only and combined changes. Refinement retains the smaller verified upper and charges both queried configurations.
- `crowding-gated.csv`: the same requested actions only when the original finite top band has at least 3 rooted classes within 2 of its largest finite upper. A gate that does not fire leaves the original pool and finder untouched. Misses remain separate.
- `example-witnesses.csv`: all champion cases plus finite top-band examples, including actual strings, k and disagreement traces.
- `run.json`, `query-audit.json`, `validation.json`, `publication-manifest.json`: inputs, source/binary fingerprints, sealed record hashes, independent replay totals and public-file hashes.

The original native journals, frozen source snapshots and full per-attempt trace records are under `out/family1-adaptiveness-20261026/policy/`. Public CSV shards were independently compared with every native row: 11,693 comparisons for m6 at joint k=2 and 39,987 for m7 at joint k=2/4. All pair strings and public-file hashes matched. Generation completion proves neighborhood coverage; a verified finite pair proves only an upper bound on shortest hard-pair length.
