#!/usr/bin/env python3
"""Compare Cosmos DB vector index types at the corpus size currently loaded.

Runs the same queries against every container and reports request charge and
latency, so flat, quantizedFlat and diskANN can be compared with index type as
the only variable. Run it after each load step to see how the comparison shifts
with corpus size.

    export COSMOS_ENDPOINT="$(terraform -chdir=environments/dev output -raw cosmos_endpoint)"
    export AZURE_OPENAI_ENDPOINT="$(terraform -chdir=environments/dev output -raw openai_endpoint)"
    python3 scripts/benchmark_indexes.py

Recall is measured against flat, which is exhaustive and therefore exact: the
fraction of flat's top-k that an approximate index also returned.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI
except ImportError as exc:  # pragma: no cover - dependency guidance
    sys.exit(f"missing dependency ({exc.name}): pip install -r scripts/requirements.txt")

API_VERSION = "2024-10-21"
SCOPE = "https://cognitiveservices.azure.com/.default"

QUERIES = [
    "my board keeps resetting when the motor starts",
    "readings drift when the sun hits the enclosure",
    "how do I stop two identical chips clashing on the bus",
    "the device forgets its settings after a power cut",
    "serial output turns into random symbols",
    "battery dies far sooner than expected outdoors",
    "servo twitches constantly when it should be still",
    "display shows nothing but a row of blocks",
    "wifi drops out every few minutes",
    "sensor works on the bench but not in the field",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.environ.get("COSMOS_ENDPOINT"))
    parser.add_argument("--openai-endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT"))
    parser.add_argument("--database", default="vectordb")
    parser.add_argument(
        "--containers",
        nargs="+",
        default=["chunks_flat", "chunks_quantized", "chunks_diskann"],
        help="first is treated as the exact baseline for recall",
    )
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3, help="runs per query, best taken")
    parser.add_argument("--dimensions", type=int, default=505)
    return parser.parse_args()


def embed(openai, deployment, texts, dimensions):
    return [d.embedding for d in openai.embeddings.create(
        model=deployment, input=texts, dimensions=dimensions
    ).data]


def run_query(container, vector, top):
    sql = (
        "SELECT TOP @top c.id, VectorDistance(c.embedding, @vector) AS score "
        "FROM c ORDER BY VectorDistance(c.embedding, @vector)"
    )
    params = [{"name": "@vector", "value": vector}, {"name": "@top", "value": top}]
    started = time.monotonic()
    rows = list(container.query_items(
        query=sql, parameters=params, enable_cross_partition_query=True
    ))
    elapsed_ms = (time.monotonic() - started) * 1000
    charge = float(container.client_connection.last_response_headers.get("x-ms-request-charge", 0))
    return [r["id"] for r in rows], charge, elapsed_ms


def main() -> int:
    args = parse_args()
    if not args.endpoint or not args.openai_endpoint:
        sys.exit("set COSMOS_ENDPOINT and AZURE_OPENAI_ENDPOINT")

    credential = DefaultAzureCredential()
    database = CosmosClient(args.endpoint, credential=credential).get_database_client(args.database)
    containers = {name: database.get_container_client(name) for name in args.containers}

    openai = AzureOpenAI(
        azure_endpoint=args.openai_endpoint, api_version=API_VERSION,
        azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), SCOPE),
    )
    vectors = embed(openai, "text-embedding-3-small", QUERIES, args.dimensions)

    baseline_name = args.containers[0]
    counts = {}
    for name, container in containers.items():
        rows = list(container.query_items(
            query="SELECT VALUE COUNT(1) FROM c", enable_cross_partition_query=True
        ))
        counts[name] = rows[0] if rows else 0

    print(f"\ndocuments: " + ", ".join(f"{n}={c:,}" for n, c in counts.items()))
    print(f"top-{args.top}, {len(QUERIES)} queries, best of {args.repeats}\n")
    print(f"{'container':<20}{'RU (median)':>14}{'ms (median)':>14}{'recall vs ' + baseline_name.split('_')[-1]:>22}")
    print("-" * 70)

    baseline_results = {}
    for i, vector in enumerate(vectors):
        ids, _, _ = run_query(containers[baseline_name], vector, args.top)
        baseline_results[i] = set(ids)

    for name, container in containers.items():
        charges, latencies, recalls = [], [], []
        for i, vector in enumerate(vectors):
            best_ms, best_ru, ids = None, None, None
            for _ in range(args.repeats):
                got, ru, ms = run_query(container, vector, args.top)
                if best_ms is None or ms < best_ms:
                    best_ms, best_ru, ids = ms, ru, got
            charges.append(best_ru)
            latencies.append(best_ms)
            overlap = len(set(ids) & baseline_results[i]) / max(len(baseline_results[i]), 1)
            recalls.append(overlap)
        print(
            f"{name:<20}{statistics.median(charges):>14.2f}"
            f"{statistics.median(latencies):>14.1f}"
            f"{statistics.mean(recalls) * 100:>21.1f}%"
        )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
