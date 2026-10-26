param([string] $Out = 'out/family1-m8-publication-rerun')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
Push-Location $repoRoot
try {
    $publishArgs = @(
        'run', '--no-project', 'python', 'scripts/family1_publish_m8_search.py',
        '--records', 'out/family1-m8-search-v1/root-lift8.jsonl',
        '--records', 'out/family1-m8-search-v1/cheap-r1/records.jsonl',
        '--records', 'out/family1-m8-search-v1/cheap-upper-r1/records.jsonl',
        '--records', 'results/family1-m8-upper-refinement/records.jsonl',
        '--records', 'out/family1-m8-search-v1/root-lift8-scored/records.jsonl',
        '--records', 'results/family1-m8-fresh-prefix-refinement/records.jsonl',
        '--records', 'out/family1-m8-r2-search/records.jsonl',
        '--observations', 'out/family1-m8-search-v1/cheap-r1/observations.jsonl',
        '--observations', 'out/family1-m8-search-v1/cheap-upper-r1/cap-96/observations.jsonl',
        '--observations', 'out/family1-m8-search-v1/cheap-upper-r1/cap-48/observations.jsonl',
        '--observations', 'out/family1-m8-search-v1/cheap-upper-r1/cap-40/observations.jsonl',
        '--observations', 'out/family1-m8-upper-refinement/observations.jsonl',
        '--observations', 'out/family1-m8-bestof-refinement/records.jsonl',
        '--observations', 'out/family1-m8-warmstart-refinement/observations.jsonl',
        '--observations', 'out/family1-m8-search-v1/root-lift8-scored/observations.jsonl',
        '--observations', 'out/family1-m8-fresh-prefix-refinement/observations.jsonl',
        '--observations', 'out/family1-m8-r2-search/observations.jsonl',
        '--extra-generation', 'out/family1-m8-r2-search/generated',
        '--lower-report', 'out/family1-m8-lower34-root-lift/report.json',
        '--lower-manifest', 'out/family1-m8-lower34-root-lift/certificate-run.json',
        '--out', $Out
    )
    & uv @publishArgs
    if ($LASTEXITCODE -ne 0) { throw 'Publication audit failed.' }
}
finally { Pop-Location }
