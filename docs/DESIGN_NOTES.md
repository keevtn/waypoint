# Design notes: measured reference rules

Measured 2026-10-25 in headless Chrome at 1280×900 from computed styles (`getComputedStyle`), not from guesses. Pages: mercury.com (home, /treasury), copilot.money (home, /download), linear.app (home, /features). Screenshots and the raw extraction (`report.json`) live in Session B's scratch folder `refs/`; they are style references only. Nothing below copies a logo, copy line, brand color, or layout.

## 1. Type scale

| Site / page | Root | Body text | Secondary text | Section heading | Page h1 | Line-height ratios (most common) |
|---|---|---|---|---|---|---|
| Mercury home | 16px | 16/24, 18/24.3 | 12/16.8 (ls +0.24px) | h2 28/33.6 and 42/48.3 | 45/49.6 | 1.40, 1.25, 1.35 |
| Mercury /treasury | 16px | 18/24.3 (w360), 16/22.4 | 12/16.8 | h2 42/48.3, 28/33.6 | 52/57.2 | 1.35, 1.40, 1.25 |
| Copilot home | 16px | 15/18, 16/22.4 | 13/15.6 | h2 48/50.4, h3 24/28.8 | 112/100.8 (ls −2.24px) | 1.20, 1.40 |
| Copilot /download | 16px | 16/22.4 | 13/18.2 | h2 48/50.4, h3 24/28.8 | — | 1.40, 1.60 |
| Linear home | 16px | 13/20, 14/24, 15/24 | 12/14, 12/16 | h2 48/48 and 40/44 (ls −0.88 to −1.06px) | 64/64 (ls −1.4px) | 1.50, 1.71, 1.17 |
| Linear /features | 16px | 15/24 (w510), 13/19.5 | 13/19.5 | h3 20/26.6 | 64/67.8 | 1.50, 1.33 |

Distinct font sizes per page: Mercury 8, Copilot 8, Linear home 8 (12, 13, 14, 15, 10, 16, 24, 40), Linear /features 7. Font weights in body copy: 400 (Mercury 400/420/480 on a variable axis; Linear 400/510/590). Nothing in body copy is 600 or 700. Large headings are 480–600, never 700.

Rules derived:
- R1. Body copy 15–16px at line-height 1.4–1.5; secondary 12–13px at 1.4–1.5; nothing below 12px.
- R2. One scale with ≤ 8 sizes. Headings tighten letter-spacing: ≥ 40px at −0.02em (Linear −1.4px at 64 = −0.022em; Mercury h1 normal).
- R3. Line-height: 1.5 at ≤ 16px, 1.3–1.4 at 18–28px, 1.0–1.1 at ≥ 40px.
- R4. Weight 500 for emphasis, 600 for headings only; no 700.

## 2. Content width

| Site / page | Outer max-width | Measured content width at 1280 | Text column |
|---|---|---|---|
| Mercury home | 1320 / 1376 | 1216 | 608 |
| Mercury /treasury | 1320 | 1216 | 688 |
| Copilot home | 1200 | 1200 | 912 |
| Copilot /download | 1200 | 920 | 920 |
| Linear home | 1364 | 1226–1260 | 541–620 |
| Linear /features | 1024 | 1024 | 620 |

Rules: R5. Outer content 1200–1260px at 1280 (gutters 10–32px); R6. Prose columns 600–690px; marketing text 540–620px.

## 3. Vertical rhythm

| Site / page | Section padding | Gap between sections |
|---|---|---|
| Mercury (both) | 0 on wrappers; spacing lives inside blocks | 40–49px between measured blocks |
| Linear home | 128/128 (×4), one block margin 224/224 | 224–237px |
| Linear /features | 96/96 | 80–128px |
| Copilot | spacing inside blocks (Framer) | — |

Rules: R7. Marketing pages: 96–128px between sections. R8. In-app: 40–48px between blocks of a page, 16px between cards in a grid (Mercury dashboard mock: 16px card gap, 24px inner padding).

## 4. Cards

| Site / page | Radius | Padding | Border | Background vs page | Shadow | Distinct card styles |
|---|---|---|---|---|---|---|
| Mercury home | 12 | 32/32 | 0 | rgb(30,30,42) on rgb(23,23,33): +7 per channel | none | 2 |
| Mercury /treasury | 12 | 32/32 | 0 (mock tables: 1px rgb(195,195,204)) | rgb(237,237,243) on white | none (1 mock element) | 2 |
| Copilot | 24 | 28/32 | 0 | transparent + shadow | yes | 1 (plus colored pills) |
| Linear home | 9–12 | 8/12 to 12/16 | 1px rgba(255,255,255,0.08) ×16, 0.12 ×4 | rgb(15,16,17) on rgb(8,9,10): +7 | none on 16 of 32 | 3 |
| Linear /features | 16 | 32/24 | 0 | rgb(15,16,17) on rgb(8,9,10) | none | 1 |

