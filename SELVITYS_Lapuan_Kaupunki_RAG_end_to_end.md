# Lapuan Kaupunki RAG – End-to-End Selostus

Tämä dokumentti selittää palvelun toiminnan kahdella tasolla: ensin tavalliselle lukijalle, sitten teknisesti tarkemmin.

**Live-palvelu:** https://www.lapuarag.org

---

## 1. Selitys tavalliselle lukijalle

Lapuan kaupunki tekee päätöksiä valtuustossa, hallituksessa ja eri lautakunnissa. Näistä syntyy pitkiä pöytäkirjoja, joita on hankala selata käsin, jos haluaa tietää esimerkiksi:

- mitä on päätetty Simpsiönvuori Oy:n lainoista ja takauksista
- miten Männikön koulun lakkauttaminen eteni
- miten kaupungin talous on kehittynyt vuoden aikana.

**Tämä palvelu on yksityishenkilön harrasteprojekti**, joka lukee pöytäkirjat automaattisesti ja rakentaa niistä "älykkään hakukoneen". Se **ei ole Lapuan kaupungin virallinen palvelu** eikä sitä ole tarkoitettu päätöksenteon, viranomaiskäytön tai oikeudellisen arvioinnin tueksi.

### Miten se toimii?

Kun kirjoitat kysymyksen (esim. *"Männikön koulu"*), järjestelmä:

1. **Etsii** kaikista pöytäkirjoista ne pykälät, joissa puhutaan aiheesta
2. **Painottaa** uudempia päätöksiä (2025 > 2024 > 2023)
3. **Kokoaa** löydetyt pykälät yhteen
4. **Pyytää** tekoälymallia (Groq LLM) selittämään päätökset selkeästi

### Mitä saat vastaukseksi?

- **Lyhyt yhteenveto** – 2-3 virkettä tärkeimmästä
- **Keskeiset päätökset** – luettelo päätöksistä (toimielin, päivämäärä, §)
- **Lähdepykälät** – lista alkuperäisistä asiakirjoista, joista vastaus on koottu

Järjestelmä ei keksi omia päätöksiä – se nojaa vain pöytäkirjoissa olevaan tekstiin ja näyttää lähteet.

---

## 2. Tekninen arkkitehtuuri

