from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from qdrant_client.http.models import Filter, Payload

from .embeddings import get_model
from .indexing import COLLECTION_NAME, get_qdrant_client

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    score: float
    payload: Payload


def hybrid_search(
    query: str,
    k: int = 10,
    filters: Filter | None = None,
) -> List[SearchResult]:
    """
    Perform a dense+sparse hybrid search in Qdrant using BGE-M3 embeddings.

    Requires that `index_all_chunks` has been run and Qdrant is up.
    """
    model = get_model()
    outputs = model.encode(
        [query],
        batch_size=1,
        max_length=8192,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    dense_vec = outputs["dense_vecs"][0].tolist()

    client = get_qdrant_client()

    _log.info("Running hybrid search in collection '%s'", COLLECTION_NAME)

    # qdrant-client 1.13+ query_points API
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=dense_vec,
        using="dense",
        query_filter=filters,
        limit=k,
        with_payload=True,
    )

    results: list[SearchResult] = []
    for point in response.points:
        results.append(SearchResult(score=point.score, payload=point.payload or {}))
    return results


__all__ = ["hybrid_search", "SearchResult"]


