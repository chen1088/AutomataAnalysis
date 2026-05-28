param(
    [ValidateSet("Debug", "Release")]
    [string] $Configuration = "Debug",

    [string] $VcpkgRoot = $env:VCPKG_ROOT
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $VcpkgRoot) {
    $VcpkgRoot = Join-Path $repoRoot ".deps\vcpkg"
}

if (-not (Test-Path $VcpkgRoot)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VcpkgRoot) | Out-Null
    git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot
}

$vcpkgExe = Join-Path $VcpkgRoot "vcpkg.exe"
if (-not (Test-Path $vcpkgExe)) {
    & (Join-Path $VcpkgRoot "bootstrap-vcpkg.bat")
}

$env:VCPKG_ROOT = $VcpkgRoot

Push-Location $repoRoot
try {
    cmake --preset msvc-vcpkg
    cmake --build --preset "msvc-vcpkg-$($Configuration.ToLowerInvariant())"
}
finally {
    Pop-Location
}