### Infrastruktuuri

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TUOTANTOYMPÄRISTÖ                           │
├─────────────────┬───────────────────────┬───────────────────────────┤
│     VERCEL      │      HETZNER VPS      │       GROQ CLOUD          │
│   (Frontend)    │      (Backend)        │        (LLM)              │
├─────────────────┼───────────────────────┼───────────────────────────┤
│ www.lapuarag.org│ lapuarag.org          │ api.groq.com              │
│ Next.js 14      │ FastAPI + Uvicorn     │ openai/gpt-oss-120b       │
│                 │ Caddy (HTTPS)         │                           │
│                 │ Qdrant (Docker)       │                           │
│                 │ BGE-M3 embeddings     │                           │
└─────────────────┴───────────────────────┴───────────────────────────┘
```

### End-to-End Pipeline

#### Vaihe 1: Raakadata
- **Lähde:** PDF-pöytäkirjat kansiossa `DATA_päättävät_elimet_20251202/`
- **Toimielimet:** Kaupunginvaltuusto, Kaupunginhallitus, Sivistyslautakunta, Ympäristölautakunta, Tekninen lautakunta

#### Vaihe 2: Docling-ingestio
- **Moduuli:** `packages/docling_pipeline`
- **Toiminto:** `docling_pipeline.cli.parse-all`
- **Output:** 
  - `data/parsed/*_docling.json` (rakenneltu JSON)
  - `data/parsed/*_full.md` (Markdown-versio)

#### Vaihe 3: Chunkkaus
- **Moduuli:** `packages/rag_core/chunking`
- **Toiminto:** `run_all()`
- **Parametrit:**
  - `MAX_TOKENS_PER_CHUNK = 700`
  - `CHUNK_OVERLAP_TOKENS = 150`
- **Output:** 
  - `data/chunks/chunks.jsonl` (1098 chunkkia)
  - Jokainen chunk sisältää: `doc_id`, `toimielin`, `poytakirja_pvm`, `pykala_nro`, `chunk_text`

#### Vaihe 4: Embeddings + Qdrant-indeksi
- **Moduuli:** `packages/rag_core/embeddings` + `indexing`
- **Malli:** BGE-M3 (FlagEmbedding) – 1024-ulotteinen dense-vektori
- **Tietokanta:** Qdrant, kokoelma `lapua_chunks`
- **Pisteitä:** 1098

#### Vaihe 5: Haku (Retrieval)
- **Moduuli:** `packages/rag_core/retrieval`
- **Funktio:** `hybrid_search(question, k=10)`
- **Toiminta:**
  1. Lasketaan kysymykselle BGE-M3 embedding
  2. Qdrant palauttaa k+5 osuvinta chunkkia
  3. **Recency boost** lasketaan jokaiselle:
     - 2025 päätökset: +25% boost
     - 2024 päätökset: +12% boost
     - 2023 ja vanhemmat: ei boostia
  4. Uudelleenjärjestetään boostatun scoren mukaan
  5. Palautetaan top-k tulosta

#### Vaihe 6: Agenttikerros
- **Moduuli:** `packages/agents/query_agent`
- **Luokka:** `LapuaQueryAgent`
- **Vaiheet:**
  1. **plan()** – Päättää k-arvon kysymyksen perusteella:
     - Oletus: k=10
     - Historia/trendit: k=20
     - Simpsiö-aiheet: k=12
  2. **retrieve()** – Kutsuu `hybrid_search()` + recency boost
  3. **answer()** – Rakentaa LLM-promptin ja kutsuu Groqia

#### Vaihe 7: LLM-inferenssi
- **Moduuli:** `apps/backend/llm/groq_client`
- **Malli:** `openai/gpt-oss-120b` (Groq Cloud)
- **Parametrit:**
  - `max_tokens = 1500`
  - `temperature = 0.2`
  - `reasoning_effort = "medium"`
- **System prompt:** Ohjeistaa vastaamaan ilman taulukoita, luettelomuodossa

#### Vaihe 8: Backend API
- **Moduuli:** `apps/backend/main.py`
- **Framework:** FastAPI
- **Endpointit:**
  - `GET /health` – `{"status": "ok"}`
  - `POST /query` – RAG-kysely
  - `POST /admin/reindex` – Uudelleenindeksointi

#### Vaihe 9: Frontend
- **Moduuli:** `apps/frontend`
- **Framework:** Next.js 14 + TypeScript
- **UI:**
  - Vasen: Kysymyskenttä + Hae-painike
  - Oikea: Vastaus (Markdown-muotoiltu)
  - Ala: Lähdepykälät (toimielin, pvm, §, score)

---

## 3. Recency Boost -algoritmi

Uudemmat päätökset saavat korkeamman painoarvon haussa:

```python
def _recency_boost(pvm_str, max_boost=1.25, decay_years=2.0):
    """
    Laskee recency-kertoimen päivämäärän perusteella.
    
    - 0 vuotta vanha: 1.25x boost
    - 1 vuosi vanha: 1.125x boost  
    - 2+ vuotta vanha: 1.0x (ei boostia)
    """
    years_old = (today - doc_date).days / 365.0
    if years_old >= decay_years:
        return 1.0
    boost = max_boost - (max_boost - 1.0) * (years_old / decay_years)
    return boost
```

**Lopputulos:** 
- Score 0.50 + 2025 pvm → 0.50 × 1.25 = **0.625**
- Score 0.55 + 2023 pvm → 0.55 × 1.00 = **0.550**
- → 2025 päätös nousee ylemmäs vaikka semanttinen osuvuus oli pienempi

---

## 4. Token-käyttö (arvio)

| Komponentti | Tokeneita |
|-------------|-----------|
| System prompt | ~150 |
| User prompt (kysymys) | ~50 |
| Konteksti (10 × 700 tok) | ~7000 |
| **Input yhteensä** | ~7200 |
| **Output max** | 1500 |

**Kustannus per kysely** (Groq hinnoittelu):
- Input: ~7200 × $0.15/M = $0.001
- Output: ~500 × $0.75/M = $0.0004
- **Yhteensä:** ~$0.0014 / kysely

---

## 5. Yhteenveto

Palvelu yhdistää neljä tekoälykerrosta:

1. **Docling** – PDF → teksti (dokumentin ymmärrys)
2. **BGE-M3** – teksti → vektori (semanttinen ymmärrys)
3. **Qdrant** – vektorihaku (relevanttien pykälien löytäminen)
4. **Groq LLM** – vastauksen generointi (luonnollisen kielen tuottaminen)

**Recency boost** varmistaa, että uusimmat päätökset näkyvät ensimmäisinä, koska ne yleensä kumoavat tai tarkentavat vanhempia päätöksiä.
