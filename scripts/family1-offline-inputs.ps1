# Shared build/package provenance. Follow project-local includes so a newly
# added native adapter is pinned automatically rather than omitted from a
# duplicated list. Standard-library and Windows SDK headers use angle brackets.
function Get-Family1OfflineSourcePins {
    param([Parameter(Mandatory = $true)] [string] $RepositoryRoot)
    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd('\', '/')
    $pending = [Collections.Generic.Stack[string]]::new()
    foreach ($entry in @('CMakeLists.txt', 'family1_offline.cpp', 'Family1LargeGraph.cpp',
        'Family1LargeEnumerator.cpp', 'Family1ExactPacked.cpp', 'Family1EditSearch.cpp')) {
        $pending.Push((Join-Path $root $entry))
    }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    while ($pending.Count) {
        $path = [IO.Path]::GetFullPath($pending.Pop())
        if (-not $path.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Offline build input is outside the source repository: $path"
        }
        if (-not $seen.Add($path)) { continue }
        $content = [IO.File]::ReadAllText($path)
        foreach ($match in [regex]::Matches($content, '(?m)^\s*#\s*include\s*"([^"]+)"')) {
            $pending.Push((Join-Path (Split-Path -Parent $path) $match.Groups[1].Value))
        }
    }
    return @($seen | Sort-Object | ForEach-Object {
        [ordered]@{
            name = $_.Substring($root.Length + 1).Replace('\', '/')
            sha256 = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
}
