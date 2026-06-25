# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

Builds **stylised art-poster maps** (HTML, with vector SVG) for any place — designed for
small towns that lack the cool poster maps big cities have. The output is a self-contained
HTML file the user opens and can download as a scalable **SVG** or a high-resolution **PNG**
(printable up to ~2 m × 2 m), or print to PDF. Users can mark an address with a heart or star
and colour the map from an uploaded palette or a preset. The full workflow is defined in
`SKILL.md` (the `design-kart-dittsted` skill).

Sister skill to `by-kart-bygger` (A4 tourist map over raster tiles). This one is vector,
poster-oriented, and aesthetics-first.

## Key commands

**Fetch OSM vector geometry for a place:**
```bash
python3 scripts/fetch_osm.py --sted "Berlevåg, Norge" --radius 1.8 --output osm-data.json
python3 scripts/fetch_osm.py --bbox 70.84,29.06,70.88,29.13 --output osm-data.json
```

**Build the poster HTML from a config + the geometry:**
```bash
python3 scripts/build_poster.py \
  --config config.json \
  --osm osm-data.json \
  --template templates/poster_template.html \
  --output outputs/berlevag-plakat.html
```

Both scripts use only the Python standard library — no `pip install`.

## Architecture

### Build pipeline

```
sted/bbox → fetch_osm.py → osm-data.json ┐
                                          ├→ build_poster.py → poster_template.html → final .html
config.json (palett, font, markør, papir) ┘
```

`fetch_osm.py` geocodes the place via **Nominatim** (preferring the `place` node over the
`administrative` boundary — small Norwegian municipalities otherwise return a centroid far
from the town), queries **Overpass** (with mirror fallback), and groups ways into layers.

