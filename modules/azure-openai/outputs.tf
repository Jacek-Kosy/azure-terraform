output "id" {
  description = "Resource ID of the Azure OpenAI account"
  value       = azurerm_cognitive_account.this.id
}

output "name" {
  description = "Name of the Azure OpenAI account"
  value       = azurerm_cognitive_account.this.name
}

output "endpoint" {
  description = "Base endpoint URL for the account"
  value       = azurerm_cognitive_account.this.endpoint
}

output "identity_principal_id" {
  description = "Principal ID of the account's system-assigned identity"
  value       = azurerm_cognitive_account.this.identity[0].principal_id
}

output "deployment_names" {
  description = "Deployment names created on this account"
  value       = sort(keys(azurerm_cognitive_deployment.this))
}
