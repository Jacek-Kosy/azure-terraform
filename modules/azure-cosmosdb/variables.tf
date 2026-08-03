variable "name" {
  description = "Cosmos DB account name. Must be globally unique: it becomes <name>.documents.azure.com."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,42}[a-z0-9]$", var.name))
    error_message = "Cosmos DB account names must be 3-44 characters of lowercase letters, digits, and hyphens, and cannot start or end with a hyphen."
  }
}

variable "resource_group_name" {
  description = "Resource group to create the account in"
  type        = string
}

variable "location" {
  description = "Azure region for the account and its single geo_location"
  type        = string
}

variable "zone_redundant" {
  description = "Spread the write region across availability zones. Off by default: zonal capacity is scarcer, and it cannot be changed later without recreating the account."
  type        = bool
  default     = false
}

variable "database_name" {
  description = "Name of the SQL (NoSQL API) database"
  type        = string
}

variable "database_throughput" {
  description = "Shared RU/s for the database, in increments of 100 with a minimum of 400. The free tier covers the first 1000 RU/s. Set at creation only: changing it forces the database to be recreated."
  type        = number
  default     = 1000
}

variable "free_tier_enabled" {
  description = "Claim the subscription's single free-tier allowance (1000 RU/s and 25 GB). Changing this forces the account to be replaced."
  type        = bool
  default     = true
}

variable "local_authentication_enabled" {
  description = "Allow account-key and connection-string auth. Off by default so access goes through Entra ID and the data-plane role assignments below."
  type        = bool
  default     = false
}

variable "public_network_access_enabled" {
  description = "Whether the account is reachable from the public internet"
  type        = bool
  default     = true
}

variable "consistency_level" {
  description = "Default consistency. Session is the Cosmos default and is appropriate for a single-writer workload."
  type        = string
  default     = "Session"
}

variable "capabilities" {
  description = "Account capabilities. EnableNoSQLVectorSearch is required before any container may declare a vector embedding policy or vector index."
  type        = list(string)
  default     = ["EnableNoSQLVectorSearch"]
}

variable "data_plane_principal_ids" {
  description = "Object IDs granted the built-in Cosmos DB Data Contributor role. Required to read or write documents at all when local authentication is disabled, including through the portal's Data Explorer."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to the account"
  type        = map(string)
  default     = {}
}
