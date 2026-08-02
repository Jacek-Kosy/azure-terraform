terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
  }

  # This stack stores its state in the storage account it creates, which is
  # circular but keeps the state off any one workstation. The circularity is
  # contained by prevent_destroy on the account and container below: tearing
  # this stack down requires deliberately editing that lifecycle block first.
  #
  # Recreating from nothing, in a subscription with no storage account yet:
  # comment this block out, apply once against local state, uncomment it, then
  # run `terraform init -migrate-state`.
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstate964eeda7"
    container_name       = "tfstate"
    key                  = "bootstrap.terraform.tfstate"
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

data "azurerm_client_config" "current" {}

module "state_resource_group" {
  source = "../modules/azure-resource-group"

  name     = var.state_resource_group_name
  location = var.location
  tags     = var.tags
}

# A default_action of Deny needs an IP allowlist, which locks the backend to
# whichever address a laptop happens to have that day and breaks `terraform init`
# from anywhere else. The real fix is a private endpoint, which needs a VNet this
# project does not yet have. Revisit before prod carries anything real.
#trivy:ignore:AVD-AZU-0012
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

  # Every stack's state lives here, including this one's. Destroying the account
  # would take the state with it and leave the whole catalog unmanageable, so
  # teardown has to be an explicit decision made by editing this block.
  lifecycle {
    prevent_destroy = true
  }
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
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}
