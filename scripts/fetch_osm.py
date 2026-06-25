#!/usr/bin/env python3
"""Hent vektorgeometri fra OpenStreetMap for et plakatkart.

Bruk:
    # Fra stedsnavn (slår opp senterpunkt via Nominatim, strammer bbox til tettstedet):
    python3 fetch_osm.py --sted "Berlevåg, Norge" --output osm-data.json

    # Med eksplisitt bbox (sør,vest,nord,øst):
    python3 fetch_osm.py --bbox 70.84,29.06,70.88,29.13 --output osm-data.json

    # Juster radius (km) rundt senterpunktet når du bruker --sted:
    python3 fetch_osm.py --sted "Berlevåg" --radius 2.0 --output osm-data.json

Skriver en JSON-fil med geometri gruppert i lag (water, coastline, parks,
roads-per-klasse, rail) + valgt bbox og senterpunkt. Mates videre til
build_poster.py. Kun Python stdlib — ingen `pip install`.
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "design-kart-dittsted/0.1 (https://snefokk.com/kart)"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Veiklasser vi tegner, fra mest til minst framtredende. Alt annet -> "other".
ROAD_CLASSES = [
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "unclassified", "living_street", "service",
    "pedestrian", "footway", "path", "track",
]
ROAD_CLASS_SET = set(ROAD_CLASSES)


def _get_json(url, data=None, timeout=90):
    headers = {"User-Agent": UA}
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# Foretrukne stedstyper, mest til minst spesifikk. Et `place`-punkt (selve
# tettstedet) er nesten alltid riktigere enn en `administrative` grense, hvis
# senterpunkt ofte er kommune-/fylkessentroide langt fra bebyggelsen.
PLACE_TYPES = ["city", "town", "village", "hamlet", "suburb", "locality", "municipality"]


def geocode(sted):
    """Stedsnavn -> (lat, lon, display_name). Bruker Nominatim.

    Foretrekker et `place`-punkt (by/tettsted/grend) framfor en
    `administrative` grense — sistnevnte gir kommunesentroiden, som for
    norske kommuner ofte ligger langt utenfor selve tettstedet."""
    q = {"q": sted, "format": "json", "limit": "10", "addressdetails": "1"}
    res = _get_json(NOMINATIM + "?" + urllib.parse.urlencode(q), timeout=30)
    if not res:
        raise SystemExit(f"Fant ikke stedet «{sted}» i Nominatim.")

    def score(r):
        is_place = r.get("class") == "place"
        typ = r.get("type", "")
        type_rank = PLACE_TYPES.index(typ) if typ in PLACE_TYPES else len(PLACE_TYPES)
        # Lavere er bedre: place-punkter først, så etter type-rang, så høyest importance.
        return (0 if is_place else 1, type_rank, -float(r.get("importance", 0)))

    r = sorted(res, key=score)[0]
    return float(r["lat"]), float(r["lon"]), r.get("display_name", sted)


def bbox_from_center(lat, lon, radius_km):
    """Kvadratisk bbox (sør,vest,nord,øst) ~radius_km fra senterpunktet.

    Justerer lengdegrad for breddegraden slik at boksen blir tilnærmet
    kvadratisk på bakken (viktig nær polene — f.eks. Finnmark)."""
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.01, math.cos(math.radians(lat))))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def overpass_query(s, w, n, e):
    """Overpass QL: hent veier, vann, kystlinje, parker, jernbane i bbox."""
    bb = f"({s},{w},{n},{e})"
    return f"""[out:json][timeout:120];
