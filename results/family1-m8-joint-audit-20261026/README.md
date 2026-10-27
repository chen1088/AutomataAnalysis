# Deterministic m=8 joint-pair recheck

No new graph with proved shortest merge length above 50 was established.
The existing length-50 pair remains a valid upper certificate; its working
estimate 49 is not a proved shortest length. The corrected joint greedy
finder is not yet calibrated closely enough to rank the unresolved cases.

## Complete candidate neighborhood

The fixed parents are every accessible root of the four underlying shapes
represented by the previous top-five refined graphs and the lower-35 anchor.
This gives the 32 rooted classes in `parents.csv`. The candidate set contains
**every accessible canonical eight-state class at rooted primitive edit
distance at most one from those parents**, including distance zero. At this
same-size radius, a primitive edit is a single port retargeting.

Independent enumeration and the native generator agree on all **3,010** keys.
Generation completed without reaching either cap. Every candidate received
both joint runs below; every miss remains in the published tables. This is
a complete local neighborhood, not the entire eight-state graph universe.
Novelty against the unavailable historical 45,004-class archive is unknown.

## Joint alphabet and parameters

Every joint step appends one of **00,01,10,11**. Joint k counts pair-symbol
steps, so a complete window has `4^k` leaves. Both full endpoint profiles are
retained, including coordinates that currently agree and may later separate.
Only distinct equal-length words qualify. All choices are deterministic.
These runs advance the chosen whole k-symbol block and inspect positives at
every intermediate depth; they do not use one-step receding-horizon updates.

| Complete run | Joint k | Greedy beam | Prefix starts | Verified upper <=50 | Upper >50 | No pair |
|---|---:|---:|---:|---:|---:|---:|
| Empty-root greedy | 8 | 1 | 0 | 1,464 | 1,043 | 503 |
| Deterministic multistart exclusion screen | 6 | 1 | 128 | 2,330 | 651 | 29 |

Both runs used maximum pair length 80, no clock limits, and 2,000,000
expansions per attempt. The multistart run enumerated complete prefix layers
through depth 16 with at most 65,536 words per layer and common-prefix
strata through eight. Every subsequent window still used all four symbols.
Its target 50 stops a graph only after scalar verification of a pair with
length at most 50. This is an exclusion screen, not a shortest-pair ranking.
All evaluated windows completed; no expansion budget was reached. Word,
prefix-pair, beam and pair-length limits remain genuine coverage limits.

Combining the two new joint runs gives **2,379** graphs with upper bounds at
most 50, **604** with larger upper witnesses, and **27** without a new pair.
Every chosen positive was independently replayed on all 256 masks: **763,648**
graph/mask checks. `new-joint-cases.csv` retains all 3,010 rows and witnesses,
with the chosen source k and prefix budget.

Previously collected positive certificates were separately replayed on all
256 masks: 2,950 graphs and **755,200** graph/mask checks. These include older
common-suffix k=6/k=8 attempts and imported historical certificates. Common
suffixes are legitimate continuations of distinct prefixes; their positive
proofs survive even though that restricted search did not explore the full
joint alphabet. No historical word was supplied to either new joint search.

After combining all these certificates, **2,812** cases have upper bounds
at most 50. The remaining **198** consist of 180 graphs with larger upper
witnesses and 18 without a pair. They are possible challengers, not proved
improvements. `all-certificates.csv` retains every graph and its strongest
collected certificate; `unresolved-cases.csv` contains all 198 unresolved
cases. Source kind distinguishes joint windows, common-suffix windows and
historical certificate imports; k is not inferred for an imported certificate.
Cases with upper bounds 49 or 50 remain in the tables; their exact scores
and the complete collection of ties remain unresolved.

## Calibration and the estimate of 49

The graph-only calibration used all eight certified m=7 maximizers, each
with true shortest length 34. With 1,024 deterministic prefix starts,
depth 18, 262,144 words per layer and greedy beam one:

| Joint k | Returned m=7 lengths in canonical-key order |
|---:|---|
| 6 | 37, 38, 36, 39, 34, 37, 35, 39 |
| 8 | 36, 36, 35, 39, 36, 40, 35, 39 |

The current m=8 leader returned 58 at joint k=6 and 56 at joint k=8 under
those same prefix settings, despite its independently verified length-50
pair. Thus these settings can miss by at least six, and their results do
not support a one-or-two-step error guarantee. `calibration.csv` retains
all cases, including the 128-prefix comparisons and misses. Longer found
pairs cannot establish harder graphs.

A separate finite local word-pair check, **k not applicable**, found no
length-49/48 collision among all one-deletion, two-deletion, or
one-deletion-plus-at-most-one-substitution variants of the existing pair.
That excludes only the explicitly enumerated word neighborhoods, not all
shorter pairs. The value 49 remains plausible and unproved.

## Reproduction and evidence

Use [the joint command reference](../../docs/family1-joint.md). Decode each
32-digit parent key into eight ordered rows, run the deterministic native
radius-one generator with path/candidate limits above the complete count,
and require complete generation and exact agreement with the published
candidate keys. Run `scripts/family1_joint_campaign.py` on all candidate rows
with the two parameter sets above. `scripts/family1_joint_report.py` audits
the complete native evidence and independently replays the selected pairs.

`summary.json` pins compact outputs and the separately retained raw reports.
Full journals, native binaries, source snapshots, exact local word pools and
per-query diagnostics remain under ignored `out/`. The joint implementation
and persistent tests are versioned. Independent small-graph tests compare
four-symbol traversal with exact shortest collisions on all 64 rooted classes
through m=3 at joint k=1 with wide beams, plus complete 16-leaf k=2 windows.
The final CTest suite passed 3/3; the joint CLI suite passed 17 invocations.
