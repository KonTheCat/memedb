#Requires -Version 7.0
<#
Bootstraps the OpenTofu remote state backend: a storage account + blob
container that hold the tfstate file(s). Everything else (Cosmos DB, Vision,
OpenAI, app blob storage, App Service, ...) is provisioned by `tofu` itself
from ../, once per environment via infra/envs/<Environment>.tfvars.

$ResourceGroupName is where the *state* storage account lives (shared across
environments) - it does NOT need to match the resource group an environment's
app resources deploy into (see infra/envs/*.tfvars for that).

Safe to re-run - every step checks for existing state first. Re-running for
an environment that was already bootstrapped just rewrites its backend.hcl
with the same values.
#>

param(
    [string]$ResourceGroupName = "memedb",
    [string]$Location = "eastus2",
    [string]$ContainerName = "tfstate",
    [ValidateSet("prod", "dev")]
    [string]$Environment = "prod"
)

$ErrorActionPreference = "Stop"

$account = az account show -o json 2>$null | ConvertFrom-Json
if (-not $account) {
    throw "Not logged into Azure CLI. Run 'az login' first."
}
Write-Host "Using subscription: $($account.name) ($($account.id))"

$rg = az group show -n $ResourceGroupName -o json 2>$null | ConvertFrom-Json
if (-not $rg) {
    throw "Resource group '$ResourceGroupName' not found. Create it first (it should already exist)."
}

# Deterministic suffix derived from the subscription id so this script needs
# no local state file and is idempotent across machines/re-runs.
$hash = [System.Security.Cryptography.MD5]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($account.id))
$suffix = -join ($hash[0..3] | ForEach-Object { $_.ToString("x2") })
$storageAccountName = "memedbtfstate$suffix"

Write-Host "State storage account: $storageAccountName"

$existing = az storage account show --name $storageAccountName --resource-group $ResourceGroupName -o json 2>$null | ConvertFrom-Json
if ($existing) {
    Write-Host "Storage account already exists, skipping creation."
}
else {
    Write-Host "Creating storage account..."
    az storage account create `
        --name $storageAccountName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku Standard_LRS `
        --kind StorageV2 `
        --min-tls-version TLS1_2 `
        --allow-blob-public-access false `
        --only-show-errors `
        -o none
}

Write-Host "Ensuring '$ContainerName' container exists..."
$accountKey = (az storage account keys list --account-name $storageAccountName --resource-group $ResourceGroupName --query "[0].value" -o tsv)
az storage container create `
    --name $ContainerName `
    --account-name $storageAccountName `
    --account-key $accountKey `
    --only-show-errors `
    -o none

# The prod key stays "memedb.tfstate" for backward compatibility with state
# bootstrapped before per-environment support existed.
$stateKey = if ($Environment -eq "prod") { "memedb.tfstate" } else { "$Environment-memedb.tfstate" }

$envsDir = Join-Path $PSScriptRoot "..\envs"
New-Item -ItemType Directory -Force -Path $envsDir | Out-Null

$backendHclPath = Join-Path $envsDir "$Environment.backend.hcl"
$backendHcl = @"
resource_group_name  = "$ResourceGroupName"
storage_account_name = "$storageAccountName"
container_name       = "$ContainerName"
key                  = "$stateKey"
"@
Set-Content -Path $backendHclPath -Value $backendHcl -Encoding utf8NoBOM
Write-Host "Wrote $backendHclPath"

Write-Host ""
Write-Host "Next steps:"
Write-Host "  cd infra"
Write-Host "  tofu init -backend-config=envs/$Environment.backend.hcl -reconfigure"
Write-Host "  tofu plan -var-file=envs/$Environment.tfvars"
Write-Host "  tofu apply -var-file=envs/$Environment.tfvars"