Border colors across a whole page: Mercury 1px rgb(195,195,204) ×18 (one color); Linear 1px rgba(255,255,255,0.08) ×66 (one color, one alpha).

Rules: R9. One card: 1px border in one color (≈ 8–12% contrast against the page), background one step lighter (light) or +7/255 (dark) than the page, padding 20–32px, no shadow. R10. Cards are never nested; inside a card use dividers or a background shift, not a second border. R11. ≤ 2 card variants per product (plain, selected).

## 5. Numbers

| Site / page | Sizes in use | Weight | Numeric features |
|---|---|---|---|
| Mercury /treasury | 18/24.3 ×15 (tables), 21/28.4, 42/48.3 (hero figure); dashboard mock balance ≈ 32px with cents ≈ 14px superscript | 360–480 | `font-variant-numeric: normal` (proportional); the typeface's figures are already even-width |
| Copilot | 13/15.6 ×20, 15/18 ×25, 48/57.6 | 100 (display face) | `font-feature-settings: "ss07"` on every figure |
| Linear | 12/16 ×19, 12/14 ×6; 2 elements `tabular-nums` | 400–510 | `"cv01","ss03"` globally |

Rules: R12. Two number sizes per view: a primary figure at 28–42px / 1.1 at weight 500, and inline figures at body size, weight 500. R13. Lining tabular figures everywhere (already set on `body`). R14. Cents are shown; a figure is never bolder than 600.

## 6. Charts

| Site / page | SVG size | Container padding | Clear space around plot |
|---|---|---|---|
| Copilot home | 608×120, 529×110 | 0/24 and 20/24 | 24–32px sides |
| Linear home | 265–304px tall in 360px boxes | 0/32 | 47–82px sides, 75–85px bottom (legend/caption) |
| Linear /features | 661×369 in 976×320 box; 476×280 in 476×400 | 32/24 | 94–222px sides on the wide one, 120px below |

Rules: R15. Container padding 24px (32 on marketing); R16. ≥ 24px clear between the plot and the card edge, 12–16px between plot and legend; R17. Axis labels 12px in the secondary text color; no label smaller than 12px.

## 7. Buttons

| Site | Primary | Secondary | Tertiary |
|---|---|---|---|
| Mercury | h40, 16px w420, px20, solid rgb(82,102,235), white text, no border | h40, same type, 20%-alpha tint background, no border | h40, 10% tint + 1px border at 22–36% alpha |
| Linear home | h32–44, 13–16px w510, px12–20, solid light rgb(229,229,230) on dark, 1px same-color border | h44, rgba(255,255,255,0.05) fill, no border | text link 13px |
| Copilot | h44, 12–16px, solid rgb(28,108,255) or white, radius 16 | (same shape, different fill) | — |

Rules: R18. Primary and secondary share height, padding, type size and weight (500); they differ by fill only: solid accent vs transparent/5–10% tint with a 1px border. R19. One primary per view. R20. Button text 14–16px.

## 8. Color budget

| Site / page | Text colors (visible text elements) | Accent uses | Border colors |
|---|---|---|---|
| Mercury home | 2 (rgb(237,237,243) ×149, rgb(195,195,204) ×50) | 1 accent on 3 buttons | 1 (plus the accent at 36% alpha) |
| Mercury /treasury | 3 (rgb(39,39,53) ×79, rgb(83,84,97) ×70, light ×97) | 1 accent on 3 buttons + 10% tint ×8 | 1 (rgb(195,195,204)) |
| Linear home | 3 greys (rgb(138,143,152) ×173, rgb(208,214,224) ×105, rgb(98,102,109) ×89) | 1 accent on 1 button | 1 (rgba(255,255,255,0.08)) |
| Linear /features | 2 greys + white | 1 accent on 1 button | 1 (rgb(35,37,42) ×125) |
| Copilot | 3 greys + many category colors (18 fills) | 1 accent on 2 buttons | 0 |

Rules: R21. Three text colors: ink, secondary, tertiary. R22. One accent, on at most one primary action per view plus the selected state. R23. One border color per theme. R24. Semantic colors only on data (flags), never on chrome.

## Applied to Waypoint (what changed, in impact order)

1. Type scale (R1–R4): Tailwind `fontSize` redefined to 8 steps, body 15/22; labels 12/18 (no 10/11px); page titles 26/32; landing h1 44/48 → 52/56 at ≥ 640px; number figures weight 500 on the large sizes.
2. Width and rhythm (R5–R8): content 1200px with 24px gutters; landing sections 96px apart; app pages 24px between blocks, 16px card gaps.
3. Cards (R9–R11): one `cardClass` (6px radius, 1px `slate-200`, paper on a `slate-50` page in light, `slate-900` on `slate-950` in dark, 20px padding) used by Card, option, module, suggestion, scenario, landing hero. Suggestions are no longer nested inside a Card.
4. Charts (R15–R17): plot margin 16px, axis labels 12px, legend 12px below the plot.
5. Buttons (R18–R20): primary and secondary share 36px height, 14px/500 type and 16px side padding; secondary is transparent with a 1px border.
