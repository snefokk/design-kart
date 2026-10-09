# design-kart-dittsted

Lag et **stilig designkart (kunstplakat)** over hjembyen din eller et lite tettsted — som de
kule bykart-plakatene for storbyer, men for stedene som ellers ikke har slike kart. Bygget med
AI, klart til print, med din egen adresse markert med et hjerte eller en stjerne.

> **Vil du heller at vi lager plakaten for deg?**
> Bestill en ferdig plakat på **[snefokk.com/designet-bykart](https://snefokk.com/designet-bykart)** — så
> bygger Snefokk den, tilpasser farger og typografi, og leverer trykkeklar fil. Dette repoet er for
> deg som vil gjøre jobben selv, gratis.

## Hva skillen lager

- **En vektor-plakat (SVG)** av stedet — gater, vann, kystlinje og parker, stilisert og rent
- **Skarpt i alle størrelser** — last ned som SVG eller høyoppløst PNG, og trykk helt opp til
  **2 m × 2 m**
- **Din adresse markert** — sett et hjerte eller en stjerne på huset, hytta eller favoritt-
  stedet
- **Dine farger** — last opp en fargepalett (med eller uten hex-koder) eller velg en ferdig
  preset; AI-en fordeler fargene på kartet
- **Tittelblokk** med stedsnavn og koordinater, som de kjente plakatene
- **Selvstendig HTML** — åpne i nettleseren, last ned SVG/PNG eller skriv ut til PDF

Kartdataene hentes fra **OpenStreetMap**. Ingen kartnøkkel, ingen `pip install`.

## Hvem det er for

- Folk på små steder som vil ha et stilig kart over hjembyen på veggen
- Gaver: en plakat med «hjemme» markert med et hjerte
- Hytteeiere, tilflyttere, lokalpatrioter — og bedrifter som vil ha stedet sitt på veggen

## To måter å få plakaten

| Gjør det selv (dette repoet) | La Snefokk gjøre jobben |
| --- | --- |
| Gratis — krever et Claude-abonnement | Bestill på **[snefokk.com/designet-bykart](https://snefokk.com/designet-bykart)** |
| Du kjører skillen selv i Claude Cowork — bygg så mange plakater du vil | Snefokk designer plakaten, tilpasser farger og format, og leverer trykkeklar fil, med én tilbakemeldingsrunde |
| **Ferdig på ~15 minutter** (med god internettforbindelse) | **Klart innen typisk en uke** |

## Slik virker det

```
Sted + palett + adresse
        │
        ▼
 fetch_osm.py  ── henter gater/vann/parker fra OpenStreetMap
        │
        ▼
 build_poster.py ── tegner alt som vektor-SVG i dine farger
        │
        ▼
 ferdig .html  ── last ned SVG / PNG, eller print til PDF
```

## Hva du trenger (for å gjøre det selv)

- Et aktivt **Claude**-abonnement — skillen kjører i Claude Cowork / Claude Code
- **Internett** — for OpenStreetMap-data
- **Python 3** — for å bygge plakaten (standardbibliotek, ingen `pip install`)
- En **fargepalett** (valgfritt) — bilde, preset eller hex-koder

## Kom i gang

1. **Last ned skillen** — klon eller last ned dette repoet.
2. **Installer i Claude Cowork** — pek Cowork mot skill-mappa.
3. **Følg `SKILL.md`** — den tar deg steg for steg: sted, palett, adresse og bygging.

## Bygg fra kommandolinja (avansert)

```bash
# 1) Hent geometri for stedet
python3 scripts/fetch_osm.py --sted "Berlevåg, Norge" --radius 1.8 \
  --output outputs/kart-arbeid/osm-data.json

# 2) Bygg plakaten (config.json med palett, font og markør — se CLAUDE.md)
python3 scripts/build_poster.py \
  --config outputs/kart-arbeid/config.json \
  --osm    outputs/kart-arbeid/osm-data.json \
  --template templates/poster_template.html \
  --output outputs/berlevag-plakat.html
```

## Ferdige paletter

`templates/palettes/`: `skandi-krem`, `midnatt-bla`, `solnedgang`, `rosa-hav`, `snefokk`.

## Søsterskill

`by-kart-bygger` lager A4-**turistkart** med bedrifter/severdigheter over rasterfliser. Denne
skillen lager en **designplakat** som vektor, for veggen. Bruk den som passer behovet.

## Eksempler

Prøv en ferdig plakat live — søk opp en adresse, sett et hjerte, og last ned eller print:

- [Berlevåg](https://snefokk.com/kart/plakat/berlevag/)
- [Alta](https://snefokk.com/kart/plakat/alta/)
- [Trondheim](https://snefokk.com/kart/plakat/trondheim/)

## Data og lisens

Kartdata © OpenStreetMap-bidragsytere ([ODbL](https://www.openstreetmap.org/copyright)).
Geokoding via Nominatim. Skillen selv: se [LICENSE](LICENSE) — åpen kildekode.
