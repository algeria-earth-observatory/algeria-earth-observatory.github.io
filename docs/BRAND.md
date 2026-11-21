# AEO brand and interface system — AZIM

**AZIM — Amazigh Computational Modernism.** It combines Amazigh constructivist geometry, meridian cartography and a pixel-atlas logic. The institution's name is **Algeria Earth Observatory (AEO)**.

Aim: a contemporary scientific atlas joined to a geospatial analysis platform. The identity should be recognisable, but it must never interfere with scientific clarity.

## 1. Tokens

All values are defined once in `src/styles/global.css` (`@theme`). Never put raw hex values in components.

| Role | Token | Value | Use |
|---|---|---|---|
| Primary text, navigation | `--color-midnight` | `#17252C` | Text, header, map workspaces |
| Main background | `--color-limestone` | `#F2EFE7` | Page background |
| Primary action | `--color-cobalt` | `#3458D4` | Buttons, links, selected states |
| Artistic accent | `--color-oxide` | `#B6503C` | Monogram lozenge, active navigation marker, geometric bands. **Never** for errors, warnings or data |
| Neutral surface | `--color-white` | `#FFFFFF` | Panels, tables |
| Subtle border | `--color-border` | `#D8D3C8` | Rules and separators (decorative) |
| Secondary text | `--color-secondary` | `#586268` | Labels, captions |
| Control border | `--color-line-strong` | `#857F73` | Inputs and selects (≥ 3:1 against white) |
| Semantic | `--color-warn`, `--color-error`, `--color-success` | `#7A5200`, `#B3261E`, `#1E6B3A` | Meaning only |

`.theme-dark` re-maps the same roles for map workspaces: the explorer, the map panels, the header.

**Scientific colour scales are independent of the brand.**
- Precipitation uses a sequential blue scale.
- Anomalies and SPEI use a diverging red–grey–blue scale.
- Hyper-arid masks use a neutral sand.

These scales are defined in the product pipelines and validated with the dataviz palette checks.

### Measured contrast (WCAG 2.2)

| Pair | Ratio | Requirement |
|---|---|---|
| Midnight on limestone | 13.66:1 | 4.5:1 text ✓ |
| Secondary on limestone | 5.44:1 | 4.5:1 ✓ |
| Secondary on recessed band `#EBE7DD` | 5.06:1 | 4.5:1 ✓ |
| Secondary on white | 6.25:1 | 4.5:1 ✓ |
| Cobalt link on limestone | 5.23:1 | 4.5:1 ✓ |
| White on cobalt button | 6.01:1 | 4.5:1 ✓ |
| White on midnight navigation | 15.70:1 | ✓ |
| Navigation text `#C5CDD2` on midnight | 9.75:1 | ✓ |
| Control border `#857F73` on white / limestone | 3.98 / 3.46:1 | 3:1 non-text ✓ |
| Oxide on limestone | 4.35:1 | decorative, never used for text |
| Subtle border `#D8D3C8` | 1.30:1 | decorative rules only, never a control boundary |

## 2. Typography

- **Family.** IBM Plex Sans for headings and body text (400, 500, 600). IBM Plex Mono for coordinates, identifiers, timestamps and scientific metadata.
- **Scale.** Use the classes, not ad-hoc sizes:

| Style | Class | Size |
|---|---|---|
| Hero | `.display` | 40–68 px (clamp) |
| Section heading | `.h-section` | 28–36 px |
| Subheading | `.h-sub` | 20–24 px |
| Body | — | 16 px |
| Technical label | `.overline`, `.meta` | 12–13 px |
| Table text | — | 14 px |

- **Weights.** Regular and medium. Semibold only for necessary emphasis.
- **Uppercase.** Only in short mono overlines, with 0.06 em letter-spacing.
- **Small panels.** No more than three text sizes in one small panel.
- **Numbers.** Use `.tabular` for statistics and tables.

## 3. Layout and spacing

