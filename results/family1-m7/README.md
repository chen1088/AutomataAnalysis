# Certified seven-state maximum

The absolute Family 1 maximum on exactly seven accessible states is **34**.
The complete collection contains **eight rooted isomorphism classes**, grouped
into **four underlying shapes** when the root may move. Root-preserving vertex
relabeling and independent outgoing-port swaps define the rooted classes.
Loops, coincident ports and arbitrary indegrees were allowed; strong
connectivity was not required. Every seed was scored separately over all
128 static XOR masks.

[summary.json](summary.json) certifies both the value and the complete tie
collection. [maximizers.jsonl](maximizers.jsonl) contains every canonical table
and its length-34 witness. The independent Burnside count and final native
audit cover all **4,166,855** classes, checking all 720 root-fixing permutations
per graph and all 128 original masks per upper witness. Fresh depth-33 checks
are collision-free for all eight winners. Three other initial upper-frontier
graphs received verified length-33 collisions; a second whole-journal audit
confirms every omitted class has an upper witness of length at most 33.

This directory preserves **32 small certificate files byte for byte** from
`out/family1-m7-global-certificate-v3`. Their relative evidence references still
resolve here. [copy-provenance.json](copy-provenance.json) records each copied
file's SHA256. Absolute paths inside the unchanged reports describe the
original execution; they are not required extraction locations. JSON lower
reports record completed executions; replay must actually rerun the checks.

The 1,207,340,983-byte full journal is kept outside this compact result copy.
It is included once as `data/checkpoint.jsonl` in the portable, source-only
[certificate ZIP](../../out/family1-m7-certificate.zip), together with these
reports, the four exact independent verification sources and standalone
Windows/MSVC replay instructions. Large artifacts remain in ignored `out/`;
distribute this ZIP separately with the paper.

| Artifact | SHA256 |
| --- | --- |
| Certified full journal | `9d6de41b2f99dd220bd9d086d6910e5d466c16e23328f22f57520654c47e3d70` |
| Certificate ZIP (87,086,445 bytes) | `6fe3dabe21a7175fe1bc07377df81eaea5df80d0d31a6e5f002037e7c60d1588` |

To repeat the complete proof in this checkout, build the native targets and
use a new certificate output directory:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File scripts\build-windows-vcpkg.ps1 -Configuration Release
uv run --no-project python scripts\family1_verify_global_certificate.py --journal out\family1-m7-global-certificate-v3\refined-checkpoint.jsonl --out out\family1-m7-independent-replay --jobs 1 --max-total-working-mib 40000 --lower-threads 8 --lower-timeout-ms 1200000 --refine-frontier
```

On another PC, extract the certificate ZIP and follow its root `README.md`:
the explicit input is `data/checkpoint.jsonl`, and the archived independent
C++ sources compile directly with MSVC, without the search project, vcpkg or
GPU. At depth 33 the eight threads share one 32 GiB hash array.

The [structure report](../family1-m7-structures/structure.md) preserves the
eight rooted classes and their four shape groups. The
[two-page drawing plate](../../output/pdf/family1-m7/family1-m7.pdf),
[reusable TikZ ZIP](../../output/pdf/family1-m7/family1-m7-tikz.zip), and
[individual picture sources](../../figures/family1-m7/README.md) contain all
eight classes. Graphs sharing a shape keep distinct root markings.

For a search starting without earlier `out/` datasets, see the
[bootstrap and full workflow](../../docs/family1-seven-state-search.md#start-from-a-fresh-search).
