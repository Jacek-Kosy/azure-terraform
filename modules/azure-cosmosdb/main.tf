resource "azurerm_cosmosdb_account" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # free_tier_enabled forces replacement when changed, and Azure permits only
  # one free-tier account per subscription, so flipping this later means
  # destroying this account before another can claim the allowance.
  free_tier_enabled = var.free_tier_enabled

  # Keyless, matching the storage and OpenAI accounts: callers authenticate with
  # Entra ID and need a data-plane role assignment, not a connection string.
  local_authentication_enabled = var.local_authentication_enabled

  public_network_access_enabled = var.public_network_access_enabled
  minimal_tls_version           = "Tls12"

  consistency_policy {
    consistency_level = var.consistency_level
  }

  # Explicitly non-zone-redundant. Capacity for zonal accounts is scarcer, and
  # northeurope refused account creation on exactly that basis.
  geo_location {
    location          = var.location
    failover_priority = 0
    zone_redundant    = var.zone_redundant
  }

  # EnableNoSQLVectorSearch is what allows a container to carry a vector
  # embedding policy and vector indexes at all.
  dynamic "capabilities" {
    for_each = var.capabilities
    content {
      name = capabilities.value
    }
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags

  # The free-tier allowance is one account per subscription, and regional Cosmos
  # capacity is not guaranteed -- northeurope refused creation outright. Losing
  # this account is therefore not reliably undoable, so teardown has to be a
  # deliberate edit rather than a stray destroy.
  lifecycle {
    prevent_destroy = true
  }
}

# The database deliberately provisions no throughput of its own. Cosmos rejects
# vector indexes on any container under a shared throughput offer with "The
# Vector Indexing is not supported for shared throughput offer", so throughput
# has to be dedicated per container instead.
#
# Throughput can only be set at creation, so switching between shared and
# dedicated later means destroying and recreating the database.
resource "azurerm_cosmosdb_sql_database" "this" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
  throughput          = var.database_throughput

  # Guards the containers and their documents. Switching between shared and
  # dedicated throughput is a recreate, so that change requires lifting this
  # block deliberately first.
  lifecycle {
    prevent_destroy = true
  }
}

# With local authentication disabled there is no connection string, so even an
# account owner cannot read data without one of these. 00000000-...-0002 is the
# built-in Cosmos DB Data Contributor role.
resource "azapi_resource" "container" {
  for_each = var.containers

  type      = "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15"
  name      = each.key
  parent_id = azurerm_cosmosdb_sql_database.this.id

  body = {
    properties = {
      # Autoscale rather than manual throughput. Manual bottoms out at 400 RU/s
      # per container, so three containers would provision 1200 against a
      # 1000 RU/s free-tier allowance. Autoscale idles at 10% of its maximum,
      # so the same three sit at 300 RU/s and stay inside the free tier.
      options = {
        autoscaleSettings = {
          maxThroughput = each.value.autoscale_max_throughput
        }
      }

      resource = {
        id = each.key

        partitionKey = {
          paths = [each.value.partition_key_path]
          kind  = "Hash"
        }

        vectorEmbeddingPolicy = {
          vectorEmbeddings = [{
            path             = each.value.vector_path
            dataType         = "float32"
            distanceFunction = each.value.distance_function
            dimensions       = each.value.dimensions
          }]
        }

        indexingPolicy = {
          indexingMode  = "consistent"
          automatic     = true
          includedPaths = [{ path = "/*" }]

          # Excluding the vector path from the normal index is not optional:
          # indexing hundreds of floats as ordinary scalar properties costs
          # enormous RU and storage for an index nothing ever queries.
          #
          # Cosmos always adds the _etag exclusion itself, so declaring it here
          # too keeps config matching reality instead of planning to strip it
          # on every run.
          excludedPaths = [
            { path = "${each.value.vector_path}/*" },
            { path = "/\"_etag\"/?" },
          ]

          vectorIndexes = [{
            path = each.value.vector_path
            type = each.value.index_type
          }]
        }
      }
    }
  }
}

resource "azurerm_cosmosdb_sql_role_assignment" "data_contributor" {
  for_each = toset(var.data_plane_principal_ids)

  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
  role_definition_id  = "${azurerm_cosmosdb_account.this.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = each.value
  scope               = azurerm_cosmosdb_account.this.id
}
