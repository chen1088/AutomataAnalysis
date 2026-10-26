# Edit-candidate benchmark figures

Each figure is available as a high-resolution PNG and an editable SVG.

1. **Complete local growth recall** — `complete-local-growth-recall.png` / `.svg`. At sizes 2–7, complete radius-1 growth from previous-size near-top parents recovers every known maximizing rooted class after accessible root closure. Fixed-root and all-root results are separate. These are complete local neighborhoods, not exhaustive graph enumeration.
2. **Budgeted seven-state ranking** — `budgeted-m7-ranking-recall.png` / `.svg`. The same budgeted near-top, radius-1, root-closed pools are compared across three sealed seeds, excluding the extra complete-growth runs. At nominal budget 2048, parent strata recover 8/8 winners for every seed; structural order recovers 7–8/8; native discovery and matched labelled random recover 0/8. The table records actual candidate counts after whole-shape block overshoot.
3. **Seven-state elimination** — `complete-m7-elimination.png` / `.svg`. Of 13,329 graphs in the complete local pool, short witnesses certify 12,691 as having H≤33. The remaining 638 comprise 630 nonmaximizers unresolved by this filter and eight known maximizers. Those survivor labels are retrospective; a filter miss supplies no lower bound.

Lines and shading in the ranking figure show the mean and minimum–maximum across the three fixed seeds. They are not confidence bounds. The matched random baseline samples labelled port tables, rejects inaccessible graphs and deduplicates rooted classes; it is not uniform over graph isomorphism classes.

`plot-data.json` retains every numerical input used in these figures. `manifest.json` pins the plotting script, published benchmark inputs, complete-growth candidate files, derived data and all six artifacts. All SVG files were parsed as XML. `visual-qa.json` records the final manually inspected artifact hashes.

Recreate from the full benchmark evidence:

```powershell
uv run --no-project --with matplotlib python scripts/family1_plot_edit_benchmarks.py
```

Recreate from the frozen figure data without the raw native candidate directories:

```powershell
uv run --no-project --with matplotlib python scripts/family1_plot_edit_benchmarks.py --data output/figures/family1-edit-candidates/plot-data.json --out out/edit-benchmark-figures-repeat
```
