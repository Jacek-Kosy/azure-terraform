variable "resource_group_name" {
  description = "Resource group name for the production environment"
  type        = string
  default     = "rg-prod-example"
}

variable "location" {
  description = "Azure region"
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
