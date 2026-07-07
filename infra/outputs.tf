output "blob_account_name" {
  value = azurerm_storage_account.images.name
}

output "blob_account_key" {
  value     = azurerm_storage_account.images.primary_access_key
  sensitive = true
}

output "blob_container" {
  value = azurerm_storage_container.memes.name
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_key" {
  value     = azurerm_cosmosdb_account.main.primary_key
  sensitive = true
}

output "cosmos_database" {
  value = azurerm_cosmosdb_sql_database.memedb.name
}

output "cosmos_container" {
  value = azapi_resource.memes.name
}

output "vision_endpoint" {
  value = azurerm_cognitive_account.vision.endpoint
}

output "vision_key" {
  value     = azurerm_cognitive_account.vision.primary_access_key
  sensitive = true
}

output "vision_model_version" {
  value = var.vision_model_version
}

output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "openai_key" {
  value     = azurerm_cognitive_account.openai.primary_access_key
  sensitive = true
}

output "openai_deployment" {
  value = azurerm_cognitive_deployment.gpt4o.name
}

output "api_app_name" {
  value = azurerm_linux_web_app.api.name
}

output "api_url" {
  value = local.api_url
}

output "frontend_app_name" {
  value = azurerm_linux_web_app.frontend.name
}

output "frontend_url" {
  value = local.frontend_url
}
