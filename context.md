# SiliconTree Project Context & Architecture Reference

This document provides a comprehensive technical, architectural, and operational overview of **SiliconTree** for developers, researchers, and AI coding agents.

---

## 1. Executive Summary & Vision

**SiliconTree** is an interactive, cycle-accurate Computer Architecture & Hardware Security simulation suite developed in pure Python. It pairs a strict Model-View-Controller (MVC) hardware engine with a high-craft **Flask Dark-Graphite Web Workbench** (inline 60 FPS SVG datapath visualization) and a fallback **Pygame-CE Desktop GUI**.

### Core Pillars
- **Strict MVC Decoupling:** `core_engine/` contains zero UI/rendering imports. Presentation layers (`web_gui/`, `gui/`) strictly consume and render serialized immutable snapshots (`CycleSnapshot`).
- **Reverse-Order Pipeline Execution:** Every clock tick evaluates pipeline stages in reverse (`WB → MEM → EX → ID → IF`), preventing intra-cycle race conditions and latch overwrites.
- **Cycle Time-Travel & Scrubbing:** Every call to `clock.step_cycle()` captures an immutable `CycleSnapshot` into an in-memory history deque, enabling exact step-back rewinds (`-1 Cyc`), reset, and post-mortem crash scrubbing.
- **Hardware Security & Speculation Modeling:** Models speculative branch execution, microarchitectural side channels (Spectre v1 bounds-check bypass), cache line warming, Flush+Reload timing attacks, and software barrier serialization (`LFENCE`).

---

## 2. Codebase Organization

```
SiliconTree/
├── main.py                     # Entry point: launches Flask Web GUI on 127.0.0.1:5000
├── requirements.txt            # Dependencies: flask, pygame-ce, pygame-gui
├── DESIGN.md                   # Impeccable dark-graphite design system specification
├── context.md                  # Comprehensive architectural context (this document)
├── report.md                   # Technical documentation scratch / report notes
├── LICENSE                     # MIT License
│
├── core_engine/                # Pure-Python cycle-accurate hardware simulation model
│   ├── __init__.py             # Public subsystem exports
│   ├── isa.py                  # 32-bit RISC ISA, two-pass assembler, and RTN generator
│   ├── alu.py                  # Booth multiplication, bit-pair recoding, restoring/non-restoring div
│   ├── memory.py               # SRAM L1/L2 caches (direct-mapped & N-way LRU), DRAM, Flush+Reload
│   ├── branch_predictor.py     # Static & 2-bit saturating counter (SNT/WNT/WT/ST) + BTB
│   ├── bus_io.py               # Single/Multi-bus arbitration, DMA cycle-stealing, and IRQs
│   ├── pipeline.py             # 5-stage pipeline, RAW hazards, forwarding, speculative rollback
│   └── clock.py                # SimulationClock, CPI tracking, and immutable CycleSnapshot deque
│
├── modes/                      # Simulation scenarios, game logic & mission controllers
│   ├── __init__.py             # Mode class exports
│   ├── base_mode.py            # Abstract BaseMode & ModeOutcome interface
│   ├── spectrescope.py         # Mode 1: SpectreScope (speculative leak detector & LFENCE)
│   ├── silicon_heist.py        # Mode 2: Silicon Heist (stealth L1 lockers & DMA escape)
│   ├── silicon_deathmatch.py   # Mode 3: Silicon Deathmatch (thermal survival & hardware drafting)
│   ├── silicon_forensic.py     # Mode 4: Silicon Forensic (crash-dump timeline scrubber)
│   └── architect_tycoon.py     # Mode 5: Architect Tycoon (die area/power budgeting & client contracts)
│
├── scenarios/                  # JSON scenarios and assembly payloads for each mode
│   ├── spectrescope.json
│   ├── silicon_heist.json
│   ├── silicon_deathmatch.json
│   ├── silicon_forensic.json
│   └── architect_tycoon.json
│
├── web_gui/                    # Flask presentation layer & interactive SVG workbench
│   ├── app.py                  # Flask routes, simulation session manager & JSON serializer
│   ├── templates/
│   │   └── index.html          # Workbench responsive layout (conveyor, cache, bus, registers, HUD)
│   └── static/
│       ├── styles.css          # Dark-graphite CSS tokens & layout grid
│       └── app.js              # 60 FPS SVG animation engine, polling loop & transport handlers
│
├── gui/                        # Pygame-CE desktop GUI fallback
│   ├── app_window.py           # Main desktop loop and event dispatcher
│   ├── theme.py                # Graphical theme and color constants
│   ├── overlays/               # Pygame HUD overlays for each simulation mode
│   │   ├── base_overlay.py
│   │   ├── spectre_hud.py
│   │   ├── heist_hud.py
│   │   ├── deathmatch_hud.py
│   │   ├── forensic_hud.py
│   │   └── tycoon_hud.py
│   └── widgets/                # Custom Pygame UI widgets (pipeline, cache, bus, registers)
│
├── docs_gen/                   # Technical report & architectural diagram generation
│   ├── build_exhaustive_word_report.py
│   ├── build_word_report.py
│   ├── generate_diagrams.py
│   └── generate_extra_diagrams.py
│
└── tests/                      # Pytest automated test suite (14 passing tests)
    ├── test_flask_gui.py
    ├── test_phase1_core.py
    ├── test_phase2_gui.py
    ├── test_phase3_spectrescope.py
    ├── test_phase4_modes.py
    └── test_phase5_integration.py
```

