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

$repoRoot = Split-Path -Parent $PSScriptRoot
$usingExplicitVcpkgRoot = $PSBoundParameters.ContainsKey("VcpkgRoot")

if (-not $usingExplicitVcpkgRoot) {
    $VcpkgRoot = $env:VCPKG_ROOT
}

$vsBundledVcpkg = $VcpkgRoot -and ($VcpkgRoot -match "\\Microsoft Visual Studio\\.*\\VC\\vcpkg$")
if (-not $VcpkgRoot -or ((-not $usingExplicitVcpkgRoot) -and $vsBundledVcpkg)) {
    $VcpkgRoot = Join-Path $repoRoot ".deps\vcpkg"
}

if (-not (Test-Path $VcpkgRoot)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VcpkgRoot) | Out-Null
    Invoke-Native { git clone https://github.com/microsoft/vcpkg.git $VcpkgRoot }
}

$vcpkgExe = Join-Path $VcpkgRoot "vcpkg.exe"
if (-not (Test-Path $vcpkgExe)) {
    Invoke-Native { & (Join-Path $VcpkgRoot "bootstrap-vcpkg.bat") }
}

$env:VCPKG_ROOT = $VcpkgRoot

Push-Location $repoRoot
try {
    Invoke-Native { cmake --preset msvc-vcpkg }
    Invoke-Native { cmake --build --preset "msvc-vcpkg-$($Configuration.ToLowerInvariant())" }
}
finally {
    Pop-Location
}
