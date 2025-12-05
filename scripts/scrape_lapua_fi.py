#!/usr/bin/env python3
"""
Web scraper for lapua.fi - Extract all public content for RAG database.

Usage:
    python scripts/scrape_lapua_fi.py [--max-pages 500] [--delay 1.0]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://lapua.fi"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "lapua_fi_scraped"
USER_AGENT = "LapuaRAG-Scraper/1.0 (Research project; contact@example.com)"


class ScrapedPage(TypedDict):
    """Structure for a scraped page."""
    url: str
    title: str
    content: str
    category: str
    scraped_at: str
    word_count: int


def get_robots_txt() -> str:
    """Fetch and display robots.txt for reference."""
    try:
        resp = httpx.get(f"{BASE_URL}/robots.txt", timeout=10.0)
        return resp.text
    except Exception:
        return "Could not fetch robots.txt"


def extract_text_content(soup: BeautifulSoup) -> str:
    """Extract clean text content from page."""
    # Remove script, style, nav, footer elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
    
    # Find main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
    
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)
    
    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def extract_category(url: str) -> str:
    """Extract category from URL path."""
    path = urlparse(url).path.strip("/")
    if not path:
        return "etusivu"
    
    parts = path.split("/")
    if parts:
        return parts[0]
    return "muu"


def get_all_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract all internal links from page."""
    links = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        
        # Skip anchors, javascript, mailto, tel
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        
        # Convert relative to absolute
        full_url = urljoin(base_url, href)
        
        # Only keep lapua.fi links
        if urlparse(full_url).netloc in ["lapua.fi", "www.lapua.fi"]:
            # Remove fragments and query strings for deduplication
            clean_url = full_url.split("#")[0].split("?")[0]
            if clean_url and clean_url not in links:
                links.append(clean_url)
    
    return links


def scrape_page(url: str, client: httpx.Client) -> tuple[ScrapedPage | None, list[str]]:
    """Scrape a single page and return content + discovered links."""
    try:
        resp = client.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        
        # Skip non-HTML content
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None, []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        
        # Extract content
        content = extract_text_content(soup)
        
        # Skip pages with very little content
        word_count = len(content.split())
        if word_count < 50:
            return None, get_all_links(soup, url)
        
        page: ScrapedPage = {
            "url": url,
            "title": title,
            "content": content,
            "category": extract_category(url),
            "scraped_at": datetime.now().isoformat(),
            "word_count": word_count,
        }
        
        links = get_all_links(soup, url)
        
        return page, links
        
    except httpx.HTTPStatusError as e:
        print(f"  HTTP {e.response.status_code}: {url}")
        return None, []
    except Exception as e:
        print(f"  Error: {e}")
        return None, []


def scrape_site(max_pages: int = 500, delay: float = 1.0) -> list[ScrapedPage]:
    """Scrape the entire site using BFS."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    visited: set[str] = set()
    queue: deque[str] = deque([BASE_URL])
    pages: list[ScrapedPage] = []
    
    print("=" * 60)
    print("LAPUA.FI WEB SCRAPER")
    print("=" * 60)
    print(f"Max pages: {max_pages}")
    print(f"Delay: {delay}s")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)
    
    # Check robots.txt
    print("\nRobots.txt:")
    print(get_robots_txt()[:500])
    print("\n" + "=" * 60 + "\n")
    
    headers = {"User-Agent": USER_AGENT}
    
    with httpx.Client(headers=headers) as client:
        while queue and len(pages) < max_pages:
            url = queue.popleft()
            
            # Skip if already visited
            if url in visited:
                continue
            
            visited.add(url)
            
            print(f"[{len(pages) + 1:3d}/{max_pages}] {url[:70]}...")
            
            page, links = scrape_page(url, client)
            
            if page:
                pages.append(page)
                print(f"         ✓ {page['word_count']} words | {page['category']}")
                
                # Save checkpoint every 50 pages
                if len(pages) % 50 == 0:
                    save_pages(pages, OUTPUT_DIR / "checkpoint.json")
                    print(f"         [Checkpoint: {len(pages)} pages saved]")
            
            # Add new links to queue
            for link in links:
                if link not in visited:
                    queue.append(link)
            
            # Rate limiting
            time.sleep(delay)
    
    return pages


def save_pages(pages: list[ScrapedPage], filepath: Path) -> None:
    """Save scraped pages to JSON file."""
    data = {
        "metadata": {
            "source": "lapua.fi",
            "scraped_at": datetime.now().isoformat(),
            "total_pages": len(pages),
            "total_words": sum(p["word_count"] for p in pages),
        },
        "pages": pages,
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape lapua.fi for RAG database")
    parser.add_argument("--max-pages", type=int, default=500, help="Maximum pages to scrape")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    
    args = parser.parse_args()
    
    pages = scrape_site(max_pages=args.max_pages, delay=args.delay)
    
    # Save final results
    output_file = OUTPUT_DIR / f"lapua_fi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_pages(pages, output_file)
    
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"Total pages: {len(pages)}")
    print(f"Total words: {sum(p['word_count'] for p in pages):,}")
    print(f"Output: {output_file}")
    
    # Category breakdown
    categories: dict[str, int] = {}
    for page in pages:
        cat = page["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()

