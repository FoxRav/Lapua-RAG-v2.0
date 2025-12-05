#!/usr/bin/env python3
"""
Web scraper for simpsio.com - Extract content for RAG database.
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.simpsio.com"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "simpsio_scraped"
USER_AGENT = "LapuaRAG-Scraper/1.0"


def extract_text(soup: BeautifulSoup) -> str:
    """Extract clean text from page."""
    for el in soup(["script", "style", "nav", "footer", "header", "aside"]):
        el.decompose()
    
    main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
    text = (main or soup).get_text(separator="\n", strip=True)
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)
    return re.sub(r'\n{3,}', '\n\n', text)


def get_links(soup: BeautifulSoup, base: str) -> list[str]:
    """Get all internal links from page."""
    links: list[str] = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        
        full = urljoin(base, href)
        parsed = urlparse(full)
        
        if "simpsio.com" in parsed.netloc:
            clean = full.split("#")[0].split("?")[0]
            if clean not in links:
                links.append(clean)
    
    return links


def scrape_simpsio(max_pages: int = 100, delay: float = 0.5) -> None:
    """Scrape simpsio.com website."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    visited: set[str] = set()
    queue: deque[str] = deque([BASE_URL])
    pages: list[dict] = []
    
    print("=" * 60)
    print("SIMPSIO.COM WEB SCRAPER")
    print("=" * 60)
    print(f"Max pages: {max_pages}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60 + "\n")
    
    headers = {"User-Agent": USER_AGENT}
    
    with httpx.Client(headers=headers, timeout=15.0) as client:
        while queue and len(pages) < max_pages:
            url = queue.popleft()
            
            if url in visited:
                continue
            visited.add(url)
            
            try:
                resp = client.get(url, follow_redirects=True)
                
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue
                
                soup = BeautifulSoup(resp.text, "html.parser")
                
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else ""
                
                content = extract_text(soup)
                word_count = len(content.split())
                
                if word_count >= 30:
                    path = urlparse(url).path.strip("/")
                    category = path.split("/")[0] if path else "etusivu"
                    
                    pages.append({
                        "url": url,
                        "title": title,
                        "content": content,
                        "category": category,
                        "scraped_at": datetime.now().isoformat(),
                        "word_count": word_count,
                    })
                    print(f"[{len(pages):3d}/{max_pages}] {url[:55]}...")
                    print(f"         ✓ {word_count} words | {category}")
                
                for link in get_links(soup, url):
                    if link not in visited:
                        queue.append(link)
                
                time.sleep(delay)
                
            except Exception as e:
                print(f"  Error: {url}: {e}")
    
    # Save results
    output = {
        "metadata": {
            "source": "simpsio.com",
            "scraped_at": datetime.now().isoformat(),
            "total_pages": len(pages),
            "total_words": sum(p["word_count"] for p in pages),
        },
        "pages": pages,
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = OUTPUT_DIR / f"simpsio_{timestamp}.json"
    
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"Total pages: {len(pages)}")
    print(f"Total words: {sum(p['word_count'] for p in pages):,}")
    print(f"Output: {outfile}")
    
    # Category breakdown
    categories: dict[str, int] = {}
    for page in pages:
        cat = page["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    scrape_simpsio()

