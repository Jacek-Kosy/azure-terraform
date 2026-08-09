# Documentation

Document environment-specific decisions, architecture notes, and deployment guidance here.

- [filtered-vector-search.md](filtered-vector-search.md) — combining
  `VectorDistance` with a `WHERE` clause on the partition key, and the measured
  cost of doing so. Includes why diskANN gets *more* expensive under a filter.
