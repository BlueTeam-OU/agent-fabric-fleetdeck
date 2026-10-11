Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$architecture = [System.Runtime.InteropServices.RuntimeInformation, mscorlib]::OSArchitecture.ToString()
Write-Host "OS architecture: $architecture"
Write-Host "Process architecture: $([System.Runtime.InteropServices.RuntimeInformation, mscorlib]::ProcessArchitecture)"
Write-Host "PowerShell: $($PSVersionTable.PSVersion) $($PSVersionTable.PSEdition)"
Write-Host "Windows: $([Environment]::OSVersion.VersionString)"
if ($architecture -ne "Arm64") {
    throw "This test requires Windows ARM64, found $architecture."
}

# This test installs the published preview over the network, so it can only run
# once FleetDeck has published one. The checked-out preview manifest is the
# record of what is published (the preview workflow commits it with each
# release), so an empty record means there is nothing to install yet, not an
# installer fault.
$publishedPreview = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot "..\distribution\preview.json") | ConvertFrom-Json
if ($null -eq $publishedPreview.assets.PSObject.Properties["windows-x86_64"]) {
    Write-Host "::warning::No FleetDeck preview with a windows-x86_64 asset is published yet (distribution/preview.json); the live ARM64 installer test did not run."
    exit 0
}

$root = Join-Path $env:RUNNER_TEMP "herdr-windows-arm64-installer-test"
$env:AGENT_FABRIC_FLEETDECK_HOME = Join-Path $root "home"
$env:AGENT_FABRIC_FLEETDECK_INSTALL_DIR = Join-Path $root "bin"
$env:AGENT_FABRIC_FLEETDECK_CHANNEL = "preview"
Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $root | Out-Null
$installer = (Resolve-Path (Join-Path $PSScriptRoot "..\distribution\install.ps1")).Path

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $installerOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer 2>&1
    $installerExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
$installerOutput | ForEach-Object { Write-Host $_ }
if ($installerExitCode -ne 0) {
    throw "The installer failed on Windows ARM64 with exit code $installerExitCode."
}

$installedHerdr = Join-Path $env:AGENT_FABRIC_FLEETDECK_INSTALL_DIR "agent-fabric-fleetdeck.exe"
if (-not (Test-Path -LiteralPath $installedHerdr -PathType Leaf)) {
    throw "The installer exited successfully without activating agent-fabric-fleetdeck.exe."
}
& $installedHerdr --version
if ($LASTEXITCODE -ne 0) {
    throw "The installed x86_64 Herdr executable failed with exit code $LASTEXITCODE."
}

$releases = Join-Path $env:AGENT_FABRIC_FLEETDECK_HOME "packages\standalone\releases"
if (@(Get-ChildItem -LiteralPath $releases -Force -Directory -Filter ".staging.*" -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "The installer succeeded but left a staging directory behind."
}

Write-Host "Windows ARM64 installer test passed."
