---
name: design-kart-dittsted
description: Lag en stilisert, printbar designplakat (kunstkart) over et sted — som de kule bykart-plakatene for storbyer, men for hjembyen din eller et lite tettsted. Kartet tegnes som vektor-SVG fra OpenStreetMap-data og kan trykkes knivskarpt helt opp til 2 m × 2 m. Brukeren kan markere sin egen adresse med et hjerte eller en stjerne, og velge farger ved å laste opp en fargepalett (med eller uten hex-koder) eller bruke en ferdig preset. Output er en selvstendig HTML-fil med nedlasting som SVG og høyoppløst PNG, samt print/PDF. Bruk denne skillen når brukeren sier «lag plakatkart», «designkart over hjembyen», «kart til veggen», «poster map», «lag et kunstkart over [sted]», «kart over byen til print», «marker huset mitt på et kart», laster opp en fargepalett og vil ha et kart, eller viser til de stiliserte bykart-plakatene (New Haven / Osaka / Budapest-stil) og vil ha noe liknende for et mindre sted.
---

# Design-kart-dittsted — stilisert designplakat (kunstkart) av et sted

Denne skillen lager en **kunstplakat** av et sted: et rent, stilisert kart (gater, vann,
kystlinje, parker) i en valgt fargepalett, med ett hjerte eller én stjerne på en valgfri
adresse, og en tittelblokk med stedsnavn + koordinater nederst — slik de populære bykart-
plakatene for storbyer ser ut, men for små steder som ellers ikke har slike kart.

Output er en **selvstendig, interaktiv HTML-side** (bygd for å hostes, f.eks. på
`kart.snefokk.com/plakat/<sted>`). I siden kan en besøkende:
- **skrive inn adressen sin** → den geokodes og et hjerte/en stjerne settes på kartet,
- **velge plakatstørrelse** blant vanlige rammeformat (30×40, 50×70, 70×100 …),
- laste ned som **SVG** (vektor — knivskarpt i alle størrelser, beste fil til trykkeri),
- laste ned som **høyoppløst PNG** (valgt cm-størrelse og DPI, opp til ~2 m × 2 m),
- skrive ut direkte / lagre som **PDF**.

Markøren settes altså vanligvis av **sluttbrukeren** i siden. Operatørens jobb er å bygge selve
plakaten (sted, palett, typografi); adresse og størrelse velges av den som skal ha plakaten.

> Dette er en søsterskill til `by-kart-bygger`. Forskjellen: by-kart-bygger lager et A4-
> **turistkart** med mange POI-markører over rasterfliser; denne lager en **designplakat**
> som vektor, for veggen, med fokus på estetikk og stor trykkstørrelse.

## Språk (VIKTIG)

**Snakk samme språk som brukeren — for norske brukere betyr det norsk hele veien.** Det
gjelder statusmeldinger, spørsmål (AskUserQuestion), oppsummeringer og feilmeldinger. Ikke
bytt til engelsk underveis. Tekniske begreper som config-feltnavn, kommandoer og filnavn
forblir på engelsk. Hvis brukeren starter på et annet språk, følg det.

## Hva trenger du før du starter

- **Internett** — for OpenStreetMap (Overpass) og Nominatim (geokoding). Begge er gratis
  åpne API-er; ingen nøkkel.
- **Python 3** — for å hente geometri og bygge HTML-en. Kun standardbibliotek, ingen
  `pip install`.
- **En fargepalett** (valgfritt) — brukeren kan laste opp et palett-bilde, velge en ferdig
  preset, eller oppgi hex-koder. Uten valg brukes en nøytral standardpalett.
- **Claude in Chrome** (valgfritt) — kun nyttig hvis brukeren vil slå opp en nøyaktig
  adresse-koordinat i Google Maps. Nominatim-fallback fungerer uten nettleser.

**Anbefalt modell:** Kjør med en kraftig modell (Fable eller Opus) — palett-lesing fra bilde
og visuell kontroll av kartet er skjønnsmessige steg.

**Filplassering:** `scripts/`, `templates/` og `references/` ligger i skillens basemappe —
bruk full sti fra basemappen. Arbeidsfiler og ferdige plakater (`outputs/...`) lagres i
brukerens workspace.

## Overordnet flyt

