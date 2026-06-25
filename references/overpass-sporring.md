# Overpass-spørring og lag-gruppering

`scripts/fetch_osm.py` henter vektorgeometri fra OpenStreetMap via **Overpass API** og
geokoder stedsnavn via **Nominatim**. Begge er gratis åpne API-er uten nøkkel.

## Geokoding (Nominatim)

`--sted "Berlevåg, Norge"` slår opp stedet. Skriptet ber om flere treff og **foretrekker et
`place`-punkt** (by/tettsted/grend) framfor en `administrative` grense. Dette er viktig: for
norske kommuner ligger grense-sentroiden ofte langt utenfor selve tettstedet (Vadsø-grensen
gir f.eks. 70.227, mens byen ligger på 70.074). Rekkefølgen er definert i `PLACE_TYPES`.

Rundt senterpunktet lages en tilnærmet kvadratisk bbox med `--radius` km, justert for
breddegrad (`bbox_from_center`) slik at boksen blir kvadratisk på bakken også nær polene.

## Overpass-spørringen

```
[out:json][timeout:120];
(
  way["highway"](bbox);
  way["natural"="water"](bbox);
  way["water"](bbox);
  way["waterway"~"river|stream|canal|riverbank"](bbox);
  way["natural"="coastline"](bbox);
  relation["natural"="water"](bbox);
  way["leisure"="park"](bbox);
  way["landuse"~"forest|grass|recreation_ground|meadow|cemetery"](bbox);
  way["leisure"~"garden|pitch|nature_reserve"](bbox);
  way["railway"~"rail|light_rail|tram|subway"](bbox);
);
out geom;
```

`out geom;` gir node-geometri direkte på hver way (ingen separat node-oppslag). Speil prøves i
rekkefølge (`OVERPASS_MIRRORS`): `overpass-api.de` → `overpass.kumi.systems` → maps.mail.ru.

## Lag-gruppering (`classify`)

Hver way sorteres til ett lag etter taggene sine:

| Lag | Fra | Tegnes som |
|---|---|---|
| `roads.<klasse>` | `highway=*` | Strek, tykkelse per klasse (`ROAD_CLASSES`) |
| `rail` | `railway=*` | Stiplet strek |
| `coastline` | `natural=coastline` | Strek + grunnlag for sjø-fyll |
| `water_polys` | lukket `natural=water` / `water=*` / `riverbank` | Fylt flate |
| `rivers` | `waterway=river`/`canal` (+ åpen `natural=water`) | **Bred** strek — samme vannfarge som sjøen, så elv og hav ser like ut |
| `water_lines` | bekker (`waterway=stream` o.l.) | Tynn strek |
| `parks` | lukket `leisure`/`landuse`-grønt | Fylt flate |

En way regnes som **lukket** (polygon) hvis første og siste punkt er like og den har ≥ 4
punkter. Veiklasser utenfor `ROAD_CLASSES` havner i `roads.other`.

## Tips

- **Timeout (504):** bbox/radius for stor → Overpass bruker for lang tid. Reduser `--radius`.
  En hel kommune-bbox er nesten alltid for stor; bruk tettsteds-radius.
- **For lite data (veier=0):** geokodingen bommet, eller radius for liten. Søk mer spesifikt,
  eller oppgi `--bbox` direkte.
- **Vær snill mot API-et:** ikke kjør mange tunge spørringer i tett rekkefølge; det er en
  delt gratistjeneste.
