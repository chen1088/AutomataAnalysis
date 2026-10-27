# Variance-adaptive joint lookahead

2026-10-27. Every search is deterministic and uses all four paired symbols
00,01,10,11. **Joint k** denotes a complete population of 4^k suffix pairs.
The main experiments disable the exact oracle: **exact depth=0**. A pair
found directly in the bounded seed catalogue has producing **k=N/A**;
it is not an exact-oracle result.

The proposed variance rule is implemented in
[HardPairJointAdaptive.h](../HardPairJointAdaptive.h). Low thresholds often
make it behave like fixed rolling k=2, with slightly more work. The matched
pilot does not establish a better quality/work tradeoff than the fixed
controls. High variance across endpoints is not sufficient evidence that
the next greedy action is well determined.

## Algorithm

For a retained distinct pair u,v, let D be the number of original static-mask
DFAs whose endpoints disagree, and N=2^m. All coordinates remain stored:
later 01 or 10 can destroy an agreement. Coincident-port realizations retain
their original mask multiplicity.

For each retained parent:

1. Enumerate every joint extension through the minimum k. Every intermediate
   depth is checked for a distinct pair with D=0.
2. At each complete depth, record the full D histogram, minimum, maximum,
   sum and sum of squares, plus the four first-action conditional populations.
3. If the chosen variance threshold is met, select that horizon. Otherwise,
   extend the complete frontier one level, through maximum k. Previously
   evaluated levels are reused.
4. For each first action, find its best endpoint under permutation-disagreement
   then full-D ranking. Retain a beam of the resulting one-symbol child states,
   breaking ties by immediate rank and lexical words. Recompute next round.
5. Return the shortest verified positive found across the retained parents
   and the fixed seed portfolio. A complete window finding a positive still
   finishes its population statistics.

The fixed block control commits its full k-symbol block. The rolling controls
and adaptive treatments commit one symbol. Adaptive block advancement is
rejected, so different selected horizons cannot mix word lengths in one beam.

With L=4^k leaf scores d_i, the normalized total population variance is

    V = (L * sum(d_i^2) - sum(d_i)^2) / (L^2 * N^2).

The variance of the normalized decrease (D(parent)-d_i)/N is the same V.
Counting synchronized DFAs with the same normalization also gives V.
Thresholds are integer parts per million of this normalized variance.
Portable exact 128-bit arithmetic compares the rational quantities; floating
point never chooses a branch or horizon.

The action-variance treatment uses the variance of the four conditional
mean D/N values. With s_a the sum of endpoint D in first-action group a,
its numerator is 4*sum(s_a^2)-sum(d_i)^2, with the same denominator.
This differs from the four conditional minima, which are exported separately.

The progress treatment additionally requires a strictly better numeric (P,D)
endpoint within the complete window. This does not require every committed
one-symbol step to improve D.

Window size is a heuristic choice, not a lower bound or confidence certificate.
If the fixed expansion budget cannot cover the minimum window, that parent
is refused before any of it is evaluated. If an additional complete layer
cannot fit, the finder finishes other affordable parents in the current
round, preserves any positive, then ends the attempt with an explicit
budget refusal. The last completed horizon is not committed as a fallback.
Its provisional selected-k statistic remains visible. No partial population
contributes to variance.

## Matched pilot

All 20 certified winners through m=7, including every tie, were tested under
11 predeclared configurations. All use beam 16, maximum length 80,
2,000,000 expansions per starting-pair attempt, and 64 starts per ranking.
The two rankings are full-D and mask-specific common-input merge distance.
Both rank the same bounded 16,384-pair catalogue from complete binary word
layers through depth 20, with a 1,048,576-word layer cap. These are bounded
seed selections, not every possible compatible pair. Catalogue generation
is physically shared across configurations; its per-policy cost is reported
separately from actual joint node expansions.
The table gives configured k bounds. Actual final spans can be shorter near
a length cap; the producing sequence records those spans explicitly.

| Policy | Joint k | Threshold ppm | Exact matches / 20 | Within one / 20 | Joint nodes |
|---|---|---:|---:|---:|---:|
| Fixed block | 4 | N/A | 14 | 19 | 22,713,788 |
| Fixed rolling | 2 | N/A | 14 | 19 | 6,658,524 |
| Fixed rolling | 4 | N/A | 15 | 19 | 93,843,612 |
| Fixed rolling | 5 | N/A | 15 | 19 | 338,848,700 |
| Total variance | 2..5 | 1,000 | 14 | 19 | 6,664,668 |
| Total variance | 2..5 | 10,000 | 14 | 19 | 31,684,444 |
| Total variance | 2..5 | 40,000 | 14 | 19 | 69,829,724 |
| First-action mean variance | 2..5 | 1,000 | 14 | 19 | 34,619,452 |
| First-action mean variance | 2..5 | 10,000 | 14 | 19 | 76,274,556 |
| Total variance, deeper minimum | 4..6 | 10,000 | 15 | 19 | 175,090,844 |
| Total variance + progress | 2..6 | 10,000 | 14 | 19 | 104,842,708 |

