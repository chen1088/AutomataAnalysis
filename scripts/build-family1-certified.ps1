param(
    [string] $SourceDirectory,
    [string] $BuildDirectory,
    [string] $OutputDirectory,
    [switch] $SkipZip
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SourceDirectory) { $SourceDirectory = Join-Path $repoRoot 'figures\family1-m7' }
if (-not (Test-Path -LiteralPath $SourceDirectory -PathType Container)) {
    throw "Certified TikZ source directory does not exist: $SourceDirectory"
}
$sourceRoot = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $SourceDirectory).ProviderPath).TrimEnd([char[]]'\/')
$sourcePrefix = $sourceRoot + [IO.Path]::DirectorySeparatorChar

function Test-PositiveInteger {
    param($Value)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -gt 0)
}

function Resolve-SourceFile {
    param([Parameter(Mandatory = $true)] [string] $RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath)) {
        throw "Manifest input must be a relative source file: $RelativePath"
    }
    $resolved = [IO.Path]::GetFullPath((Join-Path $sourceRoot $RelativePath))
    if (-not $resolved.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest input escapes SourceDirectory: $RelativePath"
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "Manifest source file is missing: $RelativePath"
    }
    # A relative path through an internal junction or symlink could otherwise
    # escape the source boundary despite passing the lexical prefix check.
    $component = $resolved
    while ($component.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        $item = Get-Item -LiteralPath $component -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Manifest input traverses a reparse point: $RelativePath"
        }
        $component = Split-Path -Parent $component
    }
    return $resolved
}

$manifestPath = Resolve-SourceFile 'source-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.maximum_value_certified -isnot [bool] -or -not $manifest.maximum_value_certified -or
    $manifest.maximizing_collection_complete -isnot [bool] -or -not $manifest.maximizing_collection_complete) {
    throw 'The source manifest must explicitly certify both the global maximum and the complete maximizing collection.'
}
if (-not (Test-PositiveInteger $manifest.m) -or $manifest.m -gt 20 -or
    -not (Test-PositiveInteger $manifest.maximum_merge_length) -or
    -not (Test-PositiveInteger $manifest.rooted_class_count)) {
    throw 'The source manifest has invalid state, maximum, or rooted-class counts.'
}
$states = [int] $manifest.m
$drawings = @($manifest.drawings)
if ($null -eq $manifest.drawings -or $drawings.Count -ne $manifest.rooted_class_count) {
    throw 'The manifest drawing count differs from the complete maximizing rooted-class count.'
}
if ($manifest.file_sha256 -isnot [pscustomobject]) {
    throw 'The source manifest must contain file_sha256 digests.'
}

# Check every recorded source digest before any compilation or artifact writes.
$verifiedInputs = @{}
$archiveRelative = [Collections.Generic.List[string]]::new()
foreach ($property in $manifest.file_sha256.PSObject.Properties) {
    $relative = $property.Name
    $file = Resolve-SourceFile $relative
    $expectedHash = [string] $property.Value
    if ($expectedHash -notmatch '^[0-9a-fA-F]{64}$' -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $expectedHash) {
        throw "Source digest mismatch: $relative"
    }
    if ($verifiedInputs.ContainsKey($file)) { throw "Duplicate manifest source path: $relative" }
    $verifiedInputs[$file] = $relative
    $archiveRelative.Add($relative)
}
$archiveRelative.Add('source-manifest.json')

function Resolve-VerifiedSource {
    param([Parameter(Mandatory = $true)] [string] $RelativePath)
    $file = Resolve-SourceFile $RelativePath
    if (-not $verifiedInputs.ContainsKey($file)) {
        throw "Compiled or packaged source lacks a manifest digest: $RelativePath"
    }
    return $file
}

$plateSource = Resolve-VerifiedSource 'plate.tex'
$null = Resolve-VerifiedSource 'README.md'
$null = Resolve-VerifiedSource 'certified-summary.json'
$null = Resolve-VerifiedSource 'maximizers.jsonl'
$seenKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$seenJobs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$jobs = [Collections.Generic.List[object]]::new()
$jobs.Add([pscustomobject]@{ Source = $plateSource; Kind = 'plate'; PdfName = "family1-m$states.pdf" })
foreach ($drawing in $drawings) {
    if ($drawing.m -ne $states -or $drawing.status -ne 'exact' -or
        $drawing.merge_length -ne $manifest.maximum_merge_length -or
        $drawing.maximum_value_certified -isnot [bool] -or -not $drawing.maximum_value_certified -or
        $drawing.maximizing_collection_complete -isnot [bool] -or -not $drawing.maximizing_collection_complete) {
        throw 'Every drawing must be an exact member of the certified complete maximizing collection.'
    }
    if ([string]::IsNullOrWhiteSpace($drawing.key) -or -not $seenKeys.Add([string] $drawing.key)) {
        throw 'Drawing keys must identify distinct rooted classes.'
    }
    $snippet = Resolve-VerifiedSource ([string] $drawing.snippet)
    $standalone = Resolve-VerifiedSource ([string] $drawing.standalone)
    if ([IO.Path]::GetExtension($snippet) -ne '.tex' -or [IO.Path]::GetExtension($standalone) -ne '.tex') {
        throw 'Snippet and standalone inputs must be TeX files.'
    }
    $jobName = [IO.Path]::GetFileNameWithoutExtension($standalone)
    if (-not $seenJobs.Add($jobName)) { throw "Standalone PDF job names collide: $jobName" }
    $jobs.Add([pscustomobject]@{ Source = $standalone; Kind = 'individual'; PdfName = "$jobName.pdf" })
}