(
  way["highway"]{bb};
  way["natural"="water"]{bb};
  way["water"]{bb};
  way["waterway"~"river|stream|canal|riverbank"]{bb};
  way["natural"="coastline"]{bb};
  relation["natural"="water"]{bb};
  way["leisure"="park"]{bb};
  way["landuse"~"forest|grass|recreation_ground|meadow|cemetery"]{bb};
  way["leisure"~"garden|pitch|nature_reserve"]{bb};
  way["railway"~"rail|light_rail|tram|subway"]{bb};
);
out geom;"""


def fetch_overpass(s, w, n, e):
    ql = overpass_query(s, w, n, e)
    last_err = None
    for mirror in OVERPASS_MIRRORS:
        try:
            sys.stderr.write(f"  Overpass: spør {mirror.split('//')[1].split('/')[0]} …\n")
            return _get_json(mirror, data={"data": ql}, timeout=180)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as ex:
            last_err = ex
            sys.stderr.write(f"  … feilet ({ex}); prøver neste speil.\n")
            time.sleep(2)
    raise SystemExit(f"Alle Overpass-speil feilet. Siste feil: {last_err}")


def classify(elements):
    """Grupper Overpass-ways i lag. Returnerer dict med geometrilister.

    Hver geometri er en liste [[lat,lon], …]. Lagene:
      water_lines, water_polys, parks, coastline, rail,
      roads: {klasse: [geom, …]}
    """
    layers = {
        "water_polys": [],   # fylte vannflater (sjø/innsjø/elvebredde)
        "rivers": [],        # elver/kanaler — tegnes som BRED vann-stripe
        "water_lines": [],   # bekker o.l. — tynne streker
        "coastline": [],
        "parks": [],
        "rail": [],
        "roads": {c: [] for c in ROAD_CLASSES + ["other"]},
    }
    for el in elements:
        if el.get("type") != "way" or "geometry" not in el:
            continue
        geom = [[p["lat"], p["lon"]] for p in el["geometry"]]
        if len(geom) < 2:
            continue
        t = el.get("tags", {})
        closed = geom[0] == geom[-1] and len(geom) >= 4

        if t.get("highway"):
            hw = t["highway"]
            cls = hw if hw in ROAD_CLASS_SET else "other"
            layers["roads"][cls].append(geom)
        elif t.get("railway"):
            layers["rail"].append(geom)
        elif t.get("natural") == "coastline":
            layers["coastline"].append(geom)
        elif t.get("natural") == "water" or t.get("water"):
            (layers["water_polys"] if closed else layers["rivers"]).append(geom)
        elif t.get("waterway"):
            ww = t["waterway"]
            if ww == "riverbank" and closed:
                layers["water_polys"].append(geom)        # elveflate -> fylt
            elif ww in ("river", "canal"):
                layers["rivers"].append(geom)             # elv/kanal -> bred stripe
            else:
                layers["water_lines"].append(geom)        # bekk -> tynn strek
        elif t.get("leisure") in ("park", "garden", "pitch", "nature_reserve") \
                or t.get("landuse") in ("forest", "grass", "recreation_ground", "meadow", "cemetery"):
            if closed:
                layers["parks"].append(geom)
    return layers


def summarize(layers):
    roads = sum(len(v) for v in layers["roads"].values())
    return (
        f"veier={roads}, vann_poly={len(layers['water_polys'])}, "
        f"elver={len(layers['rivers'])}, "
        f"vann_linjer={len(layers['water_lines'])}, kystlinje={len(layers['coastline'])}, "
        f"parker={len(layers['parks'])}, jernbane={len(layers['rail'])}"
    )


def main():
    p = argparse.ArgumentParser(description="Hent OSM-vektorgeometri for et plakatkart.")
    p.add_argument("--sted", help="Stedsnavn, f.eks. \"Berlevåg, Norge\"")
    p.add_argument("--bbox", help="Eksplisitt bbox: sør,vest,nord,øst")
    p.add_argument("--radius", type=float, default=1.8,
                   help="Radius i km rundt senterpunktet (kun med --sted). Standard 1.8.")
    p.add_argument("--output", required=True, help="Sti til osm-data.json")
    args = p.parse_args()

    center = None
    display = None
    if args.bbox:
        try:
            s, w, n, e = (float(x) for x in args.bbox.split(","))
        except ValueError:
            raise SystemExit("--bbox må være fire tall: sør,vest,nord,øst")
        center = [(s + n) / 2, (w + e) / 2]
    elif args.sted:
        lat, lon, display = geocode(args.sted)
        sys.stderr.write(f"  Nominatim: {display}\n  senter = {lat:.5f}, {lon:.5f}, radius = {args.radius} km\n")
        s, w, n, e = bbox_from_center(lat, lon, args.radius)
        center = [lat, lon]
    else:
        raise SystemExit("Oppgi enten --sted eller --bbox.")

    raw = fetch_overpass(s, w, n, e)
    layers = classify(raw.get("elements", []))
    sys.stderr.write("  Lag: " + summarize(layers) + "\n")

    out = {
        "bbox": [s, w, n, e],
        "center": center,
        "display_name": display or args.sted or args.bbox,
        "radius_km": args.radius if args.sted else None,
        "layers": layers,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    sys.stderr.write(f"  Skrev {args.output}\n")


if __name__ == "__main__":
    main()
