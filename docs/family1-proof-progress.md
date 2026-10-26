# Global proof calibration

The exhaustive class search already proves the optimum and retains every
maximizing rooted class through six states. Formal whole-graph SAT searches
are a separate route to global bounds; an incomplete SAT run does not change
those exhaustive results and does not establish a new optimum.

On 25 October 2026, the earlier five-state threshold-15 run was resumed with
its 88 learned separation pairs. A 120-second aggregate budget, 30-second
graph-solve budget, and 15-second candidate budget evaluated 41 additional
graphs and retained 129 pairs in total. It returned `unknown` after the graph
solver exhausted the aggregate budget. Its record is
`out/global-resume-audit/m5-long-before/result.json`; it is not an UNSAT
certificate. The five-state optimum remains proved by exhaustive enumeration.

The learner now postpones difficult individual models under temporary guarded
assumptions and continues collecting necessary separation constraints from
other models. It must solve again without any postponement assumptions before
claiming a global upper bound. Exported certificates contain only the original
graph formula and the learned necessary conditions. A deterministic two-state
test forces resource-capped scoring, postpones three models, and exhausts the
temporarily restricted graph space. The bare formula is satisfiable, and the
reported result correctly remains `unknown`, with no certificate CNF.

The packed full-mask scorer changes the seven-state calibration substantially.
With no imported pair constraints, a threshold-23 whole-graph run found a true
challenger after 19 candidates in 3.51 seconds. The graph with key
`0001020301040506030500020005` was then scored exactly at 25 in 7.69 seconds;
its complete 128-mask product proves minimality, and its witness was checked
by separate ordinary-state simulation on all masks. An ensuing threshold-25
run found key `0001020300040104050600010506`, independently scored exactly at
26 in 15.61 seconds. These are attained scores, not global upper bounds or
complete maximizing collections. The full-mask run records and witness pairs
are in `out/global-resume-audit/m7-first-exact.json` and
`out/global-resume-audit/m7-second-exact.json`.

Importing all earlier five/six-state learned pairs was not automatically
beneficial: the heavily seeded seven-state run timed out in graph SAT after
one candidate and 31.17 seconds. A small three-state test did benefit from
cross-size seeds and produced an UNSAT certificate independently rechecked by
PicoSAT and direct simulation on all 432 ordered accessible transition tables.
This supports seed importing as a sound scheduling option, not a guarantee
that more constraints make synthesis faster.

The optional encoder v2 implements breadth-first discovery ordering:
scan the sorted transition rows in source/port order and require first
occurrences of nonroot target labels to appear as `1,2,...,m-1`. Together with
the existing earlier-predecessor condition this keeps at least one labeling
of every rooted accessible class. Native tests independently inspect all
31,488 ordered accessible four-state tables (and all smaller tables), checking
that each has such a root-fixed labeling. Both encoders pass small global
proofs, clean byte-for-byte certificate replay, and guarded-UNKNOWN tests.
Default v1 remains compatible with its earlier artifacts; resume/replay infer
the version, and cross-version pairs can be imported as necessary conditions.
The first v2 four-state threshold-10 run proved UNSAT in 7.11 seconds after 97
candidates. A clean replay reconstructed identical CNF and proved UNSAT in
1.91 seconds; PicoSAT independently confirmed its 3,367-variable,
44,797-clause formula UNSAT. The five-state threshold-15 run returned
`unknown` after 120.006 seconds and 110 candidates/pairs. The seven-state
threshold-28 run, initialized with 64 earlier seven-state pairs, returned
`unknown` after 120.008 seconds, 10 additional candidates, and 74 pairs in
total. Neither larger run postponed a model; both exhausted the graph-solver
budget. Their records are `out/global-resume-audit/v2-m5/result.json` and
`out/global-resume-audit/v2-m7-28/result.json`. They establish no new global
upper bound. All calibration processes have finished, and their learned-pair
records can seed later searches without discarding any graph class.
