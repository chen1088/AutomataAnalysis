# Repository artifacts

Keep source code, tests, documentation, editable TikZ, compact graph tables,
witnesses and summary reports in Git. The selected publication PDFs and the
portable atlas TikZ ZIP are small enough to include. Before committing, check
the actual staged blobs:

```powershell
uv run --no-project python scripts/check-staged-size.py
git diff --cached --check
```

The size check rejects any added or modified file larger than **1 MiB**. It
checks the index, so shrinking a working copy without restaging does not bypass
the limit. This is a review command, not an automatically installed Git hook.
The ignore rules make result datasets opt-in; add a narrow exception only for a
compact artifact that belongs in the source repository.

Full graph journals, raw search observations, checkpoints, native binaries,
source snapshots, certificate archives, render previews and TeX intermediates
stay local. The cleanup does not delete these files. Large evidence archives
can be distributed separately with the paper; they are not part of a clone.
Historical manifests and reports retain their original paths, sizes and hashes,
including references to this separately retained evidence. A saved successful
report is not a substitute for replaying its full certificate.

## Fresh checkout

Build with the existing Windows/MSVC/vcpkg setup:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-windows-vcpkg.ps1 -Configuration Release
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-windows-vcpkg.ps1 -Configuration Debug
```

The publication check built both configurations with the existing installed
dependencies. An attempted clean dependency reinstall hung in MPFR's configure
probe for `gmp_printf("%a")`, with a GMP assertion `len < total_width`.
A clean vcpkg reinstall therefore remains unverified. The separate fresh-source
check reused the matching installed dependencies with
`-DVCPKG_MANIFEST_INSTALL=OFF` and
`-DVCPKG_INSTALLED_DIR=<existing-build>/vcpkg_installed`; it did not change the
MPFR checks or Windows security settings.

Run CTest from the configured build directory, selecting `-C Release` or
`-C Debug`. With `uv` installed, a fresh checkout registers **35 tests**. The
optional 36th test, `family1-independent-m5`, is registered after the full local
`out/family1-m1-m6/graphs.jsonl` journal has been regenerated and CMake has been
reconfigured. That journal contains 203,321 evaluations and is intentionally
excluded. See [the exact search commands](family1-search.md) and
[seven-state bootstrap/certificate workflow](family1-seven-state-search.md).

The committed adaptive result contains all **311 qualified graphs**, not the
45,004-graph raw archive. To start another bounded refinement using only inputs
included in the repository:

```powershell
uv run --no-project python scripts/family1_adaptive_candidate_search.py --records results/family1-adaptive-search-final/records.jsonl --refined-records results/family1-adaptive-search-final/records.jsonl --out out/my-compact-adaptive-run --start-window 10 --jobs 4 --query-seconds 20 --wall-seconds 240 --max-queries 16
```

This starts a new run on the qualified subset. It does not resume the original
raw run or establish exhaustive coverage. Existing immutable result metadata
is retained rather than rewritten to pretend its raw inputs are in Git.

Rebuild the current atlas and its portable source package with a TeX installation:

```powershell
uv run --no-project python scripts/family1_grouped_atlas.py
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts/build-family1-atlas.ps1 -Individual
uv run --no-project python scripts/family1_package_atlas.py
```

The current [atlas guide](family1-grouped-atlas.md) explains the grouped roots
and the distinction between certified maxima and heuristic examples. The
complete seven-state certificate journal and its 87 MB ZIP remain separate
local artifacts described in [the certificate report](../results/family1-m7/README.md).
