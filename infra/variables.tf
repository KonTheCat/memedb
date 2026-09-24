variable "resource_group_name" {
  description = "Existing resource group to deploy into."
  type        = string
  default     = "memedb"
}

variable "location_data" {
  description = "Region for Storage and Cosmos DB (co-located with the resource group)."
  type        = string
  default     = "eastus2"
}

variable "location_ai" {
  description = "Region for Azure AI Vision and Azure OpenAI (must support multimodal embeddings)."
  type        = string
  default     = "eastus"
}

variable "vision_model_version" {
  description = "Pinned Azure AI Vision multimodal embeddings model version."
  type        = string
  default     = "2023-04-15"
}

variable "openai_deployment_name" {
  description = "Name of the Azure OpenAI model deployment used for metadata extraction."
  type        = string
  default     = "gpt-5.1"
}

variable "location_app" {
  description = "Region for the web app and its user-assigned identity - must match the shared App Service Plan's region (West US 3)."
  type        = string
  default     = "westus3"
}

variable "environment" {
  description = "Deployment environment name, used in App Service resource naming/tagging (e.g. \"prod\", \"dev\")."
  type        = string
  default     = "prod"
}

variable "entra_tenant_id" {
  description = "Entra External ID tenant ID (GUID), created manually in the Entra admin center. Not a secret."
  type        = string
}

variable "entra_tenant_subdomain" {
  description = "Entra External ID tenant subdomain, e.g. \"memedb\" for memedb.ciamlogin.com. Not a secret."
  type        = string
}

variable "entra_client_id" {
  description = "Client ID of the SPA app registration in the Entra tenant, created manually. Not a secret - the SPA has no client secret."
  type        = string
}
