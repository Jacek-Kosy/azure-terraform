variable "subscription_id" {
  description = "Azure subscription this environment deploys into (az-subscription-jacek)"
  type        = string
  default     = "964eeda7-d407-48de-a969-ba555d0afd1e"
}

variable "tenant_id" {
  description = "Entra ID tenant that owns the subscription"
  type        = string
  default     = "060d8650-91b9-468e-bfb1-b03f1a30221d"
}

variable "resource_group_name" {
  description = "Resource group name for the development environment"
  type        = string
  default     = "rg-dev-vectordb"
}

variable "location" {
  description = "Azure region. Not westeurope: it is closed to new customers in this subscription and rejects new resources with RequestDisallowedByAzure."
  type        = string
  default     = "northeurope"
}

variable "openai_account_name" {
  description = "Azure OpenAI account name. Must be globally unique: it becomes <name>.openai.azure.com."
  type        = string
  default     = "oai-dev-964eeda7"
}

variable "openai_location" {
  description = "Region for the Azure OpenAI account. Separate from var.location because model availability is per-region and narrower than general region availability."
  type        = string
  default     = "northeurope"
}

variable "embedding_capacity" {
  description = "GlobalStandard capacity for the embedding deployment, in thousands of tokens per minute. Subscription quota for text-embedding-3-small in northeurope is 1000."
  type        = number
  default     = 50
}

variable "tags" {
  description = "Tags applied to the development resource group"
  type        = map(string)
  default = {
    environment = "dev"
    managed_by  = "terraform"
  }
}
