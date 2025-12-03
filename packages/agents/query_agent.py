from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
)

from rag_core.models import ChunkRecord
from rag_core.retrieval import SearchResult, hybrid_search
from apps.backend.llm.groq_client import ask_groq

_log = logging.getLogger(__name__)


class LapuaQueryFilters(BaseModel):
    """High-level filters the UI/backend can pass to the agent."""

    teemat: List[int] = Field(default_factory=list)
    toimielimet: List[str] = Field(default_factory=list)
    simpsio_only: bool = False
    talous_only: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    def to_qdrant_filter(self) -> Optional[Filter]:
        """Convert high-level filters into a Qdrant Filter."""
        must: list[FieldCondition] = []

        if self.teemat:
            must.append(
                FieldCondition(
                    key="teemat",
                    match=MatchAny(any=self.teemat),
                )
            )

        if self.toimielimet:
            must.append(
                FieldCondition(
                    key="toimielin",
                    match=MatchAny(any=self.toimielimet),
                )
            )

        if self.simpsio_only:
            must.append(
                FieldCondition(
                    key="simpsio_flag",
                    match=MatchValue(value=True),
                )
            )

        if self.talous_only:
            must.append(
                FieldCondition(
                    key="talous_flag",
                    match=MatchValue(value=True),
                )
            )

        # Date range can be added later when we normalise poytakirja_pvm into payload
        if not must:
            return None
        return Filter(must=must)


class QueryStrategy(str):
    """Simple enumeration for agent strategies."""

    DENSE = "dense"


class LapuaQueryPlan(BaseModel):
    """Agent's internal plan for answering a question."""

    original_question: str
    strategy: str = Field(default=QueryStrategy.DENSE)
    k: int = Field(default=10)
    filters: LapuaQueryFilters = Field(default_factory=LapuaQueryFilters)


class SourceRef(BaseModel):
    """Reference to a single source chunk."""

    doc_id: str
    toimielin: str
    poytakirja_pvm: Optional[str]
    pykala_nro: Optional[str]
    otsikko: Optional[str]
    score: float


class LapuaAnswer(BaseModel):
    """Structured answer from the agent."""

    answer: str
    sources: List[SourceRef]
    strategy_used: str
    model: str | None = None


