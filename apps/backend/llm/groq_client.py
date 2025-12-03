from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from groq import Groq

# Load .env once when module is imported so that GROQ_API_KEY/GROQ_MODEL_ID
# can be defined in a persisted config file rather than every shell session.
load_dotenv()

GROQ_MODEL_ID: str = os.getenv("GROQ_MODEL_ID", "openai/gpt-oss-120b")

# Groq client reads GROQ_API_KEY from environment/.env by default
_client = Groq()


def build_context_block(chunks: List[dict]) -> str:
    """Format chunks into a single context block for the LLM."""
    parts: list[str] = []
    for i, ch in enumerate(chunks, 1):
        header = (
            f"[LÄHDE {i}: {ch.get('doc_id')} "
            f"{ch.get('toimielin', '')} "
            f"{ch.get('poytakirja_pvm', '')} "
            f"{ch.get('pykala_nro', '')}]"
        )
        text = ch.get("chunk_text") or ""
        parts.append(header + "\n" + text)
    return "\n\n".join(parts)


def ask_groq(system_prompt: str, question: str, chunks: List[dict], max_tokens: int = 700) -> str:
    """Call Groq chat completion API with given question and context chunks."""
    context = build_context_block(chunks)
    user_content = (
        f"Kysymys:\n{question}\n\n"
        f"Hyödynnä alla olevaa kontekstia vastatessasi.\n"
        f"Vastaa suomeksi, viittaa pykäliin ja päivämääriin.\n\n"
        f"{context}"
    )
    resp = _client.chat.completions.create(
        model=GROQ_MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_completion_tokens=max_tokens,
        top_p=1,
        reasoning_effort="medium",
        stream=False,
    )
    content = resp.choices[0].message.content
    return content or ""


__all__ = ["ask_groq", "build_context_block", "GROQ_MODEL_ID"]


