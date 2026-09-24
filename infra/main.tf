data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# ---------------------------------------------------------------------------
# Blob storage for raw meme image files
# ---------------------------------------------------------------------------

resource "azurerm_storage_account" "images" {
  name                = "memedbimg${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_data

  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "memes" {
  name                  = "memes"
  storage_account_id    = azurerm_storage_account.images.id
  container_access_type = "private"
}

# ---------------------------------------------------------------------------
# Cosmos DB for NoSQL — serverless, vector search + full-text search enabled
# ---------------------------------------------------------------------------

resource "azurerm_cosmosdb_account" "main" {
  name                = "memedb-cosmos-${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_data
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  consistency_policy {
    consistency_level = "Session"
  }

  capabilities {
    name = "EnableServerless"
  }

  capabilities {
    name = "EnableNoSQLVectorSearch"
  }

  capabilities {
    name = "EnableNoSQLFullTextSearch"
  }

  geo_location {
    location          = var.location_data
    failover_priority = 0
  }
}

resource "azurerm_cosmosdb_sql_database" "memedb" {
  name                = "memedb"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
}

# Vector embedding policy, full-text policy, and vector/full-text indexes are
# immutable and must be present at container *creation* time (confirmed via
# Microsoft Learn: "vector policies and vector indexes are immutable after
# creation. To make changes, create a new collection."). azurerm_cosmosdb_sql_container
# doesn't support these fields at all (hashicorp/terraform-provider-azurerm#29597),
# and a create-then-PATCH-via-azapi_update_resource approach silently fails to
# apply them since the container already exists by the time the patch runs.
# So the container is created directly via azapi_resource with every policy
# included in the initial PUT body.
resource "azapi_resource" "memes" {
  type      = "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15"
  name      = "memes"
  parent_id = azurerm_cosmosdb_sql_database.memedb.id

  # The azapi provider's embedded schema for this api-version predates the
  # vectorEmbeddingPolicy/fullTextPolicy/vectorIndexes/fullTextIndexes fields,
  # so strict client-side validation rejects a body the actual ARM API accepts.
  schema_validation_enabled = false

  body = {
    properties = {
      resource = {
        id = "memes"

        partitionKey = {
          paths = ["/category"]
          kind  = "Hash"
        }

        indexingPolicy = {
          indexingMode = "consistent"
          automatic    = true
          includedPaths = [
            { path = "/*" }
          ]
          excludedPaths = [
            { path = "/\"_etag\"/?" },
            { path = "/visualEmbedding/*" }
          ]
          fullTextIndexes = [
            { path = "/searchableText" }
          ]
          vectorIndexes = [
            { path = "/visualEmbedding", type = "DiskANN" }
          ]
        }

        vectorEmbeddingPolicy = {
          vectorEmbeddings = [
            {
              path             = "/visualEmbedding"
              dataType         = "float32"
              distanceFunction = "cosine"
              dimensions       = 1024
            }
          ]
        }

        fullTextPolicy = {
          defaultLanguage = "en-US"
          fullTextPaths = [
            {
              path     = "/searchableText"
              language = "en-US"
            }
          ]
        }
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Azure AI Vision — multimodal embeddings (vectorizeImage / vectorizeText)
# ---------------------------------------------------------------------------

resource "azurerm_cognitive_account" "vision" {
  name                = "memedb-vision-${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_ai
  kind                = "ComputerVision"
  sku_name            = "S1"
}

# ---------------------------------------------------------------------------
# Azure OpenAI — multimodal chat model for OCR + metadata extraction.
# gpt-4o is in "Deprecating" state on this subscription and rejects new
# deployments, so we use gpt-5.1 (current GA multimodal model) instead.
# ---------------------------------------------------------------------------

resource "azurerm_cognitive_account" "openai" {
  name                = "memedb-openai-${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_data
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = var.openai_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-5.1"
    version = "2025-11-13"
  }

  sku {
    name     = "GlobalStandard"
    capacity = 10
  }
}

# ---------------------------------------------------------------------------
# App Service — single container per environment (FastAPI serving the
# pre-built static frontend), on the shared App Service Plan.
# ---------------------------------------------------------------------------

data "azurerm_service_plan" "shared" {
  name                = "shared-linux-asp-west-us-3"
  resource_group_name = "shared-global"
}

data "azurerm_container_registry" "shared" {
  name                = "sharedacra7edb0c9"
  resource_group_name = "shared-global"
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "memedb-${var.environment}-identity"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = data.azurerm_container_registry.shared.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_linux_web_app" "app" {
  name                = "memedb-${var.environment}-${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
  service_plan_id     = data.azurerm_service_plan.shared.id
  tags                = { environment = var.environment }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  site_config {
    container_registry_use_managed_identity       = true
    container_registry_managed_identity_client_id = azurerm_user_assigned_identity.app.client_id

    application_stack {
      docker_image_name   = "memedb/app:${var.environment}"
      docker_registry_url = "https://${data.azurerm_container_registry.shared.login_server}"
    }
  }

  app_settings = {
    COSMOS_ENDPOINT            = azurerm_cosmosdb_account.main.endpoint
    COSMOS_KEY                 = azurerm_cosmosdb_account.main.primary_key
    COSMOS_DATABASE            = azurerm_cosmosdb_sql_database.memedb.name
    COSMOS_CONTAINER           = azapi_resource.memes.name
    AZURE_VISION_ENDPOINT      = azurerm_cognitive_account.vision.endpoint
    AZURE_VISION_KEY           = azurerm_cognitive_account.vision.primary_access_key
    AZURE_VISION_MODEL_VERSION = var.vision_model_version
    AZURE_OPENAI_ENDPOINT      = azurerm_cognitive_account.openai.endpoint
    AZURE_OPENAI_KEY           = azurerm_cognitive_account.openai.primary_access_key
    AZURE_OPENAI_DEPLOYMENT    = azurerm_cognitive_deployment.gpt4o.name
    BLOB_ACCOUNT_NAME          = azurerm_storage_account.images.name
    BLOB_ACCOUNT_KEY           = azurerm_storage_account.images.primary_access_key
    BLOB_CONTAINER             = azurerm_storage_container.memes.name
    APP_PASSWORD               = var.app_password

    WEBSITES_PORT = "8000"
  }
}
