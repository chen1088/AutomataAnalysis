param(
    [ValidateSet("Debug", "Release")]
    [string] $Configuration = "Release",
    [string] $BuildDirectory,
    [switch] $SkipTests,
    [switch] $Package,
    [string] $PackageDirectory
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "family1-offline-inputs.ps1")

function Get-SourcePins {
    return @(Get-Family1OfflineSourcePins -RepositoryRoot $repoRoot)
}

function Invoke-Native {
    param([Parameter(Mandatory = $true)] [scriptblock] $Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE`: $Command" }
}

function Find-CMake {
    $command = Get-Command cmake.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installations = & $vswhere -products "*" -version "[17.0,18.0)" -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -ne 0) { throw "Could not locate Visual Studio 2022." }
        foreach ($installation in $installations) {
            $bundled = Join-Path $installation "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
            if (Test-Path -LiteralPath $bundled -PathType Leaf) { return $bundled }
        }
    }
    throw "CMake was not found. Install Visual Studio 2022 C++ Build Tools with CMake support."
}

if (-not $BuildDirectory) { $BuildDirectory = Join-Path $repoRoot "out\build\family1-offline" }
$BuildDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BuildDirectory)
$cmakeExe = Find-CMake
Write-Host "Using CMake: $cmakeExe"
Write-Host "Building dependency-free Family1Offline ($Configuration) in $BuildDirectory"
$sourcePins = @(Get-SourcePins)

# Override an inherited toolchain explicitly: this build needs the MSVC STL,
# not vcpkg, and must not trigger a manifest dependency installation.
Invoke-Native { & $cmakeExe -S $repoRoot -B $BuildDirectory -G "Visual Studio 17 2022" -A x64 "-DCMAKE_TOOLCHAIN_FILE=" "-DFAMILY1_OFFLINE_ONLY=ON" "-DBUILD_TESTING=ON" }
if ($SkipTests) {
    Invoke-Native { & $cmakeExe --build $BuildDirectory --config $Configuration --target Family1Offline }
} else {
    Invoke-Native { & $cmakeExe --build $BuildDirectory --config $Configuration }
}
if (-not $SkipTests) {
    $ctestExe = Join-Path (Split-Path -Parent $cmakeExe) "ctest.exe"
    if (-not (Test-Path -LiteralPath $ctestExe -PathType Leaf)) { throw "ctest.exe was not found beside CMake: $ctestExe" }
    Invoke-Native { & $ctestExe --test-dir $BuildDirectory -C $Configuration --output-on-failure }
}
$afterPins = @(Get-SourcePins)
if (($sourcePins | ConvertTo-Json -Compress) -cne ($afterPins | ConvertTo-Json -Compress)) {
    throw "Build inputs changed during compilation/tests. Run the build again before packaging."
}
$builtExecutable = Join-Path $BuildDirectory "$Configuration\Family1Offline.exe"
$receipt = [ordered]@{
    schema = 1
    configuration = $Configuration
    source_files = $sourcePins
    executable_sha256 = (Get-FileHash -LiteralPath $builtExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
    tests_passed = if ($SkipTests) { $null } else { $true }
}
[IO.File]::WriteAllText((Join-Path $BuildDirectory "$Configuration\Family1Offline.build.json"),
    ($receipt | ConvertTo-Json -Depth 6) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
if ($Package) {
    $arguments = @{ Configuration = $Configuration; BuildDirectory = $BuildDirectory }
    if ($PackageDirectory) { $arguments.PackageDirectory = $PackageDirectory }
    & (Join-Path $PSScriptRoot "package-family1-offline.ps1") @arguments
}
Write-Host "Executable: $(Join-Path $BuildDirectory "$Configuration\Family1Offline.exe")"
