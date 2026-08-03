# Azure Cosmos DB Module

Creates a Cosmos DB account on the NoSQL API with vector search enabled, plus a
SQL database with shared throughput and data-plane role assignments.

## What it does not do

**Containers are not created here.** `azurerm_cosmosdb_sql_container` has no
support for `vectorEmbeddingPolicy` or `vectorIndexes`, so a container declared
through azurerm cannot carry a vector index at all. Containers need either the
`azapi` provider or the Cosmos SDK from application code.

## Decisions worth knowing

- **Keyless.** `local_authentication_enabled` is `false`, so there is no
  connection string and no account key. Every caller authenticates with Entra ID
  and needs an entry in `data_plane_principal_ids`. Subscription Owner grants
  nothing at the data plane — including in the portal's Data Explorer, which
  will show an authorization error without a role assignment.
- **Free tier by default.** `free_tier_enabled` claims the subscription's single
  free-tier allowance: 1000 RU/s and 25 GB, permanently free. Only one account
  per subscription may hold it, and changing the setting forces the account to
  be replaced.
- **Shared database throughput.** Containers share the database's RU/s rather
  than reserving their own, which is what makes several containers holding the
  same data under different vector index types affordable.
- **Throughput is fixed at creation.** Changing `database_throughput` later
  requires destroying and recreating the database.

## Vector index types

Set per container, not here. The relevant limits:

| Type | Max dimensions | Behaviour |
| --- | --- | --- |
| `flat` | 505 | Exact search, full recall, vectors stored in the main index |
| `quantizedFlat` | 4096 | Compresses vectors, then exact search over the compressed form |
| `diskANN` | 4096 | Graph-based approximate search, built for scale |

Two constraints decide whether a comparison between them is meaningful:

- `text-embedding-3-small` produces 1536 dimensions, which **exceeds `flat`'s
  limit of 505**. Comparing against `flat` requires re-embedding at 505 or
  fewer, which `scripts/embed_chunks.py --dimensions` supports.
- `quantizedFlat` and `diskANN` **require at least 1000 vectors**. Below that
  Cosmos runs a full scan instead, so all three types behave identically and the
  comparison measures nothing.
