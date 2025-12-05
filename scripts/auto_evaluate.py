#!/usr/bin/env python3
"""
Automated RAG Evaluation using LLM-as-Judge.

Evaluates RAG answers against:
1. Faithfulness - Is the answer supported by the retrieved sources?
2. Relevance - Does the answer address the question?
3. Completeness - Does the answer cover the key information from sources?

Uses Groq API for evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from openai import OpenAI


class AutoEvalScores(TypedDict):
    faithfulness: float      # 0-1: Is answer supported by sources?
    relevance: float         # 0-1: Does answer address the question?
    completeness: float      # 0-1: Does answer cover key info?
    hallucination_risk: float  # 0-1: Risk of made-up information
    overall_score: float     # Weighted average
    reasoning: str           # LLM's reasoning


# Evaluation prompt template
EVAL_PROMPT = """Arvioi RAG-vastaus (0.0-1.0):

KYSYMYS: {question}

VASTAUS: {answer}

LÄHTEET: {sources}

Anna JSON:
{{"faithfulness": 0.0-1.0, "relevance": 0.0-1.0, "completeness": 0.0-1.0, "hallucination_risk": 0.0-1.0, "reasoning": "max 30 sanaa"}}

Kriteerit:
- faithfulness: Perustuuko vastaus lähteisiin? (1.0=täysin, 0.0=ei)
- relevance: Vastaako kysymykseen? (1.0=täysin, 0.0=ei)
- completeness: Kattaako oleelliset tiedot? (1.0=kaikki, 0.0=ei mitään)
- hallucination_risk: Keksittyä tietoa? (0.0=ei, 1.0=paljon)

