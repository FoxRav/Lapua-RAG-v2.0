#!/usr/bin/env python3
"""
Automatic company data fetcher for Finnish companies.
Uses PRH (Patent and Registration Office) open data API.

API Documentation: https://avoindata.prh.fi/ytj.html

Usage:
    python scripts/fetch_company_data.py [--update-all]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_log = logging.getLogger(__name__)

# YTJ Web Search URL (public web interface, no API key needed)
YTJ_SEARCH_URL = "https://tietopalvelu.ytj.fi/yritystiedot.aspx"
YTJ_API_URL = "https://avoindata.prh.fi/bis/v1"  # Backup API

# Database path
DATA_DIR = Path(__file__).parent.parent / "data"
COMPANIES_DB = DATA_DIR / "companies_database.json"


def search_company_by_name(name: str) -> Optional[dict]:
    """Search for a company by name using YTJ API."""
    try:
        url = PRH_API_BASE
        params = {
            "name": name,
        }
        headers = {
            "Accept": "application/json",
        }
        
        response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, list) and data:
            return data[0]
        elif isinstance(data, dict):
            results = data.get("results", data.get("companies", []))
            if results:
                return results[0]
        return None
        
    except httpx.HTTPStatusError as e:
        _log.debug(f"HTTP {e.response.status_code} for {name}")
        return None
    except Exception as e:
        _log.debug(f"Error searching for {name}: {e}")
        return None


def get_company_details(business_id: str) -> Optional[dict]:
    """Get detailed company information by Y-tunnus."""
    try:
        # Clean business_id (remove dashes if present)
        clean_id = business_id.replace("-", "")
        
        url = f"{PRH_API_BASE}/{clean_id}"
        headers = {
            "Accept": "application/json",
        }
        
        response = httpx.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, dict):
            if "businessId" in data:
                return data
            results = data.get("results", data.get("companies", []))
            if results:
                return results[0]
        return data if data else None
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            _log.debug(f"Company not found: {business_id}")
        else:
            _log.debug(f"HTTP error for {business_id}: {e}")
        return None
    except Exception as e:
        _log.debug(f"Error fetching details for {business_id}: {e}")
        return None


def parse_prh_data(prh_data: dict) -> dict:
    """Parse PRH API response into our database format."""
    parsed = {}
    
    # Basic info
    parsed["y_tunnus"] = prh_data.get("businessId", "")
    parsed["name_official"] = prh_data.get("name", "")
    
    # Registration date
    reg_date = prh_data.get("registrationDate")
    if reg_date:
        parsed["registration_date"] = reg_date
    
    # Company form
    company_form = prh_data.get("companyForm")
    if company_form:
        parsed["company_form"] = company_form
    
    # Addresses
    addresses = prh_data.get("addresses", [])
    for addr in addresses:
        if addr.get("type") == 1:  # Postal address
            parsed["address"] = {
                "street": addr.get("street", ""),
                "postal_code": addr.get("postCode", ""),
                "city": addr.get("city", ""),
            }
            break
    
    # Business lines (toimialat)
    business_lines = prh_data.get("businessLines", [])
    if business_lines:
        latest_line = business_lines[0]  # Most recent
        parsed["industry"] = {
            "code": latest_line.get("code", ""),
            "description": latest_line.get("name", ""),
        }
    
    # Contact details
    contact_details = prh_data.get("contactDetails", [])
    contact = {}
    for detail in contact_details:
        detail_type = detail.get("type", "")
        value = detail.get("value", "")
        if detail_type == "Kotisivun www-osoite":
            contact["website"] = value
        elif detail_type == "Matkapuhelin":
            contact["phone"] = value
        elif detail_type == "Puhelin":
            contact["phone"] = contact.get("phone", value)
    if contact:
        parsed["contact"] = contact
    
    # Registered offices
    registered_offices = prh_data.get("registeredOffices", [])
    if registered_offices:
        parsed["registered_office"] = registered_offices[0].get("name", "")
    
    # Company status
    status = prh_data.get("companyStatus")
    if status:
        parsed["status"] = status
    
    # Liquidations
    liquidations = prh_data.get("liquidations", [])
    if liquidations:
        parsed["liquidation_info"] = liquidations[0]
    
    return parsed


def update_company_in_database(
    db: dict,
    company_name: str,
    prh_data: dict
) -> bool:
    """Update a company entry in the database with PRH data."""
    parsed = parse_prh_data(prh_data)
    
    # Find the company in database
    for company in db.get("companies", []):
        if company.get("name", "").lower() == company_name.lower():
            # Update fields
            if parsed.get("y_tunnus"):
                company["y_tunnus"] = parsed["y_tunnus"]
            if parsed.get("address"):
                company["address"] = parsed["address"]
            if parsed.get("contact"):
                company["contact"] = {**company.get("contact", {}), **parsed["contact"]}
            if parsed.get("industry"):
                company["industry"] = parsed["industry"]
            if parsed.get("registration_date"):
                company["registration_date"] = parsed["registration_date"]
            if parsed.get("company_form"):
                company["company_form"] = parsed["company_form"]
            if parsed.get("status"):
                company["status"] = parsed["status"]
            
            company["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            company["data_source"] = "PRH avoindata"
            
            _log.info(f"✓ Updated: {company_name}")
            return True
    
    _log.warning(f"Company not found in database: {company_name}")
    return False


def load_database() -> dict:
    """Load the companies database."""
    if not COMPANIES_DB.exists():
        return {"metadata": {}, "companies": [], "categories": {}}
    return json.loads(COMPANIES_DB.read_text(encoding="utf-8"))


def save_database(db: dict) -> None:
    """Save the companies database."""
    COMPANIES_DB.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch company data from PRH")
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update all companies in database"
    )
    parser.add_argument(
        "--company",
        type=str,
        help="Update specific company by name"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls (seconds)"
    )
    
    args = parser.parse_args()
    
    db = load_database()
    companies = db.get("companies", [])
    
    if args.company:
        # Update single company
        companies_to_update = [c for c in companies if args.company.lower() in c.get("name", "").lower()]
    elif args.update_all:
        # Update all companies without y_tunnus or with old data
        companies_to_update = [
            c for c in companies
            if not c.get("y_tunnus") or not c.get("last_updated")
        ]
    else:
        # Show stats and exit
        total = len(companies)
        with_data = sum(1 for c in companies if c.get("y_tunnus"))
        print(f"\n{'='*60}")
        print(f"COMPANIES DATABASE STATUS")
        print(f"{'='*60}")
        print(f"Total companies: {total}")
        print(f"With Y-tunnus: {with_data}")
        print(f"Missing data: {total - with_data}")
        print(f"\nRun with --update-all to fetch missing data")
        return
    
    print(f"\n{'='*60}")
    print(f"FETCHING COMPANY DATA FROM PRH")
    print(f"{'='*60}")
    print(f"Companies to update: {len(companies_to_update)}")
    print(f"API: {PRH_API_BASE}")
    print(f"{'='*60}\n")
    
    updated = 0
    failed = 0
    
    for i, company in enumerate(companies_to_update, 1):
        name = company.get("name", "")
        y_tunnus = company.get("y_tunnus")
        
        print(f"[{i}/{len(companies_to_update)}] {name}...", end=" ")
        
        # Try to get data
        prh_data = None
        
        if y_tunnus:
            # Use Y-tunnus if available
            prh_data = get_company_details(y_tunnus)
        
        if not prh_data:
            # Search by name
            search_result = search_company_by_name(name)
            if search_result:
                business_id = search_result.get("businessId")
                if business_id:
                    prh_data = get_company_details(business_id)
        
        if prh_data:
            if update_company_in_database(db, name, prh_data):
                updated += 1
            else:
                failed += 1
        else:
            print(f"✗ Not found")
            failed += 1
        
        time.sleep(args.delay)
    
    # Save updated database
    save_database(db)
    
    print(f"\n{'='*60}")
    print(f"FETCH COMPLETE")
    print(f"{'='*60}")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")
    print(f"Database saved to: {COMPANIES_DB}")


if __name__ == "__main__":
    main()

