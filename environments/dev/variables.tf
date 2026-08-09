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
  description = "GlobalStandard capacity for the embedding deployment, in thousands of tokens per minute. Subscription quota for text-embedding-3-small in northeurope is 1000. GlobalStandard bills per token consumed rather than per unit provisioned, so raising this buys rate limit headroom at no cost."
  type        = number
  default     = 500
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

variable "cosmos_container_autoscale_max" {
  description = "Autoscale ceiling per vector container, in RU/s. Autoscale idles at 10% of this, so three containers at 2000 sit at 600 RU/s, inside the 1000 RU/s free allowance. Raise it for bulk loading, which otherwise throttles with TooManyRequests."
  type        = number
  default     = 2000

  validation {
    condition     = var.cosmos_container_autoscale_max >= 1000 && var.cosmos_container_autoscale_max % 1000 == 0
    error_message = "Autoscale maximum must be at least 1000 RU/s and a multiple of 1000."
  }
}

# The ceiling ratchets: Cosmos will not accept a maximum below 10% of the highest
# value ever provisioned on a container. Raising these to 20000 for a bulk load
# permanently raised their floor to 2000, which is why the default is not 1000.
# Raise it sparingly, and by the smallest amount that clears the throttling.

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

variable "app_name" {
  description = "Name of the Container App running the search front end"
  type        = string
  default     = "vectorsearch"
}

variable "registry_name" {
  description = "Container registry name. Must be globally unique and alphanumeric only."
  type        = string
  default     = "acrdevvectordb964eeda7"
}

variable "container_image" {
  description = "Image the Container App runs. Must be linux/amd64: Container Apps does not run arm64, and an arm64 image pushes fine then crash-loops with an exec format error."
  type        = string
  default     = "acrdevvectordb964eeda7.azurecr.io/vectorsearch:v3"

  # The default names the real image rather than a placeholder so that a plain
  # `terraform apply` is always safe; defaulting to a placeholder would silently
  # roll the running app back. Bootstrapping a fresh subscription is the one case
  # that needs an override, because the registry is empty until an image is
  # pushed to it:
  #
  #   terraform apply -var container_image=mcr.microsoft.com/k8se/quickstart:latest
  #   az acr login --name <registry> && docker buildx build --platform linux/amd64 \
  #     -t <registry>.azurecr.io/vectorsearch:v2 --push app/
  #   terraform apply
}

variable "cosmos_vector_dimensions" {
  description = "Vector width the app embeds queries at. Must match the containers' embedding policy, otherwise VectorDistance rejects the query."
  type        = number
  default     = 505
}

variable "tags" {
  description = "Tags applied to the development resource group"
  type        = map(string)
  default = {
    environment = "dev"
    managed_by  = "terraform"
  }
}
