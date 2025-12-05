#!/usr/bin/env python3
"""
RAG Evaluation Script - Run 150 questions through the Lapua RAG API.

Usage:
    python scripts/run_evaluation.py [--output evaluation_results/baseline.json]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

import httpx


class QuestionItem(TypedDict):
    id: int
    topic: str
    question: str


class EvaluationResult(TypedDict):
    id: int
    topic: str
    question: str
    answer: str
    sources: list[dict]
    response_time_ms: int
    timestamp: str
    error: str | None


API_BASE_URL = "https://lapuarag.org"
DEFAULT_QUESTIONS_FILE = Path(__file__).parent.parent / "kysymykset.md"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "evaluation_results"


def parse_questions(filepath: Path) -> list[QuestionItem]:
    """Parse questions from kysymykset.md file."""
    content = filepath.read_text(encoding="utf-8")
    
    questions: list[QuestionItem] = []
    current_topic = ""
    question_id = 0
    
    lines = content.split("\n")
    for line in lines:
        # Match topic headers like "### 1. Talousarvio ja taloussuunnitelma"
        topic_match = re.match(r"^### \d+\.\s+(.+)$", line)
        if topic_match:
            current_topic = topic_match.group(1).strip()
            continue
        
        # Match questions like "1. Mikä on..."
        question_match = re.match(r"^\d+\.\s+(.+\?)$", line)
        if question_match and current_topic:
            question_id += 1
            questions.append(
                QuestionItem(
                    id=question_id,
                    topic=current_topic,
                    question=question_match.group(1).strip(),
                )
            )
    
    return questions


def query_api(question: str, timeout: float = 60.0) -> tuple[dict, int]:
    """
    Send a question to the RAG API and return the response with timing.
    
    Returns:
        Tuple of (response_dict, response_time_ms)
    """
    start_time = time.perf_counter()
    
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{API_BASE_URL}/query",
            json={"question": question},
        )
        response.raise_for_status()
    
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    return response.json(), elapsed_ms


def run_evaluation(
    questions: list[QuestionItem],
    output_path: Path,
    delay_between_queries: float = 1.0,
) -> list[EvaluationResult]:
    """Run all questions through the API and save results."""
    results: list[EvaluationResult] = []
    total = len(questions)
    
    print(f"\n{'='*60}")
    print(f"Starting evaluation with {total} questions")
    print(f"API: {API_BASE_URL}")
    print(f"Output: {output_path}")
    print(f"{'='*60}\n")
    
    for i, q in enumerate(questions, 1):
        print(f"[{i:3d}/{total}] {q['topic'][:30]:<30} | {q['question'][:50]}...")
        
        try:
            response, elapsed_ms = query_api(q["question"])
            
            result = EvaluationResult(
                id=q["id"],
                topic=q["topic"],
                question=q["question"],
                answer=response.get("answer", ""),
                sources=response.get("sources", []),
                response_time_ms=elapsed_ms,
                timestamp=datetime.now().isoformat(),
                error=None,
            )
            print(f"         ✓ {elapsed_ms}ms | {len(result['answer'])} chars")
            
        except Exception as e:
            result = EvaluationResult(
                id=q["id"],
                topic=q["topic"],
                question=q["question"],
                answer="",
                sources=[],
                response_time_ms=0,
                timestamp=datetime.now().isoformat(),
                error=str(e),
            )
            print(f"         ✗ ERROR: {e}")
        
        results.append(result)
        
        # Save intermediate results
        if i % 10 == 0:
            _save_results(results, output_path)
            print(f"         [Saved checkpoint: {i} questions]")
        
        # Delay to avoid rate limiting
        if i < total:
            time.sleep(delay_between_queries)
    
    # Save final results
    _save_results(results, output_path)
    
    # Print summary
    _print_summary(results)
    
    return results


def _save_results(results: list[EvaluationResult], output_path: Path) -> None:
    """Save results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        "metadata": {
            "run_date": datetime.now().isoformat(),
            "api_url": API_BASE_URL,
            "total_questions": len(results),
            "completed": sum(1 for r in results if r["error"] is None),
            "errors": sum(1 for r in results if r["error"] is not None),
        },
        "results": results,
    }
    
    output_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_summary(results: list[EvaluationResult]) -> None:
    """Print evaluation summary."""
    completed = [r for r in results if r["error"] is None]
    errors = [r for r in results if r["error"] is not None]
    
    if completed:
        avg_time = sum(r["response_time_ms"] for r in completed) / len(completed)
        avg_length = sum(len(r["answer"]) for r in completed) / len(completed)
    else:
        avg_time = 0
        avg_length = 0
    
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total questions:    {len(results)}")
    print(f"Successful:         {len(completed)}")
    print(f"Errors:             {len(errors)}")
    print(f"Avg response time:  {avg_time:.0f}ms")
    print(f"Avg answer length:  {avg_length:.0f} chars")
    print(f"{'='*60}\n")
    
    if errors:
        print("ERRORS:")
        for r in errors[:5]:  # Show first 5 errors
            print(f"  - Q{r['id']}: {r['error']}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument(
        "--questions",
        "-q",
        type=Path,
        default=DEFAULT_QUESTIONS_FILE,
        help="Questions Markdown file path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.0,
        help="Delay between queries in seconds",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit number of questions (for testing)",
    )
    
    args = parser.parse_args()
    
    # Set output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = DEFAULT_OUTPUT_DIR / f"run_{timestamp}.json"
    
    # Parse questions
    questions = parse_questions(args.questions)
    print(f"Loaded {len(questions)} questions from {args.questions}")
    
    # Apply limit if specified
    if args.limit:
        questions = questions[: args.limit]
        print(f"Limited to {len(questions)} questions")
    
    # Run evaluation
    run_evaluation(questions, output_path, delay_between_queries=args.delay)
    
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()

