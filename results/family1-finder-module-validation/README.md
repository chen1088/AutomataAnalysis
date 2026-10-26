# Generic module and adapter validation

The generic C++ reference passed in native MSVC Release and Debug:

- 64 independently enumerated rooted seed classes, converted into explicit
  DFA families without production Family1 classes.
- 1,263 conditional common-suffix BFS comparisons, 48 forced-hash cases and
  128 complete window distributions with independently checked moments.
- Heterogeneous DFA state counts2,3,5 and nonzero roots; state/depth caps,
  interruption, repeated states, and preservation of coordinate IDs.
- Common prefixes cannot generally be canceled.
- A controlled ten-state example where a two-letter window with beam1 misses,
  while exact tail BFS finds a shortest conditional suffix of length3. Its
  resulting whole pair has length4, while the same family has H=3, explicitly
  distinguishing conditional suffix optimality from global pair optimality.

The Family1 CLI adapter suite passed in both Release and Debug. Each run
checked all64 tiny classes, obtained64 valid pair hits with16 automatic seeds,
and independently recomputed31 conditional BFS certificates. Every accepted
pair was replayed on all masks; full metric traces, capped-tail labels and
partial best-of-seeds resume guards were verified.

`validation.json` pins the header, independent test sources and native binaries.
The separate [blind 24-graph benchmark](../family1-finder-blind-benchmark/ASSESSMENT.md)
reports all72 threshold-grid outcomes, including seven misses per setting.
No global shortestness is inferred merely from a conditional BFS flag.
