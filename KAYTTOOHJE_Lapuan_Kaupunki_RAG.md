## Käyttöohje – Lapuan Kaupunki RAG

Tämä dokumentti kertoo, miten palvelua käytetään sekä kehittäjänä että loppukäyttäjänä. Palvelu on yksityishenkilön kehittämä kokeellinen hakutyökalu Lapuan kaupungin julkisiin pöytäkirjoihin; se ei ole kaupungin virallinen palvelu, eikä sitä ole tarkoitettu päätöksenteon, viranomaistyön tai oikeudellisen arvioinnin tueksi. Kaikki johtopäätökset tulee aina tarkistaa alkuperäisistä pöytäkirjoista ja virallisista kanavista.

### 1. Mitä palvelu tekee?

- Lukee Lapuan kaupungin pöytäkirjoja (valtuusto, hallitus, lautakunnat) Doclingin avulla.
- Pilkkoo tekstin pykälä- ja asiakohtaisiksi chunkeiksi ja indeksoi ne Qdrantiin (vektorihaku).
- Kysymysten yhteydessä:
  - hakee semanttisesti parhaiten vastaavat pykälät
  - antaa ne Groq‑LLM:lle (openai/gpt-oss-120b)
  - palauttaa jäsennellyn yhteenvedon sekä listan lähdepykälistä.

### 2. Loppukäyttäjän näkökulma (frontend)

1. Avaa selain: `http://localhost:3000`
2. Kirjoita kysymys:
   - Esimerkki: *"Simpsiönvuori Oy takaus"*
   - Toinen esimerkki: *"Miten vuoden 2025 talousarvion toteutuma kehittyi syyskuuhun mennessä?"*
3. Paina **Hae**.
4. Näet oikealla:
   - **Lyhyt yhteenveto** (LLM tiivistää tärkeimmät asiat).
   - **Keskeiset päätökset** luettelona (toimielin, päivämäärä, pykälä, kuvaus).
   - **Huomiot ja rajaukset**, jos konteksti ei riitä vastaamaan kaikkeen.
5. Alareunassa näet listan **lähdepykälistä**, joiden perusteella vastaus muodostettiin.

Palvelu ei vielä linkitä suoraan PDF:iin, mutta `doc_id` ja pykälän tiedot riittävät löytämään oikean pöytäkirjan `DATA_päättävät_elimet_20251202/`-kansiosta.

### 3. Kehittäjän workflow

1. **Käynnistä taustapalvelut**
   - Docker/Qdrant (yksi kontti): `lapua-qdrant` portissa 6333.
   - FastAPI-backend: `uvicorn apps.backend.main:app --reload --port 8000`
   - Frontend: `npm run dev` `apps/frontend`‑kansiossa.

2. **Päivitä data**
   - Kopioi uudet pöytäkirja‑PDF:t `DATA_päättävät_elimet_YYYYMMDD/`‑rakenteeseen.
   - Aja:

     ```bash
     python -m docling_pipeline.cli parse-all
     python -c "from rag_core.chunking import run_all; run_all()"
     python -c "from rag_core.indexing import index_all_chunks; index_all_chunks()"
     ```

3. **Testaa haku suoraan Pythonista**

   ```bash
   python -c "from agents.query_agent import LapuaQueryAgent; \
   agent = LapuaQueryAgent(); \
   plan = agent.plan('Simpsiönvuori Oy takaus'); \
   res = agent.retrieve(plan); \
   ans = agent.answer(plan, res); \
   print(ans.answer)"
   ```

### 4. Ympäristömuuttujat ja konfiguraatio

- `.env` (juuressa):

  ```env
  GROQ_API_KEY=OMA_GROQ_APIKEY
  GROQ_MODEL_ID=openai/gpt-oss-120b
  ```

- Qdrant:
  - Oletus: `http://localhost:6333`
  - Kokoelma: `lapua_chunks`

### 5. Tunnetut rajoitukset

- Data kattaa tällä hetkellä vain `DATA_päättävät_elimet_20251202/`‑kansion pöytäkirjat.
- Päätöstekstit voivat olla pitkiä; LLM tekee parhaansa, mutta kaikkea ei aina voi tiivistää täydellisesti.
- Aikafiltteröinti (päivämäärärajaukset) ei ole vielä näkyvissä frontendissä – se voidaan lisätä myöhemmin.


