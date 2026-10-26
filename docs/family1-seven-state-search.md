# Seven-state exhaustive search

There are **4,166,855** accessible rooted seven-state classes with two
unordered outgoing ports per vertex. Loops, coincident ports and arbitrary
indegrees are included. Strong connectivity is not imposed.

The seven-state maximum value is **34**, attained by **eight rooted classes**
in **four underlying shapes**. The complete collection is certified in
[the result summary](../results/family1-m7/summary.json) and
[maximizer tables](../results/family1-m7/maximizers.jsonl). The final
[independent upper audit](../results/family1-m7/independent-refined-upper-audit.json)
checks all 4,166,855 classes, all 720 root-fixing permutations per graph, and
all 128 original static masks for every upper witness. Every graph has a
verified witness of length at most 34. A fresh independent
[depth-33 lower check](../results/family1-m7/lower-0001020302030405000604060105.json)
is collision-free for key `0001020302030405000604060105`; its audited
length-34 witness therefore gives exact H=34 and attains the global upper bound.

Fresh depth-33 checks establish H>=34 for **all eight** final frontier classes.
Three other initial frontier classes have verified length-33 collisions; the
second complete upper audit confirms that every omitted graph has H<=33.
Both global certificate flags are true. Native upper-audit reports themselves
leave maximum/tie flags false because they do not check lower proofs; the
completed wrapper combines those audits with the fresh lower computations.

The [structure report](../results/family1-m7-structures/structure.md) groups the
eight rooted classes into four shapes without discarding root choices. See the
[two-page PDF plate](../output/pdf/family1-m7/family1-m7.pdf),
[reusable TikZ ZIP](../output/pdf/family1-m7/family1-m7-tikz.zip), and
[individual picture sources](../figures/family1-m7/README.md). The
[compact proof copy](../results/family1-m7/README.md) records evidence hashes;
the [portable certificate ZIP](../out/family1-m7-certificate.zip) additionally
contains the full journal and independent source-only verification workflow.
Global results through six states are described in
[the extremal-shape report](family1-extremal-shapes.md).

## Independent graph count

[The counting script](../tests/family1_burnside_count.py) imports no production
enumerator. Its [result](../results/family1-burnside-counts.json) gives counts
`1, 6, 57, 678, 10398, 192181, 4166855` for sizes one through seven. It also
directly enumerates every labelled unordered-port table and every root-fixing
permutation through four states, checking each fixed set against the formula.

For a vertex permutation p fixing the root, put f_l = |Fix(p^l)|. On a source
cycle of length l, the successor multiset must be invariant under p^l. It can
contain two fixed vertices, allowing repetition, or the two vertices of a
2-cycle. The number of choices is

\[
q_l(p)=\binom{f_l+1}{2}+\frac{f_{2l}-f_l}{2}.
\]

Consequently the number F(p) of all fixed tables is the product of q_l(p) over
the source cycles of p. The reachable set R is invariant under p and contains
the distinguished root. Let A(p) count accessible fixed tables. Then

\[
A(p)=F(p)-\sum_{\substack{R\subsetneq V,\;0\in R\\p(R)=R}}
 A(p|_R)\prod_{C\text{ a cycle of }p\text{ outside }R}q_{|C|}(p).
\]

Outside rows may target any vertex. The script groups choices of R by cycle
multiplicities, using binomial coefficients to choose nonroot cycles. The root
singleton is always included. Burnside averaging over permutations of the
m-1 nonroot vertices gives the class count. For a nonroot cycle type lambda,
its contribution is A(1 plus lambda)/z_lambda, where
z_lambda = product of l^(a_l) a_l!. All arithmetic is integral or exact rational.

## Witness covers and every maximizing class

[The exhaustive runner](../family1_exhaustive.cpp) visits canonical classes in
deterministic order. A learned witness pair is reusable on another graph only
after its two trajectories agree on **all 128 original static masks**. A pair
of length h establishes H <= h, even when the shortest length is unknown.

To prove an optimum U and collect every tie, complete coverage must establish
H <= U for every class and H >= U for at least one class. Every class omitted
from the maximizing collection needs a **strictly shorter** witness, of length
less than U, or an exact score below U. A witness of length U alone cannot
exclude that class from the tie collection. Each retained maximizer needs
both a lower proof H >= U and a witness of length U. Unresolved classes remain
in `unresolved.jsonl`; an empty or partial `maximizers.jsonl` is not a complete
maximizing collection without the corresponding completion flags.

