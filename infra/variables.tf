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
