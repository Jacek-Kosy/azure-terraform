output "resource_group_name" {
  description = "Development resource group name"
  value       = module.resource_group.resource_group_name
}

output "resource_group_id" {
  description = "Development resource group ID"
  value       = module.resource_group.resource_group_id
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint. Export as AZURE_OPENAI_ENDPOINT for scripts/embed_chunks.py."
  value       = module.openai.endpoint
}

output "openai_account_name" {
  description = "Azure OpenAI account name"
  value       = module.openai.name
}

output "embedding_deployment_name" {
  description = "Deployment name to pass as the model id when calling the embeddings API"
  value       = "text-embedding-3-small"
}

output "cosmos_endpoint" {
  description = "Cosmos DB account endpoint. Export as COSMOS_ENDPOINT for the app."
  value       = module.cosmosdb.endpoint
}

output "cosmos_account_name" {
  description = "Cosmos DB account name"
  value       = module.cosmosdb.name
}

output "cosmos_database_name" {
  description = "Cosmos DB SQL database holding the vector containers"
  value       = module.cosmosdb.database_name
}

output "cosmos_containers" {
  description = "Vector containers with the index type and dimensions each was built with"
  value       = module.cosmosdb.containers
}