The runner writes `checkpoint.jsonl`, per-graph exports and `summary.json`.
[The independent journal verifier](../tests/Family1ExhaustiveVerify.cpp) checks
accessibility, complete table/key agreement, strict ordering and every
root-fixing vertex permutation, independently of production canonicalization.
A complete set of distinct canonical classes matching the Burnside count
certifies enumeration coverage. Scalar simulation checks every upper witness.
This verifier leaves nontrivial lower bounds and shortest-length claims
explicitly unchecked.

## Independent lower checks

[The single-layer checker](../tests/Family1LayerVerify.cpp) uses one-hot endpoint
sets for all seven vertices and all 128 masks. A depth-first traversal builds
complete profiles while consulting the same mask bit on every revisit.
Complement symmetry allows storing words beginning with 0: complementing the
word permutes mask coordinates by sigma -> sigma XOR 127. Both orientations
and collisions with a word's own complement are checked.

Hashes organize profiles. Every repeated hash is checked against complete
states, so a hash match is never accepted as a collision by itself. The
ordinary mode replays scalar 128-coordinate vectors; compact mode replays the
complete one-hot profiles. Found witnesses receive a separate scalar check.
Resource exhaustion produces an incomplete result.

Compact mode can generate and sort profiles with eight CPU threads while
sharing a single hash array. The depth-33 array occupies 32 GiB; selecting
eight threads does not allocate eight copies of it.

Checking one layer is enough for a lower bound. If distinct words collide at
length n <= d, appending the same suffix of length d-n preserves equality in
every mask and gives distinct colliding words of length d. Thus injectivity
at length d proves H >= d+1. A collision found at d supplies only H <= d until
a matching lower proof is available.

JSON reports record executions, graph identities, outcomes and resource
limits. They are execution provenance, not standalone proof traces. Imported
lower reports require independent replay of the stated computation before
their lower bounds or resulting exact scores can be independently confirmed.

## Reproduction