Every configuration finds all 20 pairs and stays within two of exact H.
The adaptive 2..5 treatments and the progress treatment return the same
length vector as fixed rolling k=2. The deeper-minimum treatment returns
the same vector as fixed rolling k=4. Thus this experiment does not establish
a quality advantage from variance adaptation. Fixed rolling k=5 also gives
the same lengths as k=4 at much greater cost.

At threshold 1,000 ppm, adaptive k=2..5 deepens only 96 of 327,235
non-clipped parent decisions, adding exactly 6,144 transitions over fixed
rolling k=2. At 10,000 ppm, 7.83% of non-clipped decisions deepen, but those
extra layers consume 78.99% of node work. Every one of that treatment's
228 winning-path decisions still chooses k=2. The deeper-minimum treatment
likewise chooses k=4 on all 197 winning-path decisions. In this pilot,
additional depth is mostly spent outside the successful trajectories.

Smaller cases can finish in the seed catalogue. The report tables separately
retain the ten m=6,7 winner cases that require longer searches; the absence
of an exact oracle must not be confused with every case using greedy steps.

For comparison with the previous implementation, a separate run of the
original joint k=4, beam-16 portfolio with **512 starts per ranking** and
**exact depth=0** finds all 20 within one, with 16 exact matches. Both m=6
winners return 24 against H=23. This is a different seed budget from the
64-start pilot, so its quality and work are not a matched treatment effect.

## Stronger 512-start calibration

The five follow-up policies and a supplementary fixed-k=2 control test all
20 winners with **512 starts per ranking**, beam 16 and exact depth=0.
Every treatment finds all 20 within one, but none recovers all exact lengths.

| Policy | Configured joint k | Threshold ppm | L=H / 20 | L≤H+1 / 20 | Joint nodes |
|---|---|---:|---:|---:|---:|
| Fixed block | 4 | N/A | 16 | 20 | 141,757,088 |
| Fixed rolling | 2 | N/A | 15 | 20 | 42,534,988 |
| Fixed rolling | 4 | N/A | 16 | 20 | 599,764,196 |
| Total variance | 2..5 | 1,000 | 15 | 20 | 42,569,228 |
| Total variance, deeper minimum | 4..6 | 10,000 | 16 | 20 | 1,254,092,004 |
| Total variance + progress | 2..6 | 10,000 | 15 | 20 | 755,051,204 |

All six return 24 for both m=6 winners, against H=23. Fixed block/rolling
k=4 and adaptive k=4..6 return the m=7 length vector
35,34,34,35,34,34,34,34 in canonical key order. Adaptive k=2..5 and the
progress policy return 35,34,35,35,34,34,34,34. Increasing lookahead work
does not repair these remaining gaps.

The fixed-block control exactly reproduces all 20 pairs, D traces, uppers
and per-graph node counts from the original oracle-off finder. This confirms
that the new harness has not weakened that control. Raw adaptive k=2..5
is cheaper, but loses one exact match; deeper adaptation adds work without
a length improvement. The matched fixed rolling k=2 control produces the
same 20-length vector as low-threshold adaptation with 34,240 fewer nodes.

## Broader saved-frontier stress test

All 343 graphs in the saved frontier were tested at **64 starts per ranking**,
beam 16, exact depth=0 and the same remaining budgets. These include 288
graphs with m≤6 and 55 with m=7. Exact H is known for 296 rows; the other
47 are certified m=7 nonwinners with verified upper certificates.

| Policy | Configured joint k | Found / 343 | L=H / 296 | L≤H+1 / 296 | L≤H+2 / 296 | Largest finite known-H gap | Joint nodes |
|---|---|---:|---:|---:|---:|---:|---:|
| Fixed block | 4 | 338 | 237 | 276 | 287 | 10 | 359,699,112 |
| Fixed rolling, supplementary control | 2 | 339 | 236 | 275 | 288 | 13 | 104,768,292 |
| Fixed rolling | 4 | 340 | 264 | 283 | 290 | 10 | 1,368,244,216 |
| Total variance, 1,000 ppm | 2..5 | 339 | 236 | 275 | 288 | 13 | 104,799,396 |