```
1. Forstå ønsket   →  hvilket sted? hostet side eller ferdigmarkert gave?
2. Palett          →  last opp bilde (les farger → roller) / preset / hex
3. Hent geometri   →  fetch_osm.py --sted "…"  (juster --radius til tettstedet)
4. (valgfritt) ferdigmarker en adresse  →  Nominatim, kun for gave-plakater
5. Bygg config.json
6. Bygg plakaten   →  build_poster.py → interaktiv HTML (flere format)
7. Visuell kontroll →  åpne i nettleser, test adresse-input + format, juster
8. Lever / host    →  legg HTML-en på kart.snefokk.com/plakat/<sted>
```

---

## Trinn 1 — Forstå ønsket

Avklar kort (gjerne med AskUserQuestion):

- **Sted** — by/tettsted/bydel. Et lite sted er helt fint; det er hele poenget.
- **Hostet side eller ferdigmarkert gave?**
  - *Hostet side* (standard): besøkende skriver inn sin egen adresse og velger størrelse i
    siden. Du baker **ingen** markør inn — det gjøres interaktivt. Siden legges på
    `kart.snefokk.com/plakat/<sted>`.
  - *Ferdigmarkert gave*: du setter selv av én adresse (hjerte/stjerne) i config-en før bygging.
- **Orientering velges automatisk** (kodet regel): kartet rammer inn **hele tettstedet** og
  zoomer ut så alle adresser får plass. **Stående er standard** (som plakat-eksemplene); kun
  tydelig brede steder (forhold ≥ ~1,55, f.eks. Alta) blir **liggende**, og en smal mellomsone
  tilbyr **begge**. Siden viser bare de(n) valgte orienteringen(e), alltid i standardrammer.
- **Kyst tas med:** for steder ved vann utvides innrammingen til den naturlige **kystlinja**
  rundt stedet, så plakaten viser hele fastlandslinja i stedet for en flat avkapping i vannet.
- Du trenger normalt ikke endre dette (overstyr ev. med `--formater`, `innramming`, eller en
  romsligere `--radius` for store kyst-/ribbe-byer der hele fjorden skal med — f.eks. Alta ~10).
- **Stil på tittelblokken** — `ren` (navn på krem-/bakgrunnsbånd nederst, standard) eller
  `boks` (navn i en ramme oppå kartet, som Osaka-eksemplet).

## Trinn 2 — Palett

Tre måter (i prioritert rekkefølge):

**A) Brukeren laster opp et palett-bilde.** Les bildet med synet ditt og hent ut fargene —
**dette fungerer også når hex-kodene ikke er skrevet på bildet** (les fargene direkte fra
flatene). Fordel fargene på rollene under. Bruk `references/palett-roller.md` som veiledning:

| Rolle | Hva det styrer | Tommelregel |
|---|---|---|
| `bakgrunn` | Land/papir | Lyseste farge (eller mørkeste for «invertert» stil) |
| `vann` | Sjø, innsjø, elver | En blå/grønn/teal — eller en kontrastfarge som i Osaka |
| `parker` | Parker, skog, grøntdrag | Dempet grønn, eller nær bakgrunn |
| `veier` | Alle gater | Sterk kontrast til bakgrunn (mørk på lys, lys på mørk) |
| `jernbane` | Jernbane (stiplet) | Som veier eller litt svakere |
| `ramme` | Rammestrek + boks | Mørk aksent |
| `tittel` | Stedsnavn + koordinater | Mørk/lesbar |
| `markor` | Hjerte/stjerne | En farge **fra palettet** som harmonerer med kartet — ikke en skrikende kontrast. Omrisset (bakgrunnsfargen) gir den nok definisjon. |

Vis brukeren forslaget ditt (hvilken farge ble hvilken rolle) og la dem justere.

**B) Ferdig preset.** Velg en fra `templates/palettes/`:
- `skandi-krem` — lys, rolig, sort-på-krem (Kyoto/Budapest-stil)
- `midnatt-bla` — mørk bakgrunn, lyse gater (New Haven-stil)
- `solnedgang` — krem med varmt oransje vann (Osaka-stil, `boks`-tittel)
- `rosa-hav` — rosa/blågrønn (fra et opplastet eksempel-palett)
- `snefokk` — Snefokk husstil (krem + lilla aksent, Newsreader-tittel)

