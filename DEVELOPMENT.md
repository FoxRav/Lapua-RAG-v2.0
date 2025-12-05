# Kehitysohjeet - Lapua RAG

## ⚠️ EHDOTTOMAT SÄÄNNÖT

### 1. EI KEKSITTYÄ DATAA
```
❌ VÄÄRIN: "Yhtiön liikevaihto on noin 5 miljoonaa euroa"
✅ OIKEIN: Hae tieto Asiakastieto.fi / Finder.fi tai merkitse "Ei saatavilla"
```

### 2. VAHVISTA LÄHTEET
Kaikki data tulee vahvistaa:
- **Y-tunnukset**: YTJ (tietopalvelu.ytj.fi)
- **Talousluvut**: Asiakastieto.fi, Finder.fi, vuosikertomukset
- **Henkilöt**: Kaupparekisteri, yrityksen verkkosivut
- **Pöytäkirjatiedot**: Alkuperäiset PDF-pöytäkirjat

### 3. DOKUMENTOI LÄHTEET
```json
{
  "name": "Yhtiö Oy",
  "y_tunnus": "1234567-8",
  "sources": ["https://tietopalvelu.ytj.fi/", "https://www.asiakastieto.fi/..."],
  "last_updated": "2025-12-05"
}
```

---

## RAG-optimointi

### Hallusinaation minimointi

1. **LLM-parametrit** (`apps/backend/llm/groq_client.py`):
```python
temperature=0.01,  # Lähes deterministinen
top_p=0.5,         # Tiukka jakauma
```

2. **System prompt** (`packages/agents/query_agent.py`):
```python
"🚫 EHDOTTOMAT KIELLOT:
1. ÄLÄ KOSKAAN keksi tai arvaa tietoa
2. ÄLÄ KOSKAAN käytä ulkopuolista tietämystä
3. Jos tietoa EI löydy → 'Tätä tietoa ei löydy lähteistä.'"
```

3. **User prompt** (`apps/backend/llm/groq_client.py`):
```python
"TÄRKEÄÄ: Vastaa VAIN yllä olevien lähteiden perusteella."
```

---

## Evaluointiprosessi

### Vaihe 1: Aja kysymykset
```bash
python scripts/run_evaluation.py --output evaluation_results/run_YYYYMMDD.json
```
- Kesto: ~30-45 min (250 kysymystä)
- Tallentaa vastaukset + lähteet JSON-tiedostoon

### Vaihe 2: Auto-evaluointi
```bash
python scripts/auto_evaluate.py evaluation_results/run_YYYYMMDD.json \
  --api-key "GROQ_API_KEY" --delay 2
```
- GPT arvioi jokaisen vastauksen
- Tuottaa: `run_YYYYMMDD_enriched.json`

### Vaihe 3: Yhteenveto
```bash
python scripts/summary_results.py evaluation_results/run_YYYYMMDD_enriched.json
```

### Vaihe 4: Manuaalinen tarkistus
**TÄRKEÄÄ:** Vertaa huonoimmat vastaukset alkuperäisiin pöytäkirjoihin!
- Onko pykälä olemassa?
- Onko päivämäärä oikein?
- Onko sisältö lähteessä?

---

## Tavoitemetriikat

| Metriikka | Nykytila | Tavoite |
|-----------|----------|---------|
| Faithfulness | 38% | **>90%** |
| Hallucination | 60% | **<10%** |
| Relevance | 75% | >80% |
| Completeness | 55% | >70% |
| Overall | 53% | **>80%** |

---

## Palvelimen päivitys

### Omalla koneella (Windows):
```powershell
cd F:\-DEV-\10.Projekti-Lapua\Projekti2-02122025
git add -A
git commit -m "fix: description"
git push
```

### Palvelimella (SSH):
```bash
ssh root@lapuarag.org
cd /root/Lapua-RAG-v2.0
git pull
systemctl restart lapuarag-backend
systemctl status lapuarag-backend
```

---

## Debuggaus

### Lokit
```bash
# Palvelimen lokit
journalctl -u lapuarag-backend -f

# Qdrant lokit
docker logs lapua-qdrant -f
```

### API testaus
```bash
curl -X POST https://lapuarag.org/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Mikä on tuloveroprosentti?"}'
```

---

## Tiedostot

| Tiedosto | Tarkoitus |
|----------|-----------|
| `apps/backend/llm/groq_client.py` | LLM-parametrit (temperature, prompt) |
| `packages/agents/query_agent.py` | System prompt, kyselyn käsittely |
| `scripts/run_evaluation.py` | 250 kysymyksen ajo |
| `scripts/auto_evaluate.py` | GPT-arviointi |
| `scripts/summary_results.py` | Tulosten yhteenveto |
| `data/companies_database.json` | Yritysten VAHVISTETUT tiedot |
| `kysymykset.md` | 250 testikysymystä |

---

## Muistilista ennen committia

- [ ] Ei keksittyä dataa
- [ ] Lähteet dokumentoitu
- [ ] Testit ajettu (jos muutettu logiikkaa)
- [ ] README päivitetty (jos uusia ominaisuuksia)

