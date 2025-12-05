#!/usr/bin/env python3
"""Quick summary of auto-evaluation results."""
import json
import sys
from pathlib import Path

def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation_results/full_250_run_enriched.json")
    
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    
    evals = [r["auto_eval"] for r in data["results"] if "auto_eval" in r]
    n = len(evals)
    
    if n == 0:
        print("Ei auto-evaluointeja!")
        return
    
    faith = sum(e["faithfulness"] for e in evals) / n
    relev = sum(e["relevance"] for e in evals) / n
    compl = sum(e["completeness"] for e in evals) / n
    halluc = sum(e["hallucination_risk"] for e in evals) / n
    overall = sum(e["overall_score"] for e in evals) / n
    
    print("=" * 50)
    print("250 KYSYMYKSEN EVALUOINTI - YHTEENVETO")
    print("=" * 50)
    print(f"Faithfulness:      {faith:.1%}")
    print(f"Relevance:         {relev:.1%}")
    print(f"Completeness:      {compl:.1%}")
    print(f"Hallucination:     {halluc:.1%}")
    print(f"Overall:           {overall:.1%}")
    print(f"Evaluoituja:       {n}/250")
    print("=" * 50)
    
    # Top 5 best
    sorted_results = sorted(
        [(r["id"], r["question"][:50], r["auto_eval"]["overall_score"]) 
         for r in data["results"] if "auto_eval" in r],
        key=lambda x: x[2], reverse=True
    )
    
    print("\nPARHAAT 5:")
    for i, (qid, q, score) in enumerate(sorted_results[:5], 1):
        print(f"  {i}. Q{qid} ({score:.0%}): {q}...")
    
    print("\nHUONOIMMAT 5:")
    for i, (qid, q, score) in enumerate(sorted_results[-5:], 1):
        print(f"  {i}. Q{qid} ({score:.0%}): {q}...")

if __name__ == "__main__":
    main()