`build_poster.py` projects geometry to SVG coordinates (**Web Mercator**, centre-cropped to
the paper ratio so there is no distortion), **simplifies** each path with Douglas–Peucker
(`_rdp`, ~0.7 SVG-unit tolerance — sub-pixel at print, invisible) to keep the SVG small for big
cities (e.g. Trondheim's 250k road vertices → ~5 MB instead of ~15–20 MB), draws the layers in
the palette colours, computes the DMS coordinate line, places the marker, and fills
`poster_template.html` by token replacement (same pattern as by-kart-bygger's `build_html.py`).

**Coded rule — always the whole tettsted, orientation from its extent:**

- `town_extent()` finds the **whole contiguous built-up area** by binning road vertices into a
  ~150 m grid, keeping dense cells (`>= thresh` points = real street grid, not a lone rural
  road), flood-filling the connected cluster from the centre, and taking its (lightly trimmed)
  bounding box. This is **stable regardless of fetch radius** — unlike a raw percentile, extra
  rural roads don't inflate it. Override with `config.innramming = [s, w, n, e]`.
- `content_extent()` then **expands the box to include the natural coastline** around the town
  (coast/water within `kyst_margin` ≈ 35 % of the town size), so a coastal map shows the
  shoreline instead of a flat cut through water. `Projector` zooms out to *contain* this box.
- The view is **centred on the street centroid** (`street_centroid()` — median of non-trail road
  points), not the Nominatim point, which often sits at the edge (Trondheim: ~3 km north at the
  fjord). This shifts the frame onto the actual built-up bulk.
- `add_sea_margin()` pushes any frame edge that meets **coastline** outward into the open water
  (~1.3 km), so a town that sits right at the shore gets the fjord/sea above it instead of being
  cut flush at the frame edge. (Open sea is often coastline-only with no water vertices, so we
  can't just extend to water points — we add a fixed margin where coastline touches the edge.)
- For a **capped big city** (`fyll_ramme`), `crop_to_aspect()` crops the wide content to the
  format's shape so the map **fills the frame** rather than leaving large sea/forest margins
  (e.g. Trondheim in portrait: without it the fjord filled ~40 % of the height). Small towns are
  not capped → still *contained* (whole town visible).
- `cap_box()` enforces an **upper size limit** (`config.maks_km`, default 10 km/axis): very large,
  boundaryless cities (Trondheim, Alta sprawl 15–20 km and never converge) are framed around the
  **core + coast** instead of zooming out forever. Orientation for a capped city uses its *true*
  (uncapped) shape so the cap doesn't squash it into "begge" (which would double the formats).
  Small towns are under the limit and unaffected.

**Trails are dropped.** `footway`/`path`/`track` (`TRAIL_CLASSES`) are forest/hiking trails, not
streets — they clutter the poster and were ~47 % of vertices in Trondheim (trails through Bymarka
also inflated the density cluster into the forest). They're excluded from both the drawing and the
`town_extent` detection by default (`config.vis_stier: true` to include them). Combined with
Douglas–Peucker, Trondheim went from a projected ~15–20 MB to **~3.7 MB**.

**Road detail scales with view size.** `veiklasser_a_droppe()` drops the smallest road classes on
large, zoomed-out views so a big city's centre isn't a muddy mass: by default `service` is dropped
above ~8 km across, plus `living_street`/`pedestrian` above ~13 km. Small towns keep everything.
Override with `config.veidetalj` (`alle` / `uten_service` / `uten_smaa` / `hovedveier`) or an
explicit `config.dropp_veiklasser` list.
- `Projector` *contains* the (coast-extended) box with padding, so **all addresses are placeable**.
  The whole-town check (`meta.hele_byen`) uses the **road** box, not the coast-extended one — open
  sea clipped at the frame edge is fine and shouldn't warn.
- `town_aspect()` = the box's on-ground width/height. `velg_orienteringer()` turns it into the
  built formats. **Portrait is the default** (poster convention — all the reference examples are
  portrait): **≥ 1.55 → landscape** (4:3/7:5/10:7, only clearly-wide places like Alta ~1.67),
  **1.42–1.55 → both**, **< 1.42 → portrait** (3:4/5:7/7:10 — most places, incl. Trondheim ~1.39).
  Only the chosen orientation(s) are built/offered; the page defaults to the iconic 50×70 portrait.
- `meta.hele_byen` is False when the town box's corners fall outside the map (genuine cropping);
  `main()` then prints a warning to re-fetch a larger `--radius`. Big ribbon settlements (e.g.
  Alta, ~12 km) need a generous radius (5–6 km).

### Token replacement (build_poster.py → template)

| Token | Source |
|---|---|
| `__TITLE__` | `config.sted` + " – plakatkart" |
| `__STED__` | `config.sted` |
| `__FONT_URL__` | `config.font.url` |
| `__FONT_FAMILY__` | `config.font.family` |
| `__TITTEL_FAMILY__` | `config.font.tittel_family` |
| `__COLOR_BG__` / `__COLOR_FRAME__` / `__COLOR_TITLE__` / `__COLOR_MARKER__` | `config.palett.*` |
| `__SVGS__` | one rendered `<svg>` **per ramme-format** (portrait 3:4/5:7/7:10 + landscape 4:3/7:5/10:7), concatenated |
| `__METAS_JSON__` | per-format projection meta (for client-side marker placement) |
| `__TOWN_ASPECT__` | settlement on-ground width/height (page recommends landscape if > 1.05) |
| `__CONFIG_JSON__` | the whole config (used by the in-page logic) |

### Config JSON structure

```json
{
  "sted": "Berlevåg",
  "undertittel": "Norge",
  "tittel_stil": "ren",
  "formater": ["3:4", "5:7", "7:10"],
  "fyll_hav": true,
  "vei_skala": 1.0,
  "palett": {
    "bakgrunn": "#F4EFE6", "vann": "#B9D4D2", "parker": "#D8E2CC",
    "veier": "#3A3A3A", "jernbane": "#3A3A3A", "ramme": "#2C2C2C",
    "tittel": "#1A1A1A", "markor": "#C75D55"
  },
  "font": {
    "url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=Inter:wght@400;500&display=swap",
    "family": "'Inter', system-ui, sans-serif",
    "tittel_family": "'Playfair Display', Georgia, serif"
  }
}
```

- **`tittel_stil`**: `"moderne"` (**default** — full-bleed map edge-to-edge with the spaced-caps
  title overlaid at the bottom over a soft `scrim` gradient + thin keyline, like the Amsterdam/
  Budapest/Berlin reference posters), `"ren"` (name on a bottom band inside a frame), `"boks"`
  (name in a framed box over the map, Osaka-style), or `"ingen"` (no title).
- **`formater`**: by default the orientation rule (`velg_orienteringer`) decides which ratios to
  build from the town's shape. Set this (or `--formater …`) to force specific ratios. One SVG per
  ratio is embedded; the page fills a **standard frame** (30×40 → 3:4, 50×70 → 5:7, 70×100 → 7:10,
  and the landscape equivalents 40×30 → 4:3, 70×50 → 7:5, 100×70 → 10:7).
- **`innramming`**: optional `[s, w, n, e]` to force the framed area; default is the density-based
  road-network extent (the whole settlement).
- **`maks_km`**: upper limit on the framed area per axis (default 10). Caps boundaryless big
  cities to core + coast. Set higher (or `null`) to show more; smaller for a tighter centre.
- **`vis_stier`**: include footway/path/track trails (default `false` — they clutter and bloat).
- **`veidetalj`**: road-detail level (`alle`/`uten_service`/`uten_smaa`/`hovedveier`). Default is
  automatic by view size (small roads dropped on big-city views).
- **`fyll_hav`**: fill the sea from coastline (default `true`, with a fail-safe).
- **`vei_skala`**: global multiplier on all stroke widths.
- **`palett.markor`**: marker colour. Must **harmonise** with the palette (use a colour that
  belongs to the map, not a jarring accent). For dark/inverted palettes, the cream/road colour
  with the auto navy outline works well.
- **Markør**: usually **interactive** — the end user types an address in the page and the
  marker is placed client-side (heart/star, no text label). For a pre-marked gift poster you
  may bake one in via `markor: {type, lat, lng}` (or several via `markorer: [...]`); `storrelse`
  optional, **no `label`** (symbol only).
- **`veibredder`**: optional per-class stroke-width overrides (see `DEFAULT_ROAD_W`).
- If `koordinater` is omitted, the DMS line is computed from the map centre.

### osm-data.json structure (fetch_osm.py output)

```json
{
  "bbox": [s, w, n, e],
  "center": [lat, lon],
  "display_name": "…",
  "layers": {
    "water_polys": [[[lat,lon],…]], "rivers": [...], "water_lines": [...],
    "coastline": [...], "parks": [...], "rail": [...],
    "roads": { "primary": [...], "residential": [...], "…": [...] }
  }
}
```

### Sea fill from coastline (build_poster.py)

OSM coastlines are directed (land left, water right) and split into many segments. The filler
(`_stitch` → `_clip_runs` → `assemble_sea`) stitches segments into continuous chains
(direction-preserving), clips them to the map window, and closes each chain along the window
boundary on the water side. Islands stay land (correct hole handling). A fail-safe skips the
fill if the result covers ~none or ~all of the map (likely degenerate), keeping the coastline
stroke instead.

### Template runtime features (poster_template.html)

The output is an **interactive, self-contained page** — built to be hosted (e.g. at
`kart.snefokk.com/plakat/<sted>`). It needs no server; just drop the HTML at that path.

- **Address marking** — the visitor types an address; it is geocoded via Nominatim (biased to
  the map bbox with `bounded=1`) and a heart/star marker is placed client-side, in `markor`
  colour, **no text label**. The marker is re-projected into every format so it survives a
  size change. Out-of-bbox addresses get a friendly message.
- **Format / size switch + orientation** — one SVG per built ratio is embedded; the size dropdown
  groups standard framable sizes under **Stående** and **Liggende**. On load the page **removes
  sizes for orientations that weren't built** (hiding the empty group) and preselects the iconic
  50×70 / 70×50; `__ANBEFALT_ORIENTERING__` drives the hint. (SVG `hidden` is set via
  `setAttribute('hidden')` — the `.hidden` IDL property is HTMLElement-only and does **not** work
  on SVG elements.)
- **Download SVG** — serialises the active format with the **web font embedded as base64 data
  URIs** (fetched from the Google Fonts URL at click time), so typography is faithful at a
  print shop, marker included.
- **Download PNG** — rasterises the (font-embedded) active SVG to a canvas at the chosen
  cm×DPI; caps at ~16k px with a warning and recommends SVG for full 2 m prints.
- **Print / PDF** — `@page { size:auto; margin:0 }`, one page, toolbar hidden.

### Palette extraction from an uploaded image

Done by Claude reading the image visually (the model assigns swatches to roles) — **not** a
script: the Python stdlib can't decode JPEG/PNG, and visual reading handles palettes without
written hex codes. Role guidance lives in `references/palett-roller.md`. Presets live in
`templates/palettes/`.

## Reference files

- `references/overpass-sporring.md` — the Overpass query + layer grouping
- `references/projeksjon-og-print.md` — Web Mercator crop, DPI/size, print-shop tips
- `references/palett-roller.md` — how to map an uploaded palette onto the eight colour roles
- `references/checklist.md` — step-by-step build checklist
- `SKILL.md` — full skill definition (Norwegian-first workflow)
