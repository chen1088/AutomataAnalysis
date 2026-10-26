# Offline executable validation

The native `Family1Offline.exe` accepts one reachable graph size, an
exact/heuristic switch and explicit search budgets. It uses the static MSVC
runtime and imports only Windows `KERNEL32.dll`; Python, vcpkg packages,
third-party DLLs and a network connection are not runtime requirements.

[validation.json](validation.json) preserves the actual build-input hashes,
release artifact hashes, test outcomes and compact graph-only benchmark
findings. The executable and 331 KB ZIP remain local under ignored
`out/releases/`; they are not source-repository files. The manifest identifies
the base Git revision and the uncommitted build inputs honestly.

- Full project: 36/36 CTests passed in both Release and Debug.
- Dedicated dependency-free project: 2/2 CTests passed in both configurations.
- Independent CLI suite: 34 native invocations; every score and maximizing
  class agrees with an independent scalar enumeration for all 742 classes
  through four states.
- Exact five-state run: all 10,398 scores match the earlier complete journal;
  maximum 15, all five ties retained, 332,736 independent graph/mask replays.
- New seven-state short-budget benchmark: verified lengths
  `35,36,34,38,34,36,34,38` for eight graphs of known exact score 34.
- Eight-state graph-only benchmark: a verified length-50 pair, estimate 49,
  reconstructed in approximately 7.34 seconds, without a saved word hint.
- Extracted ZIP hashes checked; an executable-only copy with `PATH=System32`
  completed exact four-state enumeration and an actual heuristic search.

No physically disconnected second computer was available. Offline portability
was tested by import inspection and isolated executable-only copies. Exact
depth is currently capped at 31; heuristic estimates and misses do not certify
scores or global maxima. Raw run journals and build logs remain in the local
evidence directories listed in the JSON report.

See [the command reference](../../docs/family1-offline.md) and
[heuristic method](../../docs/family1-heuristic-method.md) for reproduction.
