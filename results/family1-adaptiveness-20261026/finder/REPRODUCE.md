# Reproduce the fixed-pool finder benchmark

Run from the repository root with Python 3, CMake, and a C++23 compiler. Use a fresh output directory. This regenerates the complete small universes, then tests every supplied member with deterministic four-symbol joint search. The exact-reference enumeration has k=N/A.

```bash
finder_repro=out/family1-adaptiveness-reproduction
cmake -S . -B "$finder_repro/build" -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$finder_repro/build" --target Family1Offline Family1Joint -j 4
for finder_m in 1 2 3 4; do
  "$finder_repro/build/Family1Offline" --m "$finder_m" --heuristics off --depth 12 --max-layer-states 1048576 --per-graph-ms 0 --out "$finder_repro/exact-$finder_m"
done
python3 - "$finder_repro" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
for m, expected in [(1, 1), (2, 6), (3, 57), (4, 678)]:
    rows = [json.loads(line) for line in (root / f"exact-{m}/records.jsonl").read_text().splitlines()]
    assert len(rows) == expected and all(row["status"] == "exact" for row in rows)
source = Path("results/family1-neighbor-seeds/near-top.jsonl")
rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
rows = [{"m": row["m"], "key": row["key"], "canonical_table": row["canonical_table"]}
        for row in rows if row["m"] in (6, 7)]
assert len(rows) == 124
(root / "k8-candidates.jsonl").write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
PY
python3 scripts/family1_adaptive_finder_benchmark.py \
  --pool "full-m1=$finder_repro/exact-1/records.jsonl" \
  --pool "full-m2=$finder_repro/exact-2/records.jsonl" \
  --pool "full-m3=$finder_repro/exact-3/records.jsonl" \
  --pool "full-m4=$finder_repro/exact-4/records.jsonl" \
  --pool near-top-seeds=results/family1-neighbor-seeds/near-top.jsonl \
  --exact "$finder_repro/exact-1/records.jsonl" \
  --exact "$finder_repro/exact-2/records.jsonl" \
  --exact "$finder_repro/exact-3/records.jsonl" \
  --exact "$finder_repro/exact-4/records.jsonl" \
  --exact results/family1-neighbor-seeds/near-top.jsonl \
  --exe "$finder_repro/build/Family1Joint" --out "$finder_repro/finder" \
  --ks 2 4 6 --scores total permutation --common-depth 2 --beam 1 \
  --max-length 80 --expansions 2000000 --jobs 8 --batch 8
python3 scripts/family1_adaptive_finder_benchmark.py \
  --pool "near-top-m6-m7=$finder_repro/k8-candidates.jsonl" \
  --exact results/family1-neighbor-seeds/near-top.jsonl \
  --exe "$finder_repro/build/Family1Joint" --out "$finder_repro/k8-followup" \
  --ks 8 --scores total permutation --common-depth 2 --beam 1 \
  --max-length 80 --expansions 2000000 --jobs 8 --batch 8
python3 scripts/family1_adaptive_finder_publish.py \
  --run "$finder_repro/finder" --followup "$finder_repro/k8-followup" \
  --out "$finder_repro/public-finder"
```

The main matrix has 1,005 unique graphs and 6,030 queries: joint k=2,4,6 under each of total-D and permutation-first ranking. The follow-up has 124 graphs and 248 queries at joint k=8 under both rankings. Both use divergence common-prefix depth c=2, beam 1, no diagonal or unequal-symbol quota, pair length at most 80, and at most 2,000,000 expansions per start. All windows started by the measured runs completed; no measured query reached the expansion cap. Search has no time limit or PRNG. Exact reference regeneration also has no time limit; its completeness assertion must pass before scoring.

`cases-*.csv` preserves every query, including misses, both witness words, full prefix disagreement and synchronized-count traces, exact scores when available, certified champion membership, and work. A missing witness remains unresolved. The publisher independently replays every final positive and checks the raw-record hashes. The query driver additionally replays every accepted improvement. `per-case-deltas.csv` compares independent runs; stronger windows can regress, so portfolio bounds retain the shortest verified witness. Portfolio work sums all queried configurations, with the chosen witness's work reported separately.

The 47 m7 nonwinner rows have certified H<=33; their individual exact H values are not asserted. The m5/6/7 pools deliberately include saved near-top graphs and every certified winner. Only m1..4 are full universes.

The original frozen driver copies and native journals are local under `out/family1-adaptiveness-20261026/finder`. Its manifests pin the actual source and executable hashes. The current publisher recomputes post-search portfolio work from all query costs; this analysis correction does not change native search or saved witnesses.
