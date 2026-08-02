# rg-tfstate already existed in the subscription before this catalog was
# written, so it is adopted into state rather than created. The block is a
# no-op once the resource is in state, and safe to delete afterwards.
#
# Import IDs must be literal strings on Terraform 1.5, so the subscription ID is
# repeated here rather than referencing var.subscription_id.
#
# Bootstrapping a *different* subscription? Delete this file first, otherwise
# the apply fails on a resource group that does not exist yet.
import {
  to = module.state_resource_group.azurerm_resource_group.this
  id = "/subscriptions/964eeda7-d407-48de-a969-ba555d0afd1e/resourceGroups/rg-tfstate"
}
