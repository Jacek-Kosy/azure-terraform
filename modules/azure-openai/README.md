# Azure OpenAI Module

Creates an Azure OpenAI (Cognitive Services, `kind = "OpenAI"`) account and any
number of model deployments on it.

## Usage

```hcl
module "openai" {
  source = "../../modules/azure-openai"

  name                = "oai-dev-964eeda7"
  resource_group_name = module.resource_group.resource_group_name
  location            = "northeurope"

  deployments = {
    "text-embedding-3-small" = {
      model_name    = "text-embedding-3-small"
      model_version = "1"
      sku_name      = "GlobalStandard"
      capacity      = 50
    }
  }
}
```

## Decisions worth knowing

- **Entra ID only.** `local_auth_enabled` defaults to `false`, so API keys are
  off and callers need a data-plane role such as `Cognitive Services OpenAI
  User`. Subscription Owner does not grant it. Set the variable to `true` if you
  need key auth.
- **A custom subdomain is always set** (defaults to `var.name`). Entra ID token
  auth does not work on regional endpoints, only on `<subdomain>.openai.azure.com`.
- **Deployments never auto-upgrade** (`version_upgrade_option = "NoAutoUpgrade"`).
  Embeddings from two model versions are not comparable, so an automatic upgrade
  would silently invalidate every vector already stored against the deployment.

## Region and quota

Model availability is per-region and narrower than general region availability.
Check before changing `location`:

```bash
az cognitiveservices model list -l northeurope --query "[?model.name=='text-embedding-3-small'].{version:model.version,skus:model.skus[].name}" -o json
```

```bash
az cognitiveservices usage list -l northeurope -o table
```

`capacity` is in thousands of tokens per minute and is drawn from the
subscription quota shown by the second command.
