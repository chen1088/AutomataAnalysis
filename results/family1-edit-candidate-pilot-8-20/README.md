# Bounded edit-candidate pilot, sizes8–20

The run retains 43,888 generated rooted graph classes and all104 imported projection-certified H≥34 classes: 43,992 distinct (m,key) records. It processed every root of the two selected ordinary shapes at each size, 364 queries total. There were 122 completed native UNKNOWN results and 242 timeouts, with 0 upper witnesses and0 eliminations below34. Survival supplies no lower bound. No global maximum or exhaustive graph coverage is certified.

The search used radius3, at most256 direct rooted target endpoints per size, and4096 accepted path slots. Optional root closure adds every accessible root of observed shapes outside that endpoint budget. All thirteen runs are candidate-capped; the20-state run also records the representation boundary at intermediate size20. Rerooting is separate from root-fixed edit distance. All observed generated/ranked classes and path provenance remain in the gzip JSONL exports. All104 H≥34 baseline ties are preserved in top-lower-bound-ties.jsonl; their supplied projection proof provenance is attributed, not reproved by this publisher.

| m | Generated classes | Selected roots | Completed UNKNOWN | Timeout |
|---:|---:|---:|---:|---:|
| 8 | 1,982 | 16 | 16 | 0 |
| 9 | 2,104 | 18 | 18 | 0 |
| 10 | 2,295 | 20 | 20 | 0 |
| 11 | 2,558 | 22 | 22 | 0 |
| 12 | 2,849 | 24 | 24 | 0 |
| 13 | 3,154 | 26 | 19 | 7 |
| 14 | 3,327 | 28 | 0 | 28 |
| 15 | 3,637 | 30 | 3 | 27 |
| 16 | 3,911 | 32 | 0 | 32 |
| 17 | 4,096 | 34 | 0 | 34 |
| 18 | 4,402 | 36 | 0 | 36 |
| 19 | 4,741 | 38 | 0 | 38 |
| 20 | 4,832 | 40 | 0 | 40 |

audit.json records graph/key, primitive path replay, canonicalization, input/source/executable pins, ranking preservation, selected-root coverage, native JSON/config hashes, miss semantics and baseline-tie checks. Every positive witness would be independently replayed on all static masks; this run has none. The fixed2-second timeout was a pilot work budget.

evidence.zip stores each distinct raw byte sequence once at objects/SHA256. raw-inventory.json maps all3,001 original relative file paths (887,375,361 bytes) to those objects. It excludes no raw files. external-pins.json additionally preserves pinned original inputs/executables through the same object store. Restore into a NEW empty directory:

```python
import hashlib, json, pathlib, zipfile
publication = pathlib.Path('results/family1-edit-candidate-pilot-8-20')
destination = pathlib.Path('out/restored-edit-candidate-pilot')
destination.mkdir(exist_ok=False)
with zipfile.ZipFile(publication / 'evidence.zip') as archive:
    for name, meta in json.loads((publication / 'raw-inventory.json').read_text())['files'].items():
        data = archive.read('objects/' + meta['sha256'])
        assert hashlib.sha256(data).hexdigest() == meta['sha256']
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
```

Reproduce the pipeline with `uv run --no-project python scripts/family1_edit_candidate_pilot.py --out NEW_DIRECTORY` using its pinned native executables and inputs. Publish/audit a completed run with `uv run --no-project python scripts/family1_publish_edit_candidate_pilot.py --run out/family1-edit-candidate-pilot-8-20 --out NEW_PUBLICATION_DIRECTORY`. Source snapshots and exact settings remain in the restored run. The raw run's absolute path references describe the original machine; restoring files does not automatically resume under a different path.
