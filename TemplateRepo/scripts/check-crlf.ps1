$ErrorActionPreference = 'Stop'

$files = @(git ls-files -- '*.cs')
if ($LASTEXITCODE -ne 0) {
    throw 'Could not list tracked C# files.'
}

$encoding = [System.Text.UTF8Encoding]::new($false)
$changed = @()
foreach ($file in $files) {
    $path = Join-Path $PWD $file
    $text = [System.IO.File]::ReadAllText($path)
    $normalized = $text -replace "`r?`n", "`r`n"
    if ($normalized -cne $text) {
        [System.IO.File]::WriteAllText($path, $normalized, $encoding)
        $changed += $file
    }
}

if ($changed.Count -gt 0) {
    Write-Error ("C# files must use CRLF: " + ($changed -join ', '))
    exit 1
}

Write-Host 'All tracked C# files use CRLF.'
