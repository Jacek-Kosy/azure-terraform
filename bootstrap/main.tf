terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.117"
    }
  }

  # This stack deliberately keeps local state: it creates the storage account
  # that every other stack uses as its remote backend. After the first apply you
  # may move this stack's own state into that account by uncommenting the block
  # below and running `terraform init -migrate-state`.
  #
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "sttfstate964eeda7"
  #   container_name       = "tfstate"
  #   key                  = "bootstrap.terraform.tfstate"
  #   subscription_id      = "964eeda7-d407-48de-a969-ba555d0afd1e"
  #   tenant_id            = "060d8650-91b9-468e-bfb1-b03f1a30221d"
  #   use_azuread_auth     = true
  # }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

data "azurerm_client_config" "current" {}

module "state_resource_group" {
  source = "../modules/azure-resource-group"

  name     = var.state_resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_storage_account" "state" {
  name                = var.state_storage_account_name
  resource_group_name = module.state_resource_group.resource_group_name

  # Deliberately not var.location: a resource group only holds metadata, so its
  # resources may sit in another region. westeurope rejects new customers
  # (RequestDisallowedByAzure), which would otherwise block this account.
  location = var.state_storage_location

  account_tier                    = "Standard"
  account_kind                    = "StorageV2"
  account_replication_type        = var.state_replication_type
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  # Versioning and soft delete let you recover a state file that was corrupted
  # or overwritten by a bad apply.
  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  tags = var.tags
}

# The backends authenticate with Entra ID (use_azuread_auth), which needs a
# data-plane role: subscription Owner on its own does not grant blob access.
resource "azurerm_role_assignment" "state_blob_owner" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_storage_container" "state" {
  name                  = var.state_container_name
  storage_account_name  = azurerm_storage_account.state.name
  container_access_type = "private"
}
