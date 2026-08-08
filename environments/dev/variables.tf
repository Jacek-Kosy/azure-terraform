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

variable "cosmos_account_name" {
  description = "Cosmos DB account name. Must be globally unique: it becomes <name>.documents.azure.com."
  type        = string
  default     = "cosmos-dev-964eeda7"
}

variable "cosmos_location" {
  description = "Region for the Cosmos DB account. Separate from var.location because Cosmos capacity is regional and exhausts independently: northeurope refused account creation with ServiceUnavailable while every other resource there was fine."
  type        = string
  default     = "swedencentral"
}

variable "cosmos_database_name" {
  description = "Name of the Cosmos DB SQL database holding the vector containers"
  type        = string
  default     = "vectordb"
}

variable "cosmos_database_throughput" {
  description = "Shared RU/s across the database's containers. Must stay null: Cosmos refuses vector indexes under a shared throughput offer, so each container provisions its own autoscale capacity instead."
  type        = number
  default     = null
}

variable "cosmos_containers" {
  description = "Vector containers to compare. All three sit at 505 dimensions so index type is the only variable: flat cannot exceed 505, and matching the others to it keeps the comparison controlled. Raise quantizedFlat and diskANN toward 4096 to see what the extra width costs them."
  type = map(object({
    dimensions         = number
    index_type         = string
    partition_key_path = optional(string, "/topic")
    vector_path        = optional(string, "/embedding")
    distance_function  = optional(string, "cosine")
  }))
  default = {
    chunks_flat = {
      dimensions = 505
      index_type = "flat"
    }
    chunks_quantized = {
      dimensions = 505
      index_type = "quantizedFlat"
    }
    chunks_diskann = {
      dimensions = 505
      index_type = "diskANN"
    }
  }
}

variable "tags" {
  description = "Tags applied to the development resource group"
  type        = map(string)
  default = {
    environment = "dev"
    managed_by  = "terraform"
  }
}
