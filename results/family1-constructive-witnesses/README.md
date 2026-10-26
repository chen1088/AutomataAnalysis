# Constructive universal collisions at twenty states

Both runs enumerated all **1,048,576 static masks** and independently verified
both compressed-word endpoints under every mask. No binary strings were
materialized. These are constructed collision upper bounds, not shortest-word
or global-optimum claims.

| Seed | A | B | P | Constructed equal length | Native elapsed |
|---|---:|---:|---:|---:|---:|
| Literal circulant: tau0(i)=i+1, tau1(i)=i+6 mod20 | 15 | 15 | 60 | 91 | 0.0764 s |
| Atlas root-loop projection extension | 18 | 18 | 232792560 | 232792597 | 0.0610 s |

The literal circulant pair is

`u = 0^75 1 0^15`, `v = 0^15 1 0^75`.

The projection extension pair is

`u = 0^232792578 1 0^18`, `v = 0^18 1 0^232792578`.

Each pair has equal length and different positions of its unique 1. All
revisits use the original fixed mask bit. The projection seed already has the
separate certified lower bound H>=34; combining certificates gives
`34 <= H <= 232792597`. The literal seed's currently inherited lower bound is
2, so this construction gives `2 <= H <= 91`. No quadratic lower bound is
imported from a different formula or a product over different seed sizes.

## Construction and verification

For each static mask, let f be the zero-letter transition. A is the maximum
root-orbit tail length. After f^A and one input1, let B be the maximum new
zero-orbit tail length. P is a common multiple of every prefix/suffix cycle
length. Then

`u = 0^(A+P) 1 0^B`, `v = 0^A 1 0^(B+P)`

have the same endpoint for every mask: their states agree before the 1, and
periodicity makes their final states agree. Accessibility implies that the
prefix root-orbit cycle lengths already include every directed cycle length;
the constructor asserts the suffix inclusion and P=prefix_period.

The native constructor uses Gray-code mask traversal and Floyd cycle detection.
Verification instead uses ordinary binary-order masks and a separate scalar
visited-state/modular-power implementation. It compares actual endpoints and
uses no hashes for state equality. SHA-256 protects artifact provenance only.
The generic graph-independent choice A=B=m-1, P=lcm(1,...,m) is also recorded.
Its length at m=20 is 232792599; this generic construction is not a polynomial
upper-bound theorem.

## Files and reproduction

`literal-m20.json` and `projection-m20.json` retain the original native results,
canonical transition tables, RLE words, cycle histograms, and complete-mask
verification metadata. Their matching `*-run.json` files pin native settings.
`manifest.json` pins input datasets, native executable/source hashes, timings,
and the separate lower/upper certificates. The original guarded run folders are
under `out/family1-constructive-witnesses-m20/`.

`validation.json` records unchanged-artifact resume checks for both full-size
runs and a separate Python binary-lifting cross-check on 256 specified masks
per graph. This Python check is additional; the native verifier checked every
one of the 1,048,576 masks.

```powershell
$literalKey = (Get-Content results/family1-constructive-witnesses/literal-m20.json -Raw | ConvertFrom-Json).key
.\out\build\msvc-vcpkg\Release\Family1Construct.exe --graph $literalKey --out out/family1-construct-literal-m20-new
$projectionKey = (Get-Content results/family1-constructive-witnesses/projection-m20.json -Raw | ConvertFrom-Json).key
.\out\build\msvc-vcpkg\Release\Family1Construct.exe --graph $projectionKey --out out/family1-construct-projection-m20-new
```

The default materialization limit is zero. Add `--materialize-limit 100` to a
new literal-circulant run to emit its two 91-bit words explicitly. Resume an
existing run with identical settings and `--resume`.

The independent tiny-case tests and reproducible Python/native timing comparison
are recorded separately in `results/family1-native-witness-validation/`.
The proof and scope are explained in `docs/family1-constructive-witnesses.md`.
