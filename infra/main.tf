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
  container_access_type = "blob"
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
# App Service — API (FastAPI, code deploy) + frontend (Next.js, code deploy)
#
# Names/URLs are computed locally (not read back off the resource) so the two
# web apps don't end up depending on each other's computed attributes, which
# would form a dependency cycle since each needs the other's URL.
# ---------------------------------------------------------------------------

locals {
  api_app_name      = "memedb-api-${var.environment}-${random_string.suffix.result}"
  frontend_app_name = "memedb-web-${var.environment}-${random_string.suffix.result}"
  api_url           = "https://${local.api_app_name}.azurewebsites.net"
  frontend_url      = "https://${local.frontend_app_name}.azurewebsites.net"
}

resource "azurerm_service_plan" "api" {
  name                = "memedb-api-plan-${var.environment}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
  os_type             = "Linux"
  sku_name            = var.app_service_sku
}

resource "azurerm_linux_web_app" "api" {
  name                = local.api_app_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
  service_plan_id     = azurerm_service_plan.api.id
  tags                = { environment = var.environment, role = "api" }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    app_command_line = "gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000 memedb.api.app:app"
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
    ALLOWED_ORIGINS            = local.frontend_url

    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true"
  }
}

resource "azurerm_service_plan" "frontend" {
  name                = "memedb-web-plan-${var.environment}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
  os_type             = "Linux"
  sku_name            = var.app_service_sku
}

resource "azurerm_linux_web_app" "frontend" {
  name                = local.frontend_app_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location_app
  service_plan_id     = azurerm_service_plan.frontend.id
  tags                = { environment = var.environment, role = "frontend" }

  site_config {
    application_stack {
      node_version = "20-lts"
    }
    app_command_line = "npm run start"
  }

  # NEXT_PUBLIC_* vars are baked in at build time — Oryx exposes app_settings
  # as env vars during the build it runs on deploy, so this still works.
  #
  # No WEBSITES_PORT here deliberately: that setting is for custom containers.
  # The blessed Node image always exposes 8080 and injects PORT=8080, which
  # `next start` honors automatically - setting WEBSITES_PORT to anything
  # else here would make the platform wait on a port nothing listens on.
  app_settings = {
    NEXT_PUBLIC_API_BASE_URL = local.api_url

    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true"
  }
}
