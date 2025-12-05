#!/usr/bin/env python3
"""
Lightweight website content indexer - processes one page at a time to save memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path


def chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks."""
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    if len(text) <= max_chars:
        return [text] if text else []
    
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            bp = text.rfind('\n\n', start, end)
            if bp <= start:
                bp = text.rfind('. ', start, end)
            if bp > start:
                end = bp + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def process_page(page: dict, output_file) -> int:
    """Process single page and write chunks to file."""
    url = page.get("url", "")
    title = page.get("title", "")
    content = page.get("content", "")
    category = page.get("category", "etusivu")
    scraped_at = page.get("scraped_at", "")
    
    if not content or len(content) < 50:
        return 0
    
    doc_id = f"web_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    
    try:
        scraped_date = date.fromisoformat(scraped_at.split("T")[0])
    except:
        scraped_date = date.today()
    
    text_chunks = chunk_text(content)
    count = 0
    
    for idx, chunk_text_content in enumerate(text_chunks):
        record = {
            "doc_id": doc_id,
            "toimielin": f"verkkosivut/{category}",
            "poytakirja_pvm": scraped_date.isoformat(),
            "pykala_nro": None,
            "otsikko": title if idx == 0 else f"{title} ({idx + 1})",
            "sivu": None,
            "teemat": [20],
            "asiasanat": [category],
            "simpsio_flag": "simpsi" in chunk_text_content.lower(),
            "talous_flag": any(k in chunk_text_content.lower() for k in ["euro", "milj", "budjetti"]),
            "chunk_index": idx,
            "chunk_text": chunk_text_content,
        }
        output_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        count += 1
    
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/chunks/chunks.jsonl"))
    args = parser.parse_args()
    
    print(f"Processing: {args.source}")
    
    # Stream process JSON
    with open(args.source, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    pages = data.get("pages", [])
    total = 0
    
    with open(args.output, "a", encoding="utf-8") as out:
        for i, page in enumerate(pages):
            count = process_page(page, out)
            total += count
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{len(pages)} pages, {total} chunks")
    
    print(f"Done: {total} chunks added")


if __name__ == "__main__":
    main()

