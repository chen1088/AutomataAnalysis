param(
    [ValidateSet("Debug", "Release")]
    [string] $Configuration = "Debug",

    [string] $VcpkgRoot
)

$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock] $Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Command"
    }
}

function Find-CMake {
    $cmakeCommand = Get-Command cmake.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmakeCommand) {
        return $cmakeCommand.Source
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installations = & $vswhere -products "*" -version "[17.0,18.0)" -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -ne 0) {
            throw "Could not locate Visual Studio 2022 with vswhere."
        }
        foreach ($installation in $installations) {
            $bundledCmake = Join-Path $installation "Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
            if (Test-Path -LiteralPath $bundledCmake -PathType Leaf) {
                return $bundledCmake
            }
        }
    }

    throw "CMake was not found. Install CMake 3.28 or newer, or add C++ CMake tools for Windows to Visual Studio 2022 Build Tools."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$cmakeExe = Find-CMake
$cmakeVersionOutput = @(& $cmakeExe --version)
if ($LASTEXITCODE -ne 0 -or $cmakeVersionOutput[0] -notmatch '^cmake version (\d+\.\d+\.\d+)') {
    throw "Could not determine the CMake version: $cmakeExe"
}
if ([version] $Matches[1] -lt [version] "3.28.0") {
    throw "CMake 3.28 or newer is required by CMakePresets.json. Found $($Matches[1]) at $cmakeExe."
}
Write-Host "Using CMake: $cmakeExe"

$usingExplicitVcpkgRoot = $PSBoundParameters.ContainsKey("VcpkgRoot")

if (-not $usingExplicitVcpkgRoot) {
    $VcpkgRoot = $env:VCPKG_ROOT
}

$vsBundledVcpkg = $VcpkgRoot -and ($VcpkgRoot -match "\\Microsoft Visual Studio\\.*\\VC\\vcpkg$")
if (-not $VcpkgRoot -or ((-not $usingExplicitVcpkgRoot) -and $vsBundledVcpkg)) {
    $VcpkgRoot = Join-Path $repoRoot ".deps\vcpkg"
}
$VcpkgRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($VcpkgRoot)

if (-not (Test-Path -LiteralPath $VcpkgRoot)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VcpkgRoot) | Out-Null
    Invoke-Native { git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot }
}

$vcpkgExe = Join-Path $VcpkgRoot "vcpkg.exe"
if (-not (Test-Path -LiteralPath $vcpkgExe -PathType Leaf)) {
    $bootstrapScript = Join-Path $VcpkgRoot "bootstrap-vcpkg.bat"
    if (-not (Test-Path -LiteralPath $bootstrapScript -PathType Leaf)) {
        throw "The vcpkg directory is incomplete: $VcpkgRoot. Expected bootstrap-vcpkg.bat."
    }
    Invoke-Native { & $bootstrapScript }
}

$env:VCPKG_ROOT = $VcpkgRoot
Write-Host "Using vcpkg: $VcpkgRoot"

Push-Location $repoRoot
try {
    Invoke-Native { & $cmakeExe --preset msvc-vcpkg }
    Invoke-Native { & $cmakeExe --build --preset "msvc-vcpkg-$($Configuration.ToLowerInvariant())" }
}
finally {
    Pop-Location
}
