"""
Answer caching module for Lapua RAG.
Reduces LLM inference costs by caching high-quality answers.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

_log = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
CACHE_FILE = DATA_DIR / "answers_cache.json"
QUESTIONS_LOG_FILE = DATA_DIR / "user_questions_log.json"

# Similarity threshold for cache hits (0.0 - 1.0)
SIMILARITY_THRESHOLD = 0.92


class CachedAnswer(BaseModel):
    """A cached answer entry."""
    question: str
    question_normalized: str
    answer: str
    sources: list[dict]
    quality_score: float
    created_at: str
    hit_count: int = 0
    last_hit: Optional[str] = None


class QuestionLogEntry(BaseModel):
    """A logged user question."""
    question: str
    timestamp: str
    cache_hit: bool
    topic_category: Optional[str] = None


def normalize_question(question: str) -> str:
    """Normalize question for comparison."""
    import re
    # Lowercase, remove extra whitespace, remove punctuation at end
    normalized = question.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[?!.]+$', '', normalized)
    return normalized


def simple_similarity(q1: str, q2: str) -> float:
    """Simple word-based similarity score."""
    words1 = set(normalize_question(q1).split())
    words2 = set(normalize_question(q2).split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)


def load_cache() -> dict:
    """Load the answer cache from file."""
    if not CACHE_FILE.exists():
        return {"metadata": {}, "cached_answers": []}
    
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        _log.error("Failed to load cache: %s", e)
        return {"metadata": {}, "cached_answers": []}


def save_cache(cache_data: dict) -> None:
    """Save the answer cache to file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def find_cached_answer(question: str) -> Optional[dict]:
    """
    Find a cached answer for the given question.
    Returns the cached answer dict if found, None otherwise.
    """
    cache_data = load_cache()
    normalized_q = normalize_question(question)
    
    best_match = None
    best_score = 0.0
    
    for entry in cache_data.get("cached_answers", []):
        cached_normalized = entry.get("question_normalized", "")
        
        # Exact match
        if cached_normalized == normalized_q:
            best_match = entry
            best_score = 1.0
            break
        
        # Similarity match
        similarity = simple_similarity(question, entry.get("question", ""))
        if similarity > best_score and similarity >= SIMILARITY_THRESHOLD:
            best_match = entry
            best_score = similarity
    
    if best_match:
        _log.info("Cache hit! Similarity: %.2f for question: %s", best_score, question[:50])
        # Update hit count
        best_match["hit_count"] = best_match.get("hit_count", 0) + 1
        best_match["last_hit"] = datetime.now().isoformat()
        save_cache(cache_data)
        return best_match
    
    return None


def add_to_cache(
    question: str,
    answer: str,
    sources: list[dict],
    quality_score: float = 0.8
) -> None:
    """Add a high-quality answer to the cache."""
    if quality_score < 0.7:
        _log.info("Quality score too low (%.2f), not caching", quality_score)
        return
    
    cache_data = load_cache()
    
    entry = {
        "question": question,
        "question_normalized": normalize_question(question),
        "answer": answer,
        "sources": sources,
        "quality_score": quality_score,
        "created_at": datetime.now().isoformat(),
        "hit_count": 0,
        "last_hit": None
    }
    
    # Check if similar question already exists
    normalized_q = normalize_question(question)
    for i, existing in enumerate(cache_data.get("cached_answers", [])):
        if existing.get("question_normalized") == normalized_q:
            # Update existing entry if new one has higher quality
            if quality_score > existing.get("quality_score", 0):
                cache_data["cached_answers"][i] = entry
                save_cache(cache_data)
                _log.info("Updated cached answer for: %s", question[:50])
            return
    
    cache_data["cached_answers"].append(entry)
    save_cache(cache_data)
    _log.info("Added new answer to cache for: %s", question[:50])


def log_user_question(
    question: str,
    cache_hit: bool,
    topic_category: Optional[str] = None
) -> None:
    """Log a user question for analytics."""
    try:
        if not QUESTIONS_LOG_FILE.exists():
            log_data = {
                "metadata": {"description": "User questions log"},
                "questions": [],
                "analytics": {
                    "total_questions": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "popular_topics": {}
                }
            }
        else:
            log_data = json.loads(QUESTIONS_LOG_FILE.read_text(encoding="utf-8"))
        
        # Add question entry
        entry = {
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "cache_hit": cache_hit,
            "topic_category": topic_category
        }
        log_data["questions"].append(entry)
        
        # Update analytics
        analytics = log_data.get("analytics", {})
        analytics["total_questions"] = analytics.get("total_questions", 0) + 1
        if cache_hit:
            analytics["cache_hits"] = analytics.get("cache_hits", 0) + 1
        else:
            analytics["cache_misses"] = analytics.get("cache_misses", 0) + 1
        
        if topic_category:
            topics = analytics.get("popular_topics", {})
            topics[topic_category] = topics.get(topic_category, 0) + 1
            analytics["popular_topics"] = topics
        
        log_data["analytics"] = analytics
        
        QUESTIONS_LOG_FILE.write_text(
            json.dumps(log_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        _log.error("Failed to log question: %s", e)


def populate_cache_from_evaluation(
    evaluation_file: Path,
    min_quality_score: float = 0.7
) -> int:
    """
    Populate cache from evaluation results.
    Returns the number of answers added to cache.
    """
    if not evaluation_file.exists():
        _log.error("Evaluation file not found: %s", evaluation_file)
        return 0
    
    results = json.loads(evaluation_file.read_text(encoding="utf-8"))
    added = 0
    
    for result in results.get("results", []):
        # Check if this result has been evaluated
        eval_data = result.get("evaluation", {})
        quality = eval_data.get("overall_score", 0.8)  # Default to 0.8 if not evaluated
        
        if quality >= min_quality_score:
            add_to_cache(
                question=result.get("question", ""),
                answer=result.get("answer", ""),
                sources=result.get("sources", []),
                quality_score=quality
            )
            added += 1
    
    _log.info("Added %d answers to cache from %s", added, evaluation_file)
    return added

