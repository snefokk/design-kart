#!/usr/bin/env python3
"""Bygg en stilisert SVG-plakat (HTML) fra en config og OSM-geometri.

Bruk:
    python3 build_poster.py \\
        --config config.json \\
        --osm osm-data.json \\
        --template templates/poster_template.html \\
        --output outputs/vadso-plakat.html

Projiserer OSM-geometri (Web Mercator) til SVG-koordinater croppet til
papir-ratio, tegner lagene (vann, parker, kystlinje, veier, jernbane, markør)
i palett-fargene, og fyller plakat-malen via token-erstatning. SVG-en er
oppløsningsuavhengig — kan trykkes opp til 2 m × 2 m. Kun Python stdlib.
"""

import argparse
import json
import math
import sys
from pathlib import Path

# ---- Standardverdier --------------------------------------------------------

DEFAULT_PALETTE = {
    "bakgrunn": "#F4F1E8", "vann": "#9CC3C1", "parker": "#CFE0CF",
    "veier": "#2C2C2C", "jernbane": "#2C2C2C", "ramme": "#2C2C2C",
    "tittel": "#1A1A1A", "markor": "#C0473F",
}
DEFAULT_ROAD_W = {
    "motorway": 3.2, "trunk": 3.0, "primary": 2.6, "secondary": 2.0,
    "tertiary": 1.6, "residential": 1.0, "unclassified": 1.0,
    "living_street": 0.9, "service": 0.6, "pedestrian": 0.7,
    "footway": 0.4, "path": 0.4, "track": 0.5, "other": 0.8,
}
# Tegnerekkefølge på veier: minst framtredende først (havner nederst).
ROAD_DRAW_ORDER = [
    "footway", "path", "track", "service", "pedestrian", "living_street",
    "unclassified", "residential", "tertiary", "secondary", "primary",
    "trunk", "motorway", "other",
]

RATIOS = {  # ratio -> (bredde_enheter, høyde_enheter)
    # stående
    "2:3": (1000, 1500), "3:4": (1000, 1333), "5:7": (1000, 1400),
    "7:10": (1000, 1429), "1:1": (1000, 1000), "iso": (1000, 1414),
    # liggende (samme tall, byttet om)
    "3:2": (1500, 1000), "4:3": (1333, 1000), "7:5": (1400, 1000),
    "10:7": (1429, 1000),
}

# Markør-paths i en 24×24-boks, symmetriske om x=12, skaleres senere.
MARKERS = {
    # Klassisk symmetrisk hjerte (Material-stil)
    "hjerte": "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3"
              "c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5"
              "c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
    # Symmetrisk femtakket stjerne
    "stjerne": "M12 2l2.94 5.96 6.58.96-4.76 4.64 1.12 6.55L12 17.77l-5.88 3.09"
               "1.12-6.55-4.76-4.64 6.58-.96L12 2z",
    "prikk": "M12 4a8 8 0 1 0 0.001 0z",
}
# Vertikalt ankerpunkt (y i 24-boksen) der markøren "peker" på stedet.
MARKER_ANCHOR = {"hjerte": 21.35, "stjerne": 12.0, "prikk": 12.0}


# ---- Projeksjon -------------------------------------------------------------

def merc_x(lon):
    return math.radians(lon)


