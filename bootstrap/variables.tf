variable "subscription_id" {
  description = "Azure subscription this catalog manages (az-subscription-jacek)"
  type        = string
  default     = "964eeda7-d407-48de-a969-ba555d0afd1e"
}

variable "tenant_id" {
  description = "Entra ID tenant that owns the subscription"
  type        = string
  default     = "060d8650-91b9-468e-bfb1-b03f1a30221d"
}

variable "location" {
  description = "Azure region for the state backend. Must match the existing rg-tfstate region, otherwise the resource group is replaced instead of updated."
  type        = string
  default     = "westeurope"
}

variable "state_storage_location" {
  description = "Region for the state storage account. Separate from var.location because westeurope is closed to new customers; the resource group itself can stay where it is."
  type        = string
  default     = "northeurope"
}

variable "state_resource_group_name" {
  description = "Resource group holding the Terraform state backend"
  type        = string
  default     = "rg-tfstate"
}

variable "state_storage_account_name" {
  description = "Storage account holding the Terraform state. Must be globally unique; keep it in sync with the backend blocks in environments/*/main.tf, which cannot use variables."
  type        = string
  default     = "sttfstate964eeda7"

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.state_storage_account_name))
    error_message = "Storage account names must be 3-24 characters, lowercase letters and digits only."
  }
}

variable "state_container_name" {
  description = "Blob container holding the Terraform state files"
  type        = string
  default     = "tfstate"
}

variable "state_replication_type" {
  description = "Replication for the state storage account"
  type        = string
  default     = "LRS"
}

variable "tags" {
  description = "Tags applied to the state backend resources"
  type        = map(string)
  default = {
    environment = "shared"
    managed_by  = "terraform"
    purpose     = "terraform-state"
  }
}
