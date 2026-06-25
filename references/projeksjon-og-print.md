# Projeksjon, størrelse og print

## Projeksjon

`build_poster.py` bruker **Web Mercator** (samme som vanlige nettkart, nord opp). `Projector`:

1. Regner mercator-koordinater for bbox-en.
2. **Senter-beskjærer** mercator-vinduet til kartrektangelets bredde/høyde-forhold (papir-
   ratioen) — slik unngås forvrengning; kartet fyller flaten uten å strekkes.
3. Skalerer til SVG-enheter og snur y-aksen (SVG har y nedover).

Fordi alt er vektor, er det **oppløsningsuavhengig**: samme SVG er like skarp på 30 cm og 2 m.

## SVG-enheter og papir-ratio

`viewBox` settes i logiske enheter (bredde 1000). Høyden følger ratioen:

| ratio | enheter (b×h) | typisk bruk |
|---|---|---|
| `2:3` | 1000×1500 | standard plakat (30×45, 50×70, 70×105) |
| `3:4` | 1000×1333 | litt kortere |
| `5:7` | 1000×1400 | 50×70 cm nøyaktig |
| `7:10` | 1000×1429 | 70×100 cm nøyaktig |
| `1:1` | 1000×1000 | kvadratisk |
| `iso` | 1000×1414 | A-serie (A3, A2, A1, A0) |

Selve trykkstørrelsen velges i HTML-en ved nedlasting — ratioen styrer bare formen.

## Nedlasting

- **SVG** — vektor, skrift innebygd (base64). **Beste fil til trykkeri** for store trykk;
  skaleres uendelig. Anbefal alltid denne for trykk > ~70 cm.
- **PNG** — rasteriseres i nettleseren ved valgt `cm × DPI`. Pikselmål = `cm/2.54 × DPI`.
  - 50×70 cm @ 150 DPI ≈ 2953 × 4134 px
  - 70×100 cm @ 150 DPI ≈ 4134 × 5906 px
  - 100×150 cm @ 150 DPI ≈ 5906 × 8858 px
  - 200×200 cm @ 150 DPI ≈ 11811 × 11811 px (nær nettleserens canvas-grense ~16384 px)
  Over grensen skaleres PNG-en ned med en advarsel — bruk SVG i stedet.
- **Print / PDF** — `@page { size:auto; margin:0 }`, én side, verktøylinje skjult.

## DPI-veiledning

- **150 DPI** holder fint for store plakater som ses på avstand (vegg).
- **300 DPI** for mindre trykk (≤ A3) som ses på nært hold.
- For svært store trykk: lever **SVG** til trykkeriet og la dem rastere ved riktig oppløsning.

## Trykkeri-tips

- Mange trykkerier tar gjerne imot **SVG** eller **PDF**. SVG bevarer skarphet best.
- Skriften er bygd inn i SVG/PNG ved nedlasting, så typografien blir riktig uten at trykkeriet
  har fonten installert. (Ved bruk i et vektorprogram kan det likevel være lurt å gjøre tekst
  om til baner/outlines for full sikkerhet.)
- Sjekk fargeprofil med trykkeriet (skjerm er RGB, trykk er ofte CMYK) — sterke RGB-farger kan
  dempes litt i CMYK.
