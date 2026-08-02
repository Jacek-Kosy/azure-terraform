variable "name" {
  description = "Name of the Azure OpenAI account. Must be globally unique: it becomes the endpoint hostname."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to create the account in"
  type        = string
}

variable "location" {
  description = "Azure region. Must offer the models listed in var.deployments; check with `az cognitiveservices model list -l <region>`."
  type        = string
}

variable "sku_name" {
  description = "Account SKU. S0 is the only tier Azure OpenAI offers; it is pay-per-token, not a standing charge."
  type        = string
  default     = "S0"
}

variable "custom_subdomain_name" {
  description = "Custom subdomain for the endpoint. Defaults to var.name. Required for Entra ID auth, so it is always set."
  type        = string
  default     = null
}

variable "local_auth_enabled" {
  description = "Allow API-key auth alongside Entra ID. Off by default so keys cannot leak into scripts or CI logs."
  type        = bool
  default     = false
}

variable "public_network_access_enabled" {
  description = "Whether the endpoint is reachable from the public internet"
  type        = bool
  default     = true
}

variable "deployments" {
  description = "Model deployments, keyed by deployment name. The key is what callers pass as the deployment/model id."
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = optional(string, "GlobalStandard")
    capacity      = optional(number, 50)
  }))
  default = {}
}

variable "tags" {
  description = "Tags applied to the account"
  type        = map(string)
  default     = {}
}
