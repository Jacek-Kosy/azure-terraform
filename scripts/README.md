# Scripts

Operational helpers. Install dependencies once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
```

## embed_chunks.py

Embeds a JSONL corpus with the dev Azure OpenAI embedding deployment and writes
the same records back with an `embedding` field added.

```bash
export AZURE_OPENAI_ENDPOINT="$(terraform -chdir=environments/dev output -raw openai_endpoint)"
```

```bash
.venv/bin/python scripts/embed_chunks.py
```

Defaults read [../data/arduino-basics.jsonl](../data/arduino-basics.jsonl) and
write `data/arduino-basics.embeddings.jsonl`, which is gitignored because it is
several megabytes of floats and is reproducible from the source corpus.

Useful flags:

| Flag | Purpose |
| --- | --- |
| `--input` / `--output` | Use a different corpus or destination |
| `--deployment` | Deployment name, default `text-embedding-3-small` |
| `--batch-size` | Texts per request, default 64. Lower it if the deployment returns 429 |
| `--dimensions` | Truncate vectors below the model's native 1536, trading recall for storage |

### Authentication

There is no API key. The Azure OpenAI account sets `local_auth_enabled = false`,
so the script authenticates with Entra ID via `DefaultAzureCredential` and needs
the caller to hold `Cognitive Services OpenAI User` on the account —
`environments/dev` grants that to whoever applies it.

Sign in first:

```bash
az login --tenant 060d8650-91b9-468e-bfb1-b03f1a30221d
```

A 401 usually means there is no Azure CLI session. A 403 means the role
assignment has not propagated yet, or the signed-in principal is not the one it
was granted to.

## generate_corpus.py

Builds a large synthetic corpus for benchmarking index behaviour at scale.

```bash
.venv/bin/python scripts/generate_corpus.py --count 50000
```

Text is assembled combinatorially from domain vocabulary rather than duplicated,
so vectors spread through the embedding space instead of clustering. **The
cause and remedy clauses are combined at random, so much of it is technically
nonsense.** It exists to give the index a realistic distribution of vectors to
search, not to be read. [../data/arduino-basics.jsonl](../data/arduino-basics.jsonl)
remains the corpus for anything about retrieval quality.

The seed is fixed, so the same corpus regenerates exactly.

## load_cosmos.py

Loads an embedded corpus into a Cosmos vector container, or queries one.

```bash
export COSMOS_ENDPOINT="$(terraform -chdir=environments/dev output -raw cosmos_endpoint)"
```

```bash
.venv/bin/python scripts/load_cosmos.py --container chunks_diskann --workers 64
```

```bash
.venv/bin/python scripts/load_cosmos.py --container chunks_diskann --query "why does my board reset" --top 5
```

`--offset` and `--limit` load a slice, which is how a corpus is grown in steps
to measure how the index comparison shifts with size.

Bulk loading throttles with `TooManyRequests` against the default 1000 RU/s
autoscale ceiling. Raise it for the load and lower it afterwards:

```bash
terraform -chdir=environments/dev apply -var cosmos_container_autoscale_max=10000
```

10000 is the per-container maximum Azure accepts here; higher requests are
capped silently. Leaving it raised costs real money, because the autoscale floor
is 10% of the ceiling per container and only the first 1000 RU/s across the
account is free.

## benchmark_indexes.py

Runs the same queries against every container and reports request charge,
latency, and recall measured against `flat`, which is exhaustive and therefore
exact.

```bash
.venv/bin/python scripts/benchmark_indexes.py
```

Run it after each load step. The comparison is only meaningful above 1000
vectors, below which Cosmos runs a full scan regardless of index type.
