# Create .env from env.example if missing
$Root = Split-Path -Parent $PSScriptRoot
$Example = Join-Path $Root "env.example"
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $Example)) {
    Write-Error "env.example not found at $Example"
    exit 1
}

if (Test-Path $EnvFile) {
    Write-Host ".env already exists at $EnvFile"
    Write-Host "Edit KIS_APP_KEY, KIS_APP_SECRET, ACCOUNT_NO, ANTHROPIC_API_KEY before smoke tests."
    exit 0
}

Copy-Item $Example $EnvFile
Write-Host "Created $EnvFile from env.example"
Write-Host "Next: edit .env with your KIS mock-trading keys and Anthropic API key."
