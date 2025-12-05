#!/usr/bin/env python3
"""
Populate answer cache from evaluation results.
Usage: python scripts/populate_cache.py [evaluation_file.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.backend.cache.answer_cache import add_to_cache, load_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate answer cache")
    parser.add_argument(
        "evaluation_file",
        type=Path,
        help="Path to evaluation results JSON file"
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.7,
        help="Minimum quality score to cache (default: 0.7)"
    )
    parser.add_argument(
        "--auto-eval-file",
        type=Path,
        default=None,
        help="Optional: Path to auto-evaluation results for quality scores"
    )
    
    args = parser.parse_args()
    
    if not args.evaluation_file.exists():
        print(f"Error: File not found: {args.evaluation_file}")
        sys.exit(1)
    
    # Load evaluation results
    results = json.loads(args.evaluation_file.read_text(encoding="utf-8"))
    
    # Load auto-evaluation scores if provided
    quality_scores: dict[int, float] = {}
    if args.auto_eval_file and args.auto_eval_file.exists():
        auto_eval = json.loads(args.auto_eval_file.read_text(encoding="utf-8"))
        for entry in auto_eval.get("results", []):
            q_id = entry.get("id", 0)
            evaluation = entry.get("evaluation", {})
            quality_scores[q_id] = evaluation.get("overall_score", 0.5)
    
    added = 0
    skipped = 0
    
    for result in results.get("results", []):
        q_id = result.get("id", 0)
        question = result.get("question", "")
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        
        if not question or not answer:
            skipped += 1
            continue
        
        # Get quality score
        quality = quality_scores.get(q_id, 0.75)  # Default to 0.75 if no auto-eval
        
        if quality >= args.min_quality:
            add_to_cache(
                question=question,
                answer=answer,
                sources=sources,
                quality_score=quality
            )
            added += 1
            print(f"✓ Cached Q{q_id} (quality: {quality:.2f}): {question[:50]}...")
        else:
            skipped += 1
            print(f"✗ Skipped Q{q_id} (quality: {quality:.2f}): {question[:50]}...")
    
    print(f"\n{'='*60}")
    print(f"CACHE POPULATION COMPLETE")
    print(f"{'='*60}")
    print(f"Added to cache: {added}")
    print(f"Skipped (low quality): {skipped}")
    
    # Show cache stats
    cache = load_cache()
    print(f"Total cached answers: {len(cache.get('cached_answers', []))}")


if __name__ == "__main__":
    main()

