param()
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDirectory = Join-Path $repoRoot 'figures\family1-m5'
$buildDirectory = Join-Path $repoRoot 'out\family1-m5-tikz'
$outputDirectory = Join-Path $repoRoot 'output\pdf\family1-m5'
New-Item -ItemType Directory -Force -Path $buildDirectory, $outputDirectory | Out-Null
$compiler = (Get-Command pdflatex.exe -CommandType Application -ErrorAction Stop).Source
$inputs = @('family1-m5.tex') + @(1..5 | ForEach-Object { 'graph-{0:D2}-standalone.tex' -f $_ })
Push-Location $sourceDirectory
try {
    foreach ($source in $inputs) {
        & $compiler '-interaction=nonstopmode' '-halt-on-error' '-file-line-error' "-output-directory=$buildDirectory" $source > (Join-Path $buildDirectory ($source + '.build.log')) 2>&1
        if ($LASTEXITCODE -ne 0) { throw "LaTeX failed for $source; see $buildDirectory" }
        $pdfName = [IO.Path]::ChangeExtension($source, '.pdf')
        Copy-Item -LiteralPath (Join-Path $buildDirectory $pdfName) -Destination (Join-Path $outputDirectory $pdfName)
    }
}
finally { Pop-Location }
Write-Output "Compiled plate and five separate graph PDFs: $outputDirectory"
