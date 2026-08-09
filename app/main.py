"""Vector search over the Arduino corpus in Cosmos DB.

Two modes over the same query path:

- search  — answer a question from the 1010 hand-written chunks
- compare — run the query against every vector index and report what each cost

Either mode can be narrowed to one topic. Because /topic is the containers'
partition key, that filter is not merely a WHERE clause: it routes the query to
a single physical partition, which is where most of its saving comes from.

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
from functools import lru_cache
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
    # How many documents the query could match before ranking, and whether it
    # was served from one partition. Together these explain the request charge.
    scope: int | None
    single_partition: bool


def _index_type(container_name: str) -> str:
    """Infer the index type from the container name for display purposes."""
    lowered = container_name.lower()
    for label, name in (("diskann", "diskANN"), ("quantized", "quantizedFlat"), ("flat", "flat")):
        if label in lowered:
            return name
    return "unknown"


def _default_container():
    return _cosmos.get_database_client(COSMOS_DATABASE).get_container_client(DEFAULT_CONTAINER)


@lru_cache(maxsize=1)
def topics() -> list[str]:
    """Every topic in the corpus, read once.

    Fetching each topic's size alongside its name would be the obvious thing,
    but Cosmos rejects a projected aggregate across partitions -- "Cross
    partition query only supports 'VALUE <AggregateFunc>' for aggregates" --
    and running the GROUP BY one partition at a time costs around 180 RU each.
    DISTINCT VALUE returns all 31 for about 3 RU; sizes come from scope_of()
    below, which is cheap for the one topic actually selected.

    lru_cache does not cache exceptions, so a transient failure is retried on
    the next request rather than remembered as an empty list.
    """
    return sorted(
        _default_container().query_items(
            query="SELECT DISTINCT VALUE c.topic FROM c", enable_cross_partition_query=True
        )
    )


@lru_cache(maxsize=128)
def _count(topic: str | None, real_only: bool) -> int:
    """Documents a query with this filter can match.

    COUNT is answered from the index at roughly 3 RU, and from a single
    partition when a topic is named, so this is cheap enough to run per
    distinct selection. There are 31 topics and two modes, so the cache holds
    every combination a user can reach.
    """
    # Matches search()'s predicate exactly, including testing for false rather
    # than negating true -- see the note there. If the two ever diverge this
    # reports a scope the search did not actually use.
    where = "WHERE c.synthetic = false" if real_only else ""
    routing = {"partition_key": topic} if topic else {"enable_cross_partition_query": True}
    rows = list(_default_container().query_items(f"SELECT VALUE COUNT(1) FROM c {where}", **routing))
    return rows[0] if rows else 0


def scope_of(topic: str | None, real_only: bool) -> int | None:
    """_count, but display-only: never fail a search over a figure beside it."""
    try:
        return _count(topic, real_only)
    except Exception:
        return None


def embed(text: str) -> list[float]:
    response = _openai.embeddings.create(
        model=EMBEDDING_DEPLOYMENT, input=[text], dimensions=VECTOR_DIMENSIONS
    )
    return response.data[0].embedding


def search(
    container_name: str,
    vector: list[float],
    top: int,
    real_only: bool,
    topic: str | None = None,
) -> IndexResult:
    container = _cosmos.get_database_client(COSMOS_DATABASE).get_container_client(container_name)

    conditions = []
    params = [{"name": "@vector", "value": vector}, {"name": "@top", "value": top}]

    # Generated filler is combinatorial nonsense and must never be shown as an
    # answer, so ordinary searches restrict to the hand-written corpus.
    #
    # Test for false rather than negating true. Most of the filler predates the
    # flag and carries no `synthetic` property at all, and in Cosmos an
    # undefined property matches neither `= true` nor `!= true` predictably.
    # `= false` selects exactly the 1,010 hand-written chunks and fails closed:
    # anything unflagged is excluded, which is the safe direction. See
    # scripts/README.md for the state of the data.
    if real_only:
        conditions.append("c.synthetic = false")
    if topic:
        conditions.append("c.topic = @topic")
        params.append({"name": "@topic", "value": topic})

    where = f"WHERE {' AND '.join(conditions)} " if conditions else ""

    # TOP is not optional. Without it Cosmos ranks far more candidates than the
    # caller will ever read, and charges for all of them.
    sql = (
        "SELECT TOP @top c.id, c.topic, c.title, c.text, "
        "VectorDistance(c.embedding, @vector) AS score "
        f"FROM c {where}"
        "ORDER BY VectorDistance(c.embedding, @vector)"
    )

    # /topic is the partition key, so naming it lets Cosmos route to a single
    # physical partition rather than fanning out and merging. The WHERE clause
    # alone would return the same rows; this is what makes them cheap.
    routing = {"partition_key": topic} if topic else {"enable_cross_partition_query": True}

    # Accumulated from the response rather than read off client_connection
    # afterwards: that attribute is shared mutable state, and FastAPI runs these
    # handlers on a thread pool, so concurrent searches would overwrite it.
    charges: list[float] = []

    started = time.monotonic()
    rows = list(
        container.query_items(
            query=sql,
            parameters=params,
            response_hook=lambda headers, _: charges.append(
                float(headers.get("x-ms-request-charge", 0))
            ),
            **routing,
        )
    )
    latency_ms = (time.monotonic() - started) * 1000

    return IndexResult(
        container=container_name,
        index_type=_index_type(container_name),
        request_units=sum(charges),
        latency_ms=latency_ms,
        scope=scope_of(topic, real_only),
        single_partition=topic is not None,
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


def render(request: Request, **context) -> HTMLResponse:
    """Every response is the same page. The topic list is best-effort: if Cosmos
    is unreachable the page still renders, without the filter."""
    try:
        available = topics()
    except Exception:
        available = []

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "query": "",
            "topic": "",
            "topics": available,
            "total_documents": scope_of(None, real_only=False),
            "real_documents": scope_of(None, real_only=True),
            "result": None,
            "comparison": None,
            "error": None,
            **context,
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return render(request)


@app.post("/search", response_class=HTMLResponse)
def do_search(
    request: Request,
    query: str = Form(...),
    top: int = Form(5),
    topic: str = Form(""),
) -> HTMLResponse:
    error, result = None, None
    try:
        result = search(DEFAULT_CONTAINER, embed(query), top, real_only=True, topic=topic or None)
    except Exception as exc:  # surfaced in the page rather than a 500
        error = f"{type(exc).__name__}: {exc}"

    return render(request, query=query, topic=topic, result=result, error=error)


@app.post("/compare", response_class=HTMLResponse)
def do_compare(
    request: Request,
    query: str = Form(...),
    top: int = Form(10),
    topic: str = Form(""),
) -> HTMLResponse:
    error, comparison = None, None
    try:
        # Embed once so every index answers exactly the same question.
        vector = embed(query)
        # Across the whole corpus, not just the hand-written part: the point is
        # how each index behaves at scale, and a topic filter is interesting
        # precisely because of how far it narrows that.
        results = [
            search(name, vector, top, real_only=False, topic=topic or None)
            for name in CONTAINER_NAMES
        ]

        # flat is exhaustive, so its results are the exact answer to compare
        # against -- still true under a filter, since it scans whatever the
        # filter leaves.
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

    return render(request, query=query, topic=topic, comparison=comparison, error=error)
