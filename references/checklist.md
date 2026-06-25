# Sjekkliste — bygg en designplakat

Arbeidsfiler legges i brukerens workspace, f.eks. `outputs/kart-arbeid/`.

## 1. Ønske
- [ ] Sted bestemt (lite tettsted er helt fint)
- [ ] Hostet side (interaktiv adresse) eller ferdigmarkert gave?
- [ ] Tittel-stil (`ren`/`boks`). Format er standard `["3:4","5:7","7:10"]`

## 2. Palett
- [ ] Palett-bilde lest → roller fordelt, ELLER preset valgt, ELLER hex oppgitt
- [ ] Forslag vist til bruker (hvilken farge ble hvilken rolle)
- [ ] Kontroll: høy kontrast `veier` ↔ `bakgrunn`, lesbar `tittel`, poppy `markor`

## 3. Geometri
```bash
python3 scripts/fetch_osm.py --sted "<Sted>, Norge" --radius 1.8 --output outputs/kart-arbeid/osm-data.json
```
- [ ] `Lag: veier=…` har rikelig med veier (ikke 0)
- [ ] Riktig tettsted (ikke kommune-sentroide)

## 4. Adresse-punkt (kun ferdigmarkert gave — hopp over for hostet side)
- [ ] lat/lng funnet (Nominatim eller Google Maps)
- [ ] Punktet ligger innenfor bbox-en

## 5. config.json
- [ ] `sted`, `undertittel`, `tittel_stil`
- [ ] `palett` (8 roller, `markor` harmonerer) + `font` (url/family/tittel_family)
- [ ] valgfritt: `formater`, `markor`/`markorer` (gave), `fyll_hav`, `vei_skala`, `veibredder`

## 6. Bygg
```bash
python3 scripts/build_poster.py \
  --config outputs/kart-arbeid/config.json \
  --osm    outputs/kart-arbeid/osm-data.json \
  --template templates/poster_template.html \
  --output outputs/<sted>-plakat.html
```

## 7. Visuell kontroll (åpne i nettleser)
- [ ] Utsnitt sentrert og passe stort (juster `--radius`)
- [ ] Strektykkelse god (juster `vei_skala`)
- [ ] Vann fylt riktig, øyer som land (ev. `fyll_hav:false`)
- [ ] Markørfarge harmonerer; symbol uten tekst
- [ ] Adresse-input plasserer markør riktig
- [ ] Format-bytte (30×40 / 50×70 / 70×100) fyller ramma, markør følger med
- [ ] Tittel og koordinater lesbare

## 8. Lever / host
- [ ] Legg HTML-en på `kart.snefokk.com/plakat/<sted>`
- [ ] Forklar SVG (trykkeri), PNG (størrelse + DPI), Print/PDF; SVG for trykk > ~70 cm
