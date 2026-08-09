# Azure Container App Module

Creates a container registry, a Log Analytics workspace, a Container App
environment, a user-assigned managed identity, and the Container App itself.

## Decisions worth knowing

- **Keyless.** `admin_enabled` is false on the registry. The app pulls with its
  managed identity, and operators push with their own Entra ID login through
  `AcrPush`. No registry username or password exists to leak.
- **The caller assigns data-plane roles.** The module exports
  `identity_principal_id` and grants only `AcrPull` itself; only the caller knows
  what else the app must reach.
- **Scales to zero** by default (`min_replicas = 0`), so an idle app costs
  nothing beyond the registry. The first request after idling pays a cold start.
- **`logs_destination` is set explicitly.** azurerm 5.x rejects
  `log_analytics_workspace_id` on its own with "can only be set when
  logs_destination is set to log-analytics".

## Images must be linux/amd64

Azure Container Apps runs x86-64 images only. Building on an arm64 machine
without `--platform linux/amd64` produces an image that pushes successfully and
then crash-loops with an exec format error, reported only as
`startup probe failed: connection refused` in the system log.

```bash
docker buildx build --platform linux/amd64 -t <registry>.azurecr.io/<image>:<tag> --push .
```

## Bootstrapping order

The Container App cannot start without an image that already exists, but the
registry does not exist until the first apply. Apply once with a public
placeholder image, push, then apply again with the real reference.

Changing `container_image` is what rolls a new revision, so each build needs a
new tag. Re-pushing an existing tag leaves the Terraform configuration unchanged
and nothing redeploys.

## Subscription limits

New subscriptions are capped at **one Container App Environment**. A second
creation fails with `MaxNumberOfGlobalEnvironmentsInSubExceeded`, and the
existing environment may well be in another resource group entirely.