@dataclass
class LapuaQueryAgent:
    """Lightweight query agent orchestrating retrieval and answer formatting."""

    max_k: int = 20

    def plan(self, question: str, filters: Optional[LapuaQueryFilters] = None) -> LapuaQueryPlan:
        """Decide retrieval strategy and parameters based on the question."""
        if filters is None:
            filters = LapuaQueryFilters()

        lowered = question.lower()
        k = 10
        if any(word in lowered for word in ("historia", "kehitys", "trendit", "aikajana")):
            k = min(self.max_k, 20)
        elif any(word in lowered for word in ("simpsiö", "simpsiönvuori", "takaus", "takauksen")):
            k = 12

        plan = LapuaQueryPlan(
            original_question=question,
            strategy=QueryStrategy.DENSE,
            k=k,
            filters=filters,
        )
        _log.info("Created query plan: %s", plan.model_dump())
        return plan

    def retrieve(self, plan: LapuaQueryPlan) -> List[SearchResult]:
        """Execute retrieval according to the plan."""
        qdrant_filter = plan.filters.to_qdrant_filter()
        results = hybrid_search(plan.original_question, k=plan.k, filters=qdrant_filter)
        _log.info("Retrieved %d chunks for question", len(results))
        return results

    def answer(self, plan: LapuaQueryPlan, results: List[SearchResult]) -> LapuaAnswer:
        """Build a textual answer based on retrieved chunks using Groq LLM."""
        if not results:
            return LapuaAnswer(
                answer="En löytänyt yhtään relevanttia pykälää tämän kysymyksen perusteella nykyisestä indeksistä.",
                sources=[],
                strategy_used=plan.strategy,
                model=None,
            )

        top_chunks: list[ChunkRecord] = []
        sources: list[SourceRef] = []

        for res in results[: plan.k]:
            payload_dict = dict(res.payload or {})
            try:
                chunk = ChunkRecord.model_validate(payload_dict)
            except Exception:
                continue

            top_chunks.append(chunk)
            sources.append(
                SourceRef(
                    doc_id=chunk.doc_id,
                    toimielin=chunk.toimielin,
                    poytakirja_pvm=str(chunk.poytakirja_pvm),
                    pykala_nro=chunk.pykala_nro,
                    otsikko=chunk.otsikko,
                    score=res.score,
                )
            )

        # Prepare chunk dicts for LLM client
        chunk_dicts: list[dict] = []
        for src, chunk in zip(sources, top_chunks):
            chunk_dicts.append(
                {
                    "doc_id": src.doc_id,
                    "toimielin": src.toimielin,
                    "poytakirja_pvm": src.poytakirja_pvm,
                    "pykala_nro": src.pykala_nro,
                    "sivu": chunk.sivu,
                    "chunk_text": chunk.chunk_text,
                }
            )

        system_prompt = (
            "Olet Lapuan kaupungin pöytäkirjoihin erikoistunut juridinen ja taloudellinen analyysiapu. "
            "Vastaat selkeään ja helposti luettavaan muotoon JAETTUNA seuraaviin osiin:"
            "\n\n"
            "1) 'Lyhyt yhteenveto' – 2–4 virkettä tärkeimmästä kokonaiskuvasta.\n"
            "2) 'Keskeiset päätökset' – luettelona, jossa jokainen kohta muodossa:\n"
            "   - Toimielin, päivämäärä, pykälänumero – 1–3 virkkeen kuvaus päätöksen sisällöstä.\n"
            "3) 'Huomiot ja rajaukset' – jos konteksti ei riitä kaikkiin kysymyksen osiin, kerro tässä "
            "mitä ei voi päätellä.\n\n"
            "ÄLÄ käytä taulukkoja, monimutkaista markdown-rakennetta tai liian pitkiä kappaleita – "
            "käytä otsikoita ja lyhyitä luettelokohtia. Viittaa aina päätöksen tehneeseen toimielimeen, "
            "päivämäärään ja pykälänumeroon kun ne ovat tiedossa. Älä keksi asioita, jos konteksti ei riitä, "
            "mutta VASTAA AINA edes lyhyesti – älä jätä vastausta tyhjäksi."
        )
        answer_text = ask_groq(system_prompt, plan.original_question, chunk_dicts)

        # Jos LLM palauttaa tyhjän vastauksen, kokeillaan kerran uudelleen kevyemmällä promptilla.
        if not answer_text or not answer_text.strip():
            _log.warning(
                "Groq LLM returned empty answer on first attempt, retrying with simplified prompt"
            )
            simple_prompt = (
                "Tiivistät alla olevat Lapuan kaupungin pöytäkirjapykälät suomeksi. "
                "Kerro lyhyesti mitä niissä päätetään kysytyn aiheen kannalta. "
                "Jos et ole varma kaikista yksityiskohdista, kerro se erikseen, "
                "mutta älä koskaan jätä vastausta tyhjäksi."
            )
            answer_text = ask_groq(simple_prompt, plan.original_question, chunk_dicts)

        # Fallback: jos LLM palauttaa edelleen tyhjän vastauksen, näytetään ainakin lähdepykälät selitteellä.
        if not answer_text or not answer_text.strip():
            _log.warning("Groq LLM returned empty answer, falling back to source-only summary")
            lines: list[str] = []
            lines.append(
                "Lyhyt yhteenveto\n"
                "- LLM ei palauttanut varsinaista vastaustekstiä tälle kysymykselle.\n"
                "- Alla on listattu ne pöytäkirjapykälät, joita haku piti relevantteina."
            )
            lines.append("\nKeskeiset päätökset (lähdepykälät)\n")
            for src in sources:
                lines.append(
                    f"- {src.toimielin}, {src.poytakirja_pvm or '?'} § {src.pykala_nro or '?'} "
                    f"(doc_id={src.doc_id})"
                )
            lines.append(
                "\nHuomiot ja rajaukset\n"
                "- Varsinaista tiivistettyä vastausta ei voitu muodostaa, "
                "mutta yllä olevien pykälien teksteistä löytyy haun kannalta relevantti sisältö."
            )
            answer_text = "\n".join(lines)

        return LapuaAnswer(
            answer=answer_text,
            sources=sources,
            strategy_used=plan.strategy,
            model="openai/gpt-oss-120b",
        )


__all__ = [
    "LapuaQueryAgent",
    "LapuaQueryFilters",
    "LapuaQueryPlan",
    "LapuaAnswer",
    "SourceRef",
]


