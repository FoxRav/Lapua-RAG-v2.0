## Lapuan päätöksenteon juridinen ja riskianalyysi – suunnitelma

**Nykytila**
- Aineisto: vuoden 2024–2025 pöytäkirjat keskeisistä toimielimistä (kaupunginvaltuusto, kaupunginhallitus, lautakunnat) sekä niistä muodostettu RAG-aineisto (`rag_output`).
- Esiprosessointi: `normalized_chunks.jsonl` ja yksittäisten asiakirjojen `_full.md`-tiedostot.

**Tavoite**
- Arvioida päätöksenteon lainmukaisuus, taloudellinen riskitaso ja jääviys/ammattimaisuus erityisesti:
  - Simpsiönvuori Oy / Simpsiön kehittäminen
  - Uusi uimahalli
  - Muut suuret hankkeet ja takaukset / investoinnit (esim. Invest Lapua Oy, Honkimetsän keskusvarasto, kirjasto-monipalveluauto, suuret avustushankkeet).

**Menetelmä**
- Käytetään ensisijaisesti:
  - `rag_output/normalized_chunks.jsonl` kvantitatiiviseen seulontaan (hanke-sanat, suuret euromäärät, lisämäärärahat, takaukset).
  - `rag_output/individual_documents/*_full.md` kvalitatiiviseen luentaan kohdepäätöksistä (§-tasolla).
- Vertailu keskeiseen normistoon (ei tyhjentävästi):
  - Kuntalaki (410/2015) – toimivallat, talous, takaukset (mm. 14, 39, 90–92, 129 §).
  - Hallintolaki (434/2003) – esteellisyys/jääviys (27–30 §) ja hyvän hallinnon periaatteet.
  - Julkisuuslaki ja hankintalaki siltä osin kuin ne ilmenevät pöytäkirjoista.

**Analyysivaiheet**
1. Karkeaseulonta
   - Poimitaan normalized-chunks-aineistosta kaikki:
     - viittaukset Simpsiönvuori/Simpsiöön,
     - viittaukset uimahalliin,
     - suuret investoinnit ja takaukset (esim. ≥ 100 000 €),
     - hankkeet, joissa on merkittäviä ulkopuolisia rahoituslähteitä.
2. Kohdepäätösten läpiluku
   - Luetaan `_full.md`-pöytäkirjat niistä kokouksista, joissa kohteet ratkaistaan:
     - Kh 16.12.2024 (uimahallin pääpiirustukset, Simpsiönvuori Oy:n lyhytaikainen rahoitus / otto-oikeus).
     - Kh 3.2.2025 (§ 21, 22, 29, 30 – takaus Invest Lapua Oy, Simpsiön kehittämismäärärahan käyttö).
     - Valtuuston keskeiset investointipäätökset, jos ne löytyvät aineistosta.
3. Juridinen ja prosessianalyysi
   - Tarkastellaan:
     - oikea toimielin ja delegointiketju (hallintosääntöviittaukset),
     - päätösten valmistelun laatu (selvitykset, vaikutusarviot, kustannusennusteet),
     - esteellisyysmerkinnät ja poistumiset,
     - mahdollinen otto-oikeuden käyttö tai käyttämättä jättäminen.
4. Riskianalyysi
   - Arvioidaan tapauskohtaisesti:
     - taloudellinen riski (summat, vastuut, epävarmat tulovirrat),
     - rakenteellinen riski (riippuvuus yksittäisestä yhtiöstä / hankkeesta),
     - maine- ja luottamusriskit (erimielisyydet, eriävät mielipiteet).
5. Raportti
   - Kootaan:
     - tapauskohtaiset yhteenvedot,
     - lainmukaisuuden alustava arvio (ei sitova lainopillinen kanta),
     - riskiluokitus (matala–keskisuuri–korkea),
     - havaittu jääviys- ja ammattimaisuustaso.

**Tuotos**
- Yhteenvetoraportti (markdown), joka voidaan jatkossa laajentaa kattamaan myös muut vuodet/aineistot.


