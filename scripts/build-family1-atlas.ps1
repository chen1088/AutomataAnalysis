param([switch] $Individual, [switch] $LegacyRooted)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDirectory = Join-Path $repoRoot $(if ($LegacyRooted) { 'figures\family1-atlas' } else { 'figures\family1-grouped-atlas' })
$buildDirectory = Join-Path $repoRoot $(if ($LegacyRooted) { 'out\family1-atlas-tikz' } else { 'out\family1-atlas-grouped-tikz' })
$outputDirectory = Join-Path $repoRoot 'output\pdf\family1-atlas'
New-Item -ItemType Directory -Force -Path $buildDirectory, $outputDirectory | Out-Null
$compiler = (Get-Command pdflatex.exe -CommandType Application -ErrorAction Stop).Source
Push-Location $sourceDirectory
try {
    & $compiler '-interaction=nonstopmode' '-halt-on-error' '-file-line-error' "-output-directory=$buildDirectory" 'atlas.tex' > (Join-Path $buildDirectory 'atlas.build.log') 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Atlas compilation failed; see $buildDirectory" }
    Copy-Item -LiteralPath (Join-Path $buildDirectory 'atlas.pdf') -Destination (Join-Path $outputDirectory 'family1-atlas-1-20.pdf')
}
finally { Pop-Location }
if ($Individual) {
    $individualDirectory = Join-Path $outputDirectory $(if ($LegacyRooted) { 'individual' } else { 'grouped-individual' })
    New-Item -ItemType Directory -Force -Path $individualDirectory | Out-Null
    Push-Location (Join-Path $sourceDirectory 'standalone')
    try {
        foreach ($source in Get-ChildItem -File -Filter '*.tex') {
            & $compiler '-interaction=nonstopmode' '-halt-on-error' '-file-line-error' "-output-directory=$buildDirectory" $source.Name > (Join-Path $buildDirectory ($source.Name + '.build.log')) 2>&1
            if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $($source.Name)" }
            Copy-Item -LiteralPath (Join-Path $buildDirectory ($source.BaseName + '.pdf')) -Destination $individualDirectory
        }
    }
    finally { Pop-Location }
}
Write-Output "Compiled graph atlas: $outputDirectory"
