param(
    [ValidateSet('Release', 'Debug')]
    [string] $Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'
$agreementRepo = Split-Path -Parent $PSScriptRoot
$agreementBuild = Join-Path $agreementRepo "out\family1-pair-agreement-$($Configuration.ToLowerInvariant())"
$agreementVswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $agreementVswhere -PathType Leaf)) {
    throw 'Visual Studio Installer vswhere.exe was not found.'
}
$agreementVs = & $agreementVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $agreementVs) { throw 'MSVC x64 tools were not found.' }
$agreementSetup = Join-Path $agreementVs 'Common7\Tools\VsDevCmd.bat'
if (-not (Test-Path -LiteralPath $agreementSetup -PathType Leaf)) { throw 'VsDevCmd.bat was not found.' }
New-Item -ItemType Directory -Path $agreementBuild -Force | Out-Null
$agreementFlags = if ($Configuration -eq 'Release') { '/O2' } else { '/Od /Zi /RTC1' }
$agreementCommands = @"
@echo off
call "$agreementSetup" -no_logo -arch=x64 >nul
if errorlevel 1 exit /b 1
cl /nologo $agreementFlags /EHsc /std:c++20 /I"$agreementRepo" "$agreementRepo\tests\Family1PairAgreementVerify.cpp" "$agreementRepo\Family1LargeGraph.cpp" /Fe:Family1PairAgreementVerify.exe
"@
$agreementCommandFile = Join-Path $agreementBuild 'compile.cmd'
Set-Content -LiteralPath $agreementCommandFile -Value $agreementCommands -Encoding Ascii
Push-Location -LiteralPath $agreementBuild
try {
    & $env:ComSpec /d /c $agreementCommandFile 2>&1 | Tee-Object -FilePath (Join-Path $agreementBuild 'build.log')
    if ($LASTEXITCODE -ne 0) { throw "Agreement audit compilation failed: $LASTEXITCODE" }
    & (Join-Path $agreementBuild 'Family1PairAgreementVerify.exe') 2>&1 | Tee-Object -FilePath (Join-Path $agreementBuild 'test.log')
    if ($LASTEXITCODE -ne 0) { throw "Agreement audit failed: $LASTEXITCODE" }
}
finally { Pop-Location }

$agreementFiles = @('Family1PairAgreement.h', 'Family1LargeGraph.cpp', 'Family1LargeGraph.h', 'tests\Family1PairAgreementVerify.cpp', 'tests\run-family1-pair-agreement.ps1')
$agreementHashes = @{}
foreach ($agreementFile in $agreementFiles) {
    $agreementHashes[$agreementFile.Replace('\', '/')] = (Get-FileHash -LiteralPath (Join-Path $agreementRepo $agreementFile) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$agreementValidation = [ordered]@{
    schema = 1
    configuration = $Configuration
    method = 'independent-scalar-full-counts-and-state-replay'
    tiny_rooted_classes = 64
    tiny_distinct_pairs = 320
    tiny_common_suffix_steps = 6
    tiny_full_scalar_counts_and_copy_branches_passed = $true
    large_case_sizes = @(20, 20, 20)
    large_case_models = @('balanced-circulant', 'unbounded-indegree-reset', 'coincident-cycle')
    large_initial_and_final_full_scalar_mask_counts = 1048576
    large_per_step_scalar_state_spot_checks = 256
    large_common_suffix_steps = 8
    large_permutation_mask_counts = @(32, 0, 1048576)
    exact_agreement_monotonicity_verified = $true
    permutation_mismatch_invariance_verified = $true
    production_cmake_modified = $false
    source_sha256 = $agreementHashes
    test_output_sha256 = (Get-FileHash -LiteralPath (Join-Path $agreementBuild 'test.log') -Algorithm SHA256).Hash.ToLowerInvariant()
}
$agreementValidation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $agreementBuild 'validation.json') -Encoding Utf8
