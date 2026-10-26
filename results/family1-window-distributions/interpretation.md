# Common-window gain distributions

The gain distribution depends on both the graph and the current word pair.
For a fixed pair, write \(R=2^m-S(u,v)\) and
\(D_k(w)=S(uw,vw)-S(u,v)\). The plots use \(D_k(w)/R\), counting every
length-\(k\) binary window with equal weight. These are complete finite
distributions, rather than Monte Carlo estimates.

At the initial saved pairs for the eight seven-state maximizers, the mean
normalized four-letter gain ranges from **0.341 to 0.613**. Every four-letter
window gives some gain in these particular initial cases. Later distributions
can be much more discrete: class (c), with one coordinate left, has gain zero
for eight windows and full gain for the other eight.

Stage dependence is substantial even after normalization. For class (a),
the initial gains are 33–42 out of 108 remaining coordinates. At stage 24,
the gains span 0–7 out of seven remaining coordinates, including four zero-gain
windows. Its normalized mean changes from 0.341 to 0.429 while the distribution
becomes much broader. Monotonicity of accumulated agreement does not imply a
monotone or concentrated distribution of future gains.

The plateau fixture makes the algorithmic consequence concrete. Both
one-letter gains are zero; at length two, 00 and 11 merge all four remaining
coordinates. A search that discards every neutral first step loses both paths.

For the literal twenty-state circulant and
\((u,v)=(0^5 1^5,1^5 0^5)\), initially \(S=213256\) and \(R=835320\).
All sixteen four-letter windows have positive gains: **378882–470835**,
with mean **414959.875** and population standard deviation **30269.962**.
This is one early-stage example over all 1,048,576 masks; it supplies no
general concentration statement or guarantee that every residual coordinate
can eventually merge.

The seven-state stages follow already saved common suffixes of known witness
pairs. They are not an unbiased sample of pairs or search trajectories. Original
common prefixes remain in the words throughout. No graph-score lower bound,
global optimum, or general “richness” theorem follows from these figures.

## Figures

- Early versus late empirical CDFs: [PNG](../../output/figures/family1-window-distributions/m7-early-late-ecdf.png), [SVG](../../output/figures/family1-window-distributions/m7-early-late-ecdf.svg).
- Mean gain and zero-window fractions by stage: [PNG](../../output/figures/family1-window-distributions/m7-stage-summaries.png), [SVG](../../output/figures/family1-window-distributions/m7-stage-summaries.svg).
- Neutral-step fixture: [PNG](../../output/figures/family1-window-distributions/neutral-plateau.png), [SVG](../../output/figures/family1-window-distributions/neutral-plateau.svg).
- All twenty-state windows: [PNG](../../output/figures/family1-window-distributions/m20-literal-all-windows.png), [SVG](../../output/figures/family1-window-distributions/m20-literal-all-windows.svg).

## Validation and reproduction

Fresh Release results in [native-v2.json](native-v2.json) match all **24 supported
saved scalar cases**, including every seven-state \(k=4\) stage. All **374**
native window scores, including the sixteen twenty-state windows, also match
an independent exhaustive pointwise NumPy state simulation over every mask.
Permutation metadata are checked separately; the twenty-state count is 32.
The extra saved \(k=8\) case remains scalar-only because the native API currently
supports \(k\le6\).

    uv run --no-project --with matplotlib python scripts/family1_plot_window_distributions.py --native-exe out/build/msvc-vcpkg/Release/Family1Sample.exe

Omit the native-exe option to redraw from saved data. The plot
[manifest](../../output/figures/family1-window-distributions/manifest.json)
pins the script, reference data and every PNG/SVG. All four plots were visually
inspected.