- **Grid.** 12-column grid, maximum width 1440 px, margins of 20, 32 and 48 px at the three breakpoints.
- **Spacing.** 8 px base with 4 px half-steps. Editorial sections use `--space-section` (64–120 px); analytical workspaces use compact 8–16 px spacing.
- **Separation.** Whitespace first, then 1 px rules. No nested cards, large shadows or floating decorative panels.
- **Corner radii.** 3 px for controls, 4 px for panels.

## 4. Logo and wordmark

- **Monogram.** Built on a 2-unit pixel grid in a 46 × 16 viewBox:
  - **A** — triangle with crossbar;
  - **E** — three bars, the middle one shorter;
  - **O** — lozenge with a central pixel, in oxide.
- **Files.** `src/components/Logo.astro` (inline SVG), `public/images/aeo-mark.svg` and `public/favicon.svg` (32 × 32: midnight square, white A and oxide lozenge).
- **Wordmark.** "Algeria Earth Observatory" in IBM Plex Sans 400, set to the right of the monogram. It is hidden at the smallest widths, where the monogram stands alone.
- **Clear space.** At least the height of the monogram on every side. Minimum size: 46 × 16 px on screen.
- **Do not:** recolour the lozenge, add effects, place the mark on imagery without a solid midnight or limestone field, or set the mark inside a globe, seal or badge.

### Cultural note

Triangles, chevrons and lozenges are among the most widespread primitives of Amazigh geometric decoration across North Africa, in weaving, pottery and tattoo. AEO uses these primitives **abstractly**, as construction elements on a pixel grid. The mark does **not** reproduce any specific regional or tribal motif, nor the ⵣ (yaz) symbol, whose meaning and use belong to Amazigh communities.

Before the identity is formally adopted, AEO should seek review by Amazigh cultural specialists and record their advice here.

## 5. Supporting pattern

`src/components/GeoBand.astro` is a 12 px band of alternating triangles and a lozenge, in oxide or muted.

- **Use only for:** editorial section transitions (one per page at most), the footer detail, report covers, publication graphics and presentations.
- **Never** place it behind maps, charts, tables, form controls or text.

## 6. Components and interaction

| Element | Rule |
|---|---|
| Buttons | `.btn-primary` (cobalt) for the one primary action in a region; `.btn-secondary` otherwise. **Download** always uses `.btn-primary` with the label "Download". |
| Status | `.status` + `.status-*`: a small square and a text label, so status never depends on colour alone. Available = filled cobalt square; Planned = dashed outline; Experimental / under validation = filled warning square. |
| Forms | `.field` for inputs and selects. Selects are compact; segmented controls use a midnight fill for the selected state. |
| Notes | `.note` (neutral) and `.note-warn` (caveats such as limited spatial support or hyper-arid areas). |
| Progressive disclosure | Technical metadata, advanced analysis settings and methods go in `<details>`. Units, legends, sources and data availability stay visible. |
| Motion | 150 ms (`--motion`) on colour and transform. `prefers-reduced-motion` disables transitions. |
| Focus | 2 px cobalt outline with 2 px offset (lighter blue on dark surfaces). |
| Targets | Interactive elements are at least 24 × 24 px (WCAG 2.5.8). |

## 7. Screen hierarchy (one dominant element per screen)

| Screen | Dominant element |
|---|---|
| Home | Identity and the satellite plate of Algeria (NASA Blue Marble, credited). |
| Explore | The map: compact layer panel on the left, inspector on the right (wide screens), drawer and popup on mobile. |
| Data | The searchable product index. |
| Analyze | Charts and the map, in the order Configure → Visualize → Interpret → Download. |

## 8. Imagery

- Use only genuine, credited Earth observation data.
- The homepage plate (`scripts/processing/build_hero_image.py --style plate`) leaves pixels inside Algeria unchanged and fades the surroundings towards limestone. No administrative lines are drawn on it.
