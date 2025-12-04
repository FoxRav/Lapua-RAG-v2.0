# Käyttöohje – Lapuan Kaupunki RAG

**Live-palvelu:** https://www.lapuarag.org

---

## ⚠️ Tärkeä huomautus

Tämä palvelu on **yksityishenkilön kehittämä kokeellinen hakutyökalu** Lapuan kaupungin julkisiin pöytäkirjoihin. Se **ei ole kaupungin virallinen palvelu**, eikä sitä ole tarkoitettu:
- Päätöksenteon tueksi
- Viranomaistyöhön
- Oikeudellisen arvioinnin pohjaksi

**Kaikki johtopäätökset tulee aina tarkistaa alkuperäisistä pöytäkirjoista ja virallisista kanavista.**

---

## 1. Mitä palvelu tekee?

Palvelu lukee Lapuan kaupungin pöytäkirjoja ja vastaa kysymyksiin tekoälyn avulla:

1. **Hakee** pykälät, jotka liittyvät kysymykseesi
2. **Painottaa** uudempia päätöksiä (2025 > 2024 > 2023)
3. **Tiivistää** löydökset selkeäksi vastaukseksi
4. **Näyttää** lähteet, joista vastaus on koottu

### Mistä data koostuu?

| Toimielin | Aikaväli |
|-----------|----------|
| Kaupunginvaltuusto | 2024-2025 |
| Kaupunginhallitus | 2024-2025 |
| Sivistyslautakunta | 2024-2025 |
| Tekninen lautakunta | 2024-2025 |
| Ympäristölautakunta | 2021-2025 |

**Yhteensä:** ~1098 pykälää indeksoitu

---

## 2. Käyttöohjeet

### Peruskäyttö

1. Mene osoitteeseen **https://www.lapuarag.org**
2. Kirjoita kysymys tekstikenttään, esim:
   - *"Simpsiönvuori Oy takaus"*
   - *"Männikön koulu"*
   - *"Talousarvio 2025"*
   - *"Uimahalli"*
3. Paina **Hae**
4. Odota 5-15 sekuntia

### Vastauksen lukeminen

Vastaus sisältää:

- **Lyhyt yhteenveto** – 2-3 virkettä olennaisimmasta
- **Keskeiset päätökset** – luettelo muodossa:
  - **Toimielin, pp.kk.vvvv, § X** – Mitä päätettiin
- **Lähdepykälät** – alkuperäiset asiakirjat listattuna

### Vinkkejä hyviin kysymyksiin

✅ **Hyvä:** "Mitä Männikön koulusta on päätetty?"
✅ **Hyvä:** "Simpsiönvuori Oy:n takaukset 2025"
✅ **Hyvä:** "Kaupungin talousarvion muutokset"

❌ **Huono:** "Kerro kaikki" (liian laaja)
❌ **Huono:** "Kuka on pormestari?" (ei päätösasia)

---

## 3. Vastauksen tulkinta

### Score-arvo

Jokaisen lähdepykälän vieressä näkyy **score** (0.0-1.0):
- **0.55+** = Erittäin osuva
- **0.45-0.55** = Melko osuva
- **< 0.45** = Heikosti osuva

### Recency boost

Järjestelmä painottaa **uudempia päätöksiä**:
- 2025 päätökset saavat +25% painotuksen
- 2024 päätökset saavat +12% painotuksen
- Vanhemmat päätökset eivät saa lisäpainotusta

Tämä tarkoittaa, että jos sama asia on käsitelty 2023 ja 2025, uudempi näkyy ylempänä.

---

## 4. Rajoitukset

1. **Ei reaaliaikaista dataa** – Uusimmat pöytäkirjat eivät päivity automaattisesti
2. **Ei PDF-linkkejä** – Alkuperäisiä PDF:iä ei voi avata suoraan
3. **LLM voi tulkita väärin** – Tarkista aina lähdepykälistä
4. **Vain julkiset pöytäkirjat** – Salaiset/suljetut asiat eivät ole mukana

---

## 5. Tekninen tausta

| Komponentti | Teknologia |
|-------------|------------|
| Frontend | Next.js 14 (Vercel) |
| Backend | FastAPI (Hetzner VPS) |
| Vektorihaku | Qdrant + BGE-M3 |
| LLM | Groq Cloud (gpt-oss-120b) |

### API (kehittäjille)

```bash
# Terveystarkistus
curl https://lapuarag.org/health

# Kysely
curl -X POST https://lapuarag.org/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Simpsiönvuori takaus"}'
```

---

## 6. Yhteystiedot

Palvelu on harrasteprojekti. Palaute ja kysymykset:
- GitHub: https://github.com/FoxRav/Lapua-RAG-v2.0

**Muista:** Palvelu ei korvaa virallisia lähteitä. Tarkista aina päätökset alkuperäisistä pöytäkirjoista!
