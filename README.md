# Azure Terraform Catalog

This workspace provides a starter catalog structure for Terraform-based Azure deployments.

## Structure
- modules/: reusable Terraform modules
- environments/dev/: development environment entry point
- environments/prod/: production environment entry point
- shared/: common conventions, policies, and helper configuration
- scripts/: operational helpers
- docs/: implementation notes

## Getting started
1. Review the module and environment examples.
2. Copy the example variable files and adjust values.
3. Initialize Terraform for an environment:

```bash
terraform -chdir=environments/dev init
terraform -chdir=environments/dev plan
```
