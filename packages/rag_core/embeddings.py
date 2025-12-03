from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

import numpy as np
import torch
from FlagEmbedding import BGEM3FlagModel

from docling_pipeline.config import get_settings as get_docling_settings

from .models import ChunkRecord

_log = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-m3"
_model: BGEM3FlagModel | None = None


def _get_device() -> str:
    """Return device string, prefer GPU when available."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_model() -> BGEM3FlagModel:
    """Lazily load the BGE-M3 embedding model."""
    global _model
    if _model is not None:
        return _model

    device = _get_device()
    use_fp16 = device == "cuda"

    _log.info("Loading BGEM3FlagModel '%s' on device=%s (fp16=%s)", _MODEL_NAME, device, use_fp16)
    _model = BGEM3FlagModel(
        _MODEL_NAME,
        use_fp16=use_fp16,
        device=device,
    )
    return _model


def embed_dense(texts: List[str], batch_size: int = 16, max_length: int = 8192) -> np.ndarray:
    """
    Compute dense embeddings for a list of texts using BGE-M3.

    Sparse embeddings are deliberately omitted here for simplicity; hybrid search
    will be wired later when Qdrant integration is added.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    model = get_model()
    _log.info("Encoding %d texts with BGE-M3 (batch_size=%d, max_length=%d)", len(texts), batch_size, max_length)

    outputs = model.encode(
        texts,
        batch_size=batch_size,
        max_length=max_length,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )

    dense_vecs = outputs["dense_vecs"]
    # Ensure numpy array
    dense_array = np.asarray(dense_vecs, dtype=np.float32)
    return dense_array


def precompute_all(batch_size: int = 16) -> Path:
    """
    Precompute dense BGE-M3 embeddings for all chunks in data/chunks/chunks.jsonl.

    Embeddings are stored as a NumPy array in data/chunks/bge_m3_dense.npy,
    where index i corresponds to the i-th line in chunks.jsonl.
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

    _log.info("Loading chunks from %s", chunks_path)
    texts: list[str] = []

    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            chunk = ChunkRecord.model_validate(record)
            texts.append(chunk.chunk_text)

    _log.info("Total chunks to embed: %d", len(texts))

    dense = embed_dense(texts, batch_size=batch_size)

    dense_path = chunks_dir / "bge_m3_dense.npy"
    _log.info("Saving dense embeddings to %s (shape=%s)", dense_path, dense.shape)
    np.save(dense_path, dense)

    return dense_path


__all__ = ["embed_dense", "precompute_all", "get_model"]


