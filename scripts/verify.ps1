param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
$Files = @(
    "main.py",
    "kagent"
)

Write-Host "==> Python syntax check"
& $Python -m compileall -q @Files

Write-Host "==> Ruff lint"
& $Python -m ruff check kagent

Write-Host "==> Mypy type check"
& $Python -m mypy

if (-not $SkipTests) {
    Write-Host "==> Pytest"
    & $Python -m pytest -q
}
