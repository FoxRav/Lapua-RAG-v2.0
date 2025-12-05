#!/usr/bin/env python3
"""
Incremental indexer - adds ONLY new chunks to Qdrant without re-indexing everything.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger(__name__)

COLLECTION_NAME = "lapua_chunks"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333


def get_current_count(client: QdrantClient) -> int:
    """Get current number of points in collection."""
    info = client.get_collection(COLLECTION_NAME)
    return info.points_count


def load_new_chunks(chunks_path: Path, start_from: int) -> list[dict]:
    """Load chunks starting from given index."""
    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= start_from:
                chunks.append(json.loads(line))
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Incremental indexer for new chunks")
    parser.add_argument("--chunks", type=Path, default=Path("data/chunks/chunks.jsonl"))
    parser.add_argument("--start-from", type=int, default=None, 
                        help="Start index (default: current Qdrant count)")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    
    # Connect to Qdrant
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=60.0)
    
    # Get current count
    current_count = get_current_count(client)
    start_from = args.start_from if args.start_from is not None else current_count
    
    log.info(f"Current Qdrant points: {current_count}")
    log.info(f"Starting from index: {start_from}")
    
    # Load new chunks
    new_chunks = load_new_chunks(args.chunks, start_from)
    
    if not new_chunks:
        log.info("No new chunks to index!")
        return
    
    log.info(f"New chunks to index: {len(new_chunks)}")
    
    # Load embedding model
    log.info("Loading BGE-M3 model...")
    from FlagEmbedding import BGEM3FlagModel
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True, device="cpu")
    
    # Process in batches
    total_indexed = 0
    
    for batch_start in range(0, len(new_chunks), args.batch_size):
        batch_end = min(batch_start + args.batch_size, len(new_chunks))
        batch = new_chunks[batch_start:batch_end]
        
        # Get texts
        texts = [c["chunk_text"] for c in batch]
        
        # Embed
        outputs = model.encode(
            texts,
            batch_size=len(texts),
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense_vecs = np.asarray(outputs["dense_vecs"], dtype=np.float32)
        
        # Create points
        points = []
        for i, chunk in enumerate(batch):
            global_idx = start_from + batch_start + i
            points.append(
                PointStruct(
                    id=global_idx,
                    vector={"dense": dense_vecs[i].tolist()},
                    payload=chunk,
                )
            )
        
        # Upsert
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        total_indexed += len(points)
        
        log.info(f"Indexed {total_indexed}/{len(new_chunks)} chunks")
    
    # Verify
    new_count = get_current_count(client)
    log.info(f"Done! Qdrant now has {new_count} points (added {new_count - current_count})")


if __name__ == "__main__":
    main()

