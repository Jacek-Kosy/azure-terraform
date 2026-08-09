output "fqdn" {
  description = "Public hostname of the Container App"
  value       = azurerm_container_app.this.ingress[0].fqdn
}

output "url" {
  description = "Public URL of the Container App"
  value       = "https://${azurerm_container_app.this.ingress[0].fqdn}"
}

output "identity_principal_id" {
  description = "Principal ID of the app's managed identity. Pass to modules that must grant it data-plane access."
  value       = azurerm_user_assigned_identity.app.principal_id
}

output "identity_client_id" {
  description = "Client ID of the app's managed identity, as passed to the container as AZURE_CLIENT_ID"
  value       = azurerm_user_assigned_identity.app.client_id
}

output "registry_name" {
  description = "Container registry name, for `az acr login`"
  value       = azurerm_container_registry.this.name
}

output "registry_login_server" {
  description = "Registry hostname, for tagging images"
  value       = azurerm_container_registry.this.login_server
}
