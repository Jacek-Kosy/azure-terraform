"""Vector search over the Arduino corpus in Cosmos DB.

Two modes over the same query path:

- search  — answer a question from the 1010 hand-written chunks
- compare — run the query against every vector index and report what each cost

Authentication is Entra ID throughout. Neither Cosmos nor Azure OpenAI has keys
enabled, so the app relies on its managed identity; AZURE_CLIENT_ID selects it.

The query logic here duplicates scripts/benchmark_indexes.py rather than
importing it. The container image should not depend on the operational scripts
directory, and the shared surface is small enough that coupling costs more than
it saves.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from openai import AzureOpenAI

API_VERSION = "2024-10-21"
SCOPE = "https://cognitiveservices.azure.com/.default"

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE", "vectordb")
OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
EMBEDDING_DEPLOYMENT = os.environ.get("EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
CONTAINER_NAMES = [c for c in os.environ.get("CONTAINER_NAMES", "").split(",") if c]
VECTOR_DIMENSIONS = int(os.environ.get("VECTOR_DIMENSIONS", "505"))

# Which container answers ordinary searches. The index type does not change the
# results, only what they cost, so the cheapest at this corpus size is the
# sensible default.
DEFAULT_CONTAINER = next(
    (c for c in CONTAINER_NAMES if "diskann" in c.lower()),
    CONTAINER_NAMES[0] if CONTAINER_NAMES else "chunks_diskann",
)

app = FastAPI(title="Arduino vector search")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_credential = DefaultAzureCredential()
_cosmos = CosmosClient(COSMOS_ENDPOINT, credential=_credential) if COSMOS_ENDPOINT else None
_openai = (
    AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_version=API_VERSION,
        azure_ad_token_provider=get_bearer_token_provider(_credential, SCOPE),
    )
    if OPENAI_ENDPOINT
    else None
)


@dataclass
class Hit:
    id: str
    topic: str
    title: str
    text: str
    score: float


@dataclass
class IndexResult:
    container: str
    index_type: str
    request_units: float
    latency_ms: float
    hits: list[Hit]


def _index_type(container_name: str) -> str:
    """Infer the index type from the container name for display purposes."""
    lowered = container_name.lower()
    for label, name in (("diskann", "diskANN"), ("quantized", "quantizedFlat"), ("flat", "flat")):
        if label in lowered:
            return name
    return "unknown"


def embed(text: str) -> list[float]:
    response = _openai.embeddings.create(
        model=EMBEDDING_DEPLOYMENT, input=[text], dimensions=VECTOR_DIMENSIONS
    )
    return response.data[0].embedding


def search(container_name: str, vector: list[float], top: int, real_only: bool) -> IndexResult:
    container = _cosmos.get_database_client(COSMOS_DATABASE).get_container_client(container_name)

    # Generated filler is combinatorial nonsense and must never be shown as an
    # answer, so ordinary searches restrict to the hand-written corpus.
    where = "WHERE c.synthetic = false " if real_only else ""
    sql = (
        "SELECT TOP @top c.id, c.topic, c.title, c.text, "
        "VectorDistance(c.embedding, @vector) AS score "
        f"FROM c {where}"
        "ORDER BY VectorDistance(c.embedding, @vector)"
    )
    params = [{"name": "@vector", "value": vector}, {"name": "@top", "value": top}]

    started = time.monotonic()
    rows = list(container.query_items(query=sql, parameters=params, enable_cross_partition_query=True))
    latency_ms = (time.monotonic() - started) * 1000
    charge = float(container.client_connection.last_response_headers.get("x-ms-request-charge", 0))

    return IndexResult(
        container=container_name,
        index_type=_index_type(container_name),
        request_units=charge,
        latency_ms=latency_ms,
        hits=[
            Hit(id=r["id"], topic=r["topic"], title=r["title"], text=r["text"], score=r["score"])
            for r in rows
        ],
    )


@app.get("/healthz")
def healthz() -> JSONResponse:
    """Liveness probe. Deliberately does not call Azure: a transient Cosmos
    failure should not make the platform restart a healthy container."""
    return JSONResponse({"status": "ok", "containers": CONTAINER_NAMES})


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"query": "", "result": None, "comparison": None, "error": None},
    )


@app.post("/search", response_class=HTMLResponse)
def do_search(request: Request, query: str = Form(...), top: int = Form(5)) -> HTMLResponse:
    error, result = None, None
    try:
        result = search(DEFAULT_CONTAINER, embed(query), top, real_only=True)
    except Exception as exc:  # surfaced in the page rather than a 500
        error = f"{type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"query": query, "result": result, "comparison": None, "error": error},
    )


@app.post("/compare", response_class=HTMLResponse)
def do_compare(request: Request, query: str = Form(...), top: int = Form(10)) -> HTMLResponse:
    error, comparison = None, None
    try:
        # Embed once so every index answers exactly the same question.
        vector = embed(query)
        # Across the whole corpus, not just the hand-written part: the point is
        # how each index behaves at 51k documents.
        results = [search(name, vector, top, real_only=False) for name in CONTAINER_NAMES]

        # flat is exhaustive, so its results are the exact answer to compare against.
        exact = next((r for r in results if r.index_type == "flat"), None)
        baseline = {h.id for h in exact.hits} if exact else set()
        comparison = [
            {
                "result": r,
                "recall": (len({h.id for h in r.hits} & baseline) / len(baseline) * 100)
                if baseline
                else None,
            }
            for r in results
        ]
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"query": query, "result": None, "comparison": comparison, "error": error},
    )
