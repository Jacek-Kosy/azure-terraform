# Bootstrap — Terraform state backend

Creates the remote state backend that `environments/dev` and `environments/prod`
use. It is the only stack with local state, because it builds the storage the
other stacks depend on.

## What it manages

| Resource | Name |
| --- | --- |
| Subscription | `az-subscription-jacek` (`964eeda7-d407-48de-a969-ba555d0afd1e`) |
| Tenant | `060d8650-91b9-468e-bfb1-b03f1a30221d` |
| Resource group | `rg-tfstate` (westeurope) |
| Storage account | `sttfstate964eeda7` (northeurope) |
| Blob container | `tfstate` |
| Role assignment | `Storage Blob Data Owner` for the applying principal |

`rg-tfstate` already existed in the subscription, so [imports.tf](imports.tf)
adopts it instead of creating it. The first plan shows the resource group being
imported and tagged, not replaced.

## Apply

```bash
az account set --subscription 964eeda7-d407-48de-a969-ba555d0afd1e
```

```bash
terraform -chdir=bootstrap init && terraform -chdir=bootstrap apply
```

The storage account name must be globally unique. If `sttfstate964eeda7` is
taken, change `state_storage_account_name` here **and** the matching literal in
both `environments/*/main.tf` backend blocks — backend blocks cannot read
variables.

Applying this registers the `Microsoft.Storage` resource provider in the
subscription, which is currently `NotRegistered`. The azurerm provider does that
automatically on first use.

## Notes

- State is local by default. To move it into the backend it just created,
  uncomment the `backend "azurerm"` block in [main.tf](main.tf) and run
  `terraform init -migrate-state`.
- The backends authenticate with Entra ID (`use_azuread_auth`). Subscription
  Owner does not grant blob data access on its own, which is why the role
  assignment exists. If `terraform init` in an environment fails with a 403 on
  the blob endpoint, the role has not propagated yet — wait a minute, or drop
  `use_azuread_auth` from that backend block to fall back to the account key.
- The storage account sits in `northeurope`, not in the resource group's
  `westeurope`. A resource group is only metadata, so this is allowed, and
  westeurope currently rejects new customers with
  `RequestDisallowedByAzure: The selected region is currently not accepting new
  customers`. Anything else this subscription creates in westeurope will hit the
  same wall — see https://aka.ms/locationineligible.
- Deleting this stack orphans every other stack's state. Consider a
  `CanNotDelete` lock on the storage account before real workloads land.
