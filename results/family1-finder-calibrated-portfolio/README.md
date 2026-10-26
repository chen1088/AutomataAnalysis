# Calibrated two-stage seven-state finder

Fresh run: 8/8 independently verified length-34 pairs, 13 native invocations, 87.273 seconds wall time. Each accepted pair was independently replayed over all128 static masks. Both endpoint vectors, source hashes and complete raw stage outputs are retained.

Stage1 uses k6, beam16, tail threshold8,1024 outer attempts/prefix pairs, prefix depth16/65536 words per layer,10000 expansions, drop ranking and no distance/common-prefix option. Only its nonhits proceed to stage2: k16, beam16, tail8,65536 attempts/pairs, prefix depth21/2097152 words per layer, common-prefix depth8,128 distance coordinates, remaining-count ranking and50000 expansions. Both stages use length cap34 and seed1088, without saved word hints.

This is a retrospective calibrated portfolio, not a uniform single-window configuration or a globally complete shortest-pair algorithm. The recovered34 pairs are shortest because the separate exhaustive certificate gives H=34. A miss or timeout provides no lower bound. Stage2 selection depends only on verified stage1 hits, not graph identity or saved witness strings.

Reproduce with a fresh output directory:

```powershell
uv run --no-project python scripts/family1_finder_calibrated_portfolio.py --exe out/build/msvc-vcpkg/Release/Family1Sample.exe --out out/family1-calibrated-portfolio-repeat --jobs 4 --timeout 180
```

Publication replay independently checked all eight pairs again (1,024 mask coordinates). `independent-validation.json` retains both complete vectors. `raw-evidence.zip` preserves every file from the fresh run, including exact original driver snapshots, both complete stages, executable copies, native configurations, checkpoints, logs, attempts and witnesses. `manifest.json` records every archive entry and publication-file SHA-256; the manifest itself is excluded from its own hash map. Extract the archive at the repository root to retain the recorded repo-relative paths.
