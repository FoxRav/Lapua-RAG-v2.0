from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import click

from .config import get_settings
from .parser import DocElement, parse_pdf_to_elements

_log = logging.getLogger(__name__)


def _iter_pdfs(root: Path) -> Iterable[Path]:
    for pdf_path in sorted(root.rglob("*.pdf")):
        if pdf_path.is_file():
            yield pdf_path


@click.group()
def main() -> None:
    """CLI entrypoint for the Docling ingestion pipeline."""


@main.command("parse-all")
def parse_all() -> None:
    """
    Parse all PDFs under the configured pdf_raw_dir with Docling.

    For each PDF we create:
    - full markdown (`*_full.md`)
    - raw Docling JSON (`*_docling.json`)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings = get_settings()
    pdf_root = settings.pdf_raw_dir
    output_dir = settings.parsed_dir

    _log.info("Using pdf_root=%s", pdf_root)
    _log.info("Output directory (parsed)=%s", output_dir)

    if not pdf_root.exists():
        raise FileNotFoundError(f"PDF root directory does not exist: {pdf_root}")

    pdf_files = list(_iter_pdfs(pdf_root))
    if not pdf_files:
        _log.warning("No PDF files found under %s", pdf_root)
        return

    _log.info("Found %d PDF files to process", len(pdf_files))

    for idx, pdf in enumerate(pdf_files, start=1):
        _log.info("Processing %d/%d: %s", idx, len(pdf_files), pdf)
        try:
            list(parse_pdf_to_elements(pdf, output_dir=output_dir))
        except Exception as exc:
            _log.error("Failed to parse %s: %s", pdf, exc, exc_info=True)
            continue

    _log.info("Docling parsing for all PDFs completed.")


if __name__ == "__main__":
    main()


