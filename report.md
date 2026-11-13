# SiliconTree — Architecture & Hardware Security Simulation Suite

**SiliconTree** is a pure-Python **Computer Architecture & Hardware Security** simulation suite. It models a cycle-accurate 5-stage RISC processor, memory/cache hierarchy, branch prediction, system bus/DMA/IRQ fabric, and speculative side-channel behavior, paired with a strict-MVC **Flask** web interface and 5 interactive simulation modes.

---

## 1. Architectural Overview (Strict MVC)

```
SiliconTree/
├── main.py                     # Entry point: launches Flask GUI on 127.0.0.1:5000
├── requirements.txt            # flask, pygame-ce, pygame-gui
├── DESIGN.md                   # Dark-graphite workbench design system
├── core_engine/                # Pure-Python Model (zero GUI/mode imports)
│   ├── isa.py                  # RISC ISA, two-pass assembler, RTN generator
│   ├── alu.py                  # 32-bit ALU: Booth, Bit-Pair, Restoring & Non-Restoring Div
│   ├── memory.py               # L1/L2 Direct-Mapped & N-Way LRU Cache, DRAM, Flush+Reload
│   ├── branch_predictor.py     # Static & 2-bit saturating counter + BTB
│   ├── bus_io.py               # Single vs Multi-Bus arbitration, DMA cycle-stealing, IRQs
│   ├── pipeline.py             # Reverse-order (WB->MEM->EX->ID->IF) 5-stage pipeline
│   └── clock.py                # SimulationClock, CPI metrics, immutable CycleSnapshot deque
├── modes/                      # Controller / Game-Mode Logic
│   ├── base_mode.py            # Abstract BaseMode & ModeOutcome interface
│   ├── spectrescope.py         # Mode 1: Speculative leak detector & LFENCE mitigation
│   ├── silicon_heist.py        # Mode 2: Stealth cache-locker infiltration & DMA escape
│   ├── silicon_deathmatch.py   # Mode 3: Thermal HP wave survival & hardware drafting
│   ├── silicon_forensic.py     # Mode 4: Crash-dump timeline scrubber & dirty-tag forensics
│   └── architect_tycoon.py     # Mode 5: Die area/power budgeter & client benchmarks
├── scenarios/                  # JSON payloads for all 5 modes
└── web_gui/                    # Flask Web View (strictly renders CycleSnapshot JSON)
    ├── app.py                  # Flask routes & SimulationSession serializer
    ├── templates/index.html    # Workbench layout & inline SVG viewports
    └── static/                 # styles.css & app.js (60 FPS requestAnimationFrame loop)
```

### Core Architectural Invariants
1. **Strict MVC Decoupling:** `core_engine/` never imports `flask`, `pygame`, `web_gui/`, or `modes/`. The UI never computes hardware physics, hazards, or cache hits/misses—it only renders serialized `CycleSnapshot` state.
2. **Reverse-Order Pipeline Evaluation:** Every clock tick evaluates stages in reverse order (`WB → MEM → EX → ID → IF`) so stage latches never overwrite unconsumed downstream data within the same cycle.
3. **Immutable Time-Travel Snapshots:** Every `clock.step_cycle()` pushes an immutable `CycleSnapshot` (plus frozen subsystem state) onto a `collections.deque` history buffer, enabling exact `-1 Cyc` rewind and forensic timeline scrubbing.

---

## 2. Core Hardware Engine (`core_engine/`)

- **RISC ISA & Two-Pass Assembler (`isa.py`):**
  - Supports R-type (`ADD`, `SUB`, `AND`, `OR`, `XOR`, `SLT`, `SLL`, `SRL`, `MUL`, `DIV`), I-type (`ADDI`, `ANDI`, `ORI`, `XORI`, `SLTI`, `SLLI`, `SRLI`), Memory (`LW`, `LB`, `SW`, `SB`), Control (`BEQ`, `BNE`, `BLT`, `BGE`, `JMP`, `JAL`), and System/Barriers (`NOP`, `LFENCE`, `HALT`).
  - Supports labels, `.data` / `.word` directives, `;`/`#` comments, and generates Register Transfer Notation (`RTN`) strings for every instruction.
- **Multi-Algorithm ALU (`alu.py`):**
  - Implements signed 2's-complement **Booth's multiplication**, **Radix-4 Bit-Pair recoding**, **Restoring division**, and **Non-Restoring division**, recording step-by-step micro-traces (`BoothStep`, `DivisionStep`).
- **Memory & Cache Hierarchy (`memory.py`):**
  - Configurable `L1` and optional `L2` caches supporting **Direct-Mapped** (`associativity=1`) and **N-Way Set-Associative** (`associativity=2, 4, ...`) with exact LRU replacement, write-back dirty bits, and conflict-miss detection.
  - Tracks `speculative_warm` flags on L1 lines filled during speculative execution—preserving warmed L1 lines after pipeline rollback while preventing speculative stores from corrupting DRAM.
  - Supports `flush_line()` and `probe_reload_time()` for Flush+Reload side-channel timing.
- **Branch Predictor (`branch_predictor.py`):**
  - Supports `STATIC_NOT_TAKEN`, `STATIC_TAKEN`, and `TWO_BIT_SATURATING` (`SNT/WNT/WT/ST`) with a Branch Target Buffer (`BTB`) and pre-training hooks.
