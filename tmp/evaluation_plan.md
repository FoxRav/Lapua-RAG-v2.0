# RAG-palvelun Evaluointi- ja Optimointisuunnitelma

## Tavoite
Ajaa 150 kysymyksen testipatteri läpi, arvioida vastaukset ja säätää parametrit state-of-the-art tasolle.

---

## VAIHE 1: Kysymyspatterin suoritus (Batch Query)

### 1.1 Skriptin luonti
- Luodaan Python-skripti `scripts/run_evaluation.py`
- Parsitaan kysymykset `kysymykset.md` tiedostosta
- Ajetaan jokainen kysymys API:n kautta (`POST https://www.lapuarag.org/query`)
- Tallennetaan vastaukset JSON-muodossa

### 1.2 Tallennettavat tiedot per kysymys:
```json
{
  "id": 1,
  "topic": "Talousarvio ja taloussuunnitelma",
  "question": "Mikä on Lapuan kaupungin vuoden 2025 talousarvion alijäämäennuste?",
  "answer": "...",
  "sources": [...],
  "response_time_ms": 1234,
  "timestamp": "2025-12-05T12:00:00Z"
}
```

### 1.3 Tulosten tallennus
- `evaluation_results/baseline_run_YYYYMMDD_HHMM.json`
- Jokainen ajo tallennetaan erikseen vertailua varten

---

## VAIHE 2: Vastausten arviointi (Evaluation)

### 2.1 Arviointikriteerit (1-5 asteikko)

| Kriteeri | Kuvaus |
|----------|--------|
| **Relevanssi** | Vastaako vastaus suoraan kysymykseen? |
| **Tarkkuus** | Ovatko faktat ja luvut oikein? |
| **Kattavuus** | Sisältääkö vastaus kaikki oleelliset tiedot? |
| **Lähteiden laatu** | Ovatko lähteet relevantteja ja oikein viitattuja? |
| **Selkeys** | Onko vastaus selkeä ja ymmärrettävä? |

### 2.2 Arviointityökalu
- Luodaan `scripts/evaluate_results.py`
- Interaktiivinen CLI arviointiin
- Tallentaa arviot samaan JSON-tiedostoon

### 2.3 Arviointiprosessi
1. **Automaattinen esikarsinta**:
   - Tyhjät vastaukset → 0 pistettä
   - Vastauksen pituus < 50 merkkiä → tarkastettava
   
2. **Manuaalinen arviointi**:
   - Käydään läpi jokainen vastaus
   - Tarkistetaan alkuperäisistä pöytäkirjoista
   - Merkitään virheelliset faktat

---

## VAIHE 3: Parametrien säätö (Tuning)

### 3.1 Säädettävät parametrit

#### Retrieval-parametrit (`packages/rag_core/`)
| Parametri | Nykytila | Vaihtoehto | Vaikutus |
|-----------|----------|------------|----------|
| `top_k` | 10 | 15, 20 | Enemmän kontekstia |
| `CHUNK_OVERLAP_TOKENS` | 150 | 100, 200 | Kontekstin jatkuvuus |
| `MAX_TOKENS_PER_CHUNK` | 700 | 500, 900 | Chunkin koko |
| `recency_boost` weight | ? | 0.1-0.3 | Uudemmat dokumentit |

#### LLM-parametrit (`apps/backend/llm/groq_client.py`)
| Parametri | Nykytila | Vaihtoehto | Vaikutus |
|-----------|----------|------------|----------|
| `max_completion_tokens` | 1500 | 2000, 2500 | Pidempi vastaus |
| `temperature` | ? | 0.1, 0.3 | Luovuus vs. tarkkuus |
| `system_prompt` | nykyinen | paranneltu | Vastauksen muoto |

#### Prompt Engineering (`packages/agents/query_agent.py`)
- Ohjeet vastauksen rakenteelle
- Faktojen korostus
- Lähteiden viittaaminen

### 3.2 A/B-testaus
1. Muutetaan YKSI parametri kerrallaan
2. Ajetaan sama 150 kysymyksen patteri
3. Verrataan tuloksia baseline-ajoon
4. Säilytetään parantuneet muutokset

---

## VAIHE 4: Iteratiivinen optimointi

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐  │
│  │  RUN     │ -> │ EVALUATE │ -> │  TUNE    │ -> │ TEST │  │
│  │ 150 Q's  │    │ Scores   │    │ Params   │    │ Best │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────┘  │
│       ^                                              │      │
│       └──────────────────────────────────────────────┘      │
│                    (toista kunnes tyytyväinen)              │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Tavoitemetriikat
- Keskiarvo kaikista kriteereistä: **≥ 4.0 / 5.0**
- Yksikään vastaus ei saa olla alle 2.5
- Vastausaika keskimäärin < 5 sekuntia

---

## VAIHE 5: Toteutusaikataulu

| Päivä | Tehtävä |
|-------|---------|
| **1** | Skriptien luonti, baseline-ajo |
| **2** | Manuaalinen arviointi (50 kysymystä) |
| **3** | Arviointi jatkuu (100 kysymystä) |
| **4** | Parametrien säätö 1. kierros |
| **5** | Uusi ajo, vertailu, säätö 2. kierros |
| **6** | Lopullinen validointi, dokumentointi |

---

## Seuraavat toimenpiteet

1. ✅ Kysymykset valmiina (`kysymykset.md`)
2. ⏳ Luodaan `scripts/run_evaluation.py`
3. ⏳ Luodaan `scripts/evaluate_results.py`
4. ⏳ Ajetaan baseline
5. ⏳ Arvioidaan tulokset
6. ⏳ Säädetään parametrit
7. ⏳ Iteroidaan kunnes tavoitteet saavutettu

---

## Tiedostorakenne

```
Projekti2-02122025/
├── kysymykset.md                    # 150 kysymystä
├── scripts/
│   ├── run_evaluation.py            # Kysymysten ajo
│   ├── evaluate_results.py          # Vastausten arviointi
│   └── compare_runs.py              # Ajojen vertailu
├── evaluation_results/
│   ├── baseline_20251205_1200.json
│   ├── run_topk15_20251205_1400.json
│   └── ...
└── tmp/
    └── evaluation_plan.md           # Tämä dokumentti
```