VAIN JSON:"""


def load_results(filepath: Path) -> dict:
    """Load evaluation results from JSON file."""
    return json.loads(filepath.read_text(encoding="utf-8"))


def save_results(data: dict, filepath: Path) -> None:
    """Save evaluation results to JSON file."""
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def format_sources(sources: list[dict]) -> str:
    """Format sources for the evaluation prompt (max ~2000 chars total)."""
    if not sources:
        return "[Ei lähteitä]"
    
    formatted = []
    total_chars = 0
    max_total_chars = 2000  # Keep total sources text under this
    
    for i, src in enumerate(sources[:3], 1):  # Max 3 sources
        toimielin = src.get("toimielin", "")
        pvm = src.get("poytakirja_pvm", "")
        pykala = src.get("pykala_nro", "?")
        
        # Get chunk text if available
        chunk_text = src.get("text", "")
        
        # Calculate remaining chars
        remaining = max_total_chars - total_chars
        max_chunk_len = min(400, remaining - 100)  # Leave room for formatting
        
        if max_chunk_len <= 50:
            break
        
        if chunk_text:
            chunk_preview = chunk_text[:max_chunk_len] + "..." if len(chunk_text) > max_chunk_len else chunk_text
        else:
            chunk_preview = "[Ei tekstiä]"
        
        entry = f"[{i}] {toimielin} {pvm} {pykala}: {chunk_preview}"
        formatted.append(entry)
        total_chars += len(entry)
    
    return "\n\n".join(formatted)


def evaluate_single(
    client: OpenAI,
    question: str,
    answer: str,
    sources: list[dict],
    model: str = "llama-3.1-70b-versatile",
) -> AutoEvalScores:
    """Evaluate a single question-answer pair using LLM."""
    
    prompt = EVAL_PROMPT.format(
        question=question,
        answer=answer,
        sources=format_sources(sources),
    )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Olet tarkka ja objektiivinen RAG-arvioija."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Low temperature for consistent evaluation
            max_tokens=500,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        scores = json.loads(result_text)
        
        # Calculate overall score (weighted)
        overall = (
            scores.get("faithfulness", 0) * 0.35 +
            scores.get("relevance", 0) * 0.30 +
            scores.get("completeness", 0) * 0.20 +
            (1 - scores.get("hallucination_risk", 0)) * 0.15
        )
        
        return AutoEvalScores(
            faithfulness=scores.get("faithfulness", 0),
            relevance=scores.get("relevance", 0),
            completeness=scores.get("completeness", 0),
            hallucination_risk=scores.get("hallucination_risk", 0),
            overall_score=round(overall, 3),
            reasoning=scores.get("reasoning", ""),
        )
        
    except json.JSONDecodeError as e:
        return AutoEvalScores(
            faithfulness=0,
            relevance=0,
            completeness=0,
            hallucination_risk=1,
            overall_score=0,
            reasoning=f"JSON parse error: {e}",
        )
    except Exception as e:
        # Print full error for debugging
        import traceback
        print(f"\n         DEBUG ERROR: {e}")
        return AutoEvalScores(
            faithfulness=0,
            relevance=0,
            completeness=0,
            hallucination_risk=1,
            overall_score=0,
            reasoning=f"Evaluation error: {str(e)[:100]}",
        )


def run_auto_evaluation(
    input_path: Path,
    groq_api_key: str,
    model: str = "llama-3.1-70b-versatile",
    delay: float = 1.0,
    limit: int | None = None,
) -> None:
    """Run automated evaluation on all results."""
    
    client = OpenAI(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    
    data = load_results(input_path)
    results = data.get("results", [])
    
    if limit:
        results = results[:limit]
    
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"AUTOMAATTINEN RAG-ARVIOINTI")
    print(f"{'='*60}")
    print(f"Tiedosto: {input_path}")
    print(f"Kysymyksiä: {total}")
    print(f"Malli: {model}")
    print(f"{'='*60}\n")
    
    evaluated_count = 0
    
    for i, result in enumerate(results, 1):
        if result.get("error"):
            print(f"[{i:3d}/{total}] SKIP - virheellinen tulos")
            continue
        
        # Skip if already evaluated
        if result.get("auto_eval"):
            print(f"[{i:3d}/{total}] SKIP - jo arvioitu")
            evaluated_count += 1
            continue
        
        question = result.get("question", "")
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        
        print(f"[{i:3d}/{total}] {question[:50]}...")
        
        scores = evaluate_single(client, question, answer, sources, model)
        result["auto_eval"] = dict(scores)
        result["auto_eval"]["evaluated_at"] = datetime.now().isoformat()
        
        overall = scores["overall_score"]
        faith = scores["faithfulness"]
        rel = scores["relevance"]
        
        # Color-coded output
        status = "✓" if overall >= 0.7 else "!" if overall >= 0.5 else "✗"
        print(f"         {status} Overall: {overall:.2f} | Faith: {faith:.2f} | Rel: {rel:.2f}")
        
        evaluated_count += 1
        
        # Save checkpoint every 10 questions
        if evaluated_count % 10 == 0:
            save_results(data, input_path)
            print(f"         [Checkpoint: {evaluated_count} arvioitu]")
        
        # Rate limiting
        time.sleep(delay)
    
    # Final save
    save_results(data, input_path)
    
    # Print summary
    print_summary(results)


def print_summary(results: list[dict]) -> None:
    """Print evaluation summary."""
    evaluated = [r for r in results if r.get("auto_eval")]
    
    if not evaluated:
        print("\nEi arvioituja tuloksia.")
        return
    
    print(f"\n{'='*60}")
    print("ARVIOINTIYHTEENVETO")
    print(f"{'='*60}")
    print(f"Arvioitu: {len(evaluated)}/{len(results)}")
    
    # Calculate averages
    metrics = ["faithfulness", "relevance", "completeness", "hallucination_risk", "overall_score"]
    
    for metric in metrics:
        values = [r["auto_eval"].get(metric, 0) for r in evaluated]
        avg = sum(values) / len(values) if values else 0
        
        # Visual bar
        bar_len = int(avg * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        print(f"  {metric:<20}: [{bar}] {avg:.3f}")
    
    # Distribution
    print(f"\n{'─'*60}")
    print("LAATUJAKAUMA:")
    
    excellent = sum(1 for r in evaluated if r["auto_eval"].get("overall_score", 0) >= 0.8)
    good = sum(1 for r in evaluated if 0.6 <= r["auto_eval"].get("overall_score", 0) < 0.8)
    fair = sum(1 for r in evaluated if 0.4 <= r["auto_eval"].get("overall_score", 0) < 0.6)
    poor = sum(1 for r in evaluated if r["auto_eval"].get("overall_score", 0) < 0.4)
    
    print(f"  Erinomainen (≥0.8): {excellent:3d} ({100*excellent/len(evaluated):.1f}%)")
    print(f"  Hyvä (0.6-0.8):     {good:3d} ({100*good/len(evaluated):.1f}%)")
    print(f"  Kohtalainen (0.4-0.6): {fair:3d} ({100*fair/len(evaluated):.1f}%)")
    print(f"  Heikko (<0.4):      {poor:3d} ({100*poor/len(evaluated):.1f}%)")
    
    # Worst performing
    print(f"\n{'─'*60}")
    print("HEIKOIMMAT VASTAUKSET (parannettavat):")
    
    sorted_results = sorted(evaluated, key=lambda x: x["auto_eval"].get("overall_score", 0))
    
    for r in sorted_results[:10]:
        score = r["auto_eval"].get("overall_score", 0)
        reasoning = r["auto_eval"].get("reasoning", "")[:60]
        print(f"  Q{r['id']:03d} ({score:.2f}): {r['question'][:40]}...")
        if reasoning:
            print(f"         → {reasoning}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated RAG evaluation")
    parser.add_argument("input_file", type=Path, help="Results JSON file")
    parser.add_argument("--model", "-m", default="openai/gpt-oss-120b", help="Groq model")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between API calls")
    parser.add_argument("--limit", "-l", type=int, help="Limit questions to evaluate")
    parser.add_argument("--summary", "-s", action="store_true", help="Only show summary")
    parser.add_argument("--api-key", "-k", type=str, help="Groq API key (or use GROQ_API_KEY env)")
    
    args = parser.parse_args()
    
    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}")
        return
    
    # Get API key - prefer command line, then env var
    groq_api_key = args.api_key or os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        print("Error: GROQ_API_KEY not set")
        print("Use --api-key or set GROQ_API_KEY environment variable")
        return
    
    if args.summary:
        data = load_results(args.input_file)
        print_summary(data.get("results", []))
        return
    
    run_auto_evaluation(
        args.input_file,
        groq_api_key,
        model=args.model,
        delay=args.delay,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()

