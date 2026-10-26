# Circulant Family 1 seeds

Variant: `manuscript`. Each exact size 1–20 contributes one rooted class; all vertex roots are equivalent by translation. `champions.jsonl` is a candidate-input filename, not a claim that these graphs are global maximizers.

The raw formula, ordered transition table, canonical vertex permutation, port swaps, and every root translation are retained in each record. Local mask bits remain fixed on revisits. All saved upper witnesses were replayed for every static mask and every raw root.

| m | Lower bound | Upper bound | Status |
|---:|---:|---:|---|
| 1 | 1 | 1 | exact |
| 2 | 3 | 3 | exact |
| 3 | 4 | 4 | exact |
| 4 | 7 | 7 | exact |
| 5 | 10 | 10 | exact |
| 6 | 11 | 11 | exact |
| 7 | 13 | 13 | exact |
| 8 | 13 | 13 | exact |
| 9 | 2 | unknown | incomplete |
| 10 | 2 | unknown | incomplete |
| 11 | 2 | unknown | incomplete |
| 12 | 2 | unknown | incomplete |
| 13 | 2 | unknown | incomplete |
| 14 | 2 | unknown | incomplete |
| 15 | 2 | unknown | incomplete |
| 16 | 2 | unknown | incomplete |
| 17 | 2 | unknown | incomplete |
| 18 | 2 | unknown | incomplete |
| 19 | 2 | unknown | incomplete |
| 20 | 2 | unknown | incomplete |

Exact scores through six were checked against the complete small-case journal and independently recomputed. Any further exact scores use fresh complete equal-length product-vector layers, with layer counts and SHA-256 checksums in `layers.json`. The seven-state source interval is also retained separately.

The literal supplied formula is tau0(i)=(i+1) mod m, tau1(i)=(i+floor(m/3)) mod m. Its ports coincide for m=1,3,4,5, so those scores are exactly one. No numeric quadratic bound is invented from an asymptotic claim. The separately labeled manuscript variant uses tau1(i)=(i+1+max(1,floor(m/3))) mod m; a cumulative-product theorem for that family does not imply a quadratic lower bound on this fixed-graph score.

```powershell
uv run --no-project python scripts/family1_circulant_family.py --variant manuscript --exact-through 8 --depth-cap 18
uv run --no-project python tests/family1_circulant_family_test.py
```