Build the current native targets using the existing MSVC/vcpkg configuration:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-windows-vcpkg.ps1 -Configuration Release
uv run --no-project python tests\family1_burnside_count.py --max-m 7 --out out\family1-burnside-reproduce.json
```

The following freshly checks the attained lower bound, using a new report:

```powershell
.\out\build\msvc-vcpkg\Release\Family1LayerVerify.exe --key 0001020302030405000604060105 --depth 33 --compact --threads 8 --max-working-mib 40000 --timeout-ms 1200000 --out out\family1-m7-reproduce-layer33.json
```

### Start from a fresh search

The following bootstrap needs no earlier `out/` search artifacts. It uses the
small checked-in one-through-six-state maximizer file as a source of candidate
word pairs. Each pair must be verified again on each seven-state graph's own
128 masks; seed sizes are not combined into one product.

```powershell
.\out\build\msvc-vcpkg\Release\Family1Exhaustive.exe --states 7 --target 34 --depth 16 --jobs 8 --batch-size 4096 --max-layer-states 65536 --max-working-mib 32 --timeout-ms 10000 --seed results\family1-m1-m6\maximizers.jsonl --out out\family1-m7-bootstrap
```

The target controls the search; setting it is not a proof. Repeat the same
command with `--resume` to continue its checkpoint. Keep every unresolved
record. Once the bootstrap has completed enumeration, use the optional
[GPU environment and witness workflow](family1-gpu-witness-search.md) to
complete its upper cover, then apply the positive proposals and run the CPU
certificate. Here `$gpuPython` is the isolated interpreter from that setup:

```powershell
& $gpuPython scripts\family1_gpu_cached.py --journal out\family1-m7-bootstrap\checkpoint.jsonl --out out\family1-m7-bootstrap-gpu --depths 24,28,30,31,32,33,34 --threshold 34 --window-bits 29 --max-window-blocks 0
uv run --no-project python scripts\family1_apply_upper_witnesses.py --journal out\family1-m7-bootstrap\checkpoint.jsonl --witnesses out\family1-m7-bootstrap-gpu\upper-witnesses.jsonl --out out\family1-m7-bootstrap-upper
uv run --no-project python scripts\family1_verify_global_certificate.py --journal out\family1-m7-bootstrap-upper\checkpoint.jsonl --out out\family1-m7-bootstrap-certificate --jobs 1 --max-total-working-mib 40000 --lower-threads 8 --lower-timeout-ms 1200000 --refine-frontier
```

These commands use new output directories. GPU misses remain unresolved; the
certificate fails closed if the resulting journal lacks complete upper
coverage or a required lower computation is incomplete. Further native passes
may also refine a previous journal with `--input PRIOR_CHECKPOINT` and a new
output directory. For example:

```powershell
.\out\build\msvc-vcpkg\Release\Family1Exhaustive.exe --states 7 --target 34 --backend layer --layer-storage packed --layer-step 2 --depth 24 --max-layer-states 16777216 --max-working-mib 1024 --timeout-ms 60000 --jobs 24 --input PRIOR_RUN\checkpoint.jsonl --seed PRIOR_RUN\learned-witnesses.jsonl --out NEW_REFINEMENT_DIRECTORY
```

This backend checks selected layers, comparing complete 128-mask states on
fingerprint matches. A collision supplies an upper bound; a collision-free
layer supplies a lower bound. It reports an exact score only when both match.

### Audit the completed upper cover

The frozen production input is
`out/family1-m7-gpu-seeded-base/checkpoint.jsonl`. The cached GPU run used
depths 24,28,30,31,32,33,34 and threshold 34, and its independently applied
upper cover is `out/family1-m7-complete-upper-v3/checkpoint.jsonl`.
Audit this full journal again with:

```powershell
.\out\build\msvc-vcpkg\Release\Family1ExhaustiveVerify.exe --states 7 --journal out\family1-m7-complete-upper-v3\checkpoint.jsonl --expected-count 4166855 --out out\family1-m7-reproduce-upper-audit.json
```

Omit `--expected-count` to audit a valid interrupted prefix. The verifier still
requires the full Burnside count before reporting complete coverage. Neither
an interrupted sweep nor a successful upper-witness audit alone establishes
the absolute optimum and every maximizing graph.

For a completed upper cover, the following command independently checks the
whole certificate and executes a fresh lower check for **every** class at the
largest verified upper bound. It uses the verified upper frontier rather than
the producer's maximizing-graph list. With `--refine-frontier`, a newly found
shorter collision is checked on all 128 masks and saved in a new refined
journal. A second whole-journal audit must confirm that only the freshly
lower-proved classes remain on the largest upper frontier before the complete
maximizing collection is exported:

```powershell
uv run --no-project python scripts\family1_verify_global_certificate.py --journal out\family1-m7-complete-upper-v3\checkpoint.jsonl --out NEW_CERTIFICATE_DIRECTORY --jobs 1 --max-total-working-mib 40000 --lower-threads 8 --lower-timeout-ms 1200000 --refine-frontier
```

The output directory must be new or empty. A partial journal or a frontier
graph whose matching lower bound cannot be established produces an explicit
incomplete result. If every original frontier graph receives a shorter upper,
the refined journal is retained for another invocation at the smaller frontier;
the command does not claim a completed certificate. The original journal is
preserved. Sources, executables and input files are hash-pinned before and
after execution. The command is limited to seven states and independent lower
depths through 33; its memory budget is configurable.

The completed production certificate is
`out/family1-m7-global-certificate-v3`. It refined three upper bounds to 33 and
certified all eight remaining classes at 34. Its compact files are preserved
under `results/family1-m7`; the certified full journal has SHA256
`9d6de41b2f99dd220bd9d086d6910e5d466c16e23328f22f57520654c47e3d70`.
The source-only certificate ZIP is `out/family1-m7-certificate.zip`, SHA256
`6fe3dabe21a7175fe1bc07377df81eaea5df80d0d31a6e5f002037e7c60d1588`.
Its archived README gives standalone MSVC build and fresh CPU replay commands.
Package another completed run with a new ZIP path; unfinished certificates
are refused:

```powershell
uv run --no-project python scripts\family1_package_certificate.py --input CERTIFICATE_DIRECTORY --out NEW.zip
```

Export a successfully certified collection as paper-ready TikZ, then compile
the plate and every standalone graph:

```powershell
uv run --no-project python scripts\family1_certified_tikz.py --input results\family1-m7 --states 7 --out out\family1-m7-reproduce-figures --port-labels none
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-family1-certified.ps1 -SourceDirectory out\family1-m7-reproduce-figures -BuildDirectory out\family1-m7-reproduce-latex -OutputDirectory out\family1-m7-reproduce-pdf
```

The exporter requires a new or empty destination and refuses an uncertified
or incomplete tie collection. Reusable pictures are under `snippets/`; the
completed production PDFs and source ZIP are under `output/pdf/family1-m7/`.
The commands above use separate directories to preserve those drawings.
Existing five-state figures and the earlier atlas are preserved.
