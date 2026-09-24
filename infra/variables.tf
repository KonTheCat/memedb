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

variable "app_password" {
  description = "Shared password required to use the app. Pass via TF_VAR_app_password or -var, never commit it in a tfvars file."
  type        = string
  sensitive   = true
}
