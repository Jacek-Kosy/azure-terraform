variable "resource_group_name" {
  description = "Resource group name for the development environment"
  type        = string
  default     = "rg-dev-example"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "tags" {
  description = "Tags applied to the development resource group"
  type        = map(string)
  default = {
    environment = "dev"
    managed_by  = "terraform"
  }
}
