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
