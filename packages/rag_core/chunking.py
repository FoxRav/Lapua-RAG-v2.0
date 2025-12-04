from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from docling_pipeline.config import get_settings as get_docling_settings

from .models import ChunkRecord

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedFilenameMeta:
    """Metadata parsed from a Lapua PDF/markdown filename."""

    toimielin: str
    meeting_date: date
    doc_id: str


PYKALA_PATTERN = re.compile(r"^§\s*(\d+)\b")

# Heuristic token-based chunking parameters.
# We approximate 1 token ≈ 1 word; this is sufficient to keep LLM prompts
# reasonably small while still preserving enough context.
MAX_TOKENS_PER_CHUNK = 700
CHUNK_OVERLAP_TOKENS = 150


def _parse_filename(md_path: Path) -> Optional[ParsedFilenameMeta]:
    """
    Extract toimielin and meeting date from filename.

    Expected filename examples:
    - 'Pöytäkirja-Kaupunginvaltuusto - 11.11.2024, klo 17_00_full.md'
    - 'Pöytäkirja-Kaupunginhallitus - 24.02.2025, klo 17_00_full.md'
    """
    stem = md_path.stem

    # Strip known suffixes like "_full" or "_docling"
    for suffix in ("_full", "_docling"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    # Example: "Pöytäkirja-Kaupunginvaltuusto - 11.11.2024, klo 17_00"
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", stem)
    if not date_match:
        return None

    date_str = date_match.group(1)
    try:
        meeting_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        return None

    # Toimielin: text between first "-" and " - <date>"
    # Split "Pöytäkirja-Kaupunginvaltuusto - 11.11.2024, klo 17_00"
    parts = stem.split(" - ")
    if len(parts) >= 2:
        header = parts[0]
    else:
        header = stem

    # Remove leading "Pöytäkirja-" or similar
    toimielin = header
    if header.lower().startswith("pöytäkirja-"):
        toimielin = header[len("Pöytäkirja-") :]

    toimielin = toimielin.strip()
    doc_id = f"{toimielin}_{meeting_date.isoformat()}"

    return ParsedFilenameMeta(toimielin=toimielin, meeting_date=meeting_date, doc_id=doc_id)


def _split_into_pykala_chunks(text: str) -> List[Tuple[str, Optional[str]]]:
    """
    Split markdown text into (pykala_nro, chunk_text) pairs.

    Heuristic: chunk starts at lines beginning with '§ <number>' and
    extends until the next such marker.
    """
    lines = text.splitlines()
    chunks: list[Tuple[str, Optional[str]]] = []

    current_pykala: Optional[str] = None
    current_lines: list[str] = []

    for line in lines:
        m = PYKALA_PATTERN.match(line.strip())
        if m:
            # Flush previous chunk if any
            if current_lines and current_pykala is not None:
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text:
                    chunks.append((current_pykala, chunk_text))
            # Start new chunk
            current_pykala = f"§ {m.group(1)}"
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        # Allow a final chunk even without explicit pykälä number
        chunks.append((current_pykala or None, chunk_text))

    return chunks


def _split_long_text_into_token_chunks(text: str) -> List[str]:
    """
    Split long text into overlapping token chunks.

    Tokens are approximated by whitespace-separated words. This is enough
    to keep individual chunks within the desired LLM context window while
    avoiding a heavy tokenizer dependency at this stage of the pipeline.
    """
    words = text.split()
    if not words:
        return []

    if len(words) <= MAX_TOKENS_PER_CHUNK:
        return [text]

    chunks: list[str] = []
    step = max(1, MAX_TOKENS_PER_CHUNK - CHUNK_OVERLAP_TOKENS)

    for start in range(0, len(words), step):
        end = start + MAX_TOKENS_PER_CHUNK
        segment_words = words[start:end]
        if not segment_words:
            break
        chunks.append(" ".join(segment_words))
        if end >= len(words):
            break

    return chunks


def _detect_flags(text: str) -> Tuple[bool, bool]:
    """Return (simpsio_flag, talous_flag) based on simple keyword heuristics."""
    lower = text.lower()

    simpsio_flag = any(
        kw in lower for kw in ("simpsiö", "simpsiönvuori", "simpsiönvuori oy", "simpsiön vuori")
    )
    talous_flag = any(
        kw in lower
        for kw in (
            "talousarvio",
            "budjetti",
            "määräraha",
            "investointi",
            "takaus",
            "takauksen",
            "laina",
            "talous",
            "rahoitus",
        )
    )
    return simpsio_flag, talous_flag


def _assign_themes(text: str) -> List[int]:
    """
    Very light-weight thematic tagging stub.

    Returns a list of theme ids (1–20). For now we only use a few
    obvious patterns and leave the rest to later LLM-based refinement.
    """
    lower = text.lower()
    themes: list[int] = []

    if any(kw in lower for kw in ("simpsiö", "simpsiönvuori")):
        themes.append(1)  # Example: Simpsiönvuori / riskihankkeet
    if any(kw in lower for kw in ("uimahalli", "uima-halli")):
        themes.append(2)  # Uimahalli
    if any(kw in lower for kw in ("takaus", "takauksen", "laina", "lainatakaus")):
        themes.append(14)  # Dense/Sparse/BM25 talous/rahoitus-teema

    # Deduplicate while preserving order
    seen: set[int] = set()
    unique = []
    for t in themes:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def create_chunks_from_markdown(md_path: Path, base_index: int = 0) -> List[ChunkRecord]:
    """
    Create ChunkRecord instances from a single markdown meeting document.

    We rely on filename parsing for toimielin and date, and on '§ <number>' markers
    for primary chunk boundaries.
    """
    meta = _parse_filename(md_path)
    if meta is None:
        _log.warning("Could not parse metadata from filename: %s", md_path.name)
        return []

    text = md_path.read_text(encoding="utf-8")
    pykala_chunks = _split_into_pykala_chunks(text)

    records: list[ChunkRecord] = []
    running_index = base_index

    for pykala_nro, chunk_text in pykala_chunks:
        if not chunk_text:
            continue

        sub_chunks = _split_long_text_into_token_chunks(chunk_text)
        for sub_text in sub_chunks:
            if not sub_text:
                continue

            simpsio_flag, talous_flag = _detect_flags(sub_text)
            teemat = _assign_themes(sub_text)

            record = ChunkRecord(
                doc_id=meta.doc_id,
                toimielin=meta.toimielin,
                poytakirja_pvm=meta.meeting_date,
                pykala_nro=pykala_nro,
                otsikko=None,
                sivu=None,
                teemat=teemat,
                asiasanat=[],
                simpsio_flag=simpsio_flag,
                talous_flag=talous_flag,
                chunk_index=running_index,
                chunk_text=sub_text,
            )
            records.append(record)
            running_index += 1

    return records


def run_all() -> Path:
    """
    Chunk all parsed markdown documents into a single JSONL file.

    Returns:
        Path to the written JSONL file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings = get_docling_settings()
    parsed_dir = settings.parsed_dir
    chunks_dir = settings.chunks_dir
    chunks_dir.mkdir(parents=True, exist_ok=True)

    output_jsonl = chunks_dir / "chunks.jsonl"
    output_json = chunks_dir / "chunks.json"

    md_files = sorted(parsed_dir.glob("*_full.md"))
    if not md_files:
        _log.warning("No *_full.md files found under %s", parsed_dir)
        return output_jsonl

    _log.info("Creating chunks from %d markdown files", len(md_files))

    all_records: list[ChunkRecord] = []
    for md in md_files:
        _log.info("Chunking %s", md.name)
        records = create_chunks_from_markdown(md, base_index=0)
        all_records.extend(records)

    _log.info("Total chunks created: %d", len(all_records))

    with output_jsonl.open("w", encoding="utf-8") as f_jsonl:
        for rec in all_records:
            # Pydantic v2 model_dump_json does not expose ensure_ascii; we rely on default
            f_jsonl.write(rec.model_dump_json() + "\n")

    with output_json.open("w", encoding="utf-8") as f_json:
        # Use JSONL-friendly, already-serialized form to avoid date issues.
        serializable = [json.loads(rec.model_dump_json()) for rec in all_records]
        json.dump(serializable, f_json, ensure_ascii=False, indent=2)

    _log.info("Chunks written to %s and %s", output_jsonl, output_json)
    return output_jsonl


__all__ = [
    "create_chunks_from_markdown",
    "run_all",
]


