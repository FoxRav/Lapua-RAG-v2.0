from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult, DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend

from .config import get_settings

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocElement:
    """Minimal representation of a logical document element for downstream chunking."""

    text: str
    page: int | None
    section_path: str | None


def _build_converter() -> DocumentConverter:
    """Create an optimal Docling PDF converter for RAG ingestion."""
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
    )
    pdf_format_option = PdfFormatOption(
        pipeline_options=pipeline_options,
        backend=DoclingParseV4DocumentBackend,
    )
    converter = DocumentConverter(format_options={InputFormat.PDF: pdf_format_option})
    return converter


def convert_pdf(pdf_path: Path) -> DoclingDocument:
    """Convert a single PDF to a DoclingDocument."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    converter = _build_converter()
    _log.info("Converting PDF with Docling: %s", pdf_path)
    result: ConversionResult = converter.convert(pdf_path)

    if result.status.value != "success":
        raise RuntimeError(f"Docling conversion failed: {result.status.value}")

    return result.document


def extract_elements(doc: DoclingDocument) -> List[DocElement]:
    """
    Extract logical elements from a DoclingDocument.

    This keeps the logic minimal for now: we rely on the HybridChunker and
    contextualized text, but expose elements as a separate abstraction in case
    we later want to implement pykälä-level extraction here.
    """
    chunker = HybridChunker()
    elements: list[DocElement] = []

    for chunk in chunker.chunk(doc):
        page = getattr(getattr(chunk, "meta", None), "page", None)
        section_path = None
        if getattr(chunk, "meta", None) is not None:
            doc_items = getattr(chunk.meta, "doc_items", None)
            if doc_items:
                labels: list[str] = []
                for item in doc_items:
                    label_value = getattr(item, "label", None)
                    if label_value is not None:
                        labels.append(str(label_value))
                if labels:
                    section_path = " / ".join(labels)

        elements.append(
            DocElement(
                text=chunk.text,
                page=page,
                section_path=section_path,
            )
        )

    return elements


def save_doc_outputs(doc: DoclingDocument, pdf_path: Path, output_dir: Path) -> None:
    """Persist Docling outputs (full markdown and raw doc JSON)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / f"{pdf_path.stem}_full.md"
    json_path = output_dir / f"{pdf_path.stem}_docling.json"

    markdown_content = doc.export_to_markdown()
    markdown_path.write_text(markdown_content, encoding="utf-8")

    from docling_core.types.doc import ImageRefMode

    doc.save_as_json(json_path, image_mode=ImageRefMode.PLACEHOLDER)


def parse_pdf_to_elements(pdf_path: Path, output_dir: Path | None = None) -> Iterable[DocElement]:
    """
    Convert a PDF to DocElements and persist Docling outputs for inspection.

    Returns an iterable of DocElement instances for further chunking.
    """
    settings = get_settings()
    if output_dir is None:
        output_dir = settings.parsed_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    doc = convert_pdf(pdf_path)
    save_doc_outputs(doc, pdf_path, output_dir)
    return extract_elements(doc)


__all__ = ["DocElement", "parse_pdf_to_elements"]