Hver preset inneholder `palett`, `font` og `tittel_stil`. Kopier disse inn i config-en.

**C) Hex-koder.** Brukeren oppgir farger selv → fyll rollene direkte.

> **Font:** Preset-ene har en passende font (serif-tittel + sans brødtekst). Vil brukeren ha
> en annen, sett `font.url` (Google Fonts-URL), `font.family` og `font.tittel_family`.
> Skriften bygges automatisk inn i SVG/PNG ved nedlasting, så typografien blir riktig hos
> trykkeriet.

## Trinn 3 — Hent geometri

```bash
python3 scripts/fetch_osm.py --sted "Berlevåg, Norge" --radius 1.8 --output outputs/kart-arbeid/osm-data.json
```

- `--radius` (km) styrer hvor stort område som hentes. **Vær romslig — det må dekke HELE
  tettstedet** (kartet rammer inn bebyggelsen automatisk og bruker ikke mer enn det trengs).
  Start på ~2.5 km for et lite tettsted, 4–6 km for en større by (Alta ~6). Bygge-steget
  **advarer** hvis tettstedet ikke får plass — da øker du radius.
- Skriptet velger automatisk **tettsteds-punktet** (place=town/village), ikke kommune-
  grensen. Sjekk linjen `Lag: veier=…` i utskriften:
  - **veier=0 eller veldig lavt** → senterpunktet bommet, eller radius for liten. Prøv et
    mer spesifikt søk (`"Berlevåg, Finnmark"`) eller oppgi `--bbox sør,vest,nord,øst` direkte.
  - Mange tusen veier → fint, eventuelt øk radius for mer kontekst.
- Alternativt eksplisitt utsnitt: `--bbox 70.84,29.06,70.88,29.13`.

Geometrien grupperes i lag: vann (polygoner + linjer), kystlinje, parker, veier (per klasse)
og jernbane. Se `references/overpass-sporring.md`.

## Trinn 4 — (valgfritt) ferdigmarker en adresse

For en **hostet side hopper du over dette** — besøkende setter av sin egen adresse i siden.

Skal du lage en **ferdigmarkert gave-plakat**, finn koordinaten og bak den inn i config-en:

- **Nominatim** (rask, ingen nettleser):
  ```bash
  python3 -c "import urllib.request,urllib.parse,json; q=urllib.parse.urlencode({'q':'Storgata 1, Berlevåg','format':'json','limit':'1'}); r=json.load(urllib.request.urlopen(urllib.request.Request('https://nominatim.openstreetmap.org/search?'+q,headers={'User-Agent':'design-kart-dittsted'}))); print(r[0]['lat'], r[0]['lon']) if r else print('ikke funnet')"
  ```
- **Google Maps via Claude in Chrome** — for adresser Nominatim ikke finner.

Punktet må ligge **innenfor utsnittet** (bbox-en fra Trinn 3). Markøren har **ingen tekst** —
kun symbolet (hjerte eller stjerne).

## Trinn 5 — Bygg config.json

Lag en `config.json` (se full struktur i `CLAUDE.md`). Minimum (hostet side):

```json
{
  "sted": "Berlevåg",
  "undertittel": "Norge",
  "tittel_stil": "ren",
  "palett": { "...": "fra Trinn 2" },
  "font":   { "...": "fra Trinn 2" }
}
```

- **Markørfarge:** `palett.markor` må **harmonere** med kartet (en farge som hører til
  resten), ikke en skrikende aksent. For mørke/inverterte paletter funker krem/vei-fargen med
  det automatiske omrisset godt.
- **Ferdigmarkert gave:** legg til `"markor": { "type": "hjerte", "lat": …, "lng": … }`
  (ingen `label`). Flere: `"markorer": [ {…}, {…} ]`.
- **Format:** `"formater": ["3:4","5:7","7:10"]` er standard; endre bare ved behov.
- `fyll_hav` (standard `true`) fyller sjøen fra kystlinjen. Sett `false` for innlandssteder
  eller hvis havfyllet ser feil ut (sjelden — det har en innebygd fail-safe).
- `vei_skala` (standard `1.0`) skalerer alle strektykkelser. Tynt kart → 1.2–1.5; rotete →
  0.7–0.9.

