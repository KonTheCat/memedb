#Requires -Version 7.0
<#
One-time setup for GitHub Actions deploys (.github/workflows/deploy.yml):
creates an Azure AD app registration + service principal that GitHub Actions
can log in as via OIDC (no client secret stored anywhere), federated for
this repo's "dev" and "prod" GitHub Environments, with Contributor on each
environment's resource group.

Run this yourself after reviewing it - it creates an AD app registration,
a service principal, and role assignments on your subscription.

Requires: Azure CLI logged in (`az login`) with permissions to create app
registrations and role assignments, and GitHub CLI logged in (`gh auth login`).

    ./infra/bootstrap/setup-github-oidc.ps1 -GitHubRepo "yourorg/memedb"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubRepo,
    [string]$AppName = "memedb-github-actions",
    [string]$ProdResourceGroup = "memedb",
    [string]$DevResourceGroup = "dev-memedb",
    [string]$SharedAcrId = "/subscriptions/a7edb0c9-d49d-4c7c-a3d7-776c14e253d2/resourceGroups/shared-global/providers/Microsoft.ContainerRegistry/registries/sharedacra7edb0c9"
)

$ErrorActionPreference = "Stop"

$account = az account show -o json 2>$null | ConvertFrom-Json
if (-not $account) {
    throw "Not logged into Azure CLI. Run 'az login' first."
}
Write-Host "Using subscription: $($account.name) ($($account.id))"

$app = az ad app list --display-name $AppName -o json | ConvertFrom-Json
if ($app -and $app.Count -gt 0) {
    $app = $app[0]
    Write-Host "Reusing existing app registration '$AppName' ($($app.appId))"
}
else {
    Write-Host "Creating app registration '$AppName'..."
    $app = az ad app create --display-name $AppName -o json | ConvertFrom-Json
}

$sp = az ad sp list --filter "appId eq '$($app.appId)'" -o json | ConvertFrom-Json
if (-not $sp -or $sp.Count -eq 0) {
    Write-Host "Creating service principal..."
    $sp = az ad sp create --id $app.appId -o json | ConvertFrom-Json
}
else {
    $sp = $sp[0]
}

function Set-FederatedCredential($EnvName) {
    $credName = "github-$EnvName-environment"
    $existing = az ad app federated-credential list --id $app.appId -o json | ConvertFrom-Json |
        Where-Object { $_.name -eq $credName }
    if ($existing) {
        Write-Host "Federated credential '$credName' already exists, skipping."
        return
    }
    Write-Host "Creating federated credential '$credName'..."
    $body = @{
        name        = $credName
        issuer      = "https://token.actions.githubusercontent.com"
        subject     = "repo:${GitHubRepo}:environment:${EnvName}"
        description = "GitHub Actions - $EnvName environment"
        audiences   = @("api://AzureADTokenExchange")
    } | ConvertTo-Json -Compress

    $tmp = New-TemporaryFile
    Set-Content -Path $tmp -Value $body -Encoding utf8NoBOM
    az ad app federated-credential create --id $app.appId --parameters "@$tmp" -o none
    Remove-Item $tmp
}

Set-FederatedCredential -EnvName "dev"
Set-FederatedCredential -EnvName "prod"

function Grant-ResourceGroupContributor($ResourceGroupName) {
    $rg = az group show -n $ResourceGroupName -o json 2>$null | ConvertFrom-Json
    if (-not $rg) {
        Write-Warning "Resource group '$ResourceGroupName' not found - skipping role assignment. Create it and re-run this script."
        return
    }
    Write-Host "Granting Contributor on '$ResourceGroupName' to service principal..."
    az role assignment create `
        --assignee-object-id $sp.id `
        --assignee-principal-type ServicePrincipal `
        --role "Contributor" `
        --scope $rg.id `
        -o none
}

Grant-ResourceGroupContributor -ResourceGroupName $ProdResourceGroup
Grant-ResourceGroupContributor -ResourceGroupName $DevResourceGroup

function Grant-AcrPush {
    Write-Host "Granting AcrPush on the shared container registry to service principal..."
    az role assignment create `
        --assignee-object-id $sp.id `
        --assignee-principal-type ServicePrincipal `
        --role "AcrPush" `
        --scope $SharedAcrId `
        -o none
}

Grant-AcrPush

Write-Host ""
Write-Host "Now set these in GitHub (repo Settings > Environments > dev / prod):"
Write-Host "  Environment secrets (same value in both envs):"
Write-Host "    AZURE_CLIENT_ID       = $($app.appId)"
Write-Host "    AZURE_TENANT_ID       = $($account.tenantId)"
Write-Host "    AZURE_SUBSCRIPTION_ID = $($account.id)"
Write-Host "  Environment variables:"
Write-Host "    dev  environment: RESOURCE_GROUP = $DevResourceGroup"
Write-Host "    prod environment: RESOURCE_GROUP = $ProdResourceGroup"
Write-Host ""
Write-Host "Via gh CLI, per environment (repeat with 'dev' and 'prod'):"
Write-Host "  gh secret set AZURE_CLIENT_ID -e dev -b `"$($app.appId)`""
Write-Host "  gh secret set AZURE_TENANT_ID -e dev -b `"$($account.tenantId)`""
Write-Host "  gh secret set AZURE_SUBSCRIPTION_ID -e dev -b `"$($account.id)`""
Write-Host "  gh variable set RESOURCE_GROUP -e dev -b `"$DevResourceGroup`""
Write-Host ""
Write-Host "Consider adding a required-reviewer protection rule on the 'prod' GitHub Environment so manual dispatch to prod needs approval."
