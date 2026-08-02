resource "azurerm_cognitive_account" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  kind                = "OpenAI"
  sku_name            = var.sku_name

  # Entra ID token auth only works on accounts with a custom subdomain; it also
  # becomes the endpoint host, <subdomain>.openai.azure.com.
  custom_subdomain_name = coalesce(var.custom_subdomain_name, var.name)

  local_auth_enabled            = var.local_auth_enabled
  public_network_access_enabled = var.public_network_access_enabled

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "this" {
  for_each = var.deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }

  # Vectors from two model versions are not comparable, so a silent upgrade
  # would invalidate every embedding already stored against this deployment.
  version_upgrade_option = "NoAutoUpgrade"
}
