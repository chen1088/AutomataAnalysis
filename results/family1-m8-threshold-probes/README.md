# Eight-state fixed-length SAT probes

All26 length-34 queries returned UNKNOWN. They establish neither a collision nor H≥35. The two cloning baselines retain their separately verified H≥34; the bounded SAT queries do not strengthen those bounds.

The calibration queries cover the first4 roots of the two selected edit shapes, each with16 and32 initial masks,15s aggregate/5s per-solve budgets,128 refinements and4 workers. The full batch covers all16 roots of those two shapes plus2 cloning-baseline roots, with32 initial masks and15s aggregate/per-solve budgets. It completed in75.358s wall time. Actual mask sets,0–1 refinement counts, reasons, timings and every native JSON/configuration hash are retained.

The cloning lower bounds were independently rechecked by4096 static transition tests:128 base masks ×8 child states ×2 input letters for each of the two roots. The projection preserves root0 and commutes with every transition under the explicitly lifted, fixed mask. Thus any equal-length collision in the child would also be one in the certified seven-state base, proving H(child)≥34. This is a per-graph lower bound and says nothing about global optimality at eight states.

Fixed-length semantics: no_collision at34 would exclude every earlier positive collision because a shorter pair can be extended by a common suffix. A collision would provide an upper bound34 and would be independently replayed over all256 masks. UNKNOWN adds no score bound. None of these queries returned a positive or negative SAT certificate.

`observations.jsonl` retains all graph tables, settings, decisions and native provenance; `clone-projection-validation.json` records the independently verified lifted-mask construction. The separate partitioned-layer verifier is independent work and its later results are not implied by this SAT report.

```powershell
uv run --no-project python scripts/family1_m8_threshold.py --out out/family1-m8-threshold34-full-repeat --max-graphs 16 --projection-masks 32 --include-baseline --solve-timeout-ms 15000
uv run --no-project python scripts/family1_publish_m8_threshold.py
```
