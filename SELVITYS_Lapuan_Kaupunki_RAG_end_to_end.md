## Lapuan Kaupunki RAG – end‑to‑end-selostus

Tämä dokumentti selittää palvelun toiminnan kahdella tasolla: ensin tavalliselle lukijalle, sitten teknisesti tarkemmin.

---

### 1. Selitys tavalliselle lukijalle

Lapuan kaupunki tekee päätöksiä valtuustossa, hallituksessa ja eri lautakunnissa. Näistä syntyy pitkiä pöytäkirjoja, joita on hankala selata käsin, jos haluaa tietää esimerkiksi:

- mitä on päätetty Simpsiönvuori Oy:n lainoista ja takauksista
- miten uimahallihanke on edennyt
- miten kaupungin talous on kehittynyt vuoden aikana.

Tämä palvelu on yksityishenkilön harrasteprojekti, joka lukee pöytäkirjat automaattisesti ja rakentaa niistä "älykkään hakukoneen". Se ei ole Lapuan kaupungin virallinen palvelu eikä sitä ole tarkoitettu päätöksenteon, viranomaiskäytön tai oikeudellisen arvioinnin tueksi. Kun kirjoitat kysymyksen (esim. *"Simpsiönvuori Oy takaus"*), järjestelmä:

1. etsii kaikista pöytäkirjoista ne pykälät, joissa puhutaan Simpsiönvuoresta ja lainoista
2. kokoaa ne yhteen
3. ja pyytää erikoistunutta kielimallia (Groq‑LLM) selittämään päätökset selkeällä suomen kielellä.

Lopputuloksena saat:

- lyhyen yhteenvedon siitä, mitä päätöksiä on tehty
- listan pykälistä (toimielin, päivämäärä, §‑numero), joiden pohjalta vastaus on muodostettu.

Tärkeää on, että järjestelmä ei keksi omia päätöksiä: se nojaa vain pöytäkirjoissa olevaan tekstiin ja näyttää lähteet, jotta voit tarkistaa tulkinnat itse.

---

### 2. Tekninen arkkitehtuuri lyhyesti

End‑to‑end‑ketju on seuraava:

1. **Raakadata**
   - Pöytäkirja‑PDF:t kansiossa `DATA_päättävät_elimet_20251202/`.

2. **Docling‑ingestio (`packages/docling_pipeline`)**
   - `docling_pipeline.cli.parse-all` käy läpi kaikki PDF:t ja tuottaa:
     - Docling JSON‑rakenteen (`*_docling.json`)
     - täyden markdown‑version (`*_full.md`)
   - Output tallennetaan `data/parsed/`‑hakemistoon.

3. **Chunkkaus ja normalisointi (`packages/rag_core/chunking`)**
   - `run_all()` lukee `*_full.md`‑tiedostot ja pilkkoo ne asiakohtaisiksi chunkeiksi.
   - Jokaisesta chunkista muodostetaan `ChunkRecord` (Pydantic‑malli), jossa on mm.:
     - `doc_id`, `toimielin`, `poytakirja_pvm`, `pykala_nro`
     - `chunk_text` (pätkä pöytäkirjasta)
   - Kaikki chunkit kirjoitetaan:
     - `data/chunks/chunks.jsonl`
     - `data/chunks/chunks.json`

4. **Embeddings ja Qdrant‑indeksi (`packages/rag_core/embeddings` + `indexing`)**
   - BGE‑M3 (FlagEmbedding) ‑malli ajetaan GPU:lla (RTX 4050, 6 GB) → dense‑vektorit jokaiselle chunkille.
   - `rag_core.indexing.index_all_chunks()`:
     - laskee embeddingit teksteille
     - luo Qdrant‑kokoelman `lapua_chunks` (1024‑ulotteinen vektori)
     - upsertoi kaikki chunkit pisteinä, payloadissa koko `ChunkRecord`.

5. **Haku (`packages/rag_core/retrieval`)**
   - `hybrid_search(question, k)`:
     - laskee kysymykselle BGE‑M3‑vektorin
     - tekee vektorihakua Qdrantista (dense‑haku)
     - palauttaa `SearchResult`‑joukon, joissa on sekä pisteen payload (chunk) että relevanssipisteet.

6. **Agenttikerros (`packages/agents/query_agent`)**
   - `LapuaQueryAgent` toimii kolmessa vaiheessa:
     1. **plan** – päättää haun parametrin `k` (kuinka monta chunkia haetaan) kysymyksen perusteella.
     2. **retrieve** – kutsuu `hybrid_search()`‑funktiota ja saa listan osuvimmista chunkeista.
     3. **answer** – valmistaa Groq‑LLM:lle promptin:
        - system‑ohje: miten vastauksen pitää olla jäsennelty (yhteenveto, keskeiset päätökset, rajaukset)
        - user‑viesti: käyttäjän kysymys + kontekstina valitut chunkit (toimielin, pvm, §, teksti).
   - Groq‑kutsu tehdään `apps/backend/llm/groq_client.py`‑tiedoston kautta käyttäen mallia `openai/gpt-oss-120b`.
   - Paluussa rakennetaan `LapuaAnswer`, jossa on:
     - `answer` (LLM:n vastaus)
     - `sources` (listattuina `SourceRef`‑olioina)
     - `model` ja `strategy_used` metatietona.

7. **Backend (`apps/backend/main.py`)**
   - FastAPI‑sovellus tarjoaa kolme keskeistä endpointtia:
     - `GET /health` – terveystarkistus.
     - `POST /query` – lukee `QueryRequest`in, ajaa agentin (`plan → retrieve → answer`) ja palauttaa `LapuaAnswer`in.
     - `POST /admin/reindex` – ajaa koko ingestio‑ ja indeksointiputken (Docling → chunking → Qdrant).

8. **Frontend (`apps/frontend`)**
   - Next.js 14 + TypeScript ‑pohjainen UI.
   - Päänäkymä:
     - vasen paneeli: kysymysteksti + Hae‑painike
     - oikea paneeli: vastaus (kolmiosainen jäsennelty teksti)
     - alhaalla: lähdepykälien listaus (toimielin, pvm, §, score).
   - Frontend puhuu backendille `POST /query` ‑endpointin kautta.

---

### 3. Yhteenveto

Palvelu yhdistää kolme tasoa:

1. **Rakennettu tieto** – pöytäkirjoista on tehty koneelle luettava, pykälä‑ ja asiakohtainen tietokanta.
2. **Vektorihaku** – kysymykset muutetaan numeeriseen muotoon, jolloin järjestelmä löytää semanttisesti samankaltaiset päätökset, ei vain sanallisia osumia.
3. **Kielimalli** – Groq‑LLM kokoaa löydetyt pykälät yhdeksi selkeäksi vastaukseksi, mutta näyttää aina myös lähteet, joihin vastaus perustuu.

Näin Lopputuloksena käyttäjä saa nopeasti käsityksen siitä, mitä Lapuan kaupungin pöytäkirjoissa on päätetty jostakin aiheesta, ilman että hänen tarvitsee itse etsiä ja lukea kaikkia asiakirjoja läpi.


