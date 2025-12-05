#!/usr/bin/env python3
"""
Compare multiple RAG evaluation runs to identify improvements.

Usage:
    python scripts/compare_runs.py evaluation_results/baseline.json evaluation_results/run2.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_results(filepath: Path) -> dict:
    """Load evaluation results from JSON file."""
    return json.loads(filepath.read_text(encoding="utf-8"))


def get_avg_score(result: dict) -> float | None:
    """Calculate average score for a single result."""
    ev = result.get("evaluation", {})
    if not ev:
        return None
    
    criteria = ["relevance", "accuracy", "completeness", "source_quality", "clarity"]
    scores = [ev.get(c) for c in criteria if ev.get(c) is not None]
    
    if not scores:
        return None
    return sum(scores) / len(scores)


def compare_runs(run1_path: Path, run2_path: Path) -> None:
    """Compare two evaluation runs."""
    run1 = load_results(run1_path)
    run2 = load_results(run2_path)
    
    results1 = {r["id"]: r for r in run1.get("results", [])}
    results2 = {r["id"]: r for r in run2.get("results", [])}
    
    print(f"\n{'='*70}")
    print("VERTAILU")
    print(f"{'='*70}")
    print(f"Run 1: {run1_path.name}")
    print(f"Run 2: {run2_path.name}")
    print(f"{'='*70}\n")
    
    # Overall comparison
    scores1 = []
    scores2 = []
    improvements = []
    regressions = []
    
    common_ids = set(results1.keys()) & set(results2.keys())
    
    for qid in sorted(common_ids):
        r1 = results1[qid]
        r2 = results2[qid]
        
        s1 = get_avg_score(r1)
        s2 = get_avg_score(r2)
        
        if s1 is not None:
            scores1.append(s1)
        if s2 is not None:
            scores2.append(s2)
        
        if s1 is not None and s2 is not None:
            diff = s2 - s1
            if diff > 0.5:
                improvements.append((qid, s1, s2, diff, r1["question"]))
            elif diff < -0.5:
                regressions.append((qid, s1, s2, diff, r1["question"]))
    
    # Summary stats
    if scores1:
        avg1 = sum(scores1) / len(scores1)
        print(f"Run 1 keskiarvo: {avg1:.2f}/5.0 ({len(scores1)} arvioitu)")
    else:
        print("Run 1: Ei arvioituja tuloksia")
        avg1 = 0
    
    if scores2:
        avg2 = sum(scores2) / len(scores2)
        print(f"Run 2 keskiarvo: {avg2:.2f}/5.0 ({len(scores2)} arvioitu)")
    else:
        print("Run 2: Ei arvioituja tuloksia")
        avg2 = 0
    
    if scores1 and scores2:
        diff = avg2 - avg1
        trend = "↑" if diff > 0 else "↓" if diff < 0 else "="
        print(f"\nEro: {diff:+.2f} {trend}")
    
    # Response time comparison
    times1 = [r["response_time_ms"] for r in results1.values() if r.get("response_time_ms")]
    times2 = [r["response_time_ms"] for r in results2.values() if r.get("response_time_ms")]
    
    if times1 and times2:
        avg_t1 = sum(times1) / len(times1)
        avg_t2 = sum(times2) / len(times2)
        print(f"\nVastausaika:")
        print(f"  Run 1: {avg_t1:.0f}ms")
        print(f"  Run 2: {avg_t2:.0f}ms")
        print(f"  Ero: {avg_t2 - avg_t1:+.0f}ms")
    
    # Per-criteria comparison
    criteria = ["relevance", "accuracy", "completeness", "source_quality", "clarity"]
    
    print(f"\n{'─'*70}")
    print("PER KRITEERI:")
    print(f"{'─'*70}")
    
    for criterion in criteria:
        c1 = [r["evaluation"].get(criterion) for r in results1.values() 
              if r.get("evaluation", {}).get(criterion) is not None]
        c2 = [r["evaluation"].get(criterion) for r in results2.values() 
              if r.get("evaluation", {}).get(criterion) is not None]
        
        if c1 and c2:
            a1 = sum(c1) / len(c1)
            a2 = sum(c2) / len(c2)
            diff = a2 - a1
            trend = "↑" if diff > 0.1 else "↓" if diff < -0.1 else "="
            print(f"  {criterion:<15}: {a1:.2f} → {a2:.2f} ({diff:+.2f}) {trend}")
    
    # Improvements
    if improvements:
        print(f"\n{'─'*70}")
        print(f"PARANNUKSET ({len(improvements)} kpl):")
        print(f"{'─'*70}")
        for qid, s1, s2, diff, q in sorted(improvements, key=lambda x: -x[3])[:10]:
            print(f"  Q{qid:03d}: {s1:.1f} → {s2:.1f} (+{diff:.1f}) | {q[:50]}...")
    
    # Regressions
    if regressions:
        print(f"\n{'─'*70}")
        print(f"HEIKENNYKSET ({len(regressions)} kpl):")
        print(f"{'─'*70}")
        for qid, s1, s2, diff, q in sorted(regressions, key=lambda x: x[3])[:10]:
            print(f"  Q{qid:03d}: {s1:.1f} → {s2:.1f} ({diff:.1f}) | {q[:50]}...")
    
    # Recommendation
    print(f"\n{'='*70}")
    print("SUOSITUS:")
    print(f"{'='*70}")
    
    if avg2 > avg1 + 0.1 and len(regressions) < len(improvements):
        print("✓ Run 2 on parempi. Suositellaan käyttöönottoa.")
    elif avg2 < avg1 - 0.1:
        print("✗ Run 2 on heikompi. Palataan Run 1 asetuksiin.")
    else:
        print("≈ Ei merkittävää eroa. Tarkastele yksittäisiä kysymyksiä.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare RAG evaluation runs")
    parser.add_argument("run1", type=Path, help="First run (baseline)")
    parser.add_argument("run2", type=Path, help="Second run (comparison)")
    
    args = parser.parse_args()
    
    if not args.run1.exists():
        print(f"Error: File not found: {args.run1}")
        return
    if not args.run2.exists():
        print(f"Error: File not found: {args.run2}")
        return
    
    compare_runs(args.run1, args.run2)


if __name__ == "__main__":
    main()

