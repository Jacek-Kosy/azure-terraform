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

# Throughput is shared across every container in this database. That suits
# side-by-side index comparisons, where several containers hold the same data
# under different index types and none needs dedicated capacity.
#
# Throughput must be set at creation: changing it later requires destroying and
# recreating the database.
resource "azurerm_cosmosdb_sql_database" "this" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
  throughput          = var.database_throughput

  # Guards the documents inside. Note this also means changing
  # database_throughput, which Cosmos can only do by recreating the database,
  # requires removing this block first.
  lifecycle {
    prevent_destroy = true
  }
}

# With local authentication disabled there is no connection string, so even an
# account owner cannot read data without one of these. 00000000-...-0002 is the
# built-in Cosmos DB Data Contributor role.
resource "azurerm_cosmosdb_sql_role_assignment" "data_contributor" {
  for_each = toset(var.data_plane_principal_ids)

  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name
  role_definition_id  = "${azurerm_cosmosdb_account.this.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = each.value
  scope               = azurerm_cosmosdb_account.this.id
}
