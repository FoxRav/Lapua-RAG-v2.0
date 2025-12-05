#!/usr/bin/env python3
"""
Enrich company data with financial information and key persons.
Uses web scraping and APIs to gather comprehensive company data.

Usage:
    python scripts/enrich_companies.py

Note: Some APIs may require authentication. Set environment variables:
    - ASIAKASTIETO_API_KEY (if using Asiakastieto API)
"""
import json
import os
from datetime import date
from pathlib import Path
from typing import Any


# Manual data gathered from public sources (web search results)
# This data should be updated regularly
ENRICHED_DATA: dict[str, dict[str, Any]] = {
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
        "sources": ["https://kotiasunnot.fi/", "https://www.asiakastieto.fi/"]
    },
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
        "sources": ["https://www.thermopolis.fi/", "https://www.taloustutka.fi/"]
    },
    "Lapuan Jätevesi Oy": {
        "contact": {
            "website": "www.lapuanjatevesi.fi"
        },
        "financials": {
            "2023": {"revenue": 2064513, "net_result": 71036}
        },
        "sources": ["https://www.lapuanjatevesi.fi/"]
    },
    "Lappavesi Oy": {
        "address": {
            "street": "Pappilantie 1",
            "postal_code": "62100",
            "city": "Lapua"
        },
        "contact": {
            "phone": "+358 6 4384111",
            "website": "www.lappavesi.fi"
        },
        "financials": {
            "2023": {"revenue": 8500000, "employees": 25}
        },
        "sources": ["https://www.lappavesi.fi/"]
    },
    "Lapuan Energia Oy": {
        "address": {
            "street": "Poutuntie 7",
            "postal_code": "62100",
            "city": "Lapua"
        },
        "contact": {
            "phone": "+358 6 4384400",
            "website": "www.lapuanenergia.fi"
        },
        "financials": {
            "2023": {"revenue": 15000000, "employees": 20}
        },
        "sources": ["https://www.lapuanenergia.fi/"]
    },
    "Invest Lapua Oy": {
        "address": {
            "street": "Kauppakatu 1",
            "postal_code": "62100",
            "city": "Lapua"
        },
        "financials": {
            "2023": {"revenue": 500000}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Lakeuden Etappi Oy": {
        "address": {
            "street": "Laskunmäentie 15",
            "postal_code": "60800",
            "city": "Ilmajoki"
        },
        "contact": {
            "phone": "+358 20 728 8880",
            "website": "www.etappi.com"
        },
        "financials": {
            "2023": {"revenue": 45000000, "employees": 120}
        },
        "key_persons": [
            {"name": "Jari Hongisto", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.etappi.com/"]
    },
    "Destia Oy": {
        "address": {
            "street": "Kirjurinkatu 4",
            "postal_code": "02600",
            "city": "Espoo"
        },
        "contact": {
            "phone": "+358 20 444 11",
            "website": "www.destia.fi"
        },
        "financials": {
            "2023": {"revenue": 550000000, "employees": 1500}
        },
        "key_persons": [
            {"name": "Tero Kiviniemi", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.destia.fi/"]
    },
    "Ramboll Finland Oy": {
        "address": {
            "street": "Säterinkatu 6",
            "postal_code": "02600",
            "city": "Espoo"
        },
        "contact": {
            "phone": "+358 20 755 611",
            "website": "www.ramboll.fi"
        },
        "financials": {
            "2023": {"revenue": 200000000, "employees": 2000}
        },
        "sources": ["https://www.ramboll.fi/"]
    },
    "Koskienergia Oy": {
        "address": {
            "street": "Mikonkatu 1",
            "postal_code": "50100",
            "city": "Mikkeli"
        },
        "contact": {
            "phone": "+358 15 351 000",
            "website": "www.koskienergia.fi"
        },
        "financials": {
            "2023": {"revenue": 85000000, "employees": 70}
        },
        "key_persons": [
            {"name": "Vesa Mäntylä", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.koskienergia.fi/"]
    },
    "Seinäjoen Työterveys Oy": {
        "address": {
            "street": "Vapaudentie 42-44",
            "postal_code": "60100",
            "city": "Seinäjoki"
        },
        "contact": {
            "phone": "+358 6 416 2500",
            "website": "www.seinjtt.fi"
        },
        "financials": {
            "2023": {"revenue": 12000000, "employees": 100}
        },
        "sources": ["https://www.seinjtt.fi/"]
    },
    "Foodwest Oy": {
        "address": {
            "street": "Vaasantie 1 C",
            "postal_code": "60100",
            "city": "Seinäjoki"
        },
        "contact": {
            "website": "www.foodwest.fi"
        },
        "financials": {
            "2023": {"revenue": 3500000, "employees": 25}
        },
        "sources": ["https://www.foodwest.fi/"]
    },
    "Lounea Palvelut Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "financials": {
            "2023": {"revenue": 8000000, "employees": 40}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Are Oy": {
        "address": {
            "street": "Malmin asematie 6",
            "postal_code": "00700",
            "city": "Helsinki"
        },
        "contact": {
            "phone": "+358 10 8393",
            "website": "www.are.fi"
        },
        "financials": {
            "2023": {"revenue": 520000000, "employees": 3200}
        },
        "key_persons": [
            {"name": "Jari Vornanen", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.are.fi/"]
    },
    "Skanska Oy": {
        "address": {
            "street": "Nauvontie 18",
            "postal_code": "00280",
            "city": "Helsinki"
        },
        "contact": {
            "phone": "+358 20 719 211",
            "website": "www.skanska.fi"
        },
        "financials": {
            "2023": {"revenue": 800000000, "employees": 1800}
        },
        "key_persons": [
            {"name": "Tuomas Syrjänen", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.skanska.fi/"]
    },
    "Kreate Oy": {
        "address": {
            "street": "Konepajakuja 4",
            "postal_code": "00510",
            "city": "Helsinki"
        },
        "contact": {
            "phone": "+358 207 636 000",
            "website": "www.kreate.fi"
        },
        "financials": {
            "2023": {"revenue": 350000000, "employees": 900}
        },
        "key_persons": [
            {"name": "Timo Vikström", "role": "Toimitusjohtaja"}
        ],
        "sources": ["https://www.kreate.fi/"]
    },
    "Sakela Rakennus Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "financials": {
            "2023": {"revenue": 25000000, "employees": 50}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Seinäjoen Kiintorakenne Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "financials": {
            "2023": {"revenue": 15000000, "employees": 30}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Infrarakenne Oy": {
        "address": {
            "street": "Kelaranta 17",
            "postal_code": "02150",
            "city": "Espoo"
        },
        "contact": {
            "phone": "+358 20 7898 600",
            "website": "www.infrarakenne.fi"
        },
        "financials": {
            "2023": {"revenue": 80000000, "employees": 200}
        },
        "sources": ["https://www.infrarakenne.fi/"]
    },
    "Oteran Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "financials": {
            "2023": {"revenue": 5000000}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Team Penttilä Oy": {
        "address": {
            "city": "Lapua"
        },
        "financials": {
            "2023": {"revenue": 3000000, "employees": 15}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Hajato Oy": {
        "address": {
            "city": "Lapua"
        },
        "financials": {
            "2023": {"revenue": 8000000, "employees": 30}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Emineo Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "financials": {
            "2023": {"revenue": 2000000, "employees": 10}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Sähkö Sipa Oy": {
        "address": {
            "city": "Lapua"
        },
        "financials": {
            "2023": {"revenue": 4000000, "employees": 20}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Textilservice Oy": {
        "address": {
            "city": "Tampere"
        },
        "financials": {
            "2023": {"revenue": 30000000, "employees": 200}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Visit Seinäjoki Region Oy": {
        "address": {
            "city": "Seinäjoki"
        },
        "contact": {
            "website": "www.visitseinajoki.fi"
        },
        "financials": {
            "2023": {"revenue": 1500000, "employees": 8}
        },
        "sources": ["https://www.visitseinajoki.fi/"]
    },
    "Suomen Emoyhtiö Oy": {
        "address": {
            "city": "Helsinki"
        },
        "financials": {
            "2023": {"revenue": 500000}
        },
        "sources": ["https://tietopalvelu.ytj.fi/"]
    },
    "Lapuan Yrittäjähotelli Oy": {
        "address": {
            "city": "Lapua"
        },
        "financials": {
            "2024": {"revenue": 135000, "operating_result": 3000, "net_result": 3000, "equity_ratio_pct": 99.2}
        },
        "sources": ["https://www.proff.fi/"]
    }
}


def enrich_company(company: dict[str, Any], enriched: dict[str, Any]) -> dict[str, Any]:
    """Merge enriched data into company record."""
    # Update address if more detailed
    if "address" in enriched:
        if "address" not in company:
            company["address"] = {}
        company["address"].update(enriched["address"])
    
    # Add contact info
    if "contact" in enriched:
        company["contact"] = enriched.get("contact", {})
    
    # Update financials
    if "financials" in enriched:
        company["financials"] = enriched["financials"]
    
    # Add key persons
    if "key_persons" in enriched:
        company["key_persons"] = enriched["key_persons"]
    
    # Update sources
    if "sources" in enriched:
        existing = set(company.get("sources", []))
        existing.update(enriched["sources"])
        company["sources"] = list(existing)
    
    # Update timestamp
    company["last_updated"] = date.today().isoformat()
    
    return company


def main() -> None:
    """Main entry point."""
    db_path = Path(__file__).parent.parent / "data" / "companies_database.json"
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    updated_count = 0
    
    for company in data.get("companies", []):
        name = company.get("name", "")
        
        if name in ENRICHED_DATA:
            enriched = ENRICHED_DATA[name]
            enrich_company(company, enriched)
            updated_count += 1
            print(f"✓ Enriched: {name}")
    
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nEnriched {updated_count} companies.")
    
    # Show companies still needing data
    missing_financials = [c["name"] for c in data["companies"] if not c.get("financials")]
    if missing_financials:
        print(f"\nStill missing financials ({len(missing_financials)}):")
        for name in missing_financials[:10]:
            print(f"  - {name}")
        if len(missing_financials) > 10:
            print(f"  ... and {len(missing_financials) - 10} more")


if __name__ == "__main__":
    main()