---

## 3. Hardware Subsystems (`core_engine/`)

### 3.1 Instruction Set Architecture (`core_engine/isa.py`)
- **Format:** 32-bit RISC instruction format supporting R-type, I-type, Branch, and System operations.
- **Register File:** 16 general-purpose registers (`R0` through `R15`), where `R0` is hardwired to `0`.
- **Instruction Support:**
  - *R-Type (Arithmetic/Logic):* `ADD`, `SUB`, `AND`, `OR`, `XOR`, `SLT`, `SLL`, `SRL`, `MUL`, `DIV`.
  - *I-Type (Immediate):* `ADDI`, `ANDI`, `ORI`, `XORI`, `SLTI`, `SLLI`, `SRLI`.
  - *Memory Access:* `LW`, `LB`, `SW`, `SB` (using `offset(base)` format).
  - *Control Flow:* `BEQ`, `BNE`, `BLT`, `BGE`, `JMP`, `JAL`.
  - *Barriers & System:* `NOP`, `LFENCE` (speculative serialization barrier), `HALT`.
- **Assembler:** Two-pass assembler resolving symbolic labels to byte offsets, validating syntax, and computing Register Transfer Notation (RTN) strings for every decoded instruction (e.g. `R[5] <- R[3] * R[4]`).

### 3.2 ALU & Arithmetic Algorithms (`core_engine/alu.py`)
- **Booth Multiplication:** Multi-cycle Radix-2 Booth multiplier tracking partial products, arithmetic right shifts, and step-by-step bit recordings (`M`, `Q`, `Q_-1`).
- **Radix-4 Bit-Pair Recoding:** Optimized recoding grouping multiplier bits into overlapping triplets, reducing cycle latency by roughly 50%.
- **Integer Division:**
  - *Restoring Division:* Sequential subtraction with conditional divisor restoration.
  - *Non-Restoring Division:* Avoids redundant restore cycles by alternating addition/subtraction based on partial remainder sign.
- **Latency Modeling:** Basic ALU ops take 1 cycle, Booth `MUL` takes multi-cycle steps depending on operand width, and `DIV` takes iterative cycles.

### 3.3 Memory Hierarchy & Side-Channel Modeling (`core_engine/memory.py`)
- **Hierarchical Layout:** L1 Cache $\rightarrow$ L2 Cache $\rightarrow$ DRAM.
- **Cache Configuration (`CacheConfig`):**
  - Configurable capacity (`size_bytes`), line size (`line_size`), associativity (`associativity`: 1 for direct-mapped, $N$ for $N$-way set-associative), and hit latency.
  - **Replacement Policy:** True Least-Recently Used (LRU) tracking per set.
  - **Write Policy:** Write-back with write-allocate; maintains dirty bits and tracks dirty line evictions to DRAM.
- **Hardware Security Primitives:**
  - Tracks whether cache lines are warmed speculatively (`speculative_touch`).
  - Supports side-channel analysis: **Flush+Reload** simulation timing differential (hit latency 1 cycle vs. DRAM miss latency 8–10+ cycles).

### 3.4 Branch Predictor & Speculation (`core_engine/branch_predictor.py`)
- **Modes (`PredictorMode`):**
  - `STATIC_NOT_TAKEN`: Always predicts fallthrough.
  - `STATIC_TAKEN`: Always predicts branch taken.
  - `TWO_BIT_SATURATING`: 2-bit state machine (00: Strongly Not Taken, 01: Weakly Not Taken, 10: Weakly Taken, 11: Strongly Taken).
- **Branch Target Buffer (BTB):** Caches branch targets indexed by PC.
- **Speculative Tracking:** Predictor marks instructions entering the pipeline after an unresolved branch as speculative until branch resolution in `EX`.

### 3.5 System Bus & I/O Fabric (`core_engine/bus_io.py`)
- **Topologies (`BusTopology`):**
  - `SINGLE_BUS`: Shared bus arbitrated between CPU and DMA; CPU stalls during DMA transactions.
  - `MULTI_BUS`: Split instruction/data and dedicated system buses allowing simultaneous transfers.
