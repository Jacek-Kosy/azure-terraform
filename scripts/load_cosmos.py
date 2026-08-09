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
import time
from concurrent.futures import ThreadPoolExecutor
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
    parser.add_argument("--offset", type=int, default=0, help="skip this many records")
    parser.add_argument("--limit", type=int, help="load at most this many records")
    parser.add_argument(
        "--workers",
        type=int,
        default=32,
        help="concurrent writers; each upsert is one request, so this dominates load time",
    )
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


def read_documents(args):
    with args.input.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            if index < args.offset:
                continue
            if args.limit is not None and index >= args.offset + args.limit:
                return
            record = json.loads(line)
            # The partition key must exist as a real property on the document,
            # not merely be supplied at call time, or Cosmos rejects the write.
            yield {
                "id": record["id"],
                "topic": record["topic"],
                "title": record["title"],
                "text": record["text"],
                "embedding": record["embedding"],
                # Carried through so a query can exclude generated filler, which
                # is combinatorial nonsense and must never be served as an
                # answer.
                #
                # Written on every document since this line existed, but most of
                # the loaded filler predates it and has no such property. Query
                # for `synthetic = false` to get the hand-written corpus; do not
                # query for `synthetic = true` expecting all the filler. The
                # id prefix (ard- against syn-) is the reliable discriminator.
                "synthetic": bool(record.get("synthetic", False)),
            }


def load(args, container, credential) -> int:
    if not args.input.exists():
        sys.exit(f"{args.input}: not found. Run scripts/embed_chunks.py first.")

    documents = list(read_documents(args))
    if not documents:
        sys.exit("nothing to load: check --offset and --limit against the input size")

    written = 0
    failures: list[str] = []

    # Request charge is read from each response rather than from
    # container.client_connection.last_response_headers afterwards: that
    # attribute is shared mutable state, and these upserts run on many threads.
    # list.append is atomic under the GIL, so collecting into one is safe.
    charges: list[float] = []

    def upsert(document):
        try:
            container.upsert_item(
                document,
                response_hook=lambda headers, _: charges.append(
                    float(headers.get("x-ms-request-charge", 0))
                ),
            )
            return None
        except exceptions.CosmosHttpResponseError as exc:
            return f"{document['id']}: {exc.message}"

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for error in pool.map(upsert, documents):
            written += 1
            if error:
                failures.append(error)
            if written % 5000 == 0:
                rate = written / (time.monotonic() - started)
                print(f"  {written:,} written ({rate:.0f}/s)", file=sys.stderr)

    elapsed = time.monotonic() - started
    if failures:
        print(f"{len(failures)} failures, first: {failures[0]}", file=sys.stderr)
        return 1

    total_ru = sum(charges)
    print(
        f"loaded {written:,} documents into {args.container} "
        f"in {elapsed:.0f}s ({written / elapsed:.0f}/s)",
        file=sys.stderr,
    )
    # Writing a vector is far dearer than reading one, and the per-document
    # figure is what says whether a corpus this size fits the provisioned
    # throughput. A query over the same container costs single-digit RU.
    if charges:
        print(
            f"  {total_ru:,.0f} RU total, {total_ru / len(charges):.1f} RU per document, "
            f"{total_ru / elapsed:,.0f} RU/s sustained",
            file=sys.stderr,
        )
    return 0


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

    # Naming the partition key rather than merely filtering on it is what makes
    # a topic-scoped query cheap: Cosmos routes to one physical partition
    # instead of fanning out to all of them and merging the results.
    routing = {"partition_key": args.topic} if args.topic else {"enable_cross_partition_query": True}
    results = list(container.query_items(query=sql, parameters=params, **routing))
    charge = container.client_connection.last_response_headers.get("x-ms-request-charge", "?")

    scope = f", topic={args.topic}" if args.topic else ""
    print(f"\nQ: {args.query}   [{args.container}{scope}, {charge} RU]")
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
    return load(args, container, credential)


if __name__ == "__main__":
    raise SystemExit(main())
