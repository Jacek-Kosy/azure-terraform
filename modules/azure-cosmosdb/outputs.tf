output "id" {
  description = "Resource ID of the Cosmos DB account"
  value       = azurerm_cosmosdb_account.this.id
}

output "name" {
  description = "Name of the Cosmos DB account"
  value       = azurerm_cosmosdb_account.this.name
}

output "endpoint" {
  description = "Account endpoint URL"
  value       = azurerm_cosmosdb_account.this.endpoint
}

output "database_name" {
  description = "Name of the SQL database"
  value       = azurerm_cosmosdb_sql_database.this.name
}

output "container_names" {
  description = "Vector container names created on the database"
  value       = sort(keys(azapi_resource.container))
}

output "containers" {
  description = "Vector containers with the index type and dimensions each was built with"
  value       = { for name, c in var.containers : name => { index_type = c.index_type, dimensions = c.dimensions } }
}

output "identity_principal_id" {
  description = "Principal ID of the account's system-assigned identity"
  value       = azurerm_cosmosdb_account.this.identity[0].principal_id
}
