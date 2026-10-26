# Adaptive candidate search

The active collection contains only graphs tied for the highest **estimated**
shortest merge length. The current list is
[`best-candidates.jsonl`](../results/family1-m8-estimates/best-candidates.jsonl).
Weaker estimates remain in the run archive and can become active again when a
previous leader receives a shorter pair. Every top tie is retained.
The [current vector plate](../output/pdf/family1-m8-active-best/active-best.pdf)
and [reusable TikZ](../output/pdf/family1-m8-active-best/graph-01.tex) show only
that active tier. The final [evidence package](../results/family1-adaptive-search-final/README.md)
records the completed runs and their limits.

For the best verified pair length `L`, the requested working estimate is
`L-1`, with a rough band `[L-2,L]`, clipped to any independently certified
interval. Exact scores keep their exact values; a graph without a found pair
has no numerical estimate. Estimates never increase a certified lower bound.

Cheap first-hit screening results are pending candidates. A graph enters the
refined leaderboard after an explicitly recorded stronger finder pass. The
estimator records the settings and witness sources, so a large cheap first-hit
length does not silently become a refined champion.

## Two escalation rules

`family1_adaptive_candidate_search.py` detects a crowded band within two of the
current largest verified length. The default crowding threshold is three.
It advances through `k=8,10,12,16`, recomputing the full retained leaderboard
after each batch. Native best-of-seeds searches tighten their caps whenever
they find a shorter pair. All positive results and timeout checkpoints are
replayed over every static mask before an upper bound changes.

The expansion quota grows with the window. For an unpruned full window,
`2^(k+1)-2` transitions are needed for one parent; the controller allows
multiple rounds and beam parents. The quota is **per prefix seed**, across
all its window rounds. Prefix generation, distance preprocessing, exact tail
BFS and final scalar verification also consume time outside that quota.
Wall time, prefix coverage and memory budgets are recorded separately.

If the top remains crowded after the word-search ladder,
`family1_adaptive_edit_search.py` widens the candidate neighborhood. The
eight-state run expanded from the previous radius-two pool to radius three,
using all 55 retained seven-state frontier parents. It generated 25,471 rooted
classes and selected 261 roots in 33 whole shapes absent from the previous
radius-one and radius-two pools. All 261 completed a strong `k=8` pass and
received independently verified pairs. Further word refinement then acts on
the recomputed top band.

The resulting archive has 45,004 observed rooted classes and 311 qualified
refined graphs. Generation and scoring limits remain explicit. A capped edit
pool supplies no theorem excluding farther graphs; rarity is a search
heuristic, rather than an optimality certificate.

The radius-three experiment demonstrates both corrections: its two new
length-51 leaders fell to 47 under larger windows. Previously, increasing
`k=6` to `k=8` cut another leader's length from 52 to 48, and a later pass cut
that graph to 46. The public view is rebuilt after these demotions instead
of retaining a stale winner.

## Persistence and validation

The native finder now commits a checkpoint immediately after every new
verified best-of-seeds improvement. Previously a hard timeout could arrive
between the improvement and the next periodic checkpoint. The regression
reproduces the missing checkpoint with the preserved old executable, succeeds
with both new native builds, recovers from the saved improvement, and rejects
a corrupted checkpoint. The old runs and binaries remain available.

Native Windows MSVC/vcpkg Release and Debug builds pass all **34 CTests**.
This includes the adaptive controller's eight checks and the new checkpoint
regression, alongside the existing exact, enumeration and legacy tests.
All active estimates have complete scalar witness verification.

The independent seven-state calibration provides a practical limit on the
estimate rule. Fresh graph-only inputs, whose true scores were read only
afterward, initially produced lengths `34,34,34,35,36,36,38,38` for eight
known score-34 graphs. Larger windows alone did not remove every gap. Broader
prefix searches and bounded checkpoint continuations improved this to
`34,34,34,34,34,35,36,38`. Thus the rough two-step band covered seven of eight
in that experiment; it remains a working estimate, not a confidence interval.
The [finder audit](family1-adaptive-finder-audit.md) explains the counters and
the separate effects of window length and prefix coverage.

## Commands

Generate an adaptive word-search run from the sealed eight-state corpus and
the previously refined input sets:

```powershell
uv run --no-project python scripts/family1_adaptive_candidate_search.py --out out/my-m8-adaptive --jobs 12 --wall-seconds 240
```

Use a fresh output directory for changed settings. Matching `--resume` reuses
pinned plans, source/executable snapshots and checked observations. A saved
timeout supplies only the independently verified positive checkpoint, if any.
It never supplies a lower bound.

Reproduce the crowding-triggered radius-three expansion from its pinned
trigger and existing generation:

```powershell
uv run --no-project python scripts/family1_adaptive_edit_search.py --out out/my-m8-edit-r3 --generation out/family1-m8-r3-instant-generated
```

Continue its qualified roots with the current native executable:

```powershell
uv run --no-project python scripts/family1_adaptive_candidate_search.py --records out/family1-m8-adaptive-edit-r3/archive-records.jsonl.gz --refined-records out/family1-m8-adaptive-edit-r3/qualified-records.jsonl --out out/my-m8-r3-word-search --start-window 10
```

`--strong-prefix` expands the prefix pool when memory permits. The broad
fallback runs preserve their explicit larger seed budgets and time limits.
`--admit-pending` tests additional coarse challengers before allowing them
onto the refined board. The tested top eight cheap lengths 89-91 all fell to
42-50 during their first stronger pass.

The original exhaustive lower-35 proof is preserved separately in the
[certificate archive](../results/family1-m8-search/README.md). Current estimates
and the best-only drawings are in
[the active output](../results/family1-m8-estimates/summary.json).
