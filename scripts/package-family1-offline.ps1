param(
    [ValidateSet("Debug", "Release")]
    [string] $Configuration = "Release",
    [string] $BuildDirectory,
    [string] $PackageDirectory
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "family1-offline-inputs.ps1")

function Get-PEImports {
    param([Parameter(Mandatory = $true)] [string] $Path)
    $binary = [IO.File]::ReadAllBytes($Path)
    if ([BitConverter]::ToUInt16($binary, 0) -ne 0x5a4d) { throw "Not a Windows executable: $Path" }
    $pe = [BitConverter]::ToInt32($binary, 0x3c)
    if ([BitConverter]::ToUInt32($binary, $pe) -ne 0x4550) { throw "Invalid PE signature: $Path" }
    if ([BitConverter]::ToUInt16($binary, $pe + 4) -ne 0x8664) { throw "Expected an AMD64 executable: $Path" }
    $count = [BitConverter]::ToUInt16($binary, $pe + 6)
    $optional = $pe + 24
    if ([BitConverter]::ToUInt16($binary, $optional) -ne 0x20b) { throw "Expected a Windows x64 PE executable: $Path" }
    if ([BitConverter]::ToUInt32($binary, $optional + 112 + 13 * 8)) {
        throw "Delay-loaded DLLs are not supported by the standalone package audit: $Path"
    }
    $sectionTable = $optional + [BitConverter]::ToUInt16($binary, $pe + 20)
    $sections = @(for ($index = 0; $index -lt $count; $index++) {
        $entry = $sectionTable + 40 * $index
        [pscustomobject]@{
            Address = [BitConverter]::ToUInt32($binary, $entry + 12)
            Span = [Math]::Max([BitConverter]::ToUInt32($binary, $entry + 8), [BitConverter]::ToUInt32($binary, $entry + 16))
            Offset = [BitConverter]::ToUInt32($binary, $entry + 20)
        }
    })
    function Resolve-PEOffset([uint32] $Address) {
        foreach ($section in $sections) {
            if ($Address -ge $section.Address -and $Address -lt $section.Address + $section.Span) {
                return [int]($Address - $section.Address + $section.Offset)
            }
        }
        throw "PE address is outside all sections: $Address"
    }
    $importAddress = [BitConverter]::ToUInt32($binary, $optional + 120)
    if (-not $importAddress) { return @() }
    $offset = Resolve-PEOffset $importAddress
    $imports = @(while ($true) {
        $nameAddress = [BitConverter]::ToUInt32($binary, $offset + 12)
        if (-not $nameAddress) { break }
        $nameOffset = Resolve-PEOffset $nameAddress
        $end = $nameOffset
        while ($binary[$end] -ne 0) { $end++ }
        [Text.Encoding]::ASCII.GetString($binary, $nameOffset, $end - $nameOffset)
        $offset += 20
    })
    return @($imports | Sort-Object -Unique)
}

