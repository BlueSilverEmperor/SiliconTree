# SiliconTree Design System (`DESIGN.md`)

A restrained **Dark-Graphite Hardware Workbench** designed for `Operate`-mode precision, high-density telemetry scanability, and live SVG datapath visualization.

---

## 1. Color Tokens

Defined in [`web_gui/static/styles.css`](web_gui/static/styles.css):

### Surface & Border Hierarchy
| Token | Hex | Usage |
|---|---|---|
| `--bg-root` | `#0b0f16` | Page canvas, SVG diagram wells, RTN log & cache empty cells |
| `--bg-panel` | `#121822` | Top transport bar and primary `.panel` containers |
| `--bg-card` | `#18202c` | Pipeline stage cards, register cells, mode tabs, buttons, chips |
| `--bg-elevated` | `#202a3a` | Stage header strips, button & tab hover states |
| `--border` | `#263244` | Default `1px` structural border on panels, cards, inputs |
| `--border-active` | `#22d3ee` | Active focus, selected tab, selected cache cell |

### Text Hierarchy
| Token | Hex | Usage |
|---|---|---|
| `--text-primary` | `#e6edf7` | Primary headings, register values, active instruction text |
| `--text-secondary` | `#98abc4` | Panel metadata, RTN strings, inactive mode tabs, cache sub-labels |
| `--text-muted` | `#687c96` | Telemetry labels (`<dt>`), scrollbar hover thumb |

### Semantic Hardware Roles
| Token | Hex | Hardware & UI Meaning |
|---|---|---|
| `--cyan` | `#22d3ee` | Active `IF`/`ID` stages, forwarding bypass arcs (`FWD`), primary buttons, `:focus-visible` ring |
| `--emerald` | `#34d399` | Committed `EX`/`MEM`/`WB` stages, L1 cache hits, register writes, mission/contract pass |
| `--amber` | `#f59e0b` | Speculative execution (`SPEC`), speculative register divergence, `MEM_WRITE` packets, mid-range meters |
| `--crimson` | `#f43f5e` | Pipeline stalls/`NOP` bubbles, `FLUSH`, speculatively warmed L1 lines (`L1-WARM!`), `IRQ`, critical alerts |
| `--magenta` | `#e879f9` | Active cycle-stealing `DMA` bus transfers |
| `--violet` | `#a78bfa` | `REG_ALU` internal packets and multi-cycle ALU (`MUL`/`DIV`) stalls |

---

## 2. Typography

- **UI Sans (`--font-sans`):** `"Segoe UI", system-ui, -apple-system, sans-serif`
  - Base size: `13px`, line-height: `1.4`
  - Panel headings (`h2`): `13px`, weight `700`, letter-spacing `-0.01em`
  - Brand title: `15px`, weight `700`, letter-spacing `-0.02em`
- **Telemetry & Code (`--font-mono`):** `"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace`
  - `.num` utility applies `font-variant-numeric: tabular-nums` to all cycle counts, CPI, PCs, hex registers, latencies, and cache tags.

---

## 3. Layout & Spatial Grid

- **Top Bar (`.topbar`):** Flex row (`padding: 10px 16px`, `gap: 12px`) containing Brand, Mode Tabs, Clock Transport (`-1 Cyc`, `Play/Pause`, `+1 Cyc`, `Reset`, `1–20 Hz` slider), and Telemetry Strip (`Cycle`, `Retired`, `CPI`, `PC`, `State`).
- **Workspace Grid (`.workspace`):**
  - Desktop (`> 1020px`): 2-column CSS Grid (`1.25fr 1fr`, `max-width: 1680px`, `gap: 12px`, `padding: 12px 16px 16px`).
    - Row 1 (`1 / -1`): **5-Stage Pipeline Conveyor**
    - Row 2 Col 1: **L1/L2 Cache Matrix** (`auto-fill`, `minmax(128px, 1fr)`)
    - Row 3 Col 1: **System Bus & I/O Fabric**
    - Rows 2–3 Col 2: **Register File (`R0`–`R15` in 2 columns) & RTN Log (`170px` scroll well)**
    - Row 4 (`1 / -1`): **Mission Control** (mode-specific HUD)
  - Narrow (`<= 1020px`): Collapses cleanly to a single column.
- **Radii:** `12px` panels, `8px` SVG wells & stage cards, `6px` buttons/tabs/cache cells, `5px` register cells, `999px` state pill.

---

## 4. Inline SVG & Diagram Conventions

- **Pipeline Conveyor (`#pipeline-svg`):** `viewBox="0 0 1200 175"`, `158px` rendered height. Five `212×122` stage cards (`IF`, `ID`, `EX`, `MEM`, `WB`) with `24px` header strips, directional conveyor arrows, and dashed cyan forwarding arcs (`stroke-dasharray: 5 3`) routed above the stage row.
- **Bus Fabric (`#bus-svg`):** `viewBox="0 0 640 210"`, `196px` rendered height. `84×28` chip nodes (`REG_FILE`, `ALU`, `CPU_IF`, `ICACHE`, `CPU_MEM`, `L1_CACHE`, `RAM`, `DMA`, `IRQ_CTRL`, `CPU_PC`) with `2px` tracks (`2.5px` `--magenta` when DMA is active) and `6px` interpolated packet dots driven at 60 FPS via `requestAnimationFrame`.
- **Icons:** Inline `1.6px–1.75px` stroke SVGs only (no emoji or unicode glyph stand-ins).

---

## 5. Browser Surfaces & Craft Rules

- **Focus Rings:** `2px solid #22d3ee` with `outline-offset: 2px` on `:focus-visible`.
- **Selection:** `rgba(34, 211, 238, 0.25)` highlight with `#e6edf7` foreground.
- **Scrollbars:** Custom `6px` track (`--bg-root`) and thumb (`--border` / `--text-muted` on hover).
- **Motion & Restraint:** `140ms ease` color/border transitions on interactive controls, `160ms ease` width transitions on progress meters, no gradient text, and no eyebrow kickers above headings.