Missing pairs stay in the denominators. The largest finite gap excludes
misses and the 47 rows whose exact H is unknown. One-symbol rolling improves
the broader exact-recovery count over block advancement, at about 3.8 times
the transition work. The variance rule is much cheaper but less accurate.
Neither the rolling policy nor variance adaptation passes general reliability.
No expansion-budget refusal occurred in these four treatments. For example,
at adaptive k=2..5, key 010200030204030500030005 returns 34 against exact
H=21. This six-state failure is not hidden by the successful winner subset.

The supplementary fixed rolling k=2 control returns exactly the same 343
word-pair results, including misses, as low-threshold adaptive k=2..5.
It uses 31,104 fewer nodes. Thus the lower cost is attributable to shallow
lookahead in this comparison; the variance adaptation contributes extra
probes without an observed pair improvement.
Three broader winning paths include a k=3 probe; their returned pairs still
match fixed k=2. Extra probes are therefore not exclusively off winning paths.

Among the 47 m=7 nonwinners, block k=4 finds 21 certificates of length at
most 33; rolling k=4 finds 25; adaptive k=2..5 finds 15. Each misses three
of these graphs. In particular, all three miss key
0102000304050203000604050003 despite its independently replayed prior
length-32 pair. That historical pair's producing k is unknown. Historical
certificates remain separate from new finder results and preserve the
certificate floor without masking these misses.

Rarity still fails as a quality signal. In a finite top band within two of
the largest returned upper, block k=4 retains 15 graphs including four true
winners; rolling k=4 retains 11 including three; adaptive k=2..5 retains
seven including only one. The apparently rarer band accompanies worse
recovery, rather than identifying a stronger search.

## What variance can miss

The [independent small counterexamples](../results/family1-adaptive-window-20261027/variance-counterexamples.json)
enumerate every joint k=2 extension for two three-state Family 1 graphs,
starting from the distinct words 0 and 1 and using all eight static masks.
Neither has an intermediate success in these windows.

For key 000100020202, normalized total variance is 13/256, yet all four
first-action minimum D values are 4. The large spread includes bad alternatives
and does not distinguish the next actions by their best endpoint.

For key 000100020002, all four first-action means are 5, giving zero
between-action mean variance. The action minima are 4,3,4,4: one action
has a uniquely better minimum. Mean separation can miss the rare good
continuation that an existential hard-pair search needs.

These examples refute a confidence interpretation, not the usefulness of
adaptive lookahead as a heuristic. The Family 1 comparisons determine whether
the policy helps under a declared work and seed budget.

## Evidence and reproduction

The [runner](../scripts/family1_adaptive_window_benchmark.py) freezes graph-only
inputs, all configurations, the executable and its 15-source compile
fingerprint. It verifies native configuration fields, complete-layer work
identities and every final/improvement pair before sealing all configured
query outputs. Only then are exhaustive H labels attached.

    cmake -S . -B out/build/adaptive-window -DFAMILY1_OFFLINE_ONLY=ON -DCMAKE_BUILD_TYPE=Release
    cmake --build out/build/adaptive-window -j 4
    ctest --test-dir out/build/adaptive-window --output-on-failure
    python3 scripts/family1_adaptive_window_benchmark.py \
      --exe out/build/adaptive-window/Family1AdaptiveWindowBenchmark \
      --out out/adaptive-window-pilot --starts 64 --jobs 4

Every result records both words, D and synchronized-count traces, actual
producing-k sequence, winning seed, configured k bounds and all work caps.
Aggregate k histograms cover every attempt. Detailed moment records cover
the final winning attempt's ancestry; they are not an unbiased sample of all
failed attempts. Length-limit exhaustion and expansion-budget refusal remain
distinct. A miss never establishes a lower bound.

The complete reference set was used for development. The later saved-frontier
stress test overlaps those graphs, so no independent generalization guarantee
or universal near-shortest error bound is claimed.

All 13 semantic CTests pass. The new independent test reconstructs 1,545
complete windows from scalar DFA transitions, checks full D histograms and
conditional-action statistics, and exercises portable wide arithmetic,
atomic budget refusal, winning ancestry, distinctness, shorter positives in
later retained parents and variable-horizon state deduplication.

The [evidence index](../results/family1-adaptive-window-20261027/README.md)
links all 1,712 new case/configuration results, complete paired-word tables,
winning-window moment shards and figures. The measured outcome is to retain
the variance policy as an experimental control, not make it the production
default. The next controlled comparison should separate seed coverage from
the handling of tied first actions. These variance thresholds did not solve
the broader accuracy failures.
