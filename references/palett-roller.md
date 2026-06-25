# Palett-roller

Plakaten bruker **åtte fargeroller**. Når brukeren laster opp et palett-bilde, leser du
fargene visuelt (også uten hex-koder) og fordeler dem på rollene. Vis forslaget til brukeren
og la dem justere.

| Rolle | Styrer | Tommelregel |
|---|---|---|
| `bakgrunn` | Land / papir | Den lyseste fargen. For «invertert» stil (New Haven): den mørkeste. |
| `vann` | Sjø, innsjø, elver | En blå/grønn/teal. Tør å bruke en kontrastfarge (Osaka bruker oransje). |
| `parker` | Parker, skog, grønt | Dempet grønn, eller en farge nær `bakgrunn` for et roligere kart. |
| `veier` | Alle gater | Sterkest mulig kontrast til `bakgrunn` (mørk på lys, lys på mørk). |
| `jernbane` | Jernbane (stiplet) | Som `veier`, eventuelt litt svakere. |
| `ramme` | Rammestrek + tittelboks | En mørk aksent. |
| `tittel` | Stedsnavn + koordinater | Mørk og lesbar mot bakgrunnsbåndet. |
| `markor` | Hjerte / stjerne | En farge **fra palettet** som harmonerer med kartet, ikke en skrikende kontrast. Markøren får automatisk et omriss i bakgrunnsfargen, så den blir synlig uten å bryte med stilen. For mørke/inverterte paletter funker krem/vei-fargen godt. |

## Strategi for vanlige palett-typer

- **Lyst, jordnært palett (krem + dempede farger):** lyseste → `bakgrunn`, en mørk →
  `veier`/`ramme`/`tittel`, en blågrønn → `vann`, en grønn → `parker`, sterkeste → `markor`.
- **Palett med både lyse og mørke (som det vedlagte rosa/blå-eksemplet):** velg om kartet
  skal være lyst (lys `bakgrunn`, mørke `veier`) eller invertert (mørk `bakgrunn`, lyse
  `veier`). Inverterte kart ser stilige ut, men krever lys gate-farge.
- **Monokromt ønske:** sett `vann` og `parker` til toner av samme farge som `bakgrunn`, og la
  `veier` bære kontrasten. Bare `markor` skiller seg ut.

## Kontroll

- Kontrast `veier` ↔ `bakgrunn` må være høy nok til at gatenettet leses tydelig.
- `markor` bør ikke kollidere med `vann` eller `veier` i farge.
- `tittel` må være lesbar der tittelblokken ligger (`bakgrunn`-bånd for `ren`, `bakgrunn`-boks
  for `boks`).

Roller fylles i `config.palett`. Standardverdier (hvis en rolle mangler) ligger i
`DEFAULT_PALETTE` i `scripts/build_poster.py`.
