# Download this script, review it, then run it from the project directory.
param(
    [ValidateSet("codex","claude","cursor")][string]$Agent = "codex",
    [string]$Project = ".",
    [ValidateSet("eco","balanced","detailed","manual")][string]$Mode = "eco",
    [ValidateSet("setup","repair","update","uninstall","installation-doctor")][string]$Action = "setup",
    [switch]$CaptureContext,
    [switch]$Apply
)
$ErrorActionPreference = "Stop"
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64" -and $env:PROCESSOR_ARCHITEW6432 -ne "AMD64") {
    throw "Standalone Windows preview supports x64. Use the Python install for other architectures."
}
$base = "https://github.com/Guhanavish/mirrormap/releases/download/installer-preview-1"
$name = "mirrormap-windows-x64.exe"
$directory = Join-Path ([System.IO.Path]::GetTempPath()) ("mirrormap-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $directory | Out-Null
try {
    $exe = Join-Path $directory $name
    $sums = Join-Path $directory "SHA256SUMS.txt"
    Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS.txt" -OutFile $sums
    $matchesForAsset = @(Get-Content -LiteralPath $sums | Where-Object { $_ -match "^[0-9a-fA-F]{64}\s+\*?mirrormap-windows-x64\.exe$" })
    if ($matchesForAsset.Count -ne 1) { throw "Missing or ambiguous checksum" }
    $expected = ($matchesForAsset[0] -split "\s+")[0]
    Invoke-WebRequest -UseBasicParsing -Uri "$base/$name" -OutFile $exe
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash -ne $expected) { throw "Checksum verification failed" }
    $arguments = @($Action, "--project", $Project)
    if ($Action -ne "installation-doctor") {
        $arguments += @("--agent", $Agent, "--mode", $Mode)
        if ($CaptureContext) { $arguments += "--capture-context" }
        if ($Apply) { $arguments += "--apply" }
    }
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "MirrorMap setup failed with exit code $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $directory -Recurse -Force
}
