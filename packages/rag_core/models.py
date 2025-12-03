from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class ChunkRecord(BaseModel):
    """Normalized chunk schema for Lapua RAG."""

    doc_id: str = Field(..., description="Stable identifier for the source document.")
    toimielin: str = Field(..., description="Name of the decision-making body.")
    poytakirja_pvm: date = Field(..., description="Meeting date.")

    pykala_nro: Optional[str] = Field(
        default=None,
        description="Section number (e.g. '§ 12').",
    )
    otsikko: Optional[str] = Field(
        default=None,
        description="Optional title or leading heading for the chunk.",
    )
    sivu: Optional[int] = Field(
        default=None,
        description="Page number if known.",
    )

    teemat: List[int] = Field(
        default_factory=list,
        description="List of thematic ids (1–20).",
    )
    asiasanat: List[str] = Field(
        default_factory=list,
        description="Keyword hints for filtering and display.",
    )

    simpsio_flag: bool = Field(
        default=False,
        description="True if chunk likely relates to Simpsiönvuori / Simpsiö.",
    )
    talous_flag: bool = Field(
        default=False,
        description="True if chunk is strongly financial/budget oriented.",
    )

    chunk_index: int = Field(
        ...,
        description="Index of the chunk within the document.",
    )
    chunk_text: str = Field(
        ...,
        description="Plain text used for embeddings and generation.",
    )


__all__ = ["ChunkRecord"]


