terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }

    # azurerm_cosmosdb_sql_container cannot express vectorEmbeddingPolicy or
    # indexingPolicy.vectorIndexes at all, so vector containers go through the
    # raw ARM API instead.
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.11"
    }
  }
}
