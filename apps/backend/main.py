from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.query_agent import LapuaAnswer, LapuaQueryAgent, LapuaQueryFilters

_log = logging.getLogger(__name__)

app = FastAPI(title="Lapua Kaupunki RAG API")

# CORS: allow public frontend and local dev without credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryFiltersModel(BaseModel):
    teemat: list[int] = Field(default_factory=list)
    toimielimet: list[str] = Field(default_factory=list)
    simpsio_only: bool = False
    talous_only: bool = False
    start_date: date | None = None
    end_date: date | None = None


class QueryRequest(BaseModel):
    question: str
    filters: QueryFiltersModel = Field(default_factory=QueryFiltersModel)
    mode: str = Field(default="auto")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=LapuaAnswer)
async def query(req: QueryRequest) -> LapuaAnswer:
    agent = LapuaQueryAgent()
    filters = LapuaQueryFilters(**req.filters.model_dump())
    plan = agent.plan(req.question, filters=filters)
    results = agent.retrieve(plan)
    try:
        answer = agent.answer(plan, results)
    except Exception as exc:  # noqa: BLE001
        _log.exception("LLM answer failed")
        raise HTTPException(status_code=500, detail=f"LLM answer failed: {exc}") from exc
    return answer


@app.post("/admin/reindex")
async def admin_reindex() -> dict[str, Annotated[int, Field(ge=0)]]:
    """
    Run full pipeline: Docling parse -> chunking -> Qdrant indexing.

    This endpoint is intended for manual/admin use because it can take a long time.
    Heavy Docling/Qdrant imports are done lazily here to keep API startup light,
    especially in constrained hosting environments.
    """
    try:
        from docling_pipeline.cli import parse_all as docling_parse_all
        from rag_core.chunking import run_all as chunking_run_all
        from rag_core.indexing import index_all_chunks

        _log.info("Starting admin reindex: Docling parse_all")
        docling_parse_all()
        _log.info("Docling parse_all completed, running chunking")
        chunking_run_all()
        _log.info("Chunking completed, running Qdrant indexing")
        index_all_chunks()
    except Exception as exc:  # noqa: BLE001
        _log.exception("Admin reindex failed")
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}") from exc

    return {"status": 1}


__all__ = ["app"]


