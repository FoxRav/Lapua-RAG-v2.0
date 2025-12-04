# Lapuan Kaupunki RAG

🌐 **Live:** https://www.lapuarag.org

Kokeellinen harrasteprojekti, joka tarjoaa RAG-pohjaisen haun Lapuan kaupungin julkisista pöytäkirjoista. Palvelu ei ole Lapuan kaupungin virallinen palvelu eikä sitä ole tarkoitettu päätöksenteon tueksi tai oikeudelliseksi neuvoksi; tulokset tulee aina varmistaa alkuperäisistä pöytäkirjoista ja virallisista lähteistä.

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
                        │  gpt-oss-120b    │
                        └──────────────────┘
```

## Komponentit

| Komponentti | Teknologia | Sijainti |
|-------------|------------|----------|
| **Frontend** | Next.js 14, TypeScript | Vercel (www.lapuarag.org) |
| **Backend API** | FastAPI, Python 3.12 | Hetzner VPS (lapuarag.org) |
| **Vektoritietokanta** | Qdrant 1.13+ | Hetzner VPS (Docker) |
| **Embeddings** | BGE-M3 (FlagEmbedding) | Hetzner VPS |
| **LLM** | openai/gpt-oss-120b | Groq Cloud |
| **Reverse Proxy** | Caddy (HTTPS) | Hetzner VPS |

## RAG Pipeline

1. **Docling-ingestio**: PDF-pöytäkirjat → Markdown + JSON
2. **Chunkkaus**: Pykäläkohtaiset chunkit (~700 tokenia/chunk)
3. **Embeddings**: BGE-M3 dense-vektorit (1024-dim)
4. **Qdrant**: Vektori-indeksi `lapua_chunks` (1098 pistettä)
5. **Haku**: Dense-haku + recency boost (uudemmat +25%)
6. **LLM**: Groq gpt-oss-120b tiivistää vastauksen

## Parametrit

| Parametri | Arvo | Kuvaus |
|-----------|------|--------|
| `k` | 10-20 | Haettavien chunkkien määrä |
| `max_tokens` | 1500 | LLM-vastauksen max pituus |
| `temperature` | 0.2 | LLM:n "luovuus" (matala = deterministinen) |
| `recency_boost` | 1.25x | Tuoreiden (< 2v) päätösten painotus |
| `chunk_size` | ~700 tokenia | Chunkkien koko indeksoinnissa |

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
GROQ_MODEL_ID=openai/gpt-oss-120b
EOF

# 5. Indeksoi data (vain kerran)
python -m docling_pipeline.cli parse-all
python -c "from rag_core.chunking import run_all; run_all()"
python -c "from rag_core.indexing import index_all_chunks; index_all_chunks()"

# 6. Käynnistä backend
uvicorn apps.backend.main:app --reload --port 8000

# 7. Käynnistä frontend
cd apps/frontend
npm install
npm run dev
```

## API Endpoints

| Endpoint | Metodi | Kuvaus |
|----------|--------|--------|
| `/health` | GET | Terveystarkistus |
| `/query` | POST | RAG-kysely (`{"question": "..."}`) |
| `/admin/reindex` | POST | Uudelleenindeksointi |

## Tuotantoympäristö (Hetzner)

```bash
# Backend-palvelu
systemctl status lapuarag-backend

# Qdrant-kontti
docker ps | grep qdrant

# Lokit
journalctl -u lapuarag-backend -f

# Caddy (HTTPS)
systemctl status caddy
```

## Kustannukset

| Palvelu | Kustannus |
|---------|-----------|
| Vercel (Frontend) | 0 € (Hobby) |
| Hetzner VPS (CAX11) | ~4 €/kk |
| Groq Cloud (LLM) | ~0.15-0.75 $/M tokenia |
| Domain (lapuarag.org) | ~10 €/v |

## Lisenssi

MIT License - Katso LICENSE-tiedosto.

## Tekijä

Harrasteprojekti - Marko (FoxRav)
