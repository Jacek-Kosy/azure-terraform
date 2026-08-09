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
  description = "Resource group name for the production environment"
  type        = string
  default     = "rg-prod-vectordb"
}

variable "location" {
  description = "Azure region. Not westeurope: it is closed to new customers in this subscription and rejects new resources with RequestDisallowedByAzure."
  type        = string
  default     = "northeurope"
}

variable "tags" {
  description = "Tags applied to the production resource group"
  type        = map(string)
  default = {
    environment = "prod"
    managed_by  = "terraform"
  }
}
