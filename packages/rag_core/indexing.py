from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from docling_pipeline.config import get_settings as get_docling_settings

from .embeddings import get_model
from .models import ChunkRecord

_log = logging.getLogger(__name__)

COLLECTION_NAME = "lapua_chunks"


@dataclass(frozen=True)
class QdrantSettings:
    host: str = "localhost"
    port: int = 6333
    prefer_grpc: bool = False


def get_qdrant_client(settings: QdrantSettings | None = None) -> QdrantClient:
    """Return a Qdrant client configured from settings or defaults."""
    if settings is None:
        settings = QdrantSettings()
    client = QdrantClient(
        host=settings.host,
        port=settings.port,
        grpc_port=6334,
        prefer_grpc=settings.prefer_grpc,
        timeout=60.0,
    )
    return client


def _ensure_collection(client: QdrantClient, dim: int) -> None:
    """Create collection with dense vectors if it does not exist."""
    existing = client.get_collections()
    if any(c.name == COLLECTION_NAME for c in existing.collections):
        return

    _log.info("Creating Qdrant collection '%s' (dim=%d)", COLLECTION_NAME, dim)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={"dense": VectorParams(size=dim, distance=Distance.COSINE)},
    )


def _load_chunks(chunks_path: Path) -> List[ChunkRecord]:
    records: list[ChunkRecord] = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(ChunkRecord.model_validate(data))
    return records


def _batch_iter(seq: Sequence, batch_size: int) -> Iterable[Sequence]:
    for i in range(0, len(seq), batch_size):
        yield seq[i : i + batch_size]


def index_all_chunks(batch_size: int = 64) -> None:
    """
    Index all chunks into Qdrant with dense + sparse vectors from BGE-M3.

    This re-embeds chunk texts using the GPU-enabled BGE-M3 model. For the
    current dataset size this is acceptable and simpler than mixing with the
    precomputed dense-only .npy file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings = get_docling_settings()
    chunks_dir = settings.chunks_dir
    chunks_path = chunks_dir / "chunks.jsonl"

    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    client = get_qdrant_client()
    records = _load_chunks(chunks_path)
    texts = [r.chunk_text for r in records]
    _log.info("Indexing %d chunks into Qdrant collection '%s'", len(records), COLLECTION_NAME)

    model = get_model()

    # We compute embeddings in batches to limit GPU memory usage.
    first_dense: np.ndarray | None = None
    dim: int | None = None

    for batch_indices in _batch_iter(list(range(len(records))), batch_size=batch_size):
        batch_texts = [texts[i] for i in batch_indices]
        outputs = model.encode(
            batch_texts,
            batch_size=len(batch_texts),
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense_vecs: np.ndarray = np.asarray(outputs["dense_vecs"], dtype=np.float32)

        if first_dense is None:
            first_dense = dense_vecs
            dim = first_dense.shape[1]
            _ensure_collection(client, dim)

        points: list[PointStruct] = []
        for local_idx, global_idx in enumerate(batch_indices):
            rec = records[global_idx]
            dense_vec = dense_vecs[local_idx]

            payload = rec.model_dump(mode="python")

            points.append(
                PointStruct(
                    id=int(global_idx),
                    vector={"dense": dense_vec.tolist()},
                    payload=payload,
                )
            )

        _log.info("Upserting %d points to Qdrant...", len(points))
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

    _log.info("Indexing completed.")


__all__ = ["index_all_chunks", "get_qdrant_client", "COLLECTION_NAME"]