def merc_y(lat):
    lat = max(-85.05, min(85.05, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def dms(value, pos, neg):
    hemi = pos if value >= 0 else neg
    v = abs(value)
    d = int(v)
    m_full = (v - d) * 60
    m = int(m_full)
    s = int(round((m_full - m) * 60))
    if s == 60:
        s = 0
        m += 1
    return f"{d}°{m:02d}'{s:02d}\" {hemi}"


class Projector:
    """Projiserer (lat, lon) -> SVG-koordinat innenfor kart-rekt, croppet til
    kart-rektets bredde/høyde-forhold (ingen forvrengning)."""

    def __init__(self, bbox, map_x, map_y, map_w, map_h, content=None, pad=0.11):
        # `bbox` = hentede data (sør,vest,nord,øst). `content` = boksen vi vil
        # ramme inn (selve tettstedet, fra veinettet); None => hele bbox. Vi
        # zoomer slik at content får plass (contain, m/marg), sentrert, og klemmer
        # så vinduet aldri går utenfor de hentede dataene. Slik vises HELE
        # tettstedet — også adresser i utkanten — så langt fetch-en rekker.
        s, w, n, e = bbox
        bx0, bx1 = merc_x(w), merc_x(e)
        by0, by1 = merc_y(s), merc_y(n)
        if content is not None:
            cs, cw, cn, ce = content
            cx0, cx1 = merc_x(cw), merc_x(ce)
            cy0, cy1 = merc_y(cs), merc_y(cn)
        else:
            cx0, cx1, cy0, cy1 = bx0, bx1, by0, by1
        cont_w = max(cx1 - cx0, 1e-9)
        cont_h = max(cy1 - cy0, 1e-9)
        ccx, ccy = (cx0 + cx1) / 2, (cy0 + cy1) / 2

        avail_w, avail_h = bx1 - bx0, by1 - by0
        scale_fit = min(map_w / cont_w, map_h / cont_h) * (1 - pad)
        scale_min = max(map_w / avail_w, map_h / avail_h)  # ikke zoom ut forbi data
        scale = max(scale_fit, scale_min)
        # Klamret => dataene rakk ikke å gi marg rundt tettstedet. Vi advarer
        # først når det beskjæres merkbart (>12 %, dvs. selve bebyggelsen kuttes,
        # ikke bare luftmarginen). Da trengs et større fetch-område.
        self.clamped = scale_min > scale_fit * 1.12

        win_w, win_h = map_w / scale, map_h / scale
        cx = min(max(ccx, bx0 + win_w / 2), bx1 - win_w / 2)
        cy = min(max(ccy, by0 + win_h / 2), by1 - win_h / 2)

        self.mx0 = cx - win_w / 2
        self.myt = cy + win_h / 2
        self.scale = scale
        self.map_x, self.map_y = map_x, map_y

    def __call__(self, lat, lon):
        return self.proj_xy(merc_x(lon), merc_y(lat))

    def proj_xy(self, X, Y):
        """Projiser et mercator-up-punkt (X, Y) direkte til SVG-koordinat."""
        x = (X - self.mx0) * self.scale + self.map_x
        y = (self.myt - Y) * self.scale + self.map_y
        return x, y


# ---- Sjø-fyll fra kystlinje -------------------------------------------------
# OSM-kystlinjer er retningsbestemte: land til venstre, vann til høyre. Vi
# lukker kystlinje-kjedene mot kart-rektangelet for å fylle sjøen. Web Mercator
# bevarer orientering (nord opp), så høyre-regelen holder i mercator-up-rommet.
# Fail-safe: hvis noe blir degenerert, hopper vi over fyllet og beholder streken.

def _liang_barsky(a, b, x0, y0, x1, y1):
    """Klipp segmentet a->b til rektangelet. Returnerer (a2, b2) eller None."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    p = [-dx, dx, -dy, dy]
    q = [ax - x0, x1 - ax, ay - y0, y1 - ay]
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-15:
            if qi < 0:
                return None
        else:
            r = qi / pi
            if pi < 0:
                if r > t1:
                    return None
                if r > t0:
                    t0 = r
            else:
                if r < t0:
                    return None
                if r < t1:
                    t1 = r
    return ((ax + t0 * dx, ay + t0 * dy), (ax + t1 * dx, ay + t1 * dy))


def _clip_runs(pts, win):
    """Klipp en polyline til vinduet. Returner liste av sammenhengende biter."""
    x0, y0, x1, y1 = win
    runs, cur = [], []

    def close(p, q):
        return abs(p[0] - q[0]) < 1e-9 and abs(p[1] - q[1]) < 1e-9

    for i in range(len(pts) - 1):
        seg = _liang_barsky(pts[i], pts[i + 1], x0, y0, x1, y1)
        if seg is None:
            if cur:
                runs.append(cur)
                cur = []
            continue
        a2, b2 = seg
        if not cur:
            cur = [a2, b2]
        elif close(cur[-1], a2):
            cur.append(b2)
        else:
            runs.append(cur)
            cur = [a2, b2]
    if cur:
        runs.append(cur)
    return runs


def _boundary_t(pt, win):
    """Posisjon (0..4) på rektangelets omkrets (CCW), eller None hvis innenfor."""
    x, y = pt
    x0, y0, x1, y1 = win
    tx = (x1 - x0) * 1e-6
    ty = (y1 - y0) * 1e-6
    if abs(y - y0) <= ty:
        return (x - x0) / (x1 - x0)                # bunn [0,1)
    if abs(x - x1) <= tx:
        return 1 + (y - y0) / (y1 - y0)            # høyre [1,2)
    if abs(y - y1) <= ty:
        return 2 + (x1 - x) / (x1 - x0)            # topp [2,3)
    if abs(x - x0) <= tx:
        return 3 + (y1 - y) / (y1 - y0)            # venstre [3,4)
    return None


def _corner_xy(t, win):
    x0, y0, x1, y1 = win
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return corners[int(t) % 4]


def _walk_boundary(t_from, t_to, win):
    """Hjørnepunkter mellom t_from og t_to, gående med klokka (synkende t mod 4)."""
    pts = []
    t = t_from
    guard = 0
    # gå nedover til vi passerer t_to
    target = t_to if t_to < t_from else t_to - 4
    c = math.floor(t_from)
    while c > target and guard < 12:
        pts.append(_corner_xy(c % 4, win))
        c -= 1
        guard += 1
    return pts


def _stitch(lines):
    """Slå sammen kystlinje-segmenter som deler endepunkt, til lange kjeder.
    Kun retningsbevarende skjøting (ingen reversering) — bevarer land-venstre/
    vann-høyre-invarianten fra OSM."""
    segs = [list(l) for l in lines if len(l) >= 2]

    def k(p):
        return (round(p[0], 9), round(p[1], 9))

    starts = {}
    for i, s in enumerate(segs):
        starts.setdefault(k(s[0]), []).append(i)
    ends = {}
    for i, s in enumerate(segs):
        ends.setdefault(k(s[-1]), []).append(i)

    used = [False] * len(segs)
    chains = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        chain = list(segs[i])
        ext = True
        while ext:                                  # forleng forover
            ext = False
            for j in starts.get(k(chain[-1]), []):
                if not used[j]:
                    chain.extend(segs[j][1:])
                    used[j] = True
                    ext = True
                    break
        ext = True
        while ext:                                  # forleng bakover
            ext = False
            for j in ends.get(k(chain[0]), []):
                if not used[j]:
                    chain[:0] = segs[j][:-1]
                    used[j] = True
                    ext = True
                    break
        chains.append(chain)
    return chains


def assemble_sea(coastlines, win):
    """coastlines: liste av mercator-up polylines. Returner liste av sjø-ringer."""
    chains = []
    for pts in _stitch(coastlines):
        for run in _clip_runs(pts, win):
            if len(run) < 2:
                continue
            ts = _boundary_t(run[0], win)
            te = _boundary_t(run[-1], win)
            if ts is None or te is None:
                continue  # dinglende ende (kuttet utenfor vindu) — hopp over
            chains.append({"ts": ts, "te": te, "pts": run})
    if not chains:
        return []

    def next_clockwise(t):
        # første kjede-start vi møter når vi går med klokka (synkende t)
        best, bestd = None, 1e9
        for j, ch in enumerate(chains):
            d = (t - ch["ts"]) % 4
            if d < 1e-9:
                d += 4
            if d < bestd:
                bestd, best = d, j
        return best

    rings, used = [], set()
    for i0 in range(len(chains)):
        if i0 in used:
            continue
        ring, i, guard = [], i0, 0
        while guard < len(chains) * 2 + 6:
            guard += 1
            used.add(i)
            ch = chains[i]
            ring.extend(ch["pts"])
            ring.extend(_walk_boundary(ch["te"], chains[(nxt := next_clockwise(ch["te"]))]["ts"], win))
            i = nxt
            if i == i0:
                break
        if len(ring) >= 3:
            rings.append(ring)
    return rings


# ---- SVG-bygging ------------------------------------------------------------

def _rdp(pts, eps):
    """Douglas–Peucker-forenkling i SVG-enheter. Fjerner punkter som ligger
    nærmere enn `eps` til linja — kutter overflødige noder på lange veier uten
    synlig endring (eps er under-piksel ved print). Iterativ (ingen rekursjon)."""
    n = len(pts)
    if n < 3 or eps <= 0:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        x1, y1 = pts[a]
        x2, y2 = pts[b]
        dx, dy = x2 - x1, y2 - y1
        dd = math.hypot(dx, dy) or 1e-9
        dmax, idx = eps, 0
        for i in range(a + 1, b):
            x0, y0 = pts[i]
            d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / dd
            if d > dmax:
                dmax, idx = d, i
        if idx:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [pts[i] for i in range(n) if keep[i]]


def path_d(geom, proj, close=False, eps=0.7):
    pts = [proj(lat, lon) for lat, lon in geom]
    if len(pts) > 2:
        pts = _rdp(pts, eps)
    if not pts:
        return ""
    d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    if close:
        d += "Z"
    return d


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Turstier (ikke gater) — utelates fra bebyggelses-deteksjon, ellers «vokser»
# tettstedet langs skogsstier ut i marka (Bymarka osv.).
TRAIL_CLASSES = {"footway", "path", "track"}


def _road_points(layers, skip_trails=True):
    pts = []
    for cls, glist in layers.get("roads", {}).items():
        if skip_trails and cls in TRAIL_CLASSES:
            continue
        for geom in glist:
            pts.extend(geom)
    return pts


def street_centroid(layers):
    """Gate-tyngdepunkt (median lat/lon, uten stier) — der bebyggelsen faktisk
    ligger. Brukes til å sentrere utsnittet, i stedet for det administrative
    punktet som ofte ligger i utkanten (Trondheim: ved fjorden, ~3 km nord for
    tyngdepunktet). None hvis tomt."""
    pts = _road_points(layers, skip_trails=True)
    if not pts:
        return None
    lats = sorted(p[0] for p in pts)
    lons = sorted(p[1] for p in pts)
    return (lats[len(lats) // 2], lons[len(lons) // 2])


def town_extent(layers, center=None, cell_m=150.0, thresh=8, bridge=1, max_km=10.0):
    """Ytterpunkt-boks (sør,vest,nord,øst) for HELE den sammenhengende
    bebyggelsen, fra veinettet — STABIL uansett hvor stort område som er hentet.

    Metode: legg vei-punktene i et rutenett (~cell_m meter). «Bebygde» ruter er
    de med minst `thresh` punkter (tette gatenett), i motsetning til rurale veier
    som bare streifer en rute. Flomfyll fra senter over bebygde ruter (med inntil
    `bridge` tomme ruter som bro over parker/elver), og ta boksen rundt klyngen.
    Dropper dermed spredt rural bebyggelse og lange veier ut av tettstedet, men
    beholder utkant-strøk som henger sammen med stedet."""
    pts = _road_points(layers)
    if not pts:
        return None
    clat = center[0] if center else sum(p[0] for p in pts) / len(pts)
    dlat = cell_m / 111000.0
    dlon = cell_m / (111000.0 * max(0.05, math.cos(math.radians(clat))))

    counts = {}
    for la, lo in pts:
        c = (int(la / dlat), int(lo / dlon))
        counts[c] = counts.get(c, 0) + 1
    built = {c for c, k in counts.items() if k >= thresh}
    if not built:
        built = set(counts)

    if center:
        seed = (int(center[0] / dlat), int(center[1] / dlon))
        if seed not in built:
            seed = min(built, key=lambda c: (c[0] - seed[0]) ** 2 + (c[1] - seed[1]) ** 2)
    else:
        seed = max(built, key=lambda c: counts[c])

    seen = {seed}
    stack = [seed]
    rng = range(-(1 + bridge), 2 + bridge)   # alltid 8-naboer; bridge = ekstra tomme ruter
    while stack:
        cy, cx = stack.pop()
        for ddy in rng:
            for ddx in rng:
                nc = (cy + ddy, cx + ddx)
                if nc in built and nc not in seen:
                    seen.add(nc)
                    stack.append(nc)

    lats, lons = [], []
    for la, lo in pts:
        if (int(la / dlat), int(lo / dlon)) in seen:
            lats.append(la)
            lons.append(lo)
    if not lats:
        return None
    # Lett trim (1–99 %) av klynge-punktene, så enkelte dalstrøk/spisser ikke
    # blåser opp boksen — selve den bebodde kjernen rammes inn.
    lats.sort()
    lons.sort()

    def pct(v, q):
        return v[min(len(v) - 1, max(0, int(len(v) * q)))]

    box = (pct(lats, 0.01), pct(lons, 0.01), pct(lats, 0.99), pct(lons, 0.99))
    # Øvre grense: store, grenseløse byer (Trondheim/Alta sprer seg i det
    # uendelige) kappes til maks `max_km` per akse, sentrert på stedssenteret,
    # så plakaten viser kjernen pent. Små steder er under grensa, uendret.
    return cap_box(box, center, max_km)


def cap_box(box, center, max_km):
    """Kapp en boks til maks `max_km` per akse, sentrert på `center` (lat,lon),
    men hold vinduet innenfor den opprinnelige boksen. max_km=None => ingen kapp."""
    if not box or not max_km:
        return box
    s, w, n, e = box
    clat = center[0] if center else (s + n) / 2
    clon = center[1] if center else (w + e) / 2
    half_lat = (max_km / 111.0) / 2
    half_lon = (max_km / (111.0 * max(0.05, math.cos(math.radians(clat))))) / 2

    def cap(lo, hi, c, half):
        if hi - lo <= 2 * half:
            return lo, hi
        c = min(max(c, lo + half), hi - half)
        return c - half, c + half

    s, n = cap(s, n, clat, half_lat)
    w, e = cap(w, e, clon, half_lon)
    return (s, w, n, e)


def content_extent(layers, road_box, kyst_margin=0.35):
    """Utvid tettsted-boksen til å ta med den NATURLIGE kystlinja rundt stedet,
    så kartet viser hele fastlandslinja i stedet for en flat avkapping midt i
    vannet. Tar bare med kyst/vann innenfor `kyst_margin` × tettstedets størrelse
    utenfor boksen — altså den lokale stranda, ikke åpent hav langt unna."""
    if not road_box:
        return road_box
    s, w, n, e = road_box
    dh, dw = (n - s) * kyst_margin, (e - w) * kyst_margin
    rs, rw, rn, re = s - dh, w - dw, n + dh, e + dw   # søkeområde for kyst
    cs, cw, cn, ce = s, w, n, e
    for g in layers.get("coastline", []) + layers.get("water_polys", []):
        for la, lo in g:
            if rs <= la <= rn and rw <= lo <= re:
                cs = min(cs, la); cw = min(cw, lo)
                cn = max(cn, la); ce = max(ce, lo)
    return (cs, cw, cn, ce)


def add_sea_margin(box, layers, bbox, lat, sea_km=1.3, band_km=0.6):
    """Når en kant av innrammingen ligger ved kystlinje (byen møter vannet),
    skyv kanten UT i det åpne vannet (~sea_km) så strandlinja vises og
    bebyggelsen ikke ligger klemt mot rammekanten. Åpent hav har ofte ingen
    egne punkter (bare kystlinje), så vi kan ikke bare utvide til vann-punkter —
    vi legger til en fast vann-marg der det er kyst, begrenset til hentede data."""
    s, w, n, e = box
    coast = layers.get("coastline", [])
    if not coast:
        return box
    band_lat = band_km / 111.0
    band_lon = band_km / (111.0 * max(0.05, math.cos(math.radians(lat))))
    near_n = near_s = near_e = near_w = False
    for g in coast:
        for la, lo in g:
            if not (s <= la <= n and w <= lo <= e):
                continue
            if la >= n - band_lat:
                near_n = True
            if la <= s + band_lat:
                near_s = True
            if lo >= e - band_lon:
                near_e = True
            if lo <= w + band_lon:
                near_w = True
    d_lat = sea_km / 111.0
    d_lon = sea_km / (111.0 * max(0.05, math.cos(math.radians(lat))))
    if near_n:
        n = min(bbox[2], n + d_lat)
    if near_s:
        s = max(bbox[0], s - d_lat)
    if near_e:
        e = min(bbox[3], e + d_lon)
    if near_w:
        w = max(bbox[1], w - d_lon)
    return (s, w, n, e)


def town_aspect(bounds, lat):
    """Bredde/høyde-forhold på bakken for ytterpunkt-boksen (>1 = langstrakt
    øst–vest → liggende; <1 = nord–sør → stående). Justerer lengdegrad for
    breddegraden, så avstandene blir riktige på bakken (viktig nær polene)."""
    if not bounds:
        return 1.0
    s, w, n, e = bounds
    width_km = (e - w) * math.cos(math.radians(lat)) * 111.0
    height_km = (n - s) * 111.0
    return width_km / height_km if height_km > 1e-6 else 1.0


# Terskler for orienterings-regelen (tettstedets bredde/høyde på bakken).
# Plakat-konvensjonen (og alle referanse-eksemplene) er PORTRETT — så vi
# foretrekker stående og bruker liggende kun for tydelig brede steder. En smal
# «begge»-sone like under liggende-terskelen fanger de virkelig tvetydige.
LIGGENDE_TERSKEL = 1.55   # ≥ dette = liggende (f.eks. Alta ~1,67)
BEGGE_TERSKEL = 1.42      # [BEGGE, LIGGENDE) = tilby begge; under = stående

LIGGENDE_FORMATS = ["4:3", "7:5", "10:7"]
STAENDE_FORMATS = ["3:4", "5:7", "7:10"]


def velg_orienteringer(aspect):
    """Returnerer (formatliste, anbefalt) ut fra tettstedets bredde/høyde.
    anbefalt ∈ {"liggende","staaende","begge"}. Stående er standard."""
    if aspect >= LIGGENDE_TERSKEL:
        return LIGGENDE_FORMATS, "liggende"
    if aspect >= BEGGE_TERSKEL:
        return STAENDE_FORMATS + LIGGENDE_FORMATS, "begge"
    return STAENDE_FORMATS, "staaende"


def crop_to_aspect(box, target_ar):
    """Beskjær boksen til formatets bredde/høyde-forhold (sentrert), så kartet
    FYLLER rammen i stedet for å la store marger (f.eks. mye sjø) stå igjen.
    Brukes for store byer i et format som ikke matcher byformen."""
    if not box:
        return box
    s, w, n, e = box
    lat = (s + n) / 2
    wkm = (e - w) * math.cos(math.radians(lat)) * 111
    hkm = (n - s) * 111
    if hkm <= 0 or wkm <= 0:
        return box
    cx, cy = (w + e) / 2, (s + n) / 2
    if wkm / hkm > target_ar:                       # for bred -> beskjær bredde
        half = (target_ar * hkm) / (111.0 * max(0.05, math.cos(math.radians(lat)))) / 2
        w, e = cx - half, cx + half
    else:                                           # for høy -> beskjær høyde
        half = (wkm / target_ar) / 111.0 / 2
        s, n = cy - half, cy + half
    return (s, w, n, e)


def clip_roads_to(layers, box, margin=0.35):
    """Behold bare veier som berører tettsted-boksen + margin. Lar en romslig
    fetch (nok til å få med hele byen) slippe å blåse opp SVG-en med rurale
    veier vi aldri viser. Endrer ikke vann/kystlinje/parker (mindre, og
    kystlinjen trengs hel for sjø-fyll)."""
    if not box:
        return layers
    s, w, n, e = box
    dh, dw = (n - s) * margin, (e - w) * margin
    s, w, n, e = s - dh, w - dw, n + dh, e + dw

    def touches(geom):
        return any(s <= la <= n and w <= lo <= e for la, lo in geom)

    roads = {cls: [g for g in glist if touches(g)]
             for cls, glist in layers.get("roads", {}).items()}
    out = dict(layers)
    out["roads"] = roads
    return out


# Veidetalj-nivåer: hvilke klasser som DROPPES. Mindre detalj = renere storby.
DETALJ_DROPP = {
    "alle": set(),
    "uten_service": {"service"},
    "uten_smaa": {"service", "living_street", "pedestrian"},
    "hovedveier": {"service", "living_street", "pedestrian", "unclassified", "residential"},
}


def veiklasser_a_droppe(config, content):
    """Hvilke veiklasser skal IKKE tegnes. Eksplisitt `dropp_veiklasser` eller
    `veidetalj`-nivå overstyrer; ellers settes nivået automatisk etter hvor stort
    utsnittet er — store byer mister de minste veiene så kartet ikke blir grøtete."""
    if config.get("dropp_veiklasser") is not None:
        return set(config["dropp_veiklasser"])
    if config.get("veidetalj"):
        return set(DETALJ_DROPP.get(config["veidetalj"], set()))
    if not content:
        return set()
    s, w, n, e = content
    lat = (s + n) / 2
    vkm = max((e - w) * math.cos(math.radians(lat)) * 111, (n - s) * 111)
    if vkm > 13:
        return {"service", "living_street", "pedestrian"}
    if vkm > 8:
        return {"service"}
    return set()


def marker_svg(typ, mx, my, size, fill, outline):
    """SVG-gruppe for en markør, ankret slik at "spissen" peker på (mx, my)."""
    path = MARKERS.get(typ, MARKERS["hjerte"])
    anchor = MARKER_ANCHOR.get(typ, 12.0)
    sc = size / 24.0
    tx = mx - 12 * sc
    ty = my - anchor * sc
    ow = max(0.8, size * 0.05)
    return (f'<g transform="translate({tx:.2f},{ty:.2f}) scale({sc:.4f})">'
            f'<path d="{path}" fill="{fill}" stroke="{outline}" '
            f'stroke-width="{ow / sc:.2f}" stroke-linejoin="round"/></g>')


def _stroke_group(paths, color, width, extra=""):
    if not paths:
        return ""
    body = "".join(f'<path d="{d}"/>' for d in paths)
    return (f'<g fill="none" stroke="{color}" stroke-width="{width:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round" {extra}>{body}</g>')


def build_svg(config, osm, ratio_override=None, content_box=None, town_box=None,
              fyll_ramme=False):
    pal = dict(DEFAULT_PALETTE)
    pal.update(config.get("palett", {}))
    road_w = dict(DEFAULT_ROAD_W)
    road_w.update(config.get("veibredder", {}))

    # Lokale fargevariabler (unngår subscript med anførselstegn i f-strenger)
    c_bg = pal["bakgrunn"]
    c_water = pal["vann"]
    c_park = pal["parker"]
    c_road = pal["veier"]
    c_rail = pal["jernbane"]
    c_frame = pal["ramme"]
    c_title = pal["tittel"]
    c_marker = pal["markor"]
    fam = config.get("font", {}).get("family", "system-ui, sans-serif")
    tfam = config.get("font", {}).get("tittel_family", "serif")

    papir = config.get("papir", {})
    ratio = ratio_override or papir.get("ratio", "2:3")
    W, H = RATIOS.get(ratio, RATIOS["2:3"])
    if papir.get("orientering") == "landscape":
        W, H = H, W
    uid = "p" + ratio.replace(":", "_")  # unik id-suffiks per format

    layout = config.get("tittel_stil", "moderne")  # "moderne" | "ren" | "boks" | "ingen"

    margin = round(W * 0.055)
    fx, fy = margin, margin
    fw, fh = W - 2 * margin, H - 2 * margin

    if layout == "moderne":
        # Full-bleed: kartet fyller HELE plakaten, tittel legges oppå nederst.
        map_x, map_y, map_w, map_h = 0, 0, W, H
    elif layout == "ren":
        title_band = round(H * 0.13)
        map_x, map_y = fx + margin * 0.5, fy + margin * 0.5
        map_w = fw - margin
        map_h = fh - margin - title_band
    else:  # "boks" / "ingen": kartet fyller hele rammen
        map_x, map_y = fx + margin * 0.5, fy + margin * 0.5
        map_w, map_h = fw - margin, fh - margin

    layers = osm["layers"]
    # Ramme inn hele tettstedet. `content_box` sendes inn fra main (beregnet én
    # gang); fall tilbake til config-overstyring eller densitets-extent her.
    content = content_box or config.get("innramming") or town_extent(layers, osm.get("center"))
    if fyll_ramme:                # store byer: fyll rammen i stedet for sjø-marger
        content = crop_to_aspect(content, map_w / map_h)
    proj = Projector(osm["bbox"], map_x, map_y, map_w, map_h, content=content)
    rs = (W / 1000.0) * float(config.get("vei_skala", 1.0))  # strek-skala

    p = []
    p.append(f'<svg class="poster-svg" data-ratio="{ratio}" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{esc(fam)}">')
    grad = (f'<linearGradient id="scrim-{uid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{c_bg}" stop-opacity="0"/>'
            f'<stop offset="0.55" stop-color="{c_bg}" stop-opacity="0.55"/>'
            f'<stop offset="1" stop-color="{c_bg}" stop-opacity="0.92"/>'
            f'</linearGradient>') if layout == "moderne" else ""
    p.append(f'<defs>{grad}<clipPath id="mapclip-{uid}"><rect x="{map_x:.1f}" y="{map_y:.1f}" '
             f'width="{map_w:.1f}" height="{map_h:.1f}"/></clipPath></defs>')

    # Plakatbakgrunn
    p.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{c_bg}"/>')

    # ---- Kartlag (klippet) ----
    p.append(f'<g clip-path="url(#mapclip-{uid})">')
    p.append(f'<rect x="{map_x:.1f}" y="{map_y:.1f}" width="{map_w:.1f}" '
             f'height="{map_h:.1f}" fill="{c_bg}"/>')

    # Sjø-fyll fra kystlinje (fail-safe). Lukker kystlinje-kjedene mot det fulle
    # (ukroppede) mercator-vinduet; SVG-clip skjuler overflødig.
    if config.get("fyll_hav", True) and layers.get("coastline"):
        s, w_, n, e = osm["bbox"]
        win = (merc_x(w_), merc_y(s), merc_x(e), merc_y(n))
        coast_merc = [[(merc_x(lon), merc_y(lat)) for lat, lon in g]
                      for g in layers["coastline"]]
        rings = assemble_sea(coast_merc, win)
        win_area = abs((win[2] - win[0]) * (win[3] - win[1]))

        def _area(ring):
            a = 0.0
            for i in range(len(ring)):
                x1_, y1_ = ring[i]
                x2_, y2_ = ring[(i + 1) % len(ring)]
                a += x1_ * y2_ - x2_ * y1_
            return abs(a) / 2

        total = sum(_area(r) for r in rings)
        frac = total / win_area if win_area else 0
        # Fail-safe: tomt, eller flommet hele kartet (sannsynlig feil retning)
        if rings and 0.001 < frac < 0.985:
            for ring in rings:
                pts = [proj.proj_xy(X, Y) for X, Y in ring]
                d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"
                p.append(f'<path d="{d}" fill="{c_water}" stroke="none"/>')
        else:
            sys.stderr.write(f"  (sjø-fyll hoppet over: frac={frac:.3f}, ringer={len(rings)})\n")

    # Vann-polygoner (fyll)
    for g in layers.get("water_polys", []):
        d = path_d(g, proj, close=True)
        if d:
            p.append(f'<path d="{d}" fill="{c_water}" stroke="none"/>')
    # Parker (fyll)
    for g in layers.get("parks", []):
        d = path_d(g, proj, close=True)
        if d:
            p.append(f'<path d="{d}" fill="{c_park}" stroke="none"/>')
    # Elver/kanaler — BRED vann-stripe i samme farge som sjøen (så elv og hav
    # ser like ut). Tegnes oppå parker.
    rv = [path_d(g, proj) for g in layers.get("rivers", [])]
    p.append(_stroke_group([d for d in rv if d], c_water, 5.5 * rs))
    # Bekker o.l. — tynne streker
    wl = [path_d(g, proj) for g in layers.get("water_lines", [])]
    p.append(_stroke_group([d for d in wl if d], c_water, 1.4 * rs))
    # Kystlinje (tydeligere strek)
    cl = [path_d(g, proj) for g in layers.get("coastline", [])]
    p.append(_stroke_group([d for d in cl if d], c_water, 2.4 * rs))

    # Veier — per klasse, minst framtredende først. Stier (footway/path/track)
    # er turstier, ikke gater — de roter til plakaten og er ofte 50 %+ av
    # punktene i skog-rike byer. Dropp dem som standard (config.vis_stier=true
    # for å ta dem med).
    roads = layers.get("roads", {})
    vis_stier = config.get("vis_stier", False)
    drop = veiklasser_a_droppe(config, content)
    for cls in ROAD_DRAW_ORDER:
        if cls in TRAIL_CLASSES and not vis_stier:
            continue
        if cls in drop:
            continue
        glist = roads.get(cls, [])
        if not glist:
            continue
        sw = max(0.25, road_w.get(cls, 0.8) * rs)
        ds = [path_d(g, proj) for g in glist]
        p.append(_stroke_group([d for d in ds if d], c_road, sw))

    # Jernbane (stiplet)
    rail = [path_d(g, proj) for g in layers.get("rail", [])]
    p.append(_stroke_group([d for d in rail if d], c_rail, 1.4 * rs,
                           extra=f'stroke-dasharray="{4 * rs:.1f} {3 * rs:.1f}"'))

    # Markører (hjerte/stjerne) — valgfrie, satt i config. Den interaktive
    # web-versjonen legger til markør klient-side; her tegnes kun forhåndssatte.
    # Ingen tekst-etikett — kun selve symbolet.
    markers = config.get("markorer")
    if markers is None and config.get("markor"):
        markers = [config["markor"]]
    for mk in (markers or []):
        if mk.get("lat") is None or mk.get("lng") is None:
            continue
        mx, my = proj(mk["lat"], mk["lng"])
        p.append(marker_svg(mk.get("type", "hjerte"), mx, my,
                            float(mk.get("storrelse", 30)) * rs, c_marker, c_bg))

    # Tomt lag der web-versjonen legger inn adresse-markøren (klippes til kartet)
    p.append('<g class="user-markers"></g>')

    p.append('</g>')  # slutt kartlag

    # ---- Ramme (ikke i full-bleed) ----
    if layout in ("ren", "boks"):
        p.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="none" '
                 f'stroke="{c_frame}" stroke-width="{2.5 * rs:.2f}"/>')

    # ---- Tittelblokk ----
    sted = config.get("sted", "")
    under = config.get("undertittel", "")
    coords = config.get("koordinater")
    if not coords and osm.get("center"):
        clat, clon = osm["center"]
        coords = f"{dms(clat, 'N', 'S')} / {dms(clon, 'E', 'W')}"

    if layout == "moderne":
        # Kartet fyller plakaten; tittel legges oppå nederst med en myk
        # gradient-scrim (ingen hard kant). Sperret versal-tittel + tynn strek +
        # land/koordinater (som referanse-plakatene).
        sub_txt = "  ·  ".join(esc(x) for x in (under, coords) if x)
        n = max(1, len(sted))
        # sperret tekst: ~0,80·name_size per tegn (inkl. sperring); hold < 86 % bredde
        ns_fit = (W * 0.86) / (n * 0.80)
        name_size = min(W * 0.085, H * 0.075, ns_fit)
        sub_size = min(W * 0.021, H * 0.018)
        letter = name_size * 0.18
        name_baseline = H - H * 0.05 - (sub_size * 2.2 if sub_txt else 0)
        p.append(f'<rect x="0" y="{H * 0.66:.1f}" width="{W}" height="{H * 0.34:.1f}" '
                 f'fill="url(#scrim-{uid})"/>')
        p.append(f'<text x="{W / 2:.1f}" y="{name_baseline:.1f}" text-anchor="middle" '
                 f'font-family="{esc(tfam)}" font-size="{name_size:.1f}" fill="{c_title}" '
                 f'letter-spacing="{letter:.1f}">{esc(sted.upper())}</text>')
        if sub_txt:
            line_y = name_baseline + name_size * 0.30
            lw = min(W * 0.42, n * name_size * 0.55)
            p.append(f'<line x1="{(W - lw) / 2:.1f}" y1="{line_y:.1f}" '
                     f'x2="{(W + lw) / 2:.1f}" y2="{line_y:.1f}" '
                     f'stroke="{c_title}" stroke-width="{1.2 * rs:.2f}"/>')
            p.append(f'<text x="{W / 2:.1f}" y="{line_y + sub_size * 1.5:.1f}" '
                     f'text-anchor="middle" font-family="{esc(fam)}" '
                     f'font-size="{sub_size:.1f}" fill="{c_title}" '
                     f'letter-spacing="{W * 0.005:.1f}">{sub_txt}</text>')
    elif layout in ("ren", "boks"):
        # Skaler tittelen etter den MINSTE dimensjonen, så den ikke blir for høy
        # i liggende format og dytter underteksten ut under rammelinja.
        name_size = min(W * 0.082, H * 0.072)
        sub_size = min(W * 0.022, H * 0.019)
        letter = max(1.0, name_size * 0.04)
        sub_txt = "  ·  ".join(esc(x) for x in (under, coords) if x)

        if layout == "ren":
            # Ankre tekstblokken rett over rammens underkant, så ALT ligger
            # trygt innenfor rammen (også i liggende).
            name_baseline = (fy + fh) - H * 0.045 - (sub_size * 1.6 if sub_txt else 0)
        else:  # boks — boks-høyden følger teksten, så den alltid rommer den
            pad = H * 0.022
            block_h = name_size + (sub_size * 1.9 if sub_txt else 0)
            bw = min(W * 0.7, W - 2 * margin - W * 0.04)
            bh = block_h + pad * 2
            bx, by = (W - bw) / 2, (fy + fh) - bh - margin * 0.55
            p.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                     f'fill="{c_bg}" stroke="{c_frame}" stroke-width="{2 * rs:.2f}"/>')
            name_baseline = by + pad + name_size * 0.8

        p.append(f'<text x="{W / 2:.1f}" y="{name_baseline:.1f}" text-anchor="middle" '
                 f'font-family="{esc(tfam)}" font-size="{name_size:.1f}" fill="{c_title}" '
                 f'letter-spacing="{letter:.1f}">{esc(sted.upper())}</text>')
        if sub_txt:
            sub_y = name_baseline + name_size * 0.30 + sub_size
            p.append(f'<text x="{W / 2:.1f}" y="{sub_y:.1f}" text-anchor="middle" '
                     f'font-family="{esc(fam)}" font-size="{sub_size:.1f}" '
                     f'fill="{c_title}" letter-spacing="{W * 0.006:.1f}">{sub_txt}</text>')

    p.append('</svg>')
    meta = {
        "ratio": ratio,
        "W": W, "H": H,
        "proj": {  # for klient-side: lat/lng -> SVG x,y (Web Mercator)
            "mx0": proj.mx0, "myt": proj.myt, "scale": proj.scale,
            "map_x": proj.map_x, "map_y": proj.map_y,
        },
        "mapclip": {"x": map_x, "y": map_y, "w": map_w, "h": map_h},
        "bbox": osm["bbox"],
        "marker_storrelse": float(config.get("markor_storrelse", 30)) * rs,
        # Presist: er hele BEBYGGELSEN synlig? (Sjekk vei-boksen, ikke den
        # kyst-utvidede — åpent hav som kuttes i kanten er greit.)
        "hele_byen": _box_synlig(town_box or content, proj, map_x, map_y, map_w, map_h),
    }
    return "".join(x for x in p if x), pal, meta


def _box_synlig(box, proj, mx, my, mw, mh, tol=0.5):
    if not box:
        return True
    s, w, n, e = box
    for la, lo in [(s, w), (s, e), (n, w), (n, e)]:
        x, y = proj(la, lo)
        if not (mx - tol <= x <= mx + mw + tol and my - tol <= y <= my + mh + tol):
            return False
    return True


# Standard ramme-format som bygges — både stående og liggende, slik at plakaten
# alltid fyller ei standardramme (30×40, 50×70, 70×100 og liggende motsvar).
# Web-versjonen bytter mellom dem og anbefaler orientering ut fra tettstedet.
DEFAULT_FORMATS = ["3:4", "5:7", "7:10", "4:3", "7:5", "10:7"]


# ---- Mal-fylling ------------------------------------------------------------

def fill_template(template, config, svgs, metas, pal, aspect, anbefalt):
    font = config.get("font", {})
    sted = config.get("sted", "")
    repl = {
        "__TITLE__": (sted + " – plakatkart") if sted else "Plakatkart",
        "__STED__": sted,
        "__FONT_URL__": font.get("url", ""),
        "__FONT_FAMILY__": font.get("family", "system-ui, sans-serif"),
        "__TITTEL_FAMILY__": font.get("tittel_family", "serif"),
        "__COLOR_BG__": pal["bakgrunn"],
        "__COLOR_FRAME__": pal["ramme"],
        "__COLOR_TITLE__": pal["tittel"],
        "__COLOR_MARKER__": pal["markor"],
        "__TOWN_ASPECT__": f"{aspect:.3f}",
        "__ANBEFALT_ORIENTERING__": anbefalt,
        "__SVGS__": "\n".join(svgs),
        "__METAS_JSON__": json.dumps(metas, ensure_ascii=False),
        "__CONFIG_JSON__": json.dumps(config, ensure_ascii=False),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, str(v))
    return out


def main():
    ap = argparse.ArgumentParser(description="Bygg en SVG-plakat-HTML.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--formater", default=None,
                    help="Komma-separerte ramme-format, f.eks. 3:4,5:7,7:10. "
                         "Standard: bygger alle tre vanlige format.")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    osm = json.loads(Path(args.osm).read_text(encoding="utf-8"))
    template = Path(args.template).read_text(encoding="utf-8")

    # Ytterpunkt-boks for den sammenhengende bebyggelsen, utvidet til å ta med
    # den naturlige kystlinja rundt stedet. Forhold på bakken -> orientering.
    center = osm.get("center")
    clat = (center or [(osm["bbox"][0] + osm["bbox"][2]) / 2])[0]
    max_km = config.get("maks_km", 10.0)
    capped = False
    if config.get("innramming"):
        road_box = box = config["innramming"]
        aspect = town_aspect(box, clat)
    else:
        road_full = town_extent(osm["layers"], center, max_km=None)   # sann byform
        wkm = (road_full[3] - road_full[1]) * math.cos(math.radians(clat)) * 111
        hkm = (road_full[2] - road_full[0]) * 111
        capped = max_km and max(wkm, hkm) > max_km * 1.01
        # Sentrer utsnittet på gate-tyngdepunktet (der byen ligger), ikke det
        # administrative punktet — ellers henger byen i utkanten med f.eks. mye
        # sjø over (Trondheim).
        fc = street_centroid(osm["layers"]) or center
        # Orientering: store byer som kappes -> bruk sann form (unngå at kappet
        # gjør alt kvadratisk = «begge» = dobbelt så mange format).
        road_box = cap_box(road_full, fc, max_km)
        # Utvid til kysten, men kapp så ikke hele fjorden drar boksen ut.
        box = cap_box(content_extent(osm["layers"], road_box), fc,
                      max_km * 1.4 if max_km else None)
        # Skyv kanter ved kystlinje ut i åpent vann, så strandlinja vises.
        box = add_sea_margin(box, osm["layers"], osm["bbox"], clat)
        aspect = town_aspect(road_full if capped else box, clat)

    # Regelen: ytterpunktene avgjør orientering (liggende / stående / begge).
    auto_formats, anbefalt = velg_orienteringer(aspect)
    if args.formater:
        formats = [r.strip() for r in args.formater.split(",") if r.strip()]
    elif config.get("formater"):
        formats = config["formater"]
    else:
        formats = auto_formats

    # Klipp bort rurale veier utenfor tettstedet, så en romslig fetch ikke
    # blåser opp sida. (Endrer kun denne kjøringens data, ikke fila.)
    osm = dict(osm)
    osm["layers"] = clip_roads_to(osm["layers"], box)

    svgs, metas, pal = [], [], None
    for ratio in formats:
        svg, pal, meta = build_svg(config, osm, ratio_override=ratio,
                                   content_box=box, town_box=road_box,
                                   fyll_ramme=capped)
        svgs.append(svg)
        metas.append(meta)

    out = fill_template(template, config, svgs, metas, pal, aspect, anbefalt)
    outp = Path(args.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(out, encoding="utf-8")

    beskaaret = [m["ratio"] for m in metas if not m["hele_byen"]]
    sys.stderr.write(f"  Skrev {outp} ({len(out)} tegn, {len(svgs)} format "
                     f"[{', '.join(formats)}], aspekt={aspect:.2f} -> {anbefalt})\n")
    if beskaaret:
        sys.stderr.write(f"  ADVARSEL: hele tettstedet får ikke plass i {beskaaret} "
                         f"— hent et større område (øk --radius ved fetch_osm).\n")


if __name__ == "__main__":
    main()
