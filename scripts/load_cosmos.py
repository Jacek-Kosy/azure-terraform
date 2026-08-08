#!/usr/bin/env python3
"""Load an embedded corpus into a Cosmos DB vector container, and query it.

The account sets local_authentication_enabled = false, so there is no key or
connection string: authentication is Entra ID via `az login`, and the caller
needs the built-in Cosmos DB Data Contributor role, which environments/dev
grants to whoever applies it.

    export COSMOS_ENDPOINT="$(terraform -chdir=environments/dev output -raw cosmos_endpoint)"
    python3 scripts/load_cosmos.py --container chunks_diskann
    python3 scripts/load_cosmos.py --container chunks_diskann --query "why does my board reset"

Documents are written with the vector under /embedding and partitioned by
/topic, matching the container's vector embedding policy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from azure.cosmos import CosmosClient, exceptions
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI
except ImportError as exc:  # pragma: no cover - dependency guidance
    sys.exit(f"missing dependency ({exc.name}): pip install -r scripts/requirements.txt")

API_VERSION = "2024-10-21"
SCOPE = "https://cognitiveservices.azure.com/.default"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/arduino-basics-505.embeddings.jsonl"))
    parser.add_argument("--endpoint", default=os.environ.get("COSMOS_ENDPOINT"))
    parser.add_argument("--database", default="vectordb")
    parser.add_argument("--container", required=True)
    parser.add_argument("--query", help="run a vector search instead of loading")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--topic", help="restrict a query to one partition")
    parser.add_argument(
        "--openai-endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        help="required only with --query, to embed the query text",
    )
    parser.add_argument("--deployment", default="text-embedding-3-small")
    return parser.parse_args()


def get_container(args, credential):
    client = CosmosClient(args.endpoint, credential=credential)
    return client.get_database_client(args.database).get_container_client(args.container)


def load(args, container, credential) -> int:
    if not args.input.exists():
        sys.exit(f"{args.input}: not found. Run scripts/embed_chunks.py first.")

    written = 0
    with args.input.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            # The partition key must be present as a real property, not just
            # supplied at call time, or Cosmos rejects the document.
            document = {
                "id": record["id"],
                "topic": record["topic"],
                "title": record["title"],
                "text": record["text"],
                "embedding": record["embedding"],
            }
            try:
                container.upsert_item(document)
            except exceptions.CosmosHttpResponseError as exc:
                sys.exit(f"{record['id']}: {exc.message}")
            written += 1
            if written % 200 == 0:
                print(f"  {written} written", file=sys.stderr)

    print(f"loaded {written} documents into {args.container}", file=sys.stderr)
    return written


def query(args, container) -> int:
    if not args.openai_endpoint:
        sys.exit("--query needs --openai-endpoint or $AZURE_OPENAI_ENDPOINT to embed the query")

    dimensions = len(next(iter(peek_embedding(container))))
    openai = AzureOpenAI(
        azure_endpoint=args.openai_endpoint,
        api_version=API_VERSION,
        azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), SCOPE),
    )
    vector = openai.embeddings.create(
        model=args.deployment, input=[args.query], dimensions=dimensions
    ).data[0].embedding

    where = "WHERE c.topic = @topic" if args.topic else ""
    sql = (
        f"SELECT TOP @top c.id, c.topic, c.title, "
        f"VectorDistance(c.embedding, @vector) AS score FROM c {where} "
        f"ORDER BY VectorDistance(c.embedding, @vector)"
    )
    params = [{"name": "@vector", "value": vector}, {"name": "@top", "value": args.top}]
    if args.topic:
        params.append({"name": "@topic", "value": args.topic})

    results = list(
        container.query_items(query=sql, parameters=params, enable_cross_partition_query=True)
    )
    charge = container.client_connection.last_response_headers.get("x-ms-request-charge", "?")

    print(f"\nQ: {args.query}   [{args.container}, {charge} RU]")
    for item in results:
        print(f"   {item['score']:.4f}  [{item['topic']}] {item['title']}")
    return 0


def peek_embedding(container):
    """Read one stored vector to discover the container's dimensionality."""
    rows = list(container.query_items(
        query="SELECT TOP 1 c.embedding FROM c", enable_cross_partition_query=True
    ))
    if not rows:
        sys.exit("container is empty: load it before querying")
    return [rows[0]["embedding"]]


def main() -> int:
    args = parse_args()
    if not args.endpoint:
        sys.exit("no endpoint: pass --endpoint or set COSMOS_ENDPOINT")

    credential = DefaultAzureCredential()
    container = get_container(args, credential)

    if args.query:
        return query(args, container)
    load(args, container, credential)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