if (-not $BuildDirectory) { $BuildDirectory = Join-Path $repoRoot "out\build\family1-offline" }
$BuildDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BuildDirectory)
if (-not $PackageDirectory) {
    $suffix = if ($Configuration -eq "Debug") { "-debug" } else { "" }
    $PackageDirectory = Join-Path $repoRoot "out\releases\family1-offline-windows-x64$suffix"
}
$PackageDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PackageDirectory)
$executable = Join-Path $BuildDirectory "$Configuration\Family1Offline.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw "Build Family1Offline first: $executable" }
$imports = @(Get-PEImports $executable)
$unexpected = @($imports | Where-Object {
    $_ -notmatch '^(KERNEL32|NTDLL|ADVAPI32|USER32|SHELL32|WS2_32|BCRYPT|OLE32|OLEAUT32|GDI32|COMDLG32|VERSION|RPCRT4|SHLWAPI)\.dll$' -and
    $_ -notmatch '^api-ms-win-(core|security|service|eventing)-.+\.dll$'
})
if ($unexpected.Count) { throw "Executable needs additional DLLs; rebuild with static runtime: $($unexpected -join ', ')" }
Write-Host "Verified PE imports (Windows OS only): $($imports -join ', ')"
$archive = "$PackageDirectory.zip"
if (Test-Path -LiteralPath $archive) { throw "Archive already exists; use a fresh package directory: $archive" }
if (Test-Path -LiteralPath $PackageDirectory) {
    if (@(Get-ChildItem -LiteralPath $PackageDirectory -Force).Count -gt 0) {
        throw "Use a fresh package directory; refusing to mix releases: $PackageDirectory"
    }
}
$revision = $null
$sourceDirty = $null
$gitCommand = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($gitCommand) {
    try {
        $candidateRevision = & $gitCommand.Source -C $repoRoot rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            $revision = $candidateRevision
            $statusLines = @(& $gitCommand.Source -C $repoRoot status --porcelain 2>$null)
            if ($LASTEXITCODE -eq 0) { $sourceDirty = $statusLines.Count -gt 0 }
        }
    } catch { $revision = $null; $sourceDirty = $null }
}
$sourcePins = @(Get-Family1OfflineSourcePins -RepositoryRoot $repoRoot)
$receiptPath = Join-Path $BuildDirectory "$Configuration\Family1Offline.build.json"
if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
    throw "No successful helper-build receipt. Run scripts/build-family1-offline.ps1 before packaging."
}
$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
if ($receipt.configuration -ne $Configuration -or $receipt.source_files.Count -ne $sourcePins.Count -or
    $receipt.executable_sha256 -ne (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()) {
    throw "Build receipt does not match executable/configuration. Rebuild before packaging."
}
foreach ($pin in $sourcePins) {
    $saved = @($receipt.source_files | Where-Object { $_.name -ceq $pin.name })
    if ($saved.Count -ne 1 -or $saved[0].sha256 -cne $pin.sha256) {
        throw "Build input changed since compilation: $($pin.name). Rebuild before packaging."
    }
}
New-Item -ItemType Directory -Force -Path $PackageDirectory | Out-Null
Copy-Item -LiteralPath $executable -Destination (Join-Path $PackageDirectory "Family1Offline.exe")
foreach ($manual in @("family1-offline.md", "family1-heuristic-method.md", "family1-graph-edits.md")) {
    $source = Join-Path $repoRoot "docs\$manual"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing release manual: $source" }
    Copy-Item -LiteralPath $source -Destination (Join-Path $PackageDirectory $manual)
}
$readme = @'
Family 1 Offline (Windows x64)

Run Family1Offline.exe directly. No Python, GPU, vcpkg, DLL installation,
repository checkout, or Internet connection is needed to run it.

  .\Family1Offline.exe --help
  .\Family1Offline.exe --m 3 --heuristics off --depth 8 --out exact-m3
  .\Family1Offline.exe --m 8 --heuristics on --out heuristic-m8

Read family1-offline.md for commands, budgets, resume and output schemas.
Read family1-heuristic-method.md for the mathematics and heuristic method.
Exact mode certifies only completed enumeration/scoring. Heuristic estimates
and found word-pair lengths do not establish an absolute maximum.

Copy the executable anywhere writable; manual files are optional at runtime.
Search output is written only to the directory supplied with --out.
This package contains no full search journals or large evidence archives.
'@
[IO.File]::WriteAllText((Join-Path $PackageDirectory "README.txt"), $readme + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
$files = @(Get-ChildItem -LiteralPath $PackageDirectory -File | Sort-Object Name | ForEach-Object {
    [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$manifest = [ordered]@{
    schema = 1
    program = "Family1Offline"
    platform = "windows-x64"
    configuration = $Configuration
    source_revision = $revision
    source_tree_dirty = $sourceDirty
    source_files = $sourcePins
    build_inputs_verified = $true
    build_tests_passed = $receipt.tests_passed
    executable_built_utc = (Get-Item -LiteralPath $executable).LastWriteTimeUtc.ToString("o")
    packaged_utc = [DateTime]::UtcNow.ToString("o")
    static_msvc_runtime = $true
    pe_imports = $imports
    third_party_runtime_dependencies = @()
    runtime_network_required = $false
    files = $files
}
[IO.File]::WriteAllText((Join-Path $PackageDirectory "manifest.json"), ($manifest | ConvertTo-Json -Depth 8) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Compress-Archive -LiteralPath (Join-Path $PackageDirectory "Family1Offline.exe"), (Join-Path $PackageDirectory "README.txt"), (Join-Path $PackageDirectory "family1-offline.md"), (Join-Path $PackageDirectory "family1-heuristic-method.md"), (Join-Path $PackageDirectory "family1-graph-edits.md"), (Join-Path $PackageDirectory "manifest.json") -DestinationPath $archive -CompressionLevel Optimal
Write-Host "Offline package: $PackageDirectory"
Write-Host "Offline ZIP: $archive"
