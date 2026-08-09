output "subscription_id" {
  description = "Subscription the state backend lives in"
  value       = var.subscription_id
}

output "state_resource_group_name" {
  description = "Resource group holding the Terraform state backend"
  value       = module.state_resource_group.resource_group_name
}

output "state_resource_group_id" {
  description = "Resource ID of the state backend resource group"
  value       = module.state_resource_group.resource_group_id
}

output "state_storage_account_name" {
  description = "Storage account holding the Terraform state"
  value       = azurerm_storage_account.state.name
}

output "state_container_name" {
  description = "Blob container holding the Terraform state files"
  value       = azurerm_storage_container.state.name
}

output "backend_config" {
  description = "Values the environment backend blocks must match"
  value = {
    resource_group_name  = module.state_resource_group.resource_group_name
    storage_account_name = azurerm_storage_account.state.name
    container_name       = azurerm_storage_container.state.name
    subscription_id      = var.subscription_id
    tenant_id            = var.tenant_id
  }
}
