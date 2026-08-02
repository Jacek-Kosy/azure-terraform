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
- environments/dev/: development environment entry point, including Azure OpenAI embeddings
- environments/prod/: production environment entry point
- data/: source corpora to embed
- shared/: common conventions, policies, and helper configuration
- scripts/: operational helpers
- docs/: implementation notes

## Regions

`westeurope` is closed to new customers in this subscription and rejects new
resources with `RequestDisallowedByAzure`. Both environments default to
`northeurope`. The one exception is the `rg-tfstate` resource group, which
predates this catalog and stays in `westeurope` — a resource group only holds
metadata, so the storage account inside it sits in `northeurope` regardless.

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

## Checks

[.github/workflows/terraform-checks.yml](.github/workflows/terraform-checks.yml)
runs on every push: `terraform fmt`, `validate` across all five stacks, tflint
with the azurerm ruleset, and a trivy config scan failing on HIGH or CRITICAL.

**It never runs plan or apply and holds no Azure credentials.** Deployment stays
a deliberate local action. `validate` works credential-free because it runs
`init -backend=false`; wiring CI up to Azure would mean OIDC federated
credentials, which is a separate decision.

To reproduce the same checks locally:

```bash
terraform fmt -check -recursive -diff
```

```bash
docker run --rm -v "$PWD":/data -w /data --entrypoint sh ghcr.io/terraform-linters/tflint:v0.64.0 -c 'tflint --init >/dev/null && tflint --recursive --config=/data/.tflint.hcl'
```

```bash
docker run --rm -v "$PWD":/data aquasec/trivy:0.72.0 config /data --severity HIGH,CRITICAL --exit-code 1
```

One trivy finding is suppressed in place, with its reasoning, at the storage
account in [bootstrap/main.tf](bootstrap/main.tf): `AVD-AZU-0012` wants a
network `default_action` of `Deny`, which would lock the state backend to a
single IP address and break `terraform init` elsewhere. The real fix is a
private endpoint.

## Embedding the corpus

The dev environment provisions an Azure OpenAI account with a
`text-embedding-3-small` deployment. After applying dev, embed the 200-chunk
Arduino corpus in [data/arduino-basics.jsonl](data/arduino-basics.jsonl):

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
```

```bash
export AZURE_OPENAI_ENDPOINT="$(terraform -chdir=environments/dev output -raw openai_endpoint)" && .venv/bin/python scripts/embed_chunks.py
```

See [scripts/README.md](scripts/README.md) for options and authentication
details.
