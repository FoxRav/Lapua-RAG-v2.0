from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class DoclingPipelineSettings(BaseSettings):
    """Configuration for the Docling ingestion pipeline."""

    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2],
        description="Repository root directory.",
    )

    # Input PDFs (Lapua data). By default we reference the existing DATA-folder.
    pdf_raw_dir: Path = Field(
        default_factory=lambda: Path("DATA_päättävät_elimet_20251202"),
        description="Root directory containing original PDF files.",
    )

    # Parsed Docling outputs
    parsed_dir: Path = Field(
        default_factory=lambda: Path("data") / "parsed",
        description="Directory for per-document parsed outputs (JSON/Markdown).",
    )

    # Optional directory for combined/chunked data
    chunks_dir: Path = Field(
        default_factory=lambda: Path("data") / "chunks",
        description="Directory for combined chunk outputs (JSON/JSONL).",
    )

    class Config:
        env_prefix = "LAPUA_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    def resolve_paths(self) -> "DoclingPipelineSettings":
        """Return a copy with all relative paths resolved against project_root."""

        def _resolve(path: Path) -> Path:
            if path.is_absolute():
                return path
            return self.project_root / path

        return DoclingPipelineSettings(
            project_root=self.project_root,
            pdf_raw_dir=_resolve(self.pdf_raw_dir),
            parsed_dir=_resolve(self.parsed_dir),
            chunks_dir=_resolve(self.chunks_dir),
        )


def get_settings() -> DoclingPipelineSettings:
    """Return settings with resolved paths."""
    return DoclingPipelineSettings().resolve_paths()


__all__ = ["DoclingPipelineSettings", "get_settings"]


