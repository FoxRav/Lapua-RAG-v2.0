# Lapuan Kaupunki RAG

🌐 **Live:** https://www.lapuarag.org

Kokeellinen harrasteprojekti, joka tarjoaa RAG-pohjaisen haun Lapuan kaupungin julkisista pöytäkirjoista. Palvelu ei ole Lapuan kaupungin virallinen palvelu eikä sitä ole tarkoitettu päätöksenteon tueksi tai oikeudelliseksi neuvoksi; tulokset tulee aina varmistaa alkuperäisistä pöytäkirjoista ja virallisista lähteistä.

---

## Arkkitehtuuri

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Vercel         │────▶│  Hetzner VPS     │────▶│  Qdrant         │
│  (Frontend)     │     │  (FastAPI)       │     │  (Vektori-DB)   │
│  www.lapuarag.org     │  lapuarag.org    │     │  localhost:6333 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Groq Cloud      │
                        │  (LLM Inference) │
                        │  llama-3.3-70b   │
                        └──────────────────┘
```

## Komponentit

| Komponentti | Teknologia | Sijainti |
|-------------|------------|----------|
| **Frontend** | Next.js 14, TypeScript | Vercel (www.lapuarag.org) |
| **Backend API** | FastAPI, Python 3.12 | Hetzner VPS (lapuarag.org) |
| **Vektoritietokanta** | Qdrant 1.13+ | Hetzner VPS (Docker) |
| **Embeddings** | BGE-M3 (FlagEmbedding) | Hetzner VPS |
| **LLM** | llama-3.3-70b-versatile | Groq Cloud |
| **Reverse Proxy** | Caddy (HTTPS) | Hetzner VPS |

---

## RAG Pipeline

1. **Docling-ingestio**: PDF-pöytäkirjat → Markdown + JSON
2. **Web scraping**: lapua.fi, simpsio.com, thermopolis.fi
3. **Chunkkaus**: Pykäläkohtaiset chunkit (~700 tokenia/chunk)
4. **Embeddings**: BGE-M3 dense-vektorit (1024-dim)
5. **Qdrant**: Vektori-indeksi `lapua_chunks` (1630 pistettä)
6. **Haku**: Dense-haku + recency boost (uudemmat +25%)
7. **LLM**: Groq llama-3.3-70b tiivistää vastauksen
8. **Jälkikäsittely**: Poistaa taulukot ja markdown-muotoilun

## Parametrit

| Parametri | Arvo | Kuvaus |
|-----------|------|--------|
| `temperature` | **0.1** | Matala = johdonmukainen muotoilu |
| `top_p` | **0.9** | Tasapaino tarkkuuden ja joustavuuden välillä |
| `k` | 5-12 | Haettavien chunkkien määrä (adaptiivinen) |
| `max_tokens` | 1500 | LLM-vastauksen max pituus |
| `recency_boost` | 1.25x | Tuoreiden (< 2v) päätösten painotus |

---

## Evaluointiprosessi

### 1. Kysymysten ajo (250 kpl)
```bash
python scripts/run_evaluation.py --output evaluation_results/run_YYYYMMDD.json
```

### 2. Auto-evaluointi (GPT arvioi vastaukset)
```bash
python scripts/auto_evaluate.py evaluation_results/run_YYYYMMDD.json --api-key "GROQ_API_KEY" --delay 2
```

### 3. Tulosten yhteenveto
```bash
python scripts/summary_results.py evaluation_results/run_YYYYMMDD_enriched.json
```

### 4. Vertailu PÖYTÄKIRJOIHIN (tärkein!)
Vastauksia TÄYTYY verrata alkuperäisiin pöytäkirjoihin:
- Ovatko pykälänumerot oikein?
- Ovatko päivämäärät oikein?
- Onko sisältö lähteissä?

### Tavoitemetriikat
| Metriikka | Tavoite | Kuvaus |
|-----------|---------|--------|
| Faithfulness | **>90%** | Vastaus perustuu lähteisiin |
| Hallucination | **<10%** | Ei keksittyä tietoa |
| Relevance | >80% | Vastaa kysymykseen |
| Completeness | >70% | Kattaa kysytyn asian |

---

## Kehitysympäristö

### Vaatimukset
- Python 3.10+
- Node.js 18+
- Docker Desktop
- Groq Cloud API-avain

### Asennus

```bash
# 1. Kloonaa repo
git clone https://github.com/FoxRav/Lapua-RAG-v2.0.git
cd Lapua-RAG-v2.0

