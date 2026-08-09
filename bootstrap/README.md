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
the backend blocks of [main.tf](main.tf) and both `environments/*/main.tf` —
backend blocks cannot read variables.

`Microsoft.Storage` and `Microsoft.CognitiveServices` are already registered in
this subscription. In a fresh one the azurerm provider registers what it needs
on first use, which adds a few minutes to the first apply.

## Notes

- This stack stores its state in the storage account it creates, under the key
  `bootstrap.terraform.tfstate`. That is circular, and deliberate: it keeps the
  state off any single workstation, where losing it would mean re-importing
  every backend resource by hand.
- The circularity is contained by `prevent_destroy` on the storage account and
  the container. `terraform destroy` fails with `Instance cannot be destroyed`
  until someone removes those lifecycle blocks, which is the intended friction.
- Bootstrapping a subscription that has no state storage account yet is the one
  case needing local state: comment out the `backend "azurerm"` block, apply
  once, uncomment it, then run `terraform init -migrate-state`.
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
- `prevent_destroy` guards against Terraform, not against Azure. A portal
  deletion or an `az` command still removes the account and every stack's state
  with it. Add a `CanNotDelete` management lock before real workloads land.
