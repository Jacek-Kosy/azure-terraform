# One identity the app uses for everything: pulling its own image, calling Azure
# OpenAI, and reading Cosmos. The caller assigns the data-plane roles, since only
# it knows what the app needs to reach.
resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.name}-identity"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_container_registry" "this" {
  name                = var.registry_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.registry_sku

  # Keyless like everything else here: pulls go through the app's managed
  # identity and pushes through the operator's Entra ID login.
  admin_enabled = false

  tags = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Whoever applies this also builds and pushes the image. Subscription Owner
# happens to permit it, but granting AcrPush explicitly matches how every other
# data-plane permission in this repo is handled.
resource "azurerm_role_assignment" "acr_push" {
  for_each = toset(var.image_push_principal_ids)

  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = each.value
}

# Container App environments require a Log Analytics workspace for console and
# system logs; there is no way to run one without it.
resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.name}-logs"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                = "${var.name}-env"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  # azurerm 5.x rejects log_analytics_workspace_id unless the destination is
  # named explicitly; the workspace alone is not enough to imply it.
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "this" {
  name                         = var.name
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  # Pull with the managed identity rather than a registry username and password,
  # which is why admin_enabled is false on the registry.
  dynamic "registry" {
    for_each = var.registry_login_server == null ? [] : [var.registry_login_server]
    content {
      server   = registry.value
      identity = azurerm_user_assigned_identity.app.id
    }
  }

  ingress {
    external_enabled = true
    target_port      = var.target_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Scales to zero when idle, which is what keeps a demo app free between uses.
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = var.name
      image  = var.container_image
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = var.environment_variables
        content {
          name  = env.key
          value = env.value
        }
      }

      # DefaultAzureCredential cannot tell which identity to use when more than
      # one is available, so the client id has to be passed explicitly.
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }
    }
  }

  # The image is pushed after the registry exists, so the first apply runs a
  # placeholder. Ignoring the image afterwards would hide real changes, so it is
  # deliberately not ignored: re-apply with the new tag to roll the revision.
  depends_on = [azurerm_role_assignment.acr_pull]
}