## Trinn 6 — Bygg plakaten

```bash
python3 scripts/build_poster.py \
  --config outputs/kart-arbeid/config.json \
  --osm    outputs/kart-arbeid/osm-data.json \
  --template templates/poster_template.html \
  --output outputs/berlevag-plakat.html
```

## Trinn 7 — Visuell kontroll (ikke hopp over)

Åpne HTML-en i en nettleser og test:

- **Utsnitt** — er tettstedet sentrert og passe stort? Juster `--radius` i Trinn 3 og bygg om.
- **Strektykkelse** — er gatene for tynne/tjukke? Juster `vei_skala`.
- **Vann** — er sjøen fylt riktig? Øyer skal være land (ikke fylt). Hvis havet ser feil ut,
  prøv `fyll_hav: false` (da vises kystlinjen som strek).
- **Palett** — god kontrast mellom gater og bakgrunn? Lesbar tittel? **Markørfargen** må
  harmonere med kartet.
- **Adresse-input** — skriv inn en adresse i stedet → kommer hjertet/stjerna på rett sted?
- **Format-bytte** — bytt mellom 30×40, 50×70, 70×100 → fyller plakaten ramma, og følger
  markøren med?

Juster config/parametre og bygg om til det sitter.

## Trinn 8 — Lever / host

Siden er en **selvstendig statisk HTML-fil**. For et hostet plakat-produkt: legg fila på
`kart.snefokk.com/plakat/<sted>` (krever ingen server). Du kan ikke publisere til serveren fra
skillen — lever fila, så laster brukeren den opp dit.

Forklar besøker-flyten i siden:

- **Adresse** — skriv inn adressen → hjerte/stjerne settes av (bytt symbol med ♥/★).
- **Størrelse** — velg en vanlig rammestørrelse (30×40 … 140×200 cm); plakaten fyller ramma.
- **Last ned SVG** — vektor, skarpt i alle størrelser, skrift innebygd. **Beste fil til
  trykkeri** for stort trykk.
- **Last ned PNG** — valgt trykkstørrelse + DPI (150 for stort trykk, 300 for mindre). Veldig
  store mål skaleres ned med en advarsel — bruk SVG for full 2 m-størrelse.
- **Print / PDF** — for utskrift hjemme.

Trykkeri-tips finnes i `references/projeksjon-og-print.md`.

---

## Feilsøking

| Symptom | Årsak / løsning |
|---|---|
| `veier=0` ved fetch | Geokoding traff kommunegrense eller feil punkt. Søk mer spesifikt, eller bruk `--bbox`. |
| Overpass timeout (504) | Bbox/radius for stor. Reduser `--radius`. Skriptet prøver flere speil automatisk. |
| Sjøen er ikke fylt | Stedet mangler `natural=coastline` i OSM, eller fail-safe slo til. Bruk `fyll_hav:false`, eller aksepter kystlinje-strek. |
| Hele kartet ble «vann» | Fail-safe skal fange dette; hvis ikke, sett `fyll_hav:false`. |
| Tittelen i feil font | Sjekk at `font.url` er en gyldig Google Fonts-URL. Innbygging skjer ved nedlasting. |
| Kartet er rotete/tett | Senk `vei_skala`, eller reduser `--radius`. |
| Kartet er tomt/tynt | Øk `--radius`, eller sjekk at stedet finnes i OSM. |
| `ADVARSEL: hele tettstedet får ikke plass …` ved bygging | Tettstedet er større enn det hentede området (vanlig for store ribbe-byer som Alta, ~12 km). Hent et større område: øk `--radius` (5–6 km for Alta). Regelen velger uansett orientering som passer formen. |
| En adresse i utkanten kommer ikke med | Skjer kun hvis adressen ligger utenfor det hentede området. Øk `--radius`, eller sett `innramming: [s,w,n,e]` i config. Siden foreslår dessuten hvilken størrelse som inkluderer adressen. |

## Avgrensning

- Ingen bedrifts-/POI-verifisering (det er `by-kart-bygger` sitt domene).
- Ingen interaktiv web-versjon — dette er en ren plakat.
- Sjø-fyll krever `natural=coastline` i OSM; uten det vises kysten som strek.
