# Controlled larger-lookahead sweep

All64 runs use the same new native version and all eight certified seven-state maximizers: k=2,4,6,8,10,12,14,16; beam4; exact-tail threshold8;128 automatic seeds; fixed pair-length cap76; and a1,000,000-node expansion budget per prefix. Prefix preprocessing remains at the previous128-pair/65,536-word settings. No saved witness or witness-derived prefix is supplied.

**Only ordinal2470130 reaches the independently known H=34.** It does so at k4,6,8,10,14,16; k12 instead returns35. Its minimum successful k in this tested grid is4. The other seven graphs do not reach34 even at k16 under this fixed budget.

| Ordinal | k2 | k4 | k6 | k8 | k10 | k12 | k14 | k16 | Minimum matched k |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 539749 | 38 | 37 | 35 | 37 | 35 | 36 | 36 | 35 | none |
| 679758 | 38 | 37 | 37 | 36 | 37 | 36 | 36 | 36 | none |
| 1783759 | 37 | 37 | 38 | 38 | 36 | 35 | 37 | 36 | none |
| 2221624 | 41 | 39 | 39 | 39 | 39 | 39 | 38 | 39 | none |
| 2470130 | 36 | 34 | 34 | 34 | 34 | 35 | 34 | 34 | 4 |
| 2471796 | 36 | 36 | 37 | 36 | 37 | 36 | 36 | 36 | none |
| 3411148 | 38 | 39 | 39 | 38 | 39 | 38 | 38 | 38 | none |
| 4099217 | 39 | 40 | 39 | 40 | 39 | 38 | 39 | 39 | none |

Entries are total pair lengths, not suffix lengths; H=34 in every row. The best lengths over this whole tested grid are35,36,35,38,34,36,38,38. Larger k is not monotone for the bounded first-hit/window/beam procedure.

All64 returned pairs were independently replayed with every one of the128 static masks. Runs.csv gives gaps, ratios, runtime, expanded nodes, expansion-cap counts, tail calls/states and selected/last tail cap status; runs.jsonl retains full module and prefix metadata. The total recorded expansion-limit events were0. A cap or a missed optimum is not a proof that a shorter suffix or pair does not exist.

The k16 native times ranged from4.053 to7.387 seconds per graph. These are observed concurrent-run timings, not an isolated hardware speed benchmark.

The binary/DLL snapshot and binding.json pin this version independently of later project builds. The first k1?6 grid and every earlier quality report remain unchanged. A separate fixed-target length34 experiment is required to study recovery under a tighter total-length constraint.
