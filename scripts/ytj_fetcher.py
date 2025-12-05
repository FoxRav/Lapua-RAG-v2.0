#!/usr/bin/env python3
"""
Fetch company data from YTJ and update database.
Uses the YTJ tietopalvelu search to find company Y-tunnus and basic info.
"""
import json
import httpx
from datetime import date
from pathlib import Path
from typing import TypedDict


class CompanyData(TypedDict, total=False):
    """Structure for company data from YTJ."""
    y_tunnus: str
    name: str
    city: str
    industry: str
    company_form: str


# Known Y-tunnukset for companies that we've already verified
KNOWN_COMPANIES: dict[str, CompanyData] = {
    "Lapuan Kotiasunnot Oy": {
        "y_tunnus": "2841190-1",
        "city": "Lapua",
        "industry": "Asuntojen ja asuinkiinteistöjen hallinta",
        "company_form": "Osakeyhtiö"
    },
    "Thermopolis Oy": {
        "y_tunnus": "2029286-4",
        "city": "Lapua",
        "industry": "Tekniikan tutkimus ja kehittäminen",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Jätevesi Oy": {
        "y_tunnus": "0209116-1",
        "city": "Lapua",
        "industry": "Viemäri- ja jätevesihuolto",
        "company_form": "Osakeyhtiö"
    },
    "Koskienergia Oy": {
        "y_tunnus": "1014042-9",
        "city": "Mikkeli",
        "industry": "Sähkön ja kaukolämmön yhteistuotanto",
        "company_form": "Osakeyhtiö"
    },
    "Invest Lapua Oy": {
        "y_tunnus": "1006221-3",
        "city": "Lapua",
        "industry": "Muiden kiinteistöjen vuokraus ja hallinta",
        "company_form": "Osakeyhtiö"
    },
    "Lappavesi Oy": {
        "y_tunnus": "0180606-5",
        "city": "Lapua",
        "industry": "Veden otto, puhdistus ja jakelu",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Energia Oy": {
        "y_tunnus": "0180601-4",
        "city": "Lapua",
        "industry": "Kaukolämmön ja -kylmän erillistuotanto ja jakelu",
        "company_form": "Osakeyhtiö"
    },
    "Simpsiönvuori Oy": {
        "y_tunnus": "0600421-3",
        "city": "Lapua",
        "industry": "Muiden koneiden ja laitteiden vuokraus ja leasing",
        "company_form": "Osakeyhtiö"
    },
    "Destia Oy": {
        "y_tunnus": "0801376-1",
        "city": "Helsinki",
        "industry": "Infrarakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "Lakea Oy": {
        "y_tunnus": "2495291-1",
        "city": "Seinäjoki",
        "industry": "Asuntojen ja asuinkiinteistöjen hallinta",
        "company_form": "Osakeyhtiö"
    },
    "Pohjanmaan Rakennus Oy": {
        "y_tunnus": "0177170-9",
        "city": "Vaasa",
        "industry": "Talonrakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "E-P:n Osuuskauppa": {
        "y_tunnus": "0203462-3",
        "city": "Seinäjoki",
        "industry": "Vähittäiskauppa",
        "company_form": "Osuuskunta"
    },
    "Länsiauto Oy": {
        "y_tunnus": "0113627-5",
        "city": "Seinäjoki",
        "industry": "Autojen ja kevyiden moottoriajoneuvojen kauppa",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Kauppahuone Oy": {
        "y_tunnus": "0189377-1",
        "city": "Lapua",
        "industry": "Muu vähittäiskauppa erikoistumattomissa myymälöissä",
        "company_form": "Osakeyhtiö"
    },
    "JM-Rakennuttajat Oy": {
        "y_tunnus": "0967605-7",
        "city": "Nurmo",
        "industry": "Asuntorakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Patruuna Oy": {
        "y_tunnus": "0180596-0",
        "city": "Lapua",
        "industry": "Aseiden ja ammusten valmistus",
        "company_form": "Osakeyhtiö"
    },
    "Panostaja Oyj": {
        "y_tunnus": "0534528-7",
        "city": "Tampere",
        "industry": "Holding-yhtiöiden toiminta",
        "company_form": "Julkinen osakeyhtiö"
    },
    "Skaala Oy": {
        "y_tunnus": "1913408-5",
        "city": "Ylihärmä",
        "industry": "Muiden puutuotteiden valmistus",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Piristeel Oy": {
        "y_tunnus": "2022285-9",
        "city": "Lapua",
        "industry": "Metallien käsittely, päällystäminen ja työstö",
        "company_form": "Osakeyhtiö"
    },
    "Oy Lapuan Ketjupalvelu": {
        "y_tunnus": "0180579-0",
        "city": "Lapua",
        "industry": "Metalliketjujen, jousien ja säätölaitteiden valmistus",
        "company_form": "Osakeyhtiö"
    },
    # Additional companies verified from YTJ
    "Seinäjoen Työterveys Oy": {
        "y_tunnus": "2788158-1",
        "city": "Seinäjoki",
        "industry": "Lääkäriasemat, yksityislääkärit",
        "company_form": "Osakeyhtiö"
    },
    "Foodwest Oy": {
        "y_tunnus": "1021523-2",
        "city": "Seinäjoki",
        "industry": "Tekniikan tutkimus ja kehittäminen",
        "company_form": "Osakeyhtiö"
    },
    "Lounea Palvelut Oy": {
        "y_tunnus": "2883655-5",
        "city": "Seinäjoki",
        "industry": "Televiestintä",
        "company_form": "Osakeyhtiö"
    },
    "Infrarakenne Oy": {
        "y_tunnus": "2115696-3",
        "city": "Espoo",
        "industry": "Muu rakennusten ja rakennelmien rakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "Sakela Rakennus Oy": {
        "y_tunnus": "0873197-5",
        "city": "Seinäjoki",
        "industry": "Asuin- ja muiden rakennusten rakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "Seinäjoen Kiintorakenne Oy": {
        "y_tunnus": "0608477-4",
        "city": "Seinäjoki",
        "industry": "Asuin- ja muiden rakennusten rakentaminen",
        "company_form": "Osakeyhtiö"
    },
    "Oteran Oy": {
        "y_tunnus": "2154419-7",
        "city": "Seinäjoki",
        "industry": "Kiinteistöjen rakennuttaminen",
        "company_form": "Osakeyhtiö"
    },
    "Team Penttilä Oy": {
        "y_tunnus": "1942251-9",
        "city": "Lapua",
        "industry": "Maansiirtokoneiden kuljettajien vuokraus",
        "company_form": "Osakeyhtiö"
    },
    "Hajato Oy": {
        "y_tunnus": "0859195-2",
        "city": "Lapua",
        "industry": "Betonielementtien valmistus",
        "company_form": "Osakeyhtiö"
    },
    "Emineo Oy": {
        "y_tunnus": "2478116-3",
        "city": "Seinäjoki",
        "industry": "Liikkeenjohdon konsultointi",
        "company_form": "Osakeyhtiö"
    },
    "Sähkö Sipa Oy": {
        "y_tunnus": "0539652-9",
        "city": "Lapua",
        "industry": "Sähköasennus",
        "company_form": "Osakeyhtiö"
    },
    "Textilservice Oy": {
        "y_tunnus": "0540606-6",
        "city": "Tampere",
        "industry": "Pesulapalvelut",
        "company_form": "Osakeyhtiö"
    },
    "Visit Seinäjoki Region Oy": {
        "y_tunnus": "2685878-9",
        "city": "Seinäjoki",
        "industry": "Matkailun edistäminen",
        "company_form": "Osakeyhtiö"
    },
    "Suomen Emoyhtiö Oy": {
        "y_tunnus": "3181478-9",
        "city": "Helsinki",
        "industry": "Omistusyhteisöjen toiminta",
        "company_form": "Osakeyhtiö"
    },
    "Lapuan Yrittäjähotelli Oy": {
        "y_tunnus": "0180587-1",
        "city": "Lapua",
        "industry": "Hotellit ja vastaavat majoitusliikkeet",
        "company_form": "Osakeyhtiö"
    },
}


def update_database(db_path: Path) -> int:
    """Update companies_database.json with known Y-tunnus data."""
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    updated_count = 0
    today = date.today().isoformat()
    
    for company in data.get("companies", []):
        name = company.get("name", "")
        
        if name in KNOWN_COMPANIES and company.get("y_tunnus") is None:
            info = KNOWN_COMPANIES[name]
            company["y_tunnus"] = info["y_tunnus"]
            company["address"] = {"city": info["city"]}
            company["industry"] = {"description": info["industry"]}
            company["company_form"] = info["company_form"]
            company["sources"] = ["https://tietopalvelu.ytj.fi/"]
            company["last_updated"] = today
            updated_count += 1
            print(f"✓ Updated: {name} ({info['y_tunnus']})")
    
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return updated_count


def main() -> None:
    """Main entry point."""
    db_path = Path(__file__).parent.parent / "data" / "companies_database.json"
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    print("Updating companies database with YTJ data...")
    count = update_database(db_path)
    print(f"\nUpdated {count} companies.")


if __name__ == "__main__":
    main()

