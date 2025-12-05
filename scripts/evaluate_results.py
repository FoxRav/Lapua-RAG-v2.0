#!/usr/bin/env python3
"""
RAG Evaluation Scoring Tool - Manually evaluate RAG responses.

Usage:
    python scripts/evaluate_results.py evaluation_results/run_20251205_1200.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict


class EvaluationScores(TypedDict):
    relevance: int       # 1-5: Does the answer address the question?
    accuracy: int        # 1-5: Are the facts correct?
    completeness: int    # 1-5: Is the answer comprehensive?
    source_quality: int  # 1-5: Are sources relevant and correct?
    clarity: int         # 1-5: Is the answer clear and readable?
    notes: str           # Evaluator notes


CRITERIA = {
    "relevance": "Relevanssi (1-5): Vastaako vastaus suoraan kysymykseen?",
    "accuracy": "Tarkkuus (1-5): Ovatko faktat ja luvut oikein?",
    "completeness": "Kattavuus (1-5): Sisältääkö vastaus kaikki oleelliset tiedot?",
    "source_quality": "Lähteiden laatu (1-5): Ovatko lähteet relevantteja?",
    "clarity": "Selkeys (1-5): Onko vastaus selkeä ja ymmärrettävä?",
}


def load_results(filepath: Path) -> dict:
    """Load evaluation results from JSON file."""
    return json.loads(filepath.read_text(encoding="utf-8"))


def save_results(data: dict, filepath: Path) -> None:
    """Save evaluation results to JSON file."""
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_score(prompt: str, default: int | None = None) -> int:
    """Get a score from user input."""
    while True:
        try:
            if default is not None:
                user_input = input(f"{prompt} [{default}]: ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt}: ").strip()
            
            score = int(user_input)
            if 1 <= score <= 5:
                return score
            print("  → Anna arvo 1-5")
        except ValueError:
            print("  → Anna kokonaisluku 1-5")
        except KeyboardInterrupt:
            raise


def evaluate_single(result: dict, index: int, total: int) -> EvaluationScores | None:
    """Evaluate a single result interactively."""
    print(f"\n{'='*70}")
    print(f"KYSYMYS {index}/{total} (ID: {result['id']})")
    print(f"{'='*70}")
    print(f"Aihe: {result['topic']}")
    print(f"Kysymys: {result['question']}")
    print(f"{'─'*70}")
    print("VASTAUS:")
    print(result.get("answer", "[Ei vastausta]")[:2000])
    if len(result.get("answer", "")) > 2000:
        print(f"\n... [{len(result['answer']) - 2000} merkkiä lisää]")
    print(f"{'─'*70}")
    
    sources = result.get("sources", [])
    if sources:
        print(f"LÄHTEET ({len(sources)} kpl):")
        for i, src in enumerate(sources[:5], 1):
            doc_id = src.get("doc_id", "?")
            pykala = src.get("pykala_nro", "?")
            score = src.get("score", 0)
            print(f"  {i}. {doc_id} §{pykala} (score: {score:.2f})")
        if len(sources) > 5:
            print(f"  ... ja {len(sources) - 5} lisää")
    else:
        print("LÄHTEET: Ei lähteitä")
    
    print(f"{'─'*70}")
    print("Vastausaika: {:.1f}s".format(result.get("response_time_ms", 0) / 1000))
    print(f"{'─'*70}")
    
    # Check for existing scores
    existing = result.get("evaluation", {})
    
    print("\nARVIOINTI (paina Enter säilyttääksesi olemassa olevan, 's' ohittaaksesi):")
    
    # Check for skip
    first_input = input(f"{CRITERIA['relevance']} [{existing.get('relevance', '')}]: ").strip()
    if first_input.lower() == 's':
        print("  → Ohitettu")
        return None
    
    try:
        if first_input:
            relevance = int(first_input)
            if not (1 <= relevance <= 5):
                raise ValueError()
        else:
            relevance = existing.get("relevance", 3)
    except ValueError:
        print("  → Virheellinen arvo, käytetään oletusta 3")
        relevance = 3
    
    scores = EvaluationScores(
        relevance=relevance,
        accuracy=get_score(CRITERIA["accuracy"], existing.get("accuracy")),
        completeness=get_score(CRITERIA["completeness"], existing.get("completeness")),
        source_quality=get_score(CRITERIA["source_quality"], existing.get("source_quality")),
        clarity=get_score(CRITERIA["clarity"], existing.get("clarity")),
        notes=input("Huomautukset (vapaaehtoinen): ").strip() or existing.get("notes", ""),
    )
    
    avg = (
        scores["relevance"]
        + scores["accuracy"]
        + scores["completeness"]
        + scores["source_quality"]
        + scores["clarity"]
    ) / 5
    print(f"\n  → Keskiarvo: {avg:.2f}/5.0")
    
    return scores


def print_summary(results: list[dict]) -> None:
    """Print evaluation summary statistics."""
    evaluated = [r for r in results if r.get("evaluation")]
    
    if not evaluated:
        print("\nEi arvioituja tuloksia.")
        return
    
    print(f"\n{'='*70}")
    print("ARVIOINTIYHTEENVETO")
    print(f"{'='*70}")
    print(f"Arvioitu: {len(evaluated)}/{len(results)} kysymystä")
    
    # Calculate averages
    criteria_names = ["relevance", "accuracy", "completeness", "source_quality", "clarity"]
    
    for criterion in criteria_names:
        scores = [r["evaluation"][criterion] for r in evaluated if criterion in r.get("evaluation", {})]
        if scores:
            avg = sum(scores) / len(scores)
            print(f"  {criterion:<15}: {avg:.2f}/5.0")
    
    # Overall average
    all_scores = []
    for r in evaluated:
        ev = r.get("evaluation", {})
        for c in criteria_names:
            if c in ev:
                all_scores.append(ev[c])
    
    if all_scores:
        overall_avg = sum(all_scores) / len(all_scores)
        print(f"\n  {'KOKONAISARVIO':<15}: {overall_avg:.2f}/5.0")
    
    # Distribution
    print(f"\n{'─'*70}")
    print("JAKAUMA (kokonaisarviot per kysymys):")
    
    for r in evaluated:
        ev = r.get("evaluation", {})
        scores = [ev.get(c, 0) for c in criteria_names]
        avg = sum(scores) / len(scores) if scores else 0
        bar = "█" * int(avg) + "░" * (5 - int(avg))
        print(f"  Q{r['id']:03d}: [{bar}] {avg:.1f}")
    
    # Worst performing
    print(f"\n{'─'*70}")
    print("HEIKOIMMAT VASTAUKSET:")
    
    scored = []
    for r in evaluated:
        ev = r.get("evaluation", {})
        scores = [ev.get(c, 0) for c in criteria_names]
        avg = sum(scores) / len(scores) if scores else 0
        scored.append((avg, r))
    
    scored.sort(key=lambda x: x[0])
    for avg, r in scored[:5]:
        print(f"  Q{r['id']:03d} ({avg:.1f}): {r['question'][:50]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG results")
    parser.add_argument("input_file", type=Path, help="Input JSON file with results")
    parser.add_argument("--start", "-s", type=int, default=1, help="Start from question ID")
    parser.add_argument("--summary", action="store_true", help="Only show summary")
    
    args = parser.parse_args()
    
    if not args.input_file.exists():
        print(f"Error: File not found: {args.input_file}")
        sys.exit(1)
    
    data = load_results(args.input_file)
    results = data.get("results", [])
    
    if args.summary:
        print_summary(results)
        return
    
    print(f"Ladattu {len(results)} tulosta tiedostosta {args.input_file}")
    
    # Find starting point
    start_index = 0
    for i, r in enumerate(results):
        if r["id"] >= args.start:
            start_index = i
            break
    
    try:
        for i, result in enumerate(results[start_index:], start_index + 1):
            if result.get("error"):
                print(f"\n[Q{result['id']}] Ohitetaan virheellinen tulos: {result['error']}")
                continue
            
            scores = evaluate_single(result, i, len(results))
            
            if scores:
                result["evaluation"] = dict(scores)
                # Save after each evaluation
                save_results(data, args.input_file)
                print("  → Tallennettu")
    
    except KeyboardInterrupt:
        print("\n\nKeskeytettiin. Tulokset tallennettu.")
        save_results(data, args.input_file)
    
    print_summary(results)


if __name__ == "__main__":
    main()

