#!/usr/bin/env python3
"""
Enrich company data with financial information and key persons.
ONLY VERIFIED DATA from web searches - no fabricated/estimated data.

Usage:
    python scripts/enrich_companies.py
"""
import json
from datetime import date
from pathlib import Path
from typing import Any


# ONLY data that was ACTUALLY VERIFIED through web search results
# Source: Web search results from 2025-12-05
VERIFIED_DATA: dict[str, dict[str, Any]] = {
    # Verified from kotiasunnot.fi and taloustutka.fi
    "Lapuan Kotiasunnot Oy": {
        "address": {
            "street": "Poutuntie 7",
            "postal_code": "62100",
            "city": "Lapua"
        },
        "contact": {
            "phone": "+358 44 4384088",
            "website": "kotiasunnot.fi"
        },
        "financials": {
            "2024": {"revenue": 4741515, "operating_result": 690732, "net_result": -36726, "equity_ratio_pct": 2, "employees": 9},
            "2023": {"revenue": 4633962, "operating_result": 565846, "net_result": 43, "employees": 8},
            "2022": {"revenue": 4455386, "operating_result": 598284, "net_result": 140617, "employees": 4}
        },
        "key_persons": [
            {"name": "Jussi Voutilainen", "role": "Toimitusjohtaja"},
            {"name": "Kai Pöntinen", "role": "Hallituksen puheenjohtaja"},
            {"name": "Tarja Isotalo", "role": "Hallituksen jäsen"},
            {"name": "Jorma Kallio", "role": "Hallituksen jäsen"},
            {"name": "Kim-Peter Lindström", "role": "Hallituksen jäsen"},
            {"name": "Hanne Ronkainen", "role": "Hallituksen jäsen"},
            {"name": "Elina Pesonen", "role": "Tilintarkastaja"}
        ],
        "sources": ["https://kotiasunnot.fi/yhteystiedot/", "https://www.taloustutka.fi/company/2841190-1"]
    },
    # Verified from taloustutka.fi and thermopolis.fi
    "Thermopolis Oy": {
        "address": {
            "street": "Vanhan Paukun tie 1 B",
            "postal_code": "62100",
            "city": "Lapua"
        },
        "contact": {
            "website": "www.thermopolis.fi"
        },
        "financials": {
            "2024": {"revenue": 122061, "operating_result": 6678, "net_result": 7835, "employees": 4},
            "2023": {"revenue": 161856, "operating_result": -8898, "net_result": -9349, "employees": 5},
            "2022": {"revenue": 104736, "operating_result": -7066, "net_result": -9083, "employees": 8}
        },
        "sources": ["https://www.thermopolis.fi/", "https://www.taloustutka.fi/company/2029286-4"]
    },
    # Verified from lapuanjatevesi.fi vuosikertomus
    "Lapuan Jätevesi Oy": {
        "contact": {
            "website": "www.lapuanjatevesi.fi"
        },
        "financials": {
            "2023": {"revenue": 2064513, "net_result": 71036}
        },
        "sources": ["https://www.lapuanjatevesi.fi/wp-content/uploads/2024/04/Vuosikertomus-JV-2023.pdf"]
    },
    # Verified from proff.fi
    "Lapuan Yrittäjähotelli Oy": {
        "financials": {
            "2024": {"revenue": 135000, "operating_result": 3000, "net_result": 3000, "equity_ratio_pct": 99.2}
        },
        "sources": ["https://www.proff.fi/yritys/lapuan-yrittajahotelli-oy/"]
    }
}


def enrich_company(company: dict[str, Any], verified: dict[str, Any]) -> dict[str, Any]:
    """Merge verified data into company record."""
    if "address" in verified:
        if "address" not in company:
            company["address"] = {}
        company["address"].update(verified["address"])
    
    if "contact" in verified:
        if "contact" not in company:
            company["contact"] = {}
        company["contact"].update(verified["contact"])
    
    if "financials" in verified:
        company["financials"] = verified["financials"]
    
    if "key_persons" in verified:
        company["key_persons"] = verified["key_persons"]
    
    if "sources" in verified:
        existing = set(company.get("sources", []))
        existing.update(verified["sources"])
        company["sources"] = list(existing)
    
    company["last_updated"] = date.today().isoformat()
    
    return company


def remove_unverified_financials(company: dict[str, Any], verified_names: set[str]) -> None:
    """Remove financials from companies that weren't verified."""
    name = company.get("name", "")
    # Keep Simpsiönvuori - that was verified earlier from Asiakastieto
    if name not in verified_names and name != "Simpsiönvuori Oy":
        if "financials" in company:
            del company["financials"]
        if "key_persons" in company and name != "Simpsiönvuori Oy":
            del company["key_persons"]


def main() -> None:
    """Main entry point."""
    db_path = Path(__file__).parent.parent / "data" / "companies_database.json"
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    verified_names = set(VERIFIED_DATA.keys())
    verified_names.add("Simpsiönvuori Oy")  # This was verified earlier
    
    # First, remove unverified data
    for company in data.get("companies", []):
        remove_unverified_financials(company, verified_names)
    
    # Then add verified data
    updated_count = 0
    for company in data.get("companies", []):
        name = company.get("name", "")
        if name in VERIFIED_DATA:
            enrich_company(company, VERIFIED_DATA[name])
            updated_count += 1
            print(f"✓ Verified: {name}")
    
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Count status
    total = len(data["companies"])
    with_fin = sum(1 for c in data["companies"] if c.get("financials"))
    with_kp = sum(1 for c in data["companies"] if c.get("key_persons"))
    
    print(f"\n✓ Updated {updated_count} companies with VERIFIED data")
    print(f"Total: {total}, With financials: {with_fin}, With key persons: {with_kp}")


if __name__ == "__main__":
    main()
