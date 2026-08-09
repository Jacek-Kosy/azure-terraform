# Filtered vector search

Combining `VectorDistance` with a `WHERE` clause, and what it costs.

Both [app/](../app/) and [scripts/benchmark_indexes.py](../scripts/benchmark_indexes.py)
can narrow a query to one topic:

```sql
SELECT TOP @top c.id, c.topic, c.title, c.text,
       VectorDistance(c.embedding, @vector) AS score
FROM c WHERE c.topic = @topic
ORDER BY VectorDistance(c.embedding, @vector)
```

## The filter is not the interesting part — the routing is

`/topic` is the containers' partition key. The SQL above returns the same rows
whether or not the client names the partition, but naming it lets Cosmos serve
the query from one physical partition instead of fanning out to all of them and
merging:

```python
routing = {"partition_key": topic} if topic else {"enable_cross_partition_query": True}
container.query_items(query=sql, parameters=params, **routing)
```

**No indexing policy change was needed.** `includedPaths: ["/*"]` already
indexes `topic`, and filtered vector search needs no composite index. The
policy in [modules/azure-cosmosdb/main.tf](../modules/azure-cosmosdb/main.tf)
was already sufficient.

## Measurements

`benchmark_indexes.py`, top-10, 10 queries, best of 3, 505 dimensions. All
three containers hold identical data; index type is the only variable.

**Unfiltered — 51,010 documents, cross-partition**

| container | RU (median) | ms (median) | recall vs flat |
| --- | ---: | ---: | ---: |
| `flat` | 889.68 | 519.5 | 100% |
| `quantizedFlat` | 85.18 | 393.1 | 95% |
| `diskANN` | **21.79** | 425.6 | 94% |

**Filtered to `sensors` — 4,283 documents, single partition**

| container | RU (median) | ms (median) | recall vs flat |
| --- | ---: | ---: | ---: |
| `flat` | 240.30 | 118.4 | 100% |
| `quantizedFlat` | **85.20** | 96.4 | 98% |
| `diskANN` | 86.30 | 98.8 | 98% |

**Filtered to `power` — 4,208 documents, single partition**

| container | RU (median) | ms (median) | recall vs flat |
| --- | ---: | ---: | ---: |
| `flat` | 236.14 | 115.9 | 100% |
| `quantizedFlat` | **84.91** | 93.9 | 95% |
| `diskANN` | 85.51 | 104.4 | 97% |

## What the numbers say

**diskANN gets four times more expensive when the search gets twelve times
smaller.** 21.79 RU unfiltered, 85–86 RU filtered. This is the opposite of the
intuition that a narrower search is a cheaper one, and it is the single most
useful thing in this document.

The likely mechanism — inferred, not measured — is that a filter does not
shrink the DiskANN proximity graph. The graph is still built over all 51,010
vectors, so the traversal has to walk further to collect ten neighbours that
also satisfy the predicate. `flat` and `quantizedFlat` have no graph to walk;
they simply scan fewer rows.

**quantizedFlat is effectively flat-rate.** 85.18 unfiltered, 85.20 and 84.91
filtered — unchanged across a twelvefold difference in scope. Why its cost is so
insensitive to the number of vectors scanned is not explained by anything
measured here.

**flat is the only index that behaves as expected**, falling 3.7× (889.68 →
240.30) for a 11.9× narrowing. Sublinear, but in the right direction.

**Latency improves for every index**, roughly 4×, from ~400–520 ms to ~94–118
ms. This is the partition routing rather than the filter: no fan-out, no merge.

**Recall improves for the approximate indexes**, 94–95% → 95–98%. Fewer
candidates, fewer chances to miss one.

**So the cheapest index depends on the query, not the corpus.** Unfiltered,
diskANN wins outright at a quarter of quantizedFlat's cost. Filtered, the two
are within 1% of each other and the choice stops mattering. This matches
Microsoft's guidance that quantizedFlat suits searches scoped to ~50k vectors
or fewer and diskANN suits larger ones — our corpus straddles that line, and
the filter is what moves it across.

diskANN therefore remains the app's default container: it wins decisively in
the unfiltered case and merely ties in the filtered one.

## Cost of the app's own searches

Ordinary searches restrict to the 1,010 hand-written chunks
(`WHERE c.synthetic = false`), which is a much smaller job than the tables
above. Measured against `chunks_diskann`, top-5:

| query | RU | ms | ranked |
| --- | ---: | ---: | ---: |
| unfiltered | 12.10 | 378 | 1,010 |
| `topic=sensors` | 6.17 | 100 | 116 |
| `topic=i2c` | 3.63 | 180 | 8 |

## Reading costs almost nothing; writing costs a lot

`load_cosmos.py` now reports the request charge for a load:

```
loaded 50 documents into chunks_diskann in 6s (9/s)
  4,662 RU total, 93.2 RU per document, 831 RU/s sustained
```

**93 RU to write one 505-dimensional vector, against 12 RU to search all 1,010
of them.** One write costs about eight searches. This is why bulk loading
throttles against the autoscale ceiling while querying never does, and it is
the figure to reach for when sizing throughput for an ingest.

### Patching one property costs the same as rewriting the document

The obvious way to correct a single scalar on a stored document is
`patch_item`, which sends only the changed property instead of the whole
record. On a vector-indexed container it saves nothing:

| operation | RU |
| --- | ---: |
| `upsert_item` — full document, vector included | 93.2 |
| `patch_item` — one boolean, vector untouched | 94.25 |

The vector is re-indexed on any write to the document, and that dominates the
charge; the bytes on the wire barely matter. So on a container like this one,
**there is no cheap edit** — plan corrections as if they were reloads.

This is what makes the missing `synthetic` flag not worth fixing: 101,027
affected documents × ~94 RU is roughly 9.5M RU to populate a field the `ard-`
against `syn-` id prefix already encodes for nothing. See
[../scripts/README.md](../scripts/README.md) for the convention that replaces
it.

## A Cosmos limitation worth knowing

Populating the topic dropdown wanted a count per topic. The obvious query fails:

```
SELECT c.topic, COUNT(1) AS n FROM c GROUP BY c.topic
→ BadRequest: Cross partition query only supports 'VALUE <AggregateFunc>' for aggregates.
```

Cosmos will not project a grouped aggregate across partitions, with or without
`enable_cross_partition_query`. Running the same `GROUP BY` against a single
partition works but costs ~180 RU each, so ~5,600 RU for 31 topics.

What the app does instead, in [app/main.py](../app/main.py):

- `SELECT DISTINCT VALUE c.topic FROM c` — all 31 names for about 3 RU.
- `SELECT VALUE COUNT(1) FROM c` per selection, single-partition when a topic is
  named — also about 3 RU, since `COUNT` is answered from the index.

Both are cached for the process lifetime with `lru_cache`, which does not cache
exceptions, so a transient Cosmos failure is retried on the next request rather
than remembered as an empty dropdown.
