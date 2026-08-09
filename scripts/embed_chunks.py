#!/usr/bin/env python3
"""Embed a JSONL corpus using the dev Azure OpenAI embedding deployment.

The account is created with local_auth_enabled = false, so there is no API key
to supply: authentication is Entra ID via `az login`, and the caller needs the
"Cognitive Services OpenAI User" role, which environments/dev grants.

    export AZURE_OPENAI_ENDPOINT="$(terraform -chdir=environments/dev output -raw openai_endpoint)"
    python3 scripts/embed_chunks.py

Reads records with an "id" and "text" field and writes the same records back
with an added "embedding" field.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI
except ImportError as exc:  # pragma: no cover - dependency guidance
    sys.exit(f"missing dependency ({exc.name}): pip install -r scripts/requirements.txt")

# Embeddings are stable in this GA version; pinning avoids a service-side
# default shifting the response shape underneath the script.
API_VERSION = "2024-10-21"
SCOPE = "https://cognitiveservices.azure.com/.default"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/arduino-basics.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/arduino-basics.embeddings.jsonl"))
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        help="defaults to $AZURE_OPENAI_ENDPOINT",
    )
    parser.add_argument("--deployment", default="text-embedding-3-small")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="texts per request; lower this if the deployment returns 429",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="truncate vectors to this width; text-embedding-3-small defaults to 1536",
    )
    return parser.parse_args()


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                sys.exit(f"{path}:{lineno}: invalid JSON: {exc}")
            if not record.get("text"):
                sys.exit(f"{path}:{lineno}: record {record.get('id', '?')} has no text")
            records.append(record)
    if not records:
        sys.exit(f"{path}: no records found")
    return records


def batched(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main() -> int:
    args = parse_args()

    if not args.endpoint:
        sys.exit("no endpoint: pass --endpoint or set AZURE_OPENAI_ENDPOINT")
    if not args.input.exists():
        sys.exit(f"{args.input}: not found")

    records = load_records(args.input)
    print(f"read {len(records)} records from {args.input}", file=sys.stderr)

    client = AzureOpenAI(
        azure_endpoint=args.endpoint,
        api_version=API_VERSION,
        azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(), SCOPE),
        max_retries=5,
    )

    extra = {"dimensions": args.dimensions} if args.dimensions else {}
    total_tokens = 0
    width = None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for batch_no, batch in enumerate(batched(records, args.batch_size), start=1):
            response = client.embeddings.create(
                model=args.deployment,
                input=[record["text"] for record in batch],
                **extra,
            )
            # The API preserves input order, but index is authoritative.
            vectors = {item.index: item.embedding for item in response.data}
            if len(vectors) != len(batch):
                sys.exit(f"batch {batch_no}: asked for {len(batch)} vectors, got {len(vectors)}")

            for offset, record in enumerate(batch):
                vector = vectors[offset]
                width = width or len(vector)
                out.write(
                    json.dumps(
                        {**record, "model": args.deployment, "embedding": vector},
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            total_tokens += response.usage.total_tokens
            print(
                f"batch {batch_no}: {len(batch)} embedded "
                f"({total_tokens} tokens so far)",
                file=sys.stderr,
            )

    print(
        f"wrote {len(records)} vectors of width {width} to {args.output} "
        f"using {total_tokens} tokens",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
