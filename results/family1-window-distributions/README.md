# Exact common-window gain distributions

Every mask and every length-k binary window is evaluated by ordinary scalar simulation. D(w) counts newly agreeing coordinates. Normalized gains divide by the coordinates still unequal before the window. Counts and vectors concern these specific pairs, rather than a random sample or a theorem about graph richness.

| Case | S / total | Remaining | k | Gain min / mean / max | Stddev | Zero windows |
|---|---:|---:|---:|---|---:|---:|
| plateau-k1 | 4/8 | 4 | 1 | 0 / 0 / 0 | 0 | 2/2 |
| plateau-k2 | 4/8 | 4 | 2 | 0 / 2 / 4 | 2 | 2/4 |
| plateau-k4 | 4/8 | 4 | 4 | 0 / 3.5 / 4 | 1.323 | 2/16 |
| m7-class1-stage0-k4 | 20/128 | 108 | 4 | 33 / 36.88 / 42 | 2.848 | 0/16 |
| m7-class1-stage8-k4 | 78/128 | 50 | 4 | 8 / 12.81 / 19 | 2.603 | 0/16 |
| m7-class1-stage16-k4 | 107/128 | 21 | 4 | 2 / 4.375 / 8 | 1.615 | 0/16 |
| m7-class1-stage24-k4 | 121/128 | 7 | 4 | 0 / 3 / 7 | 2.574 | 4/16 |
| m7-class2-stage0-k4 | 42/128 | 86 | 4 | 39 / 52.12 / 73 | 11.44 | 0/16 |
| m7-class2-stage8-k4 | 123/128 | 5 | 4 | 0 / 1.625 / 3 | 1.111 | 2/16 |
| m7-class3-stage0-k4 | 40/128 | 88 | 4 | 41 / 52.88 / 69 | 9.727 | 0/16 |
| m7-class3-stage8-k4 | 117/128 | 11 | 4 | 3 / 4.5 / 6 | 0.866 | 0/16 |
| m7-class3-stage16-k4 | 127/128 | 1 | 4 | 0 / 0.5 / 1 | 0.5 | 8/16 |
| m7-class4-stage0-k4 | 47/128 | 81 | 4 | 29 / 42.19 / 64 | 12.12 | 0/16 |
| m7-class4-stage8-k4 | 119/128 | 9 | 4 | 1 / 3.062 / 7 | 1.56 | 0/16 |
| m7-class5-stage0-k4 | 20/128 | 108 | 4 | 42 / 44.5 / 49 | 2.449 | 0/16 |
| m7-class5-stage8-k4 | 93/128 | 35 | 4 | 1 / 10.62 / 19 | 7.132 | 0/16 |
| m7-class5-stage16-k4 | 121/128 | 7 | 4 | 0 / 1.812 / 6 | 2.068 | 8/16 |
| m7-class6-stage0-k4 | 41/128 | 87 | 4 | 39 / 53.31 / 75 | 12.15 | 0/16 |
| m7-class6-stage8-k4 | 123/128 | 5 | 4 | 0 / 1.625 / 4 | 1.364 | 5/16 |
| m7-class7-stage0-k4 | 31/128 | 97 | 4 | 35 / 49.88 / 72 | 12.45 | 0/16 |
| m7-class7-stage8-k4 | 108/128 | 20 | 4 | 1 / 5.625 / 11 | 2.643 | 0/16 |
| m7-class7-stage16-k4 | 125/128 | 3 | 4 | 1 / 1.5 / 3 | 0.866 | 0/16 |
| m7-class8-stage0-k4 | 60/128 | 68 | 4 | 22 / 36.81 / 56 | 12.38 | 0/16 |
| m7-class8-stage8-k4 | 124/128 | 4 | 4 | 0 / 1.5 / 3 | 1 | 2/16 |
| m7-class1-stage0-k8 | 20/128 | 108 | 8 | 44 / 56.88 / 68 | 5.143 | 0/256 |

`cases.jsonl` retains all window strings, full gain vectors, endpoint-agreement counts, normalized gains, histograms, and summary statistics. `summary.csv` is intended for plotting. Seven-state stages append 0,8,16,24 letters of the previously saved common suffix whenever that stage exists. Original common prefixes are retained in the two words; no cancellation is used.

```powershell
uv run --no-project python scripts/family1_window_distribution_reference.py
```

These are scalar reference distributions, not native performance measurements. No witness search or global maximum is certified by this diagnostic.
