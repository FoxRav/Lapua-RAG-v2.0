from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
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


def _recency_boost(pvm_str: str | None, max_boost: float = 1.3, decay_years: float = 2.0) -> float:
    """
    Calculate a recency boost factor based on document date.
    
    Newer documents get higher boost (up to max_boost).
    Documents older than decay_years get boost of 1.0 (no change).
    
    Args:
        pvm_str: Date string in format "YYYY-MM-DD"
        max_boost: Maximum boost for very recent documents (e.g., 1.3 = 30% boost)
        decay_years: How many years back until boost becomes 1.0
    
    Returns:
        Boost factor between 1.0 and max_boost
    """
    if not pvm_str:
        return 1.0
    try:
        doc_date = datetime.strptime(pvm_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1.0
    
    today = date.today()
    days_old = (today - doc_date).days
    years_old = days_old / 365.0
    
    if years_old >= decay_years:
        return 1.0
    
    # Linear interpolation: 0 years old = max_boost, decay_years old = 1.0
    boost = max_boost - (max_boost - 1.0) * (years_old / decay_years)
    return max(1.0, boost)


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
        word_count = len(question.split())
        
        # Simple questions (mikä on X, kuka on Y) need fewer sources
        simple_patterns = ("mikä on", "kuka on", "mitä on", "missä on", "milloin")
        is_simple = any(lowered.startswith(p) for p in simple_patterns) and word_count <= 6
        
        if is_simple:
            k = 5  # Simple factual questions need few sources
        elif any(word in lowered for word in ("historia", "kehitys", "trendit", "aikajana", "kaikki")):
            k = min(self.max_k, 20)  # Broad questions need more sources
        elif any(word in lowered for word in ("simpsiö", "simpsiönvuori", "takaus", "takauksen")):
            k = 12  # Specific complex topics
        else:
            k = 8  # Default for normal questions

        plan = LapuaQueryPlan(
            original_question=question,
            strategy=QueryStrategy.DENSE,
            k=k,
            filters=filters,
        )
        _log.info("Created query plan: k=%d for question: %s", k, question[:50])
        return plan

    def retrieve(self, plan: LapuaQueryPlan) -> List[SearchResult]:
        """Execute retrieval according to the plan, with recency boost."""
        qdrant_filter = plan.filters.to_qdrant_filter()
        # Fetch more results to allow re-ranking
        results = hybrid_search(plan.original_question, k=plan.k + 5, filters=qdrant_filter)
        
        # Apply recency boost and re-sort
        boosted_results: list[tuple[float, SearchResult]] = []
        for res in results:
            pvm = res.payload.get("poytakirja_pvm") if res.payload else None
            pvm_str = str(pvm) if pvm else None
            boost = _recency_boost(pvm_str, max_boost=1.25, decay_years=2.0)
            boosted_score = res.score * boost
            boosted_results.append((boosted_score, res))
        
        # Sort by boosted score (descending) and take top k
        boosted_results.sort(key=lambda x: x[0], reverse=True)
        final_results = [res for _, res in boosted_results[:plan.k]]
        
        _log.info("Retrieved %d chunks (with recency boost) for question", len(final_results))
        return final_results

    def answer(self, plan: LapuaQueryPlan, results: List[SearchResult]) -> LapuaAnswer:
        """Build a textual answer based on retrieved chunks using Groq LLM."""
        if not results:
            return LapuaAnswer(
                answer="En löytänyt yhtään relevanttia pykälää tämän kysymyksen perusteella nykyisestä indeksistä.",
                sources=[],
                strategy_used=plan.strategy,
                model=None,
            )

        # Group chunks by doc_id to avoid duplicates (same document only once)
        # For meeting minutes: doc_id|pykala_nro
        # For website content: doc_id alone (URL-based)
        doc_map: dict[str, dict] = {}
        
        for res in results[: plan.k]:
            payload_dict = dict(res.payload or {})
            try:
                chunk = ChunkRecord.model_validate(payload_dict)
            except Exception:
                continue

            # Create unique key - for website content use doc_id alone
            is_website = chunk.toimielin.startswith("verkkosivu")
            if is_website:
                # Website: deduplicate by URL (doc_id)
                dedup_key = chunk.doc_id
            else:
                # Meeting minutes: deduplicate by doc_id + pykälä
                dedup_key = f"{chunk.doc_id}|{chunk.pykala_nro or 'unknown'}"
            
            if dedup_key not in doc_map:
                # First chunk from this source
                doc_map[dedup_key] = {
                    "chunk": chunk,
                    "score": res.score,
                    "texts": [chunk.chunk_text],
                }
            else:
                # Additional chunk from same source - merge text
                existing = doc_map[dedup_key]
                if chunk.chunk_text not in existing["texts"]:
                    existing["texts"].append(chunk.chunk_text)
                # Keep highest score
                existing["score"] = max(existing["score"], res.score)

        # Build deduplicated sources and merged chunk dicts
        sources: list[SourceRef] = []
        chunk_dicts: list[dict] = []
        
        for dedup_key, data in doc_map.items():
            chunk = data["chunk"]
            merged_text = "\n\n".join(data["texts"])
            
            sources.append(
                SourceRef(
                    doc_id=chunk.doc_id,
                    toimielin=chunk.toimielin,
                    poytakirja_pvm=str(chunk.poytakirja_pvm),
                    pykala_nro=chunk.pykala_nro,
                    otsikko=chunk.otsikko,
                    score=data["score"],
                )
            )
            chunk_dicts.append(
                {
                    "doc_id": chunk.doc_id,
                    "toimielin": chunk.toimielin,
                    "poytakirja_pvm": str(chunk.poytakirja_pvm),
                    "pykala_nro": chunk.pykala_nro,
                    "sivu": chunk.sivu,
                    "chunk_text": merged_text,
                }
            )
        
        _log.info("Merged %d chunks into %d unique pykälät", len(results[:plan.k]), len(sources))

        # Check if the question is too broad (generic words without specifics)
        broad_keywords = ["mitä päätöksiä", "mitä on tehty", "mitä on päätetty", "kaikki", "yleisesti"]
        question_lower = plan.original_question.lower()
        is_broad_question = any(kw in question_lower for kw in broad_keywords) and len(sources) > 8
        
        if is_broad_question:
            # Add guidance for broad questions
            broad_guidance = (
                "\n\nHUOM: Kysymys on laaja. Jos lähteet käsittelevät monia eri aiheita, "
                "kehota käyttäjää tarkentamaan kysymystä, esim: "
                "'Kysymys on laaja ja lähteet käsittelevät useita eri päätöksiä. "
                "Tarkenna kysymystäsi esim. tiettyyn vuoteen, toimielimeen tai aihealueeseen.'\n"
            )
        else:
            broad_guidance = ""

        system_prompt = (
            "Olet Lapuan kaupungin pöytäkirja-avustaja. Tiivistä alla olevat lähteet vastaukseksi.\n\n"
            "OHJEET:\n"
            "- Kerro mitä lähteissä sanotaan aiheesta\n"
            "- Mainitse toimielin, päivämäärä ja pykälä\n"
            "- Käytä vain lähteiden tietoa\n\n"
            "MUOTO: Lyhyt yhteenveto, sitten luettelo päätöksistä."
            f"{broad_guidance}"
        )
        answer_text = ask_groq(system_prompt, plan.original_question, chunk_dicts)

        # Jos LLM palauttaa tyhjän vastauksen, kokeillaan kerran uudelleen kevyemmällä promptilla.
        if not answer_text or not answer_text.strip():
            _log.warning(
                "Groq LLM returned empty answer on first attempt, retrying with simplified prompt"
            )
            simple_prompt = (
                "Tiivistä alla olevat Lapuan kaupungin pöytäkirjapykälät suomeksi."
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