# 2. Python-riippuvuudet
pip install -e .[embeddings]

# 3. Käynnistä Qdrant
docker run -d -p 6333:6333 -p 6334:6334 --name lapua-qdrant qdrant/qdrant:latest

# 4. Konfiguroi .env
cat > .env << EOF
GROQ_API_KEY=gsk_xxxxx
GROQ_MODEL_ID=llama-3.3-70b-versatile
EOF

# 5. Käynnistä backend
uvicorn apps.backend.main:app --reload --port 8000
```

---

## Tuotantoympäristö (Hetzner)

### Palvelun hallinta
```bash
# Palvelun tila
systemctl status lapuarag-backend

# Uudelleenkäynnistys (päivityksen jälkeen)
systemctl restart lapuarag-backend

# Lokit
journalctl -u lapuarag-backend -f

# Qdrant
docker ps | grep qdrant
```

### Päivitysprosessi
```bash
# 1. OMALLA KONEELLA: Commit ja push
git add -A
git commit -m "description"
git push

# 2. PALVELIMELLA (SSH):
cd /root/Lapua-RAG-v2.0
git pull && systemctl restart lapuarag-backend
```

### Inkrementaalinen indeksointi (UUDEN DATAN LISÄYS)

**ÄLÄ KOSKAAN** aja koko indeksointia uudelleen - kestää tunteja!

```bash
# 1. Lisää uudet chunkit
python3 scripts/index_website_lite.py --source data/uusi_data.json

# 2. Tarkista nykyinen pistemäärä
python3 -c "from qdrant_client import QdrantClient; c=QdrantClient('localhost',6333); print(c.get_collection('lapua_chunks').points_count)"

# 3. Indeksoi VAIN uudet (start-from = vanha määrä)
python3 scripts/index_incremental.py --start-from <VANHA_MÄÄRÄ>

# 4. Käynnistä uudelleen
systemctl restart lapuarag-backend
```

---

## API Endpoints

| Endpoint | Metodi | Kuvaus |
|----------|--------|--------|
| `/health` | GET | Terveystarkistus |
| `/query` | POST | RAG-kysely (`{"question": "..."}`) |
| `/admin/reindex` | POST | Uudelleenindeksointi |

---

## Tiedostorakenne

```
├── apps/
│   ├── backend/          # FastAPI backend
│   │   ├── llm/          # Groq client + output cleanup
│   │   └── main.py
│   └── frontend/         # Next.js frontend
├── packages/
│   ├── agents/           # Query agent (system prompt)
│   └── rag_core/         # Retrieval, embeddings, indexing
├── scripts/
│   ├── run_evaluation.py     # Aja 250 kysymystä
│   ├── auto_evaluate.py      # GPT-arviointi
│   ├── index_incremental.py  # Inkrementaalinen indeksointi
│   ├── index_website_lite.py # Website chunkkaus
│   ├── scrape_lapua_fi.py    # Web scraping
│   └── summary_results.py    # Yhteenveto
├── data/                     # (ei GitHubissa - .gitignore)
│   ├── chunks/               # Vektori-indeksin data
│   ├── parsed/               # Parsitut pöytäkirjat
│   └── *_scraped/            # Scrapattu verkkosisältö
└── kysymykset.md             # 250 testikysymystä
```

---

## Kustannukset

| Palvelu | Kustannus |
|---------|-----------|
| Vercel (Frontend) | 0 € (Hobby) |
| Hetzner VPS (CAX11) | ~4 €/kk |
| Groq Cloud (LLM) | ~0.15-0.75 $/M tokenia |
| Domain (lapuarag.org) | ~10 €/v |

---

## Lisenssi

MIT License - Katso LICENSE-tiedosto.

## Tekijä

Harrasteprojekti - Marko (FoxRav)