- **Arbitration Policies:** Priority-based and Round-Robin.
- **Direct Memory Access (DMA):** Supports cycle-stealing mode (interleaving single-word transfers with CPU execution) and burst transfer mode.
- **Interrupt Controller (IRQ):** Hardware interrupt lines with prioritized dispatching.

### 3.6 5-Stage Pipeline Engine (`core_engine/pipeline.py`)
- **Stages:**
  1. `IF` (Instruction Fetch): Reads instruction from memory at `PC`, queries branch predictor.
  2. `ID` (Instruction Decode): Decodes operands, reads register file, detects hazard conditions.
  3. `EX` (Execute): ALU evaluation, branch condition resolution, effective address computation.
  4. `MEM` (Memory Access): L1/L2 cache reads and writes.
  5. `WB` (Write Back): Commits results to the register file and retires instructions.
- **Execution Invariant:** Evaluated in reverse order (`WB → MEM → EX → ID → IF`) on every clock tick.
- **Data Hazards & Forwarding:**
  - Hazard Detection Unit detects RAW (Read-After-Write) dependencies.
  - Load-Use Hazard Detection: Automatically inserts 1-cycle `NOP` bubble if an instruction consumes the result of an immediately preceding `LW`.
  - Data Forwarding Paths: Bypasses data from `EX/MEM` and `MEM/WB` pipeline registers back to `ID/EX`.
- **Control Hazards & Speculative Rollback:**
  - Branch mispredictions detected in `EX` trigger an immediate squash of instructions in `IF` and `ID`.
  - Reverts register file to shadow state if speculative instructions modified speculative registers.
  - Speculative memory accesses leave microarchitectural footprints (e.g. warmed L1 lines), faithfully reproducing transient execution behavior.

### 3.7 Simulation Clock & Time-Travel History (`core_engine/clock.py`)
- **`SimulationClock`:** Master driver for clock ticks, CPI/IPC calculation, and retirement metrics.
- **`CycleSnapshot`:** Complete, immutable, frozen dataclass capturing:
  - Global cycle, instructions retired, current CPI, current PC, halted flag.
  - Architectural registers (`regs`) & speculative registers (`spec_regs`).
  - Active instruction state in all 5 pipeline stages (`IF`, `ID`, `EX`, `MEM`, `WB`), stall reasons, and forwarding paths.
  - L1 and L2 cache line states (valid, dirty, tag, set, speculative warming).
  - Bus packets, DMA activity, predictor misprediction count, and memory access telemetry.
- **Time-Travel Buffer:** Uses an internal `deque` storing snapshots. Calling `clock.rewind(steps)` restores the exact register, memory, and pipeline state from cycle $N - k$.

---

## 4. Simulation Scenarios & Game Modes (`modes/`)

All modes inherit from `BaseMode` (`modes/base_mode.py`) and implement a standardized interface: `load_scenario()`, `evaluate_tick()`, `check_victory()`, `on_rewind()`, and `serialize_overlay()`.

| Mode | Identifier | Theme | Core Mechanics & Objectives |
|---|---|---|---|
| **SpectreScope** | `spectrescope` | Hardware Security | Models Spectre v1 bounds-check bypass gadget (`BGE` misprediction + speculative out-of-bounds load + probe array access). Users observe speculative L1 line warming, execute a Flush+Reload timing attack to recover the leaked secret byte, and toggle the `LFENCE` barrier to serialize execution. |
| **Silicon Heist** | `silicon_heist` | Stealth / Control Hazards | Infiltrate secure L1 cache lockers without exceeding the bus noise threshold. Steer execution around alarm traps using branch hazards, and exfiltrate payload via cycle-stealing DMA. |
| **Silicon Deathmatch** | `silicon_deathmatch` | Thermal Survival | Survive 3 workload waves (ALU Storm, Strided Cache Thrashing, Memory Chaos). Cache conflict misses and pipeline stalls generate heat that drains Thermal HP. Users draft architectural upgrades (e.g. upgrading to 4-Way L1, adding a Vapor Chamber). |
| **Silicon Forensic** | `silicon_forensic` | Post-Mortem Debugging | The CPU halted due to a fatal machine-check exception. Users scrub backwards through an immutable crash-dump timeline to identify the exact cycle an invalid dirty tag was committed. |
| **Architect Tycoon** | `architect_tycoon` | SoC Design & Optimization | Configure die area ($\text{mm}^2$), clock speed ($1.0 - 4.5\text{ GHz}$), TDP/power ($\text{W}$), and cache associativity to hit client contract benchmarks under strict budget limits. |
| **Architecture Sandbox** | `sandbox` | Free Play | Free-form exploration of RAW hazards, Booth multiplication, L1/L2 conflict misses, and speculative branch rollback. |

---

## 5. Web GUI Architecture (`web_gui/`)

