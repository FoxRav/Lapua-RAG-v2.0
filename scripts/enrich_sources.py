#!/usr/bin/env python3
"""
Enrich evaluation results with source chunk text from normalized_chunks.jsonl.

This allows the auto-evaluation to verify answers against actual source content.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_chunks_index(chunks_file: Path) -> dict[str, dict]:
    """
    Load normalized chunks and create an index by organisaatio + kokous_pvm + pykala.
    
    Chunk fields: organisaatio, kokous_pvm, pykala
    Source fields: toimielin, poytakirja_pvm, pykala_nro
    """
    index: dict[str, dict] = {}
    
    with open(chunks_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            
            chunk = json.loads(line)
            
            # Create key from organisaatio + kokous_pvm + pykala
            organisaatio = chunk.get("organisaatio", "")
            kokous_pvm = chunk.get("kokous_pvm", "")
            pykala = chunk.get("pykala", "")
            
            if organisaatio and kokous_pvm and pykala:
                # Normalize pykala (remove spaces, etc.)
                pykala_normalized = pykala.strip().replace(" ", "")
                key = f"{organisaatio}|{kokous_pvm}|{pykala_normalized}"
                
                # Store or concatenate if multiple chunks for same pykälä
                if key not in index:
                    index[key] = {
                        "text": chunk.get("text", ""),
                        "organisaatio": organisaatio,
                        "kokous_pvm": kokous_pvm,
                        "pykala": pykala,
                    }
                else:
                    # Append text if same pykälä has multiple chunks
                    existing_text = index[key]["text"]
                    new_text = chunk.get("text", "")
                    if new_text and new_text not in existing_text:
                        index[key]["text"] = existing_text + "\n\n" + new_text
    
    return index


def enrich_results(results_file: Path, chunks_file: Path) -> None:
    """Enrich results with source text."""
    
    print(f"Loading chunks from: {chunks_file}")
    chunks_index = load_chunks_index(chunks_file)
    print(f"Loaded {len(chunks_index)} unique doc+pykälä combinations")
    
    print(f"\nLoading results from: {results_file}")
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    results = data.get("results", [])
    print(f"Found {len(results)} results")
    
    enriched_count = 0
    source_count = 0
    
    for result in results:
        sources = result.get("sources", [])
        
        for source in sources:
            toimielin = source.get("toimielin", "")
            pvm = source.get("poytakirja_pvm", "")
            pykala = source.get("pykala_nro", "")
            
            # Normalize pykala to match chunk format
            pykala_normalized = pykala.strip().replace(" ", "") if pykala else ""
            
            key = f"{toimielin}|{pvm}|{pykala_normalized}"
            
            if key in chunks_index:
                chunk_data = chunks_index[key]
                source["text"] = chunk_data["text"][:2000]  # Limit text length
                source_count += 1
        
        if sources:
            enriched_count += 1
    
    # Save enriched results
    output_file = results_file.with_stem(results_file.stem + "_enriched")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"ENRICHMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Results enriched: {enriched_count}/{len(results)}")
    print(f"Sources with text: {source_count}")
    print(f"Output saved to: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich results with source text")
    parser.add_argument("results_file", type=Path, help="Results JSON file")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("DATA_päättävät_elimet_20251202/rag_output/normalized_chunks.jsonl"),
        help="Chunks JSONL file",
    )
    
    args = parser.parse_args()
    
    if not args.results_file.exists():
        print(f"Error: Results file not found: {args.results_file}")
        return
    
    if not args.chunks.exists():
        print(f"Error: Chunks file not found: {args.chunks}")
        return
    
    enrich_results(args.results_file, args.chunks)


if __name__ == "__main__":
    main()

