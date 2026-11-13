# SiliconTree — Interactive Computer Architecture & Hardware Security Simulation Suite

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Web_GUI-Flask_3.1-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-14%20Passed-brightgreen.svg)]()

**SiliconTree** is an interactive, cycle-accurate Computer Architecture & Hardware Security simulation suite built in pure Python. It combines a strict-MVC hardware simulation engine with an **Impeccable Dark-Graphite Flask Web Workbench** and an interactive **Pygame-CE GUI**.

It models pipelined CPU execution, arithmetic algorithms, cache hierarchy, bus arbitration, and hardware vulnerability analysis (e.g. speculative side channels like Spectre v1) with 1-click cycle time-travel and forensic timeline scrubbing.

---

## 🌟 Key Highlights

- **Strict MVC Decoupling:** `core_engine/` contains zero web/GUI imports. The presentation layers strictly consume and render serialized immutable snapshots (`CycleSnapshot`).
- **Reverse-Order Pipeline Execution:** Evaluates stages in reverse order (`WB → MEM → EX → ID → IF`) on every clock tick, preventing stage latches from overwriting unconsumed data within the same clock cycle.
- **Immutable Time-Travel Snapshots:** Every call to `clock.step_cycle()` records an immutable snapshot, enabling exact cycle rewinds (`-1 Cyc`), reset, and post-mortem crash scrubbing.
- **Dual GUI Support:**
  - **Flask Web Workbench (`web_gui/`):** Clean inline-SVG pipeline conveyor, set-associative cache matrix, animated bus packets, register table, and mode-specific mission control HUDs.
  - **Desktop Pygame GUI (`gui/`):** 60 FPS conveyor with forwarding arcs, live telemetry, and control deck.

---

## 🏗️ Architecture & Modules

```
SiliconTree/
├── main.py                     # Primary entry point: launches Flask GUI on 127.0.0.1:5000
├── requirements.txt            # flask, pygame-ce, pygame-gui
├── DESIGN.md                   # Impeccable dark-graphite workbench design specifications
├── report.md                   # Comprehensive technical architectural documentation
├── core_engine/                # Pure-Python hardware simulation model
│   ├── isa.py                  # 32-bit RISC ISA, two-pass assembler, and RTN generator
│   ├── alu.py                  # Booth multiplication, bit-pair recoding, restoring/non-restoring div
│   ├── memory.py               # SRAM L1/L2 caches (direct-mapped & N-way LRU), DRAM, Flush+Reload
│   ├── branch_predictor.py     # Static & 2-bit saturating counter (SNT/WNT/WT/ST) + BTB
│   ├── bus_io.py               # Single/Multi-bus arbitration, DMA cycle-stealing, and IRQs
│   ├── pipeline.py             # 5-stage pipeline, RAW hazards, forwarding, speculative rollback
│   └── clock.py                # SimulationClock, CPI tracking, and immutable CycleSnapshot deque
├── modes/                      # Interactive simulation scenarios & game modes
│   ├── base_mode.py            # Abstract BaseMode & ModeOutcome interface
│   ├── spectrescope.py         # Mode 1: SpectreScope (speculative leak detector & LFENCE)
│   ├── silicon_heist.py        # Mode 2: Silicon Heist (stealth L1 lockers & DMA escape)
│   ├── silicon_deathmatch.py   # Mode 3: Silicon Deathmatch (thermal survival & hardware drafting)
│   ├── silicon_forensic.py     # Mode 4: Silicon Forensic (crash-dump timeline scrubber)
│   └── architect_tycoon.py     # Mode 5: Architect Tycoon (die area/power budgeting & client contracts)
├── scenarios/                  # JSON scenarios for all modes
├── web_gui/                    # Flask presentation layer & interactive SVG workbench
│   ├── app.py                  # Flask routes & simulation session manager
│   ├── templates/index.html    # Workbench responsive layout
│   └── static/                 # styles.css & app.js (60 FPS SVG animation engine)
├── gui/                        # Pygame-CE desktop GUI fallback
└── tests/                      # Automated test suite (14 unit/integration tests)
```

---

## 🎮 The 5 Simulation Modes

### 1. SpectreScope (`Mode 1 // Security`)
- **Vulnerability:** Executes a Spectre v1 bounds-check bypass gadget (`BGE` misprediction + speculative load + scaled probe load).
- **Features:** Real-time red alert when an out-of-bounds speculative load warms an L1 cache line, interactive **Flush+Reload** cycle timer bar recovering the leaked byte, and an **`LFENCE`** barrier toggle to serialize speculative execution.

### 2. Silicon Heist (`Mode 2 // Stealth`)
- **Objective:** Infiltrate hardware and touch secret L1 cache lockers without triggering alarm addresses or exceeding the stealth noise threshold.
- **Escape:** Initiate a **cycle-stealing DMA** transfer to exfiltrate the payload while keeping the CPU data bus arbitrated.

### 3. Silicon Deathmatch (`Mode 3 // Survival`)
- **Challenge:** Survive 3 workload waves (ALU Storm, Strided Cache Thrashing, Memory Chaos) without thermal meltdown.
- **Upgrades:** Conflict misses and pipeline stalls drain Thermal HP. Draft architectural upgrades between waves (e.g. upgrading Direct-Mapped L1 to **4-Way Set-Associative** or installing a **Vapor-Chamber Cooling Sink**).

### 4. Silicon Forensic (`Mode 4 // Forensics`)
- **Investigation:** A fatal exception halted the processor. Scrub backwards through the pre-populated crash dump timeline to pinpoint the exact cycle where a corrupted dirty L1 tag was committed.

### 5. Architect Tycoon (`Mode 5 // SoC Design`)
- **Optimization:** Balance die area ($\text{mm}^2$), clock speed ($1.0 - 4.5\text{ GHz}$), dynamic power dissipation ($\text{W}$), and cache associativity to fulfill client benchmark contracts under strict budget limits.

### + Architecture Sandbox (`Free Play`)
- Interactive free-play sandbox showcasing RAW data hazards (ALU forwarding and Load-Use bubbles), Booth multiplication, L1/L2 conflict misses, and speculative branch rollback.

---

## 🚀 Quick Start

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/BlueSilverEmperor/SiliconTree.git
cd SiliconTree

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch the Flask Web Workbench

```bash
python main.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🧪 Running Automated Tests

Run the complete 14-test suite covering core engine math, pipeline hazards, speculative rollback, time-travel rewind, and all 5 modes:

```bash
pytest tests -v
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

