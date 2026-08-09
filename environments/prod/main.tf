terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
  }

  # Backend blocks cannot use variables, so these values are literals. They must
  # match the bootstrap stack — see `backend_config` in bootstrap/outputs.tf.
  # Requires bootstrap to have been applied first.
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstate964eeda7"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
    subscription_id      = "964eeda7-d407-48de-a969-ba555d0afd1e"
    tenant_id            = "060d8650-91b9-468e-bfb1-b03f1a30221d"
    use_azuread_auth     = true
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

module "resource_group" {
  source = "../../modules/azure-resource-group"

  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}