- **Bus & I/O Subsystem (`bus_io.py`):**
  - Models `SINGLE_BUS` (I-fetch/Data/DMA contention) vs `MULTI_BUS` (split I/D buses), **cycle-stealing DMA** transfers, prioritized hardware **Interrupts (`IRQ`)**, and `BusPacket` descriptors for animation.
- **5-Stage Pipeline (`pipeline.py`):**
  - Includes `EX→EX` and `MEM→EX` data forwarding bypasses, 1-cycle Load-Use RAW stalls, multi-cycle ALU/cache-miss stalls, `LFENCE` serialization barriers, non-blocking MSHRs, and speculative shadow registers (`spec_regs`) that roll back cleanly on misprediction.

---

## 3. Interactive Simulation Modes (`modes/` & `scenarios/`)

| Mode | File | What It Simulates & Objective |
|---|---|---|
| **1. SpectreScope** | [spectrescope.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/modes/spectrescope.py) | Executes a Spectre v1 bounds-check bypass gadget (`BGE` misprediction + speculative `LW` + `SLLI` + probe `LW`). Shows a **Red Alert** when L1 is speculatively warmed, provides an interactive **Flush+Reload** latency probe recovering the secret byte (`5`), and lets you toggle **`LFENCE`** to serialize speculation, insert stalls, increase CPI, and eliminate the leak. |
| **2. Silicon Heist** | [silicon_heist.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/modes/silicon_heist.py) | Stealth infiltration puzzle. Touch target L1 cache lockers (`0x0300`, `0x0340`) without tripping alarm addresses (`0x0F00`) or exceeding the stealth noise budget, then trigger a **cycle-stealing DMA** escape to exfiltrate the payload to `0x0900`. |
| **3. Silicon Deathmatch** | [silicon_deathmatch.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/modes/silicon_deathmatch.py) | Wave-based thermal survival across 3 escalating workloads (ALU Storm, Strided Cache Thrashing, Branch & Memory Chaos). Conflict misses and stalls drain **Thermal HP**; between waves, draft hardware upgrades (such as upgrading Direct-Mapped L1 to **4-Way Set-Associative** or adding a **Vapor-Chamber Cooling Sink**). |
| **4. Silicon Forensic** | [silicon_forensic.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/modes/silicon_forensic.py) | Pre-loads a crash-dump execution history. Use the **timeline scrubber** to inspect historical `CycleSnapshot` frames, locate the cycle where the corrupted dirty L1 tag (`0x02`) was written, and submit the evidence. |
| **5. Architect Tycoon** | [architect_tycoon.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/modes/architect_tycoon.py) | Tune clock frequency (`1.0–4.5 GHz`), L1 associativity (`1/2/4-Way`), and data forwarding within a strict **Die Area (`mm²`)** and **Power (`W`)** budget, then run the synthetic client benchmark to pass the target effective CPI. |
| **Architecture Sandbox** | [web_gui/app.py](file:///c:/Users/sridh/Desktop/cao_prj/SiliconTree/web_gui/app.py) | Free-play showcase combining RAW hazards, Booth `MUL`, L1/L2 conflict misses, and speculative branch rollback. |

---

## 4. Flask Web GUI & API (`web_gui/`)

- **Workbench Interface (`/`):**
  - Mode switcher tabs, transport controls (`-1 Cyc` rewind, `Play/Pause`, `+1 Cyc` step, `Reset`, `1–20 Hz` speed slider), and live telemetry (`Cycle`, `Retired`, `CPI`, `PC`, `State`).
  - **Inline SVG 5-Stage Pipeline Conveyor** with dashed forwarding arcs and speculative/stall badges.
  - **Interactive L1/L2 Cache Matrix** with click-to-inspect 64-byte word contents.
  - **Inline SVG System Bus & I/O Fabric** with 60 FPS interpolated packet motion.
  - **Register File (`R0`–`R15`) & RTN Micro-Op Log**, plus the dynamic **Mission Control** HUD.
- **JSON API Endpoints:**
  - `GET /api/state`, `POST /api/mode/<mode_id>`, `POST /api/step`, `POST /api/rewind`, `POST /api/reset`
  - Mode actions: `/api/spectre/lfence`, `/api/spectre/probe`, `/api/heist/dma`, `/api/deathmatch/upgrade`, `/api/deathmatch/next_wave`, `/api/forensic/scrub`, `/api/forensic/submit`, `/api/tycoon/configure`, `/api/tycoon/evaluate`.

---

## 5. Verification & Running

- **Test Suite (`14 passed in 1.54s`):**
  - `test_phase1_core.py`: Strict MVC AST import check, Booth/Bit-Pair/Division math, conflict miss vs 2-way L1, DMA cycle-stealing & IRQ, speculative L1 warm + rollback + 3-cycle rewind, Spectre v1 + `LFENCE`.
  - `test_phase2_gui.py`, `test_phase3_spectrescope.py`, `test_phase4_modes.py`, `test_phase5_integration.py`, and `test_flask_gui.py`.
- **Launch Command (from `SiliconTree/`):**
  ```powershell
  python main.py
  ```
  Opens the Flask workbench at `http://127.0.0.1:5000`.

