Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'backend\scripts\start_demo_test.ps1') -QuickStart -UseExistingBuild -OpenBrowser
