#!/usr/bin/env python3
"""
Extract companies, projects, and key entities from Lapua RAG chunks.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


def extract_companies(text: str) -> list[str]:
    """Extract company names from text."""
    patterns = [
        r'\b([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*\s+(?:Oy|Ab|Oyj))\b',
        r'\b([A-ZÄÖÅ][a-zäöå]+(?:[-][A-Za-zäöå]+)*\s+(?:Oy|Ab|Oyj))\b',
        r'\b([A-ZÄÖÅ][A-ZÄÖÅa-zäöå]+\s+(?:Osuuskunta|osuuskunta))\b',
        r'\b(Thermopolis\s+Oy)\b',
        r'\b(Simpsiönvuori\s+Oy)\b',
        r'\b(Lapuan\s+[A-ZÄÖÅ][a-zäöå]+\s+Oy)\b',
        r'\b([A-ZÄÖÅ][a-zäöå]+\s+Kiinteistö(?:t)?\s+Oy)\b',
    ]
    
    companies = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        companies.extend(matches)
    
    return companies


def extract_projects(text: str) -> list[str]:
    """Extract major project references from text."""
    project_keywords = [
        r'(uimahalli\w*)',
        r'(Simpsiö\w*)',
        r'(investoint\w+)',
        r'(hank\w+)',
        r'(rakennus\w*)',
        r'(saneerau\w+)',
        r'(peruskorja\w+)',
        r'(laajennu\w+)',
    ]
    
    projects = []
    for pattern in project_keywords:
        matches = re.findall(pattern, text, re.IGNORECASE)
        projects.extend(matches)
    
    return projects


def extract_money_amounts(text: str) -> list[tuple[str, str]]:
    """Extract monetary amounts with context."""
    # Pattern for euro amounts
    pattern = r'(\d[\d\s]*(?:,\d+)?\s*(?:miljoon\w*|milj\.?|€|euroa?|M€))'
    matches = re.findall(pattern, text)
    return matches


def main() -> None:
    chunks_file = Path("DATA_päättävät_elimet_20251202/rag_output/normalized_chunks.jsonl")
    
    if not chunks_file.exists():
        print(f"Error: {chunks_file} not found")
        return
    
    all_companies: Counter[str] = Counter()
    all_projects: Counter[str] = Counter()
    company_contexts: dict[str, list[str]] = {}
    
    print("Analyzing chunks...")
    
    with open(chunks_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            text = chunk.get("text", "")
            org = chunk.get("organisaatio", "")
            pvm = chunk.get("kokous_pvm", "")
            pykala = chunk.get("pykala", "")
            
            # Extract companies
            companies = extract_companies(text)
            for company in companies:
                company_clean = company.strip()
                if len(company_clean) > 5:  # Filter out noise
                    all_companies[company_clean] += 1
                    if company_clean not in company_contexts:
                        company_contexts[company_clean] = []
                    if len(company_contexts[company_clean]) < 3:
                        company_contexts[company_clean].append(f"{org} {pvm} {pykala}")
            
            # Extract projects
            projects = extract_projects(text)
            for project in projects:
                all_projects[project.lower()] += 1
    
    print("\n" + "="*60)
    print("YHTIÖT JA YRITYKSET (esiintymiskerrat)")
    print("="*60)
    
    for company, count in all_companies.most_common(50):
        contexts = company_contexts.get(company, [])
        context_str = " | ".join(contexts[:2])
        print(f"{count:4d}x  {company}")
        if context_str:
            print(f"       → {context_str}")
    
    print("\n" + "="*60)
    print("HANKKEET JA PROJEKTIT (esiintymiskerrat)")
    print("="*60)
    
    for project, count in all_projects.most_common(30):
        print(f"{count:4d}x  {project}")
    
    # Save to file
    output = {
        "companies": [
            {"name": name, "count": count, "contexts": company_contexts.get(name, [])}
            for name, count in all_companies.most_common(100)
        ],
        "projects": [
            {"keyword": kw, "count": count}
            for kw, count in all_projects.most_common(50)
        ]
    }
    
    output_file = Path("tmp/extracted_entities.json")
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTallennettu: {output_file}")


if __name__ == "__main__":
    main()