The web interface is built with Flask and clean vanilla JavaScript / inline SVG, implementing an Impeccable Dark-Graphite design system.

### REST API Endpoints (`web_gui/app.py`)
- `GET /`: Serves `index.html`.
- `GET /api/state`: Returns full JSON representation of the current `CycleSnapshot`, register table, cache lines, bus packets, and mode-specific overlay telemetry.
- `POST /api/step`: Advances the simulation by $N$ cycles (default: 1). Body: `{"count": 1}`.
- `POST /api/rewind`: Rewinds the simulation by $N$ cycles (default: 1). Body: `{"count": 1}`.
- `POST /api/reset`: Resets the active mode and reloads its initial scenario.
- `POST /api/mode`: Switches the active mode. Body: `{"mode": "<mode_id>"}`.
- `POST /api/action`: Triggers a mode-specific action (e.g., `toggle_lfence`, `flush_reload`, `draft_upgrade`).

### Frontend Visualization Engine (`web_gui/static/app.js`)
- **Pipeline Conveyor (`#pipeline-svg`):** Inline SVG diagram rendering all 5 stages (`IF`, `ID`, `EX`, `MEM`, `WB`) with directional conveyor indicators, status badges (`ACTIVE`, `STALL`, `SPEC`, `BUBBLE`), instruction text, RTN descriptions, and animated dashed cyan forwarding arcs (`stroke-dasharray: 5 3`).
- **Cache Matrix:** Visual grid showing L1 and L2 cache sets, lines, tags, valid/dirty bits, and red alerts for speculatively warmed lines (`L1-WARM!`).
- **System Bus Fabric (`#bus-svg`):** Node-graph representation of CPU, caches, DMA, and memory with animated 60 FPS packet particles running via `requestAnimationFrame`.
- **Mission Control HUD:** Dynamically updates mode-specific controls, sliders, and progress indicators depending on the active scenario.

---

## 6. Design System (`DESIGN.md`)

- **Palette:** Dark graphite surfaces (`--bg-root: #0b0f16`, `--bg-panel: #121822`, `--bg-card: #18202c`, `--border: #263244`).
- **Hardware Semantics:**
  - `--cyan (#22d3ee)`: Active `IF`/`ID` stages, forwarding arcs (`FWD`), focus rings.
  - `--emerald (#34d399)`: Committed `EX`/`MEM`/`WB` stages, cache hits, register writes, mission pass.
  - `--amber (#f59e0b)`: Speculative execution (`SPEC`), shadow registers, memory writes.
  - `--crimson (#f43f5e)`: Stalls/bubbles, `FLUSH`, speculatively warmed L1 lines (`L1-WARM!`), interrupts.
  - `--magenta (#e879f9)`: Active cycle-stealing DMA transfers.
  - `--violet (#a78bfa)`: Multi-cycle ALU operations (`MUL`/`DIV`).
- **Typography:** Modern UI sans-serif for labels; tabular monospaced fonts (`Cascadia Mono`, `Consolas`) with `font-variant-numeric: tabular-nums` for cycle counts, hex addresses, and telemetry values.

---

## 7. Developer Workflow & Commands

### Virtual Environment Setup
```bash
# Windows PowerShell
.\.venv\Scripts\activate

# Install dependencies if needed
pip install -r requirements.txt
```

### Running the Web GUI
```bash
# Launch Flask workbench on http://127.0.0.1:5000
python main.py

# Optional CLI flags:
python main.py --host 127.0.0.1 --port 5000 --no-browser
```

### Running the Test Suite
The test suite consists of 14 unit and integration tests verifying MVC boundaries, arithmetic algorithms, pipeline hazards, speculative execution, and all 5 modes:
```bash
.\.venv\Scripts\pytest -v
```

### Generating Documentation & Diagrams
```bash
python docs_gen/generate_diagrams.py
python docs_gen/build_exhaustive_word_report.py
```

---

## 8. Critical Architectural Invariants

When adding features or refactoring code in SiliconTree, adhere strictly to the following rules:

1. **Strict MVC Separation:** Never import Flask, Pygame, or any UI/DOM logic inside `core_engine/` or `modes/`. The core engine must remain 100% headless, deterministic, and testable via pure Python datastructures.
2. **Reverse Stage Ordering:** In `core_engine/pipeline.py`, always process stages from output to input (`WB → MEM → EX → ID → IF`). Evaluating stages forward causes stage registers to overwrite data that downstream stages have not yet consumed within the same cycle.
3. **Immutable Snapshots:** Data stored in `CycleSnapshot` must be frozen tuples and mappings (`MappingProxyType`). Never mutate a snapshot after creation, as time-travel rewind and forensic analysis depend on absolute snapshot integrity.
4. **Speculative Containment:** Speculative instructions must not alter architectural memory or committed register state. Architectural commit only occurs when an instruction successfully reaches `WB` without being squashed.
