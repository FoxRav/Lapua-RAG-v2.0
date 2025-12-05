#!/usr/bin/env python3
"""
Convert scraped lapua.fi content to ChunkRecord format and add to index.

Usage:
    python scripts/index_website_content.py [--source data/lapua_fi_scraped/lapua_fi_*.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

# Category to theme mapping (based on existing theme IDs 1-20)
CATEGORY_TO_THEMES: dict[str, list[int]] = {
    "varhaiskasvatus-ja-koulutus": [4],  # Koulutus
    "hyvinvointi": [5, 6],  # Hyvinvointi, Terveys
    "kulttuuri-vapaa-aika-ja-matkailu": [7, 8],  # Kulttuuri, Liikunta
    "asuminen-ja-ymparisto": [9, 10],  # Asuminen, Ympäristö
    "hallinto-ja-paatoksenteko": [1, 2],  # Hallinto, Päätöksenteko
    "tyo-ja-yrittaminen": [3, 11],  # Työllisyys, Elinkeinot
    "uutisia": [20],  # Ajankohtaiset
    "kansalaisopisto": [7],  # Kulttuuri
    "kirjasto": [7],  # Kulttuuri
    "info": [1],  # Yleinen
}

# Keywords for flag detection
SIMPSIO_KEYWORDS = ["simpsiö", "simpsio", "simpsiönvuori"]
TALOUS_KEYWORDS = ["talous", "budjetti", "euro", "miljoonaa", "rahoitus", "maksu", "hinta"]


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks based on approximate token count."""
    # Rough estimate: 1 token ≈ 4 characters for Finnish
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4
    
    # Clean text
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    if len(text) <= max_chars:
        return [text] if text else []
    
    chunks: list[str] = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            break_point = text.rfind('\n\n', start, end)
            if break_point == -1 or break_point <= start:
                # Look for sentence break
                break_point = text.rfind('. ', start, end)
            if break_point == -1 or break_point <= start:
                # Look for any whitespace
                break_point = text.rfind(' ', start, end)
            if break_point > start:
                end = break_point + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start with overlap
        start = end - overlap_chars if end < len(text) else end
    
    return chunks


def detect_flags(text: str) -> tuple[bool, bool]:
    """Detect Simpsiö and financial content flags."""
    text_lower = text.lower()
    
    simpsio = any(kw in text_lower for kw in SIMPSIO_KEYWORDS)
    talous = any(kw in text_lower for kw in TALOUS_KEYWORDS)
    
    return simpsio, talous


def create_doc_id(url: str) -> str:
    """Create stable document ID from URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"lapua_fi_{url_hash}"


def page_to_chunks(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a scraped page to ChunkRecord dicts."""
    url = page.get("url", "")
    title = page.get("title", "")
    content = page.get("content", "")
    category = page.get("category", "etusivu")
    scraped_at = page.get("scraped_at", "")
    
    if not content or len(content) < 50:
        return []
    
    doc_id = create_doc_id(url)
    
    # Parse date from scraped_at
    try:
        scraped_date = date.fromisoformat(scraped_at.split("T")[0])
    except (ValueError, IndexError):
        scraped_date = date.today()
    
    # Get themes from category
    themes = CATEGORY_TO_THEMES.get(category, [20])  # Default to "Ajankohtaiset"
    
    # Chunk the content
    text_chunks = chunk_text(content)
    
    records: list[dict[str, Any]] = []
    
    for idx, chunk_text_content in enumerate(text_chunks):
        simpsio_flag, talous_flag = detect_flags(chunk_text_content)
        
        record = {
            "doc_id": doc_id,
            "toimielin": f"lapua.fi/{category}",
            "poytakirja_pvm": scraped_date.isoformat(),
            "pykala_nro": None,
            "otsikko": title if idx == 0 else f"{title} (osa {idx + 1})",
            "sivu": None,
            "teemat": themes,
            "asiasanat": [category, "verkkosivut"],
            "simpsio_flag": simpsio_flag,
            "talous_flag": talous_flag,
            "chunk_index": idx,
            "chunk_text": chunk_text_content,
            # Extra metadata for website content
            "_source_url": url,
            "_source_type": "website",
        }
        records.append(record)
    
    return records


def process_scraped_json(input_path: Path, output_path: Path) -> int:
    """Process scraped JSON and append to chunks.jsonl."""
    
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    pages = data.get("pages", [])
    print(f"Processing {len(pages)} pages from {input_path.name}")
    
    all_chunks: list[dict[str, Any]] = []
    
    for page in pages:
        chunks = page_to_chunks(page)
        all_chunks.extend(chunks)
    
    print(f"Created {len(all_chunks)} chunks")
    
    # Append to existing chunks.jsonl
    mode = "a" if output_path.exists() else "w"
    
    with open(output_path, mode, encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False, default=str) + "\n")
    
    return len(all_chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index website content into RAG chunks")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to scraped JSON file (default: latest in data/lapua_fi_scraped/)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/chunks/chunks.jsonl"),
        help="Output chunks.jsonl path"
    )
    
    args = parser.parse_args()
    
    # Find source file
    if args.source:
        source_path = args.source
    else:
        scraped_dir = Path("data/lapua_fi_scraped")
        if not scraped_dir.exists():
            raise FileNotFoundError(f"Scraped data directory not found: {scraped_dir}")
        
        json_files = sorted(scraped_dir.glob("lapua_fi_*.json"))
        if not json_files:
            raise FileNotFoundError(f"No scraped JSON files found in {scraped_dir}")
        
        source_path = json_files[-1]  # Latest file
    
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    print("=" * 60)
    print("WEBSITE CONTENT INDEXER")
    print("=" * 60)
    print(f"Source: {source_path}")
    print(f"Output: {args.output}")
    print("=" * 60)
    
    # Count existing chunks
    existing_count = 0
    if args.output.exists():
        with open(args.output, "r", encoding="utf-8") as f:
            existing_count = sum(1 for _ in f)
        print(f"Existing chunks: {existing_count}")
    
    # Process and append
    new_count = process_scraped_json(source_path, args.output)
    
    print("=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"New chunks added: {new_count}")
    print(f"Total chunks: {existing_count + new_count}")
    print()
    print("Next step: Re-index to Qdrant with:")
    print("  python -m packages.rag_core.indexing")


if __name__ == "__main__":
    main()

