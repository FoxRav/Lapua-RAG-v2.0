#!/usr/bin/env python3
"""Scrape thermopolis.fi for RAG."""
import json, time, re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque
import httpx
from bs4 import BeautifulSoup

BASE = "https://www.thermopolis.fi"
OUT = Path(__file__).parent.parent / "data" / "thermopolis_scraped"

def extract(soup):
    for el in soup(["script", "style", "nav", "footer", "header"]):
        el.decompose()
    main = soup.find("main") or soup.find("article") or soup
    return re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))

def links(soup, base):
    out = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.startswith(("#", "javascript:", "mailto:", "tel:")): continue
        full = urljoin(base, h)
        if "thermopolis.fi" in urlparse(full).netloc:
            out.append(full.split("#")[0].split("?")[0])
    return list(set(out))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    visited, queue, pages = set(), deque([BASE]), []
    print("Scraping thermopolis.fi...")
    
    with httpx.Client(headers={"User-Agent": "LapuaRAG/1.0"}, timeout=15) as c:
        while queue and len(pages) < 80:
            url = queue.popleft()
            if url in visited: continue
            visited.add(url)
            try:
                r = c.get(url, follow_redirects=True)
                if "text/html" not in r.headers.get("content-type", ""): continue
                soup = BeautifulSoup(r.text, "html.parser")
                title = soup.find("title")
                title = title.get_text(strip=True) if title else ""
                content = extract(soup)
                wc = len(content.split())
                if wc >= 30:
                    cat = urlparse(url).path.strip("/").split("/")[0] or "etusivu"
                    pages.append({
                        "url": url, "title": title, "content": content,
                        "category": cat, "scraped_at": datetime.now().isoformat(),
                        "word_count": wc
                    })
                    print(f"[{len(pages):2d}] {url[:55]}... ({wc} words)")
                for l in links(soup, url):
                    if l not in visited: queue.append(l)
                time.sleep(0.5)
            except Exception as e:
                print(f"Error: {e}")
    
    out = {
        "metadata": {
            "source": "thermopolis.fi",
            "scraped_at": datetime.now().isoformat(),
            "total_pages": len(pages),
            "total_words": sum(p["word_count"] for p in pages)
        },
        "pages": pages
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = OUT / f"thermopolis_{ts}.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print(f"Done: {len(pages)} pages, {sum(p['word_count'] for p in pages)} words -> {f}")

if __name__ == "__main__":
    main()

