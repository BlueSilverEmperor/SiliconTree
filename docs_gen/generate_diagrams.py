"""Generate high-resolution architecture diagrams and charts for the SiliconTree Word report."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Visual styling
BG_DARK = "#0B0F16"
PANEL_DARK = "#121822"
CARD_DARK = "#18202C"
CYAN = "#22D3EE"
EMERALD = "#34D399"
AMBER = "#F59E0B"
CRIMSON = "#F43F5E"
VIOLET = "#A78BFA"
TEXT_WHITE = "#E6EDF7"
TEXT_MUTED = "#98ABC4"
BORDER = "#263244"

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Segoe UI"]

# ==============================================================================
# Diagram 1: Overall System Architecture (Strict MVC Decoupling)
# ==============================================================================
def make_diagram1():
    fig, ax = plt.subplots(figsize=(12, 6.8), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Title
    ax.text(50, 96, "SiliconTree High-Level Architecture & Strict MVC Decoupling", 
            ha="center", va="center", fontsize=15, fontweight="bold", color=CYAN)
    ax.text(50, 92, "Unidirectional Dataflow with Immutable CycleSnapshot State Isolation", 
            ha="center", va="center", fontsize=10, color=TEXT_MUTED)

    # Box 1: Core Engine (Model)
    rect1 = patches.FancyBboxPatch((4, 18), 34, 70, boxstyle="round,pad=1.5", 
                                  facecolor=PANEL_DARK, edgecolor=CYAN, linewidth=2)
    ax.add_patch(rect1)
    ax.text(21, 84, "CORE ENGINE (MODEL)", ha="center", va="center", fontsize=12, fontweight="bold", color=CYAN)
    ax.text(21, 80, "Pure Python 3.11+ · Zero GUI Imports", ha="center", va="center", fontsize=8.5, color=TEXT_MUTED)

    engine_items = [
        ("isa.py", "RISC ISA, Assembler & RTN Generator"),
        ("alu.py", "Booth MUL, Bit-Pair, Restoring/Non-Restoring DIV"),
        ("memory.py", "L1/L2 Direct-Mapped/N-Way LRU Cache & DRAM"),
        ("branch_predictor.py", "Static & 2-Bit Saturating FSM + BTB"),
        ("bus_io.py", "Single/Multi-Bus, DMA Cycle-Steal, IRQ"),
        ("pipeline.py", "5-Stage Reverse Pipeline (WB->MEM->EX->ID->IF)"),
        ("clock.py", "SimulationClock & CycleSnapshot History"),
    ]
    for i, (fn, desc) in enumerate(engine_items):
        y = 73 - i * 7.5
        box = patches.FancyBboxPatch((6, y - 2.8), 30, 5.5, boxstyle="round,pad=0.5", 
                                     facecolor=CARD_DARK, edgecolor=BORDER, linewidth=1)
        ax.add_patch(box)
        ax.text(8, y + 0.3, fn, ha="left", va="center", fontsize=8.5, fontweight="bold", color=EMERALD)
        ax.text(8, y - 1.5, desc, ha="left", va="center", fontsize=7.2, color=TEXT_MUTED)

    # Box 2: Modes & Scenarios (Controller)
    rect2 = patches.FancyBboxPatch((42, 18), 26, 70, boxstyle="round,pad=1.5", 
                                  facecolor=PANEL_DARK, edgecolor=VIOLET, linewidth=2)
    ax.add_patch(rect2)
    ax.text(55, 84, "MODES / CONTROLLER", ha="center", va="center", fontsize=12, fontweight="bold", color=VIOLET)
    ax.text(55, 80, "Hardware Scenarios & Game Loops", ha="center", va="center", fontsize=8.5, color=TEXT_MUTED)

    modes_items = [
        ("SpectreScope", "Speculative Leak & LFENCE Barrier", CRIMSON),
        ("Silicon Heist", "L1 Locker Stealth & DMA Escape", VIOLET),
        ("Silicon Deathmatch", "Thermal HP & Hardware Drafting", AMBER),
        ("Silicon Forensic", "Timeline Scrubber & Dirty Tags", CYAN),
        ("Architect Tycoon", "SoC Area/Power & Benchmark Evaluation", EMERALD),
        ("Architecture Sandbox", "Free-Play Pipeline & Hazard Lab", TEXT_WHITE),
    ]
    for i, (mn, desc, col) in enumerate(modes_items):
        y = 72 - i * 9.2
        box = patches.FancyBboxPatch((44, y - 3.4), 22, 6.8, boxstyle="round,pad=0.5", 
                                     facecolor=CARD_DARK, edgecolor=BORDER, linewidth=1)
        ax.add_patch(box)
        ax.text(46, y + 0.6, mn, ha="left", va="center", fontsize=8.5, fontweight="bold", color=col)
        ax.text(46, y - 1.6, desc, ha="left", va="center", fontsize=7.2, color=TEXT_MUTED)

    # Box 3: Presentation Layers (View)
    rect3 = patches.FancyBboxPatch((72, 18), 24, 70, boxstyle="round,pad=1.5", 
                                  facecolor=PANEL_DARK, edgecolor=EMERALD, linewidth=2)
    ax.add_patch(rect3)
    ax.text(84, 84, "PRESENTATION (VIEW)", ha="center", va="center", fontsize=12, fontweight="bold", color=EMERALD)
    ax.text(84, 80, "Strict Read-Only Renderers", ha="center", va="center", fontsize=8.5, color=TEXT_MUTED)

    view_boxes = [
        ("Flask Web Workbench", "web_gui/\n· Inline SVG Pipeline Conveyor\n· Set-Associative Cache Matrix\n· Animated Bus & Packet Dots\n· Live Register File (R0-R15)\n· Dynamic Mission Control HUD", CYAN),
        ("Pygame-CE Desktop GUI", "gui/\n· 60 FPS Desktop AppWindow\n· pygame-gui Control Deck\n· Interpolated Bus Animation\n· Time-Travel Scrubber Bar", EMERALD),
    ]
    for i, (vn, bullets, col) in enumerate(view_boxes):
        y = 66 - i * 27
        box = patches.FancyBboxPatch((74, y - 11), 20, 22, boxstyle="round,pad=0.8", 
                                     facecolor=CARD_DARK, edgecolor=BORDER, linewidth=1)
        ax.add_patch(box)
        ax.text(76, y + 8, vn, ha="left", va="center", fontsize=9, fontweight="bold", color=col)
        ax.text(76, y - 2, bullets, ha="left", va="center", fontsize=7.2, color=TEXT_MUTED, linespacing=1.3)

    # Dataflow Arcs
    ax.annotate("", xy=(38, 52), xytext=(42, 52), 
                arrowprops=dict(arrowstyle="<->", color=CYAN, lw=2, shrinkA=2, shrinkB=2))
    ax.text(40, 56, "Ticks /\nConfig", ha="center", va="bottom", fontsize=7.5, color=CYAN, fontweight="bold")

    ax.annotate("", xy=(72, 52), xytext=(68, 52), 
                arrowprops=dict(arrowstyle="->", color=EMERALD, lw=2, shrinkA=2, shrinkB=2))
    ax.text(70, 56, "Immutable\nCycleSnapshot", ha="center", va="bottom", fontsize=7.5, color=EMERALD, fontweight="bold")

    # Time-travel rewind feedback loop
    ax.annotate("", xy=(21, 15), xytext=(84, 15),
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.8, linestyle="dashed",
                                connectionstyle="arc3,rad=-0.12"))
    ax.text(52, 9, "1-Click Time Travel: Rewind (-1 Cyc) & Scrub Exact Register/Cache State", 
            ha="center", va="center", fontsize=8.5, fontweight="bold", color=AMBER)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig1_system_architecture.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 2: 5-Stage Reverse Pipelined Datapath & Hazard Resolution
# ==============================================================================
def make_diagram2():
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 95, "5-Stage Reverse-Order RISC Pipeline & Forwarding Bypass Network", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=CYAN)
    ax.text(50, 90, "Evaluation Order: WB -> MEM -> EX -> ID -> IF (Prevents Same-Cycle Latch Overwrites)", 
            ha="center", va="center", fontsize=9.5, color=TEXT_MUTED)

    stages = [
        ("IF", "INSTRUCTION FETCH", "· Fetch instruction from PC\n· 2-Bit Saturating Branch Pred.\n· Advance speculative epoch\n· Bus packet emit (INST_BUS)", CYAN, 12),
        ("ID", "INSTRUCTION DECODE", "· Register File read (R0-R15)\n· Detect RAW Hazards\n· Insert Load-Use NOP bubble\n· LFENCE serialization check", CYAN, 31),
        ("EX", "EXECUTE / ALU", "· 32-bit ALU operation\n· Booth MUL / Non-Restoring DIV\n· Speculative Address Gen (AGU)\n· Forwarding operand muxing", EMERALD, 50),
        ("MEM", "MEMORY ACCESS", "· L1 Cache lookup (1c hit)\n· Miss: DRAM latency stall\n· Speculative warm tracking\n· Resolve branch outcome", EMERALD, 69),
        ("WB", "WRITEBACK", "· Commit to Register File\n· Speculative shadow regs promote\n· Retired instruction count ++\n· CPU HALT termination", VIOLET, 88),
    ]

    for name, title, desc, col, cx in stages:
        box = patches.FancyBboxPatch((cx - 8, 38), 16, 42, boxstyle="round,pad=1", 
                                     facecolor=CARD_DARK, edgecolor=col, linewidth=2)
        ax.add_patch(box)
        hdr = patches.FancyBboxPatch((cx - 7.5, 68), 15, 11, boxstyle="round,pad=0.5", 
                                     facecolor=PANEL_DARK, edgecolor=col, linewidth=1)
        ax.add_patch(hdr)
        ax.text(cx, 75, name, ha="center", va="center", fontsize=13, fontweight="bold", color=col)
        ax.text(cx, 70, title, ha="center", va="center", fontsize=6.8, fontweight="bold", color=TEXT_WHITE)
        ax.text(cx - 6.5, 52, desc, ha="left", va="center", fontsize=7.2, color=TEXT_MUTED, linespacing=1.35)

    # Inter-stage progression arrows (left to right dataflow)
    for i in range(4):
        x1 = stages[i][4] + 8.5
        x2 = stages[i+1][4] - 8.5
        ax.annotate("", xy=(x2, 59), xytext=(x1, 59), 
                    arrowprops=dict(arrowstyle="->", color=TEXT_MUTED, lw=2, shrinkA=1, shrinkB=1))

    # Evaluation Order arrow (Right to Left!)
    ax.annotate("", xy=(12, 83), xytext=(88, 83), 
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=2.5, linestyle="solid", shrinkA=2, shrinkB=2))
    ax.text(50, 86, "REVERSE EVALUATION ORDER (Clock Cycle Step): WB -> MEM -> EX -> ID -> IF", 
            ha="center", va="center", fontsize=9, fontweight="bold", color=AMBER)

    # Forwarding Bypass Arcs
    # MEM -> EX
    ax.annotate("", xy=(50, 36), xytext=(69, 36), 
                arrowprops=dict(arrowstyle="->", color=CYAN, lw=2, linestyle="dashed",
                                connectionstyle="arc3,rad=-0.4"))
    ax.text(59.5, 22, "EX/MEM -> EX Forwarding Bypass (ALU Result)", ha="center", va="center", fontsize=8, color=CYAN, fontweight="bold")

    # WB -> EX
    ax.annotate("", xy=(48, 36), xytext=(88, 36), 
                arrowprops=dict(arrowstyle="->", color=VIOLET, lw=2, linestyle="dashed",
                                connectionstyle="arc3,rad=-0.5"))
    ax.text(68, 12, "MEM/WB -> EX Forwarding Bypass (Loaded Memory Word)", ha="center", va="center", fontsize=8, color=VIOLET, fontweight="bold")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig2_pipeline_stages.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 3: Memory Hierarchy & Cache Microarchitecture
# ==============================================================================
def make_diagram3():
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 95, "SRAM L1/L2 Cache Microarchitecture & Address Decomposition", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=CYAN)
    ax.text(50, 90, "Direct-Mapped & N-Way Set-Associative with Write-Back, LRU, and Speculative Tracking", 
            ha="center", va="center", fontsize=9.5, color=TEXT_MUTED)

    # Address Decomposition Bar
    ax.text(12, 79, "32-Bit Memory Address:", fontsize=9, fontweight="bold", color=TEXT_WHITE)
    
    # Tag
    rect_tag = patches.Rectangle((32, 74), 30, 8, facecolor=CARD_DARK, edgecolor=CYAN, linewidth=1.5)
    ax.add_patch(rect_tag)
    ax.text(47, 78, "TAG BITS [31 : (Index+Offset)]", ha="center", va="center", fontsize=8.5, fontweight="bold", color=CYAN)

    # Index
    rect_idx = patches.Rectangle((62, 74), 20, 8, facecolor=CARD_DARK, edgecolor=EMERALD, linewidth=1.5)
    ax.add_patch(rect_idx)
    ax.text(72, 78, "SET INDEX [s-1 : 6]", ha="center", va="center", fontsize=8.5, fontweight="bold", color=EMERALD)

    # Offset
    rect_off = patches.Rectangle((82, 74), 14, 8, facecolor=CARD_DARK, edgecolor=AMBER, linewidth=1.5)
    ax.add_patch(rect_off)
    ax.text(89, 78, "OFFSET [5:0] (64B)", ha="center", va="center", fontsize=8, fontweight="bold", color=AMBER)

    # Cache Sets Matrix
    cache_bg = patches.FancyBboxPatch((6, 12), 88, 54, boxstyle="round,pad=1", facecolor=PANEL_DARK, edgecolor=BORDER, linewidth=1.5)
    ax.add_patch(cache_bg)
    ax.text(12, 61, "L1 CACHE DIRECTORY & DATA WAYS", fontsize=11, fontweight="bold", color=CYAN)

    headers = ["Set #", "Way 0 Line [V | D | Spec | Tag | Data]", "Way 1 Line [V | D | Spec | Tag | Data]", "LRU Status"]
    col_x = [10, 22, 54, 84]
    for h, x in zip(headers, col_x):
        ax.text(x, 56, h, fontsize=8.5, fontweight="bold", color=TEXT_WHITE)

    rows = [
        ("Set 0", "V: 1 | D: 0 | Spec: 0 | Tag: 0x08 | [Data Words: 64B]", "V: 1 | D: 1 | Spec: 0 | Tag: 0x0A | [Data Words: 64B]", "Way 0 MRU", EMERALD),
        ("Set 1", "V: 1 | D: 0 | Spec: 1 | Tag: 0x24 | [WARMED BY SPEC!]", "V: 0 | D: 0 | Spec: 0 | Tag: 0x00 | [Empty Line]", "Way 1 LRU (Victim)", CRIMSON),
        ("Set 2", "V: 1 | D: 1 | Spec: 0 | Tag: 0x12 | [Dirty Write-Back]", "V: 1 | D: 0 | Spec: 0 | Tag: 0x15 | [Data Words: 64B]", "Way 1 MRU", AMBER),
        ("Set 3", "V: 0 | D: 0 | Spec: 0 | Tag: 0x00 | [Empty Line]", "V: 0 | D: 0 | Spec: 0 | Tag: 0x00 | [Empty Line]", "Way 0 Initial", TEXT_MUTED),
    ]

    for i, (s_lbl, w0, w1, lru, col) in enumerate(rows):
        y = 48 - i * 9
        row_bg = patches.Rectangle((8, y - 3), 84, 7, facecolor=CARD_DARK, edgecolor=col if col != TEXT_MUTED else BORDER, linewidth=1)
        ax.add_patch(row_bg)
        ax.text(col_x[0], y + 0.5, s_lbl, fontsize=8, fontweight="bold", color=CYAN)
        ax.text(col_x[1], y + 0.5, w0, fontsize=7.5, color=col if "WARMED" in w0 else TEXT_WHITE)
        ax.text(col_x[2], y + 0.5, w1, fontsize=7.5, color=TEXT_WHITE if "Data" in w1 else TEXT_MUTED)
        ax.text(col_x[3], y + 0.5, lru, fontsize=7.5, color=TEXT_MUTED)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig3_cache_architecture.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 4: Spectre v1 Speculative Attack & Flush+Reload Timing Chart
# ==============================================================================
def make_diagram4():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), dpi=300, facecolor=BG_DARK)
    
    # Left: Flush+Reload Probe Latency (LFENCE OFF vs ON)
    ax1.set_facecolor(PANEL_DARK)
    slots = [f"Slot {i}" for i in range(8)]
    # With LFENCE OFF: Slot 5 is warm (hit = 1 cycle), others are cold (13 cycles)
    latencies_vuln = [13, 13, 13, 13, 13, 1, 13, 13]
    colors_vuln = [CYAN if lat > 5 else CRIMSON for lat in latencies_vuln]

    bars1 = ax1.bar(slots, latencies_vuln, color=colors_vuln, width=0.55, edgecolor=BORDER, linewidth=1)
    ax1.axhline(5, color=AMBER, linestyle="--", linewidth=1.5, label="L1 Hit Threshold (≤2 cycles)")
    ax1.set_title("Spectre v1 Flush+Reload Latency (LFENCE OFF)\nLeaked Secret Byte = 5 (1 Cycle L1 Hit)", 
                  fontsize=11, fontweight="bold", color=CRIMSON, pad=12)
    ax1.set_ylabel("Access Latency (Clock Cycles)", fontsize=9, color=TEXT_WHITE)
    ax1.set_ylim(0, 16)
    ax1.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax1.spines.values():
        spine.set_color(BORDER)
    ax1.legend(loc="upper right", facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    # Add label over slot 5
    ax1.annotate("LEAKED SECRET!\n1 cycle (L1 Cache Hit)", xy=(5, 1.2), xytext=(5, 7.5),
                 arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.8),
                 ha="center", fontsize=8, fontweight="bold", color=CRIMSON,
                 bbox=dict(boxstyle="round,pad=0.4", facecolor=CARD_DARK, edgecolor=CRIMSON))

    # Right: With LFENCE Mitigation Active
    ax2.set_facecolor(PANEL_DARK)
    latencies_safe = [13, 13, 13, 13, 13, 13, 13, 13]
    ax2.bar(slots, latencies_safe, color=CYAN, width=0.55, edgecolor=BORDER, linewidth=1)
    ax2.axhline(5, color=AMBER, linestyle="--", linewidth=1.5, label="L1 Hit Threshold")
    ax2.set_title("With LFENCE Barrier Active (Safe)\nZero Speculative Cache Warming Across All Slots", 
                  fontsize=11, fontweight="bold", color=EMERALD, pad=12)
    ax2.set_ylabel("Access Latency (Clock Cycles)", fontsize=9, color=TEXT_WHITE)
    ax2.set_ylim(0, 16)
    ax2.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color(BORDER)
    ax2.legend(loc="upper right", facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    ax2.text(3.5, 8, "PROTECTED BY LFENCE\nAll candidate lines cold in DRAM\nSecret remains confidential", 
             ha="center", va="center", fontsize=9, fontweight="bold", color=EMERALD,
             bbox=dict(boxstyle="round,pad=0.5", facecolor=CARD_DARK, edgecolor=EMERALD))

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig4_spectre_timing.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 5: 2-Bit Saturating Branch Predictor State Machine
# ==============================================================================
def make_diagram5():
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 94, "2-Bit Saturating Counter Branch Predictor FSM", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=CYAN)
    ax.text(50, 88, "Hysteresis Prevents Premature Branch Flips on Single Loop Exits", 
            ha="center", va="center", fontsize=9, color=TEXT_MUTED)

    states = [
        ("SNT (00)", "Strongly\nNot Taken", 16, 50, CRIMSON),
        ("WNT (01)", "Weakly\nNot Taken", 38, 50, AMBER),
        ("WT  (10)", "Weakly\nTaken", 62, 50, CYAN),
        ("ST  (11)", "Strongly\nTaken", 84, 50, EMERALD),
    ]

    for code, lbl, cx, cy, col in states:
        circle = patches.Circle((cx, cy), 8, facecolor=CARD_DARK, edgecolor=col, linewidth=2.5)
        ax.add_patch(circle)
        ax.text(cx, cy + 1.5, code, ha="center", va="center", fontsize=9, fontweight="bold", color=col)
        ax.text(cx, cy - 3.5, lbl, ha="center", va="center", fontsize=6.8, color=TEXT_WHITE)

    # Transitions Right (Taken: T)
    for i in range(3):
        x1 = states[i][2] + 8
        x2 = states[i+1][2] - 8
        ax.annotate("", xy=(x2, 54), xytext=(x1, 54), 
                    arrowprops=dict(arrowstyle="->", color=EMERALD, lw=2, shrinkA=1, shrinkB=1))
        ax.text((x1+x2)/2, 58, "Taken (T)", ha="center", va="center", fontsize=7.5, color=EMERALD, fontweight="bold")

    # Transitions Left (Not Taken: NT)
    for i in range(1, 4):
        x1 = states[i][2] - 8
        x2 = states[i-1][2] + 8
        ax.annotate("", xy=(x2, 46), xytext=(x1, 46), 
                    arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=2, shrinkA=1, shrinkB=1))
        ax.text((x1+x2)/2, 42, "Not Taken (NT)", ha="center", va="center", fontsize=7.5, color=CRIMSON, fontweight="bold")

    # Self-loops on SNT and ST
    ax.annotate("NT", xy=(10, 54), xytext=(10, 46),
                arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.8, connectionstyle="arc3,rad=-1.8"),
                ha="center", fontsize=8, color=CRIMSON, fontweight="bold")
    ax.annotate("T", xy=(90, 46), xytext=(90, 54),
                arrowprops=dict(arrowstyle="->", color=EMERALD, lw=1.8, connectionstyle="arc3,rad=-1.8"),
                ha="center", fontsize=8, color=EMERALD, fontweight="bold")

    # Prediction Decision Regions
    pred_nt = patches.Rectangle((6, 18), 42, 14, facecolor=CARD_DARK, edgecolor=CRIMSON, linewidth=1, linestyle="--")
    ax.add_patch(pred_nt)
    ax.text(27, 25, "PREDICTION: PREDICT NOT TAKEN (Counter < 2)", ha="center", va="center", fontsize=8, fontweight="bold", color=CRIMSON)

    pred_t = patches.Rectangle((52, 18), 42, 14, facecolor=CARD_DARK, edgecolor=EMERALD, linewidth=1, linestyle="--")
    ax.add_patch(pred_t)
    ax.text(73, 25, "PREDICTION: PREDICT TAKEN (Counter >= 2)", ha="center", va="center", fontsize=8, fontweight="bold", color=EMERALD)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig5_branch_predictor_fsm.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 6: Booth Multiplication & Non-Restoring Division
# ==============================================================================
def make_diagram6():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.4), dpi=300, facecolor=BG_DARK)

    # Left: Radix-4 Bit-Pair Recoding Table & Algorithm
    ax1.set_facecolor(PANEL_DARK)
    ax1.set_title("Radix-4 Modified Booth (Bit-Pair Recoding)\nHalves Multiply Cycles from 32 to 16", 
                  fontsize=10.5, fontweight="bold", color=CYAN, pad=10)
    ax1.axis("off")

    triples = [
        ("0 0 0", "0", "0 * M (Hold / Shift Only)"),
        ("0 0 1", "+1", "+1 * M (Add Multiplicand)"),
        ("0 1 0", "+1", "+1 * M (Add Multiplicand)"),
        ("0 1 1", "+2", "+2 * M (Shift M left 1, then Add)"),
        ("1 0 0", "-2", "-2 * M (Shift M left 1, then Subtract)"),
        ("1 0 1", "-1", "-1 * M (Subtract Multiplicand)"),
        ("1 1 0", "-1", "-1 * M (Subtract Multiplicand)"),
        ("1 1 1", "0", "0 * M (Hold / Shift Only)"),
    ]

    table_data = [[t[0], t[1], t[2]] for t in triples]
    table = ax1.table(cellText=table_data, colLabels=["Bit Triple (q2i+1, q2i, q2i-1)", "Recoded Digit", "Operation on Accumulator"],
                      cellLoc="center", loc="center", colColours=[CARD_DARK, CARD_DARK, CARD_DARK])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.05, 1.35)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER)
        if row == 0:
            cell.set_text_props(color=CYAN, weight="bold")
            cell.set_facecolor(CARD_DARK)
        else:
            cell.set_facecolor(PANEL_DARK)
            cell.set_text_props(color=TEXT_WHITE)

    # Right: Non-Restoring Division Flow
    ax2.set_facecolor(PANEL_DARK)
    ax2.set_title("Non-Restoring Division Algorithm\nZero Restoration Step on Negative Trial Remainder", 
                  fontsize=10.5, fontweight="bold", color=EMERALD, pad=10)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 100)
    ax2.axis("off")

    flow_steps = [
        ("INITIALIZE", "A = 0, Q = Dividend, M = Divisor", 85, CYAN),
        ("SHIFT LEFT", "Shift (A, Q) left 1 bit position", 68, TEXT_WHITE),
        ("CONDITIONAL ALU", "If A >= 0: A <- A - M\nIf A < 0: A <- A + M", 48, AMBER),
        ("SET QUOTIENT BIT", "If A >= 0: Q0 <- 1\nIf A < 0: Q0 <- 0", 28, EMERALD),
        ("FINAL SIGN RESTORE", "If final A < 0: A <- A + M\nRemainder = A, Quotient = Q", 10, VIOLET),
    ]

    for title, desc, y, col in flow_steps:
        b = patches.FancyBboxPatch((15, y - 6.5), 70, 13, boxstyle="round,pad=0.5", 
                                   facecolor=CARD_DARK, edgecolor=col, linewidth=1.5)
        ax2.add_patch(b)
        ax2.text(50, y + 2, title, ha="center", va="center", fontsize=8.5, fontweight="bold", color=col)
        ax2.text(50, y - 2.5, desc, ha="center", va="center", fontsize=7.2, color=TEXT_MUTED)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig6_alu_booth_division.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 7: Architect Tycoon & Deathmatch Engineering Trade-Offs
# ==============================================================================
def make_diagram7():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.0), dpi=300, facecolor=BG_DARK)

    # Left: Conflict Misses vs Associativity (Deathmatch validation)
    ax1.set_facecolor(PANEL_DARK)
    assoc_labels = ["1-Way (DM)", "2-Way SA", "4-Way SA", "8-Way SA"]
    conflict_misses = [42, 14, 2, 0]
    thermal_dmg = [252.0, 84.0, 12.0, 0.0]

    x = np.arange(len(assoc_labels))
    width = 0.35

    rects1 = ax1.bar(x - width/2, conflict_misses, width, label="Conflict Misses", color=CRIMSON, edgecolor=BORDER)
    rects2 = ax1.bar(x + width/2, thermal_dmg, width, label="Thermal Damage (HP)", color=AMBER, edgecolor=BORDER)

    ax1.set_title("Silicon Deathmatch: Cache Thrashing vs Associativity\nUpgrading to 4-Way Eliminates Meltdown Risk", 
                  fontsize=10.5, fontweight="bold", color=TEXT_WHITE, pad=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(assoc_labels, color=TEXT_WHITE, fontsize=8.5)
    ax1.set_ylabel("Quantity", fontsize=9, color=TEXT_WHITE)
    ax1.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax1.spines.values():
        spine.set_color(BORDER)
    ax1.legend(facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    # Right: Architect Tycoon: Frequency vs Power & Die Area
    ax2.set_facecolor(PANEL_DARK)
    freqs = np.linspace(1.0, 4.5, 30)
    # Area = 26 mm^2 (2-Way) vs 32 mm^2 (4-Way)
    power_2way = (26.0 * 0.14) * (freqs ** 1.35)
    power_4way = (32.0 * 0.14) * (freqs ** 1.35)

    ax2.plot(freqs, power_2way, color=CYAN, linewidth=2.2, label="2-Way Cache (Area: 26.0 mm²)")
    ax2.plot(freqs, power_4way, color=EMERALD, linewidth=2.2, label="4-Way Cache (Area: 32.0 mm²)")
    ax2.axhline(18.0, color=CRIMSON, linestyle="--", linewidth=1.5, label="Max Power Budget (18.0 W)")
    ax2.axvline(2.4, color=AMBER, linestyle=":", linewidth=1.5, label="Optimal Operating Point (2.4 GHz)")

    ax2.set_title("Architect Tycoon: Dynamic Power vs Clock Frequency\nBalancing Die Area & Power Budget Limits", 
                  fontsize=10.5, fontweight="bold", color=TEXT_WHITE, pad=12)
    ax2.set_xlabel("Clock Frequency (GHz)", fontsize=9, color=TEXT_WHITE)
    ax2.set_ylabel("Power Dissipation (Watts)", fontsize=9, color=TEXT_WHITE)
    ax2.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color(BORDER)
    ax2.legend(loc="upper left", facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig7_tycoon_tradeoffs.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    make_diagram1()
    make_diagram2()
    make_diagram3()
    make_diagram4()
    make_diagram5()
    make_diagram6()
    make_diagram7()
    print("All 7 figures generated successfully in", OUT_DIR)