if (-not $BuildDirectory) { $BuildDirectory = Join-Path $repoRoot "out\family1-m$states-tikz" }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot "output\pdf\family1-m$states" }
$buildRoot = [IO.Path]::GetFullPath($BuildDirectory)
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
foreach ($destination in @($buildRoot, $outputRoot)) {
    if ($destination.Equals($sourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $destination.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'BuildDirectory and OutputDirectory must be outside the authored SourceDirectory.'
    }
}
$compiler = (Get-Command pdflatex.exe -CommandType Application -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path $buildRoot, $outputRoot | Out-Null
$compiled = [Collections.Generic.List[object]]::new()
foreach ($job in $jobs) {
    $sourceFile = [string] $job.Source
    $sourceCwd = Split-Path -Parent $sourceFile
    $sourceName = Split-Path -Leaf $sourceFile
    $jobName = [IO.Path]::GetFileNameWithoutExtension($sourceFile)
    $jobBuild = Join-Path $buildRoot ([string] $job.Kind)
    New-Item -ItemType Directory -Force -Path $jobBuild | Out-Null
    $logPath = Join-Path $jobBuild "$jobName.build.log"
    Push-Location -LiteralPath $sourceCwd
    try {
        & $compiler '-interaction=nonstopmode' '-halt-on-error' '-file-line-error' "-output-directory=$jobBuild" $sourceName > $logPath 2>&1
        if ($LASTEXITCODE -ne 0) { throw "LaTeX failed for $sourceName; inspect $logPath" }
    }
    finally { Pop-Location }
    $compiledPdf = Join-Path $jobBuild "$jobName.pdf"
    if (-not (Test-Path -LiteralPath $compiledPdf -PathType Leaf) -or
        (Get-Item -LiteralPath $compiledPdf).Length -eq 0) {
        throw "LaTeX produced no nonempty PDF for $sourceName; inspect $logPath"
    }
    $publishedPdf = Join-Path $outputRoot ([string] $job.PdfName)
    Copy-Item -LiteralPath $compiledPdf -Destination $publishedPdf -Force
    $compiled.Add([pscustomobject]@{
        source = $sourceFile
        kind = [string] $job.Kind
        pdf = $publishedPdf
        pdf_sha256 = (Get-FileHash -LiteralPath $publishedPdf -Algorithm SHA256).Hash.ToLowerInvariant()
        log = $logPath
        native_exit_code = 0
    })
}

$zipPath = $null
if (-not $SkipZip) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zipPath = Join-Path $outputRoot "family1-m$states-tikz.zip"
    $stream = [IO.File]::Open($zipPath, [IO.FileMode]::Create, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $archive = $null
    try {
        $archive = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
        foreach ($relative in $archiveRelative) {
            $file = Resolve-SourceFile $relative
            $entryName = $relative.Replace('\', '/')
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file, $entryName, [IO.Compression.CompressionLevel]::Optimal)
        }
    }
    finally {
        if ($null -ne $archive) { $archive.Dispose() } else { $stream.Dispose() }
    }
}

$report = [ordered]@{
    m = $states
    maximum_merge_length = $manifest.maximum_merge_length
    rooted_class_count = $drawings.Count
    maximum_value_certified = $true
    maximizing_collection_complete = $true
    certification_inherited_from_source_manifest = $true
    source_manifest = $manifestPath
    source_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    source_digests_verified = $true
    compiler = $compiler
    compilation_passed = $true
    pdf_visual_inspection_passed = $false
    outputs = @($compiled.ToArray())
    tikz_zip = $zipPath
    completed_utc = [DateTime]::UtcNow.ToString('o')
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot 'build-report.json') -Encoding UTF8
Write-Output "Compiled the complete certified m=$states plate and $($drawings.Count) individual PDFs: $outputRoot"
if ($zipPath) { Write-Output "Reusable TikZ source archive: $zipPath" }
Write-Output 'PDF visual inspection remains a separate step.'
