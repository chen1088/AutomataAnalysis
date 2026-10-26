# Optional GPU witness search

The GPU accelerates discovery of **upper witnesses** for individual seven-state
graphs. A result is accepted only when two distinct words of the same positive
length have equal endpoints for every one of the 128 original static masks.
The CPU check uses `tau[x XOR sigma[s]][s]`, sharing the same fixed mask across
both trajectories and every revisit. Different seed graphs are scored separately.

The completed independent CPU upper audit covers all 4,166,855 rooted classes
with witnesses of length at most 34. Fresh independent depth-33 lower checks
attain this bound, so the **seven-state maximum value is 34**. The complete tie
collection is now certified: **eight rooted classes across four underlying
shapes**. See the [certificate summary](../results/family1-m7/summary.json),
[structure report](../results/family1-m7-structures/structure.md),
[PDF plate](../output/pdf/family1-m7/family1-m7.pdf), and
[reusable TikZ ZIP](../output/pdf/family1-m7/family1-m7-tikz.zip).
This conclusion uses the CPU proof workflow below, not a GPU miss or the
chosen search threshold.

## Isolated Windows setup

The validated host uses native Windows, an NVIDIA GeForce RTX 5090, and
CuPy 14.2.0. Its CUDA toolkit wheel bundle is 13.4.3; the installed CUDA runtime
component package is 13.4.92. CuPy provides Windows CUDA wheels and optional
CUDA component wheels through the `[ctk]` extra; see the official
[CuPy installation instructions](https://docs.cupy.dev/en/stable/install.html#installing-cupy-from-pypi).

Run from the repository root to create a separate reproduction environment:

```powershell
uv venv --python 3.11 out\family1-gpu-reproduce-venv
uv pip install --python out\family1-gpu-reproduce-venv\Scripts\python.exe "cupy-cuda13x[ctk]==14.2.0" "cuda-toolkit==13.4.3"
$gpuPython = (Resolve-Path out\family1-gpu-reproduce-venv\Scripts\python.exe).Path
& $gpuPython tests\family1_gpu_witnesses_test.py --require-gpu
```

This optional environment is separate from MSVC/vcpkg and the generating-function
executables. The test uses small arrays to check complete mask vectors, static
revisits, loops, coincident ports, forced hash collisions, word windows, and
CLI/resume behavior. `--require-gpu` fails if the optional GPU runtime is absent;
without it, the test may explicitly skip.

## Reproduce the frozen v3 search

The completed run is `out/family1-m7-gpu-full-v3-fast`. Its `run.json` records
the parameters and source SHA256, and `source-at-start.py` preserves the exact
self-contained proposer. The archived proposer source hash is
`03deeac04ee72a6825d6ebd433384000dd0a12d8a23e884ad1f630d9a5ada3a4`.
The [cached launcher](../scripts/family1_gpu_cached.py) keeps a private CuPy
memory pool between graphs, avoiding repeated allocation overhead. It runs the
same proposer and releases its own pool at exit; it changes allocation policy,
not the witness checks. `allocator-policy.json` and
`cached-launcher-at-resume.py` preserve that policy and source. Use the frozen
repository scripts with a new output directory to reproduce it:

```powershell
& $gpuPython scripts\family1_gpu_cached.py `
  --journal out\family1-m7-gpu-seeded-base\checkpoint.jsonl `
  --out out\family1-m7-gpu-v3-reproduce `
  --depths 24,28,30,31,32,33,34 --threshold 34 `
  --window-bits 29 --max-window-blocks 0
```

The frozen input contains 4,166,855 records. Omit `--follow` for this snapshot;
that option waits for a growing producer's completion marker. Resume with the
same arguments and `--resume`. Changed source, depths, threshold, or window
settings require a new run directory. Preserve the archive and `run.json`.
For a self-contained source copy, keep `family1_gpu_cached.py` and
`family1_gpu_witnesses.py` together under their original filenames; the launcher
loads the adjacent proposer. A fresh search without this frozen input is given
in the [native bootstrap commands](family1-seven-state-search.md#start-from-a-fresh-search).

At depth `D<=31`, the search covers all words beginning with zero and their
complements. For `D>=32`, v3 searches separate prefix windows of at most
`2^29` representatives. `--max-window-blocks 0` visits all windows, but pairs
from different windows are omitted. Those omissions can hide collisions.

**Every GPU miss, error, and apparently collision-free GPU layer remains
inconclusive.** No GPU outcome supplies a certified lower bound. Hashes select
candidates; complete endpoint vectors are compared, and each proposed witness
must additionally pass a separate CPU simulation of all 128 masks. The
`--threshold 34` setting selects work; it does not assert that the optimum is 34.

`upper-witnesses.jsonl` contains accepted positive proposals. `attempts.jsonl`
keeps misses/errors separately, while `progress.json` and `summary.json` record
run progress. Their maximum/tie certificate flags remain false. The completed
v3 run traversed the full journal and accumulated 174,596 positive proposals,
with no unresolved GPU attempts or errors. These execution counts do not
replace the independent enumeration and CPU audits.

## Apply positive witnesses

After the sparse proposal file is frozen and complete, apply it to a full
journal in a new output directory:

```powershell
uv run --no-project python scripts\family1_apply_upper_witnesses.py `
  --journal out\family1-m7-gpu-seeded-base\checkpoint.jsonl `
  --witnesses out\family1-m7-gpu-full-v3-fast\upper-witnesses.jsonl `
  --out out\family1-m7-gpu-v3-applied-reproduce
```

The applicator independently repeats all 128 scalar mask checks, matches each
proposal to the base ordinal, key, and transition table, preserves inherited
lower bounds, and never weakens an existing upper bound. Duplicate identities,
false witnesses, contradictory bounds, changed sources, and nonempty output
destinations fail. Completed files are published atomically with source/output
hashes and a copy of the sparse evidence. GPU no-hit records are not inputs to
this command. The output still makes no global optimum or complete-tie claim.
The completed production overlay is
`out/family1-m7-complete-upper-v3/checkpoint.jsonl`: all 4,166,855 records are
retained, and all 174,596 proposals independently improved their upper bounds.
Its provenance records the frozen base, sparse evidence and output hashes.

## Certify the maximum and every tie

Use the separate CPU certificate workflow after every graph has a verified
upper witness:

```powershell
uv run --no-project python scripts\family1_verify_global_certificate.py `
  --journal out\family1-m7-complete-upper-v3\checkpoint.jsonl `
  --out out\family1-m7-global-certificate-v3-reproduce `
  --jobs 1 --max-total-working-mib 40000 --lower-threads 8 `
  --lower-timeout-ms 1200000 --refine-frontier
```

It freshly recomputes the Burnside class count and runs the independent native
audit on **all 4,166,855 records**, checking accessibility, rooted canonical
tables, distinct identities, and every upper witness. If the largest verified
upper bound is `U`, it then actually runs the independent complete-mask lower
checker at `U-1` for **every** graph on that initial upper frontier. Producer
best lists and claimed exact scores do not supply those proofs.

With `--refine-frontier`, a collision found by a fresh lower computation is
independently replayed on all 128 static masks. Its shorter upper bound is saved
in a new full journal, preserving inherited lower bounds and the original
journal. The native whole-journal audit then runs again. Only when the remaining
largest-upper frontier is exactly the set with fresh matching lower proofs does
the wrapper export every maximizer. If all frontier uppers decrease, or any
required computation is incomplete, it fails closed and retains the refined
journal for further work. Without this option, a frontier collision prevents
certification. Sources, executables and input hashes are checked before and
after execution.

For `U=34`, the compact depth-33 check needs a 32 GiB hash array; the command
allows 40,000 MiB with one graph worker and eight threads sharing that array.
The current independent checker supports depths through 33. An unresolved
graph or insufficient resources leaves the complete-tie result uncertified.

The actual initial audit in the
[compact proof copy](../results/family1-m7/README.md) passed all
4,166,855 records, every root-fixing permutation and every upper witness. Its
maximum/tie flags remain false because that native audit checks uppers only.
All eleven initial frontier graphs received fresh depth-33 CPU checks: eight
were collision-free, and three supplied verified length-33 collisions. A
second complete native audit on the refined journal establishes upper bound
33 for every omitted class. The completed wrapper summary certifies maximum
34 and the complete collection of eight rooted classes. Root movement groups
them into four shapes and removes no rooted class from the result.

The full journal is retained in the source-only
[portable certificate ZIP](../out/family1-m7-certificate.zip), with SHA256
`6fe3dabe21a7175fe1bc07377df81eaea5df80d0d31a6e5f002037e7c60d1588`.
Its `data/checkpoint.jsonl` has SHA256
`9d6de41b2f99dd220bd9d086d6910e5d466c16e23328f22f57520654c47e3d70`.
The ZIP includes exact independent verification sources and standalone Windows
replay commands; no GPU is needed to replay the certificate.
