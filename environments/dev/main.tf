terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }

    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.11"
    }
  }

  # Backend blocks cannot use variables, so these values are literals. They must
  # match the bootstrap stack — see `backend_config` in bootstrap/outputs.tf.
  # Requires bootstrap to have been applied first.
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstate964eeda7"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
    subscription_id      = "964eeda7-d407-48de-a969-ba555d0afd1e"
    tenant_id            = "060d8650-91b9-468e-bfb1-b03f1a30221d"
    use_azuread_auth     = true
  }
}

provider "azurerm" {
  features {}

  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

provider "azapi" {
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
}

data "azurerm_client_config" "current" {}

module "resource_group" {
  source = "../../modules/azure-resource-group"

  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "openai" {
  source = "../../modules/azure-openai"

  name                = var.openai_account_name
  resource_group_name = module.resource_group.resource_group_name
  location            = var.openai_location
  tags                = var.tags

  deployments = {
    "text-embedding-3-small" = {
      model_name    = "text-embedding-3-small"
      model_version = "1"
      sku_name      = "GlobalStandard"
      capacity      = var.embedding_capacity
    }
  }
}

# The account has local_auth_enabled = false, so a data-plane role is the only
# way to call it. Owner on the subscription does not imply this.
resource "azurerm_role_assignment" "openai_user" {
  scope                = module.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = data.azurerm_client_config.current.object_id
}

module "cosmosdb" {
  source = "../../modules/azure-cosmosdb"

  name                = var.cosmos_account_name
  resource_group_name = module.resource_group.resource_group_name
  location            = var.cosmos_location
  database_name       = var.cosmos_database_name
  database_throughput = var.cosmos_database_throughput
  containers = {
    for name, container in var.cosmos_containers :
    name => merge(container, { autoscale_max_throughput = var.cosmos_container_autoscale_max })
  }
  tags = var.tags

  # Grants the applying principal read/write on documents. Without it the portal
  # Data Explorer cannot show anything either, since keys are disabled.
  data_plane_principal_ids = [data.azurerm_client_config.current.object_id]

  # The app only ever queries, so it gets Data Reader rather than Contributor.
  data_plane_reader_principal_ids = { app = module.container_app.identity_principal_id }
}

module "container_app" {
  source = "../../modules/azure-container-app"

  name                = var.app_name
  resource_group_name = module.resource_group.resource_group_name
  location            = var.location
  registry_name       = var.registry_name
  container_image     = var.container_image
  tags                = var.tags

  # Configure registry authentication only once container_image actually points
  # at our registry. On the first apply it is still the public placeholder, and
  # declaring credentials for a registry holding no image just fails the pull.
  # Computed from the name rather than the module's own output, which would be
  # a circular reference.
  registry_login_server = startswith(var.container_image, "${var.registry_name}.azurecr.io") ? "${var.registry_name}.azurecr.io" : null

  # Whoever applies this builds and pushes the image from their own machine.
  image_push_principal_ids = [data.azurerm_client_config.current.object_id]

  environment_variables = {
    COSMOS_ENDPOINT       = module.cosmosdb.endpoint
    COSMOS_DATABASE       = module.cosmosdb.database_name
    AZURE_OPENAI_ENDPOINT = module.openai.endpoint
    EMBEDDING_DEPLOYMENT  = "text-embedding-3-small"
    CONTAINER_NAMES       = join(",", module.cosmosdb.container_names)
    VECTOR_DIMENSIONS     = tostring(var.cosmos_vector_dimensions)
  }
}

# The app calls the embeddings endpoint to vectorise each incoming query.
resource "azurerm_role_assignment" "app_openai_user" {
  scope                = module.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = module.container_app.identity_principal_id
}
