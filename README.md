# Azure Terraform Catalog

This workspace provides a starter catalog structure for Terraform-based Azure deployments.

## Target subscription

Every stack is pinned to a single subscription and tenant:

| | |
| --- | --- |
| Subscription | `az-subscription-jacek` |
| Subscription ID | `964eeda7-d407-48de-a969-ba555d0afd1e` |
| Tenant ID | `060d8650-91b9-468e-bfb1-b03f1a30221d` |

The IDs are defaults on the `subscription_id` / `tenant_id` variables in each
stack and are set explicitly on every `provider "azurerm"` block, so an apply
cannot silently follow whatever subscription the Azure CLI happens to have
selected.

## Structure
- bootstrap/: remote state backend (`rg-tfstate`), applied once before anything else
- modules/: reusable Terraform modules
- environments/dev/: development environment entry point
- environments/prod/: production environment entry point
- shared/: common conventions, policies, and helper configuration
- scripts/: operational helpers
- docs/: implementation notes

## Getting started

1. Sign in and select the subscription:

```bash
az login --tenant 060d8650-91b9-468e-bfb1-b03f1a30221d && az account set --subscription 964eeda7-d407-48de-a969-ba555d0afd1e
```

2. Create the state backend. This is required before any environment can
   `init`, since they store state in the storage account it creates. See
   [bootstrap/README.md](bootstrap/README.md).

```bash
terraform -chdir=bootstrap init && terraform -chdir=bootstrap apply
```

3. Initialize an environment against the remote backend:

```bash
terraform -chdir=environments/dev init
```

```bash
terraform -chdir=environments/dev plan
```
