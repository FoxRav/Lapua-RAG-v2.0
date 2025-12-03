https://lapua-rag-v2-0.vercel.app/

## Lapuan Kaupunki RAG

Kokeellinen harrasteprojekti, joka tarjoaa RAG-pohjaisen haun Lapuan kaupungin julkisista pöytäkirjoista. Palvelu ei ole Lapuan kaupungin virallinen palvelu eikä sitä ole tarkoitettu päätöksenteon tueksi tai oikeudelliseksi neuvoksi; tulokset tulee aina varmistaa alkuperäisistä pöytäkirjoista ja virallisista lähteistä.

Docling-pohjainen RAG-hakupalvelu, jossa Qdrant-vektorihaku ja Groq-LLM analysoivat Lapuan kaupungin pöytäkirjoja (valtuusto, hallitus, lautakunnat).

### Kokonaisuus lyhyesti

- **Docling-ingestio**: `DATA_päättävät_elimet_20251202/` PDF-pöytäkirjat → `data/parsed/` (Docling JSON + Markdown)
- **Chunkkaus**: pykälä- ja asiakohtaiset chunkit → `data/chunks/chunks.jsonl`
- **Embeddings + Qdrant**: BGE-M3 (FlagEmbedding) dense-vektorit → Qdrant-kokoelma `lapua_chunks`
- **Agentti + LLM**: `LapuaQueryAgent` suunnittelee haun, hakee Qdrantista ja kutsuu Groq Cloudin `openai/gpt-oss-120b` ‑mallia vastausten koostamiseen
- **Frontend**: Next.js UI (`apps/frontend`), jossa teksti­haku ja lähdepykälien listaus

### Pikaohje kehittäjälle

1. **Vaatimukset**
   - Python 3.10
   - Node.js + npm
   - Docker Desktop (Qdrantille)
   - Groq Cloud ‑API-avain (`GROQ_API_KEY`)

2. **Asennus (juurikansiossa)**

   ```bash
   pip install -e .[embeddings]
   ```

3. **Käynnistä Qdrant**

   ```bash
   docker run --rm -p 6333:6333 -p 6334:6334 --name lapua-qdrant qdrant/qdrant:latest
   ```

4. **Aja ingestio + indeksointi (vain kun data muuttuu)**

   ```bash
   python -m docling_pipeline.cli parse-all
   python -c "from rag_core.chunking import run_all; run_all()"
   python -c "from rag_core.indexing import index_all_chunks; index_all_chunks()"
   ```

5. **Konfiguroi Groq ja käynnistä backend**

   `.env` juureen:

   ```env
   GROQ_API_KEY=OMA_GROQ_APIKEY
   GROQ_MODEL_ID=openai/gpt-oss-120b
   ```

   ja sitten:

   ```bash
   uvicorn apps.backend.main:app --reload --port 8000
   ```

6. **Käynnistä frontend**

   ```bash
   cd apps/frontend
   npm install
   npm run dev
   ```

   UI löytyy osoitteesta `http://localhost:3000`, backend `http://127.0.0.1:8000`.

