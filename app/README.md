# Vector search app

A small FastAPI front end over the Cosmos DB vector containers, deployed to Azure
Container Apps.

- **Search** answers a question from the 1,010 hand-written Arduino chunks,
  filtered to `WHERE c.synthetic = false` so generated filler is never returned
  as an answer.
- **Compare** runs the same query and the same embedding against all three
  indexes over the whole corpus, reporting request charge, latency, and recall
  measured against `flat`, which is exhaustive and therefore exact.
- **Topic filter** narrows either mode to one topic, combining `VectorDistance`
  with a `WHERE` clause.

## The topic filter

`/topic` is the containers' partition key, so a topic filter does more than
drop rows. Passing `partition_key=` to `query_items` routes the query to a
single physical partition instead of fanning out across all of them and merging
— the same SQL without it returns identical rows for more RU.

The filter is also the one control that changes *which index wins*, so the
comparison is worth running both ways. Measured numbers and the reasoning are
in [../docs/filtered-vector-search.md](../docs/filtered-vector-search.md).

No indexing policy change was needed for any of this: `includedPaths: ["/*"]`
already indexes `topic`, and filtered vector search needs no composite index.

## No generated answers

The app returns ranked source passages, not a generated answer. The only model
deployment is `text-embedding-3-small`.

This was once forced: the subscription had no chat quota in any region. **That is
no longer true.** Checked 2026-08-09 against the existing northeurope account:

| | |
| --- | --- |
| `gpt-5.4`, `gpt-5.4-mini` | `GlobalStandard`, deployable on this account |
| Quota | 1,000k TPM, none of it used |
| RBAC | none needed — `Cognitive Services OpenAI User` already covers chat completions |

So adding generation is a `deployments` entry in
[../modules/azure-openai](../modules/azure-openai/) and an app endpoint reusing
`search()` and `embed()`, not new infrastructure. Re-check before relying on it;
quota moves.

## Authentication

Nothing here holds a credential. Cosmos and Azure OpenAI both have key auth
disabled, and the app's user-assigned managed identity holds
`Cognitive Services OpenAI User` and the Cosmos **Data Reader** role — read-only,
since the app never writes.

`AZURE_CLIENT_ID` is passed to the container because `DefaultAzureCredential`
cannot otherwise tell which identity to use.

## Building and deploying

ACR Tasks needs a quota increase on this subscription, so the image is built
locally and pushed.

```bash
az acr login --name "$(terraform -chdir=../environments/dev output -raw registry_name)"
```

```bash
docker buildx build --platform linux/amd64 -t acrdevvectordb964eeda7.azurecr.io/vectorsearch:v3 --push .
```

**`--platform linux/amd64` is not optional.** Azure Container Apps runs x86-64
images only. On an arm64 machine a plain `docker build` pushes successfully and
then crash-loops with an exec format error, which is a slow way to find out.
Verify before deploying:

```bash
docker manifest inspect acrdevvectordb964eeda7.azurecr.io/vectorsearch:v3
```

Then bump `container_image` in `environments/dev/variables.tf` to the new tag and
apply. A new tag is required: re-pushing the same tag leaves the Terraform config
unchanged, so no new revision is created.

```bash
terraform -chdir=../environments/dev apply
```

`az acr login` tokens last about three hours; a `401 Unauthorized` on push means
it expired.

## Running locally

The app reads the same environment variables locally and authenticates as
whoever is signed in with `az login`.

```bash
COSMOS_ENDPOINT="$(terraform -chdir=../environments/dev output -raw cosmos_endpoint)" AZURE_OPENAI_ENDPOINT="$(terraform -chdir=../environments/dev output -raw openai_endpoint)" COSMOS_DATABASE=vectordb CONTAINER_NAMES=chunks_flat,chunks_quantized,chunks_diskann VECTOR_DIMENSIONS=505 uvicorn main:app --reload
```

## Diagnosing a failed deployment

```bash
az containerapp logs show -n vectorsearch -g rg-dev-vectordb --type console --tail 40
```

The system log (`--type system`) shows image pulls and probe failures; the
console log shows the application's own output. A replica stuck on
`startup probe failed: connection refused` means the process died before binding
its port, and the console log carries the traceback.
