"""Generate additional high-resolution technical diagrams for the comprehensive SiliconTree report."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
# Diagram 8: RISC Instruction Format & 32-Bit Bitfield Encodings
# ==============================================================================
def make_diagram8():
    fig, ax = plt.subplots(figsize=(12, 5.8), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 94, "SiliconTree 32-Bit RISC Instruction Word Formats & Bitfields", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=CYAN)
    ax.text(50, 89, "Standardized Fixed-Width 32-Bit Encodings Across 6 Functional Classes", 
            ha="center", va="center", fontsize=9.5, color=TEXT_MUTED)

    formats = [
        ("R-Type (Arithmetic/Logic)", "ADD, SUB, AND, OR, XOR, SLT, SLL, SRL, MUL, DIV", [
            ("Opcode [31:26] (6b)", 20, CYAN),
            ("rd [25:21] (5b)", 16, EMERALD),
            ("rs1 [20:16] (5b)", 16, AMBER),
            ("rs2 [15:11] (5b)", 16, VIOLET),
            ("shamt [10:6] (5b)", 12, TEXT_MUTED),
            ("funct [5:0] (6b)", 14, TEXT_WHITE),
        ], 74),
        ("I-Type (Immediate ALU)", "ADDI, ANDI, ORI, XORI, SLTI, SLLI, SRLI", [
            ("Opcode [31:26] (6b)", 20, CYAN),
            ("rd [25:21] (5b)", 16, EMERALD),
            ("rs1 [20:16] (5b)", 16, AMBER),
            ("Immediate Value [15:0] (16-bit signed/unsigned)", 42, TEXT_WHITE),
        ], 55),
        ("Memory Access (Load/Store)", "LW, LB, SW, SB  ·  Effective Addr = Reg[rs1] + SignExt(imm)", [
            ("Opcode [31:26] (6b)", 20, CYAN),
            ("rd / rs2 [25:21] (5b)", 18, EMERALD),
            ("base rs1 [20:16] (5b)", 18, AMBER),
            ("Memory Byte Offset [15:0] (16-bit signed offset)", 38, TEXT_WHITE),
        ], 36),
        ("Branch & Jump (Control Flow)", "BEQ, BNE, BLT, BGE, JMP, JAL  ·  PC-Relative / Absolute Target", [
            ("Opcode [31:26] (6b)", 20, CYAN),
            ("rs1 [25:21] (5b)", 16, AMBER),
            ("rs2 [20:16] (5b)", 16, VIOLET),
            ("Target Address / Offset [15:0] (16-bit)", 42, CRIMSON),
        ], 17),
    ]

    for title, ops, fields, y_pos in formats:
        ax.text(6, y_pos + 6.5, title, fontsize=9.5, fontweight="bold", color=TEXT_WHITE)
        ax.text(38, y_pos + 6.5, f"({ops})", fontsize=7.5, color=TEXT_MUTED)

        cur_x = 6
        for f_label, f_width, f_col in fields:
            box = patches.FancyBboxPatch((cur_x, y_pos - 4.5), f_width - 1, 9, boxstyle="round,pad=0.4",
                                         facecolor=CARD_DARK, edgecolor=f_col, linewidth=1.2)
            ax.add_patch(box)
            ax.text(cur_x + (f_width - 1)/2, y_pos, f_label, ha="center", va="center", 
                    fontsize=7.2, fontweight="bold", color=f_col)
            cur_x += f_width

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig8_isa_encoding.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 9: Hazard Detection & Forwarding Multiplexer Matrix
# ==============================================================================
def make_diagram9():
    fig, ax = plt.subplots(figsize=(12, 5.4), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 94, "Hazard Detection & Forwarding Unit Multiplexer Control Matrix", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=CYAN)
    ax.text(50, 89, "Exact Boolean Combinational Equations Evaluated in ID and EX Stages", 
            ha="center", va="center", fontsize=9.5, color=TEXT_MUTED)

    # Table of Forwarding Rules
    rules = [
        ("EX/MEM Hazard\n(ALU -> ALU Bypass)", "EX_MEM.RegWrite and (EX_MEM.rd != 0)\nand (EX_MEM.rd == ID_EX.rs1)", "ForwardA = 2'b10\n(Mux selects EX/MEM ALU Result)", "0 Stalls\n(Full Speed)", EMERALD),
        ("MEM/WB Hazard\n(Memory -> ALU Bypass)", "MEM_WB.RegWrite and (MEM_WB.rd != 0)\nand (MEM_WB.rd == ID_EX.rs1)\nand not (EX/MEM Hazard on rs1)", "ForwardA = 2'b01\n(Mux selects MEM/WB Loaded/ALU Data)", "0 Stalls\n(Full Speed)", CYAN),
        ("Load-Use Hazard\n(Memory Read Delay)", "ID_EX.is_load and (ID_EX.rd != 0)\nand ((ID_EX.rd == IF_ID.rs1) or (ID_EX.rd == IF_ID.rs2))", "Inject 1 Bubble (ID_EX = NOP)\nStall IF_ID latch & PC counter", "1 Bubble Cycle\n(Required)", AMBER),
        ("LFENCE Barrier Hazard\n(Speculation Serialize)", "lfence_enforced and has_unresolved_branch_ahead()\nor (IF_ID.opcode == LFENCE and branch_ahead)", "Stall ID decode stage;\nDo not issue younger speculative ops", "Dynamic Wait\n(Until branch MEM)", CRIMSON),
        ("No Hazard\n(Register File Path)", "No register conflict detected", "ForwardA = 2'b00\n(Mux selects Register File Output)", "0 Stalls", TEXT_WHITE),
    ]

    table_data = [[r[0], r[1], r[2], r[3]] for r in rules]
    table = ax.table(cellText=table_data, 
                     colLabels=["Hazard Condition", "Boolean Detection Logic", "Multiplexer Action / Latch Control", "Pipeline Impact"],
                     cellLoc="left", loc="center", 
                     colColours=[PANEL_DARK, PANEL_DARK, PANEL_DARK, PANEL_DARK])
    table.auto_set_font_size(False)
    table.set_fontsize(7.8)
    table.scale(1.0, 1.95)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER)
        if row == 0:
            cell.set_text_props(color=CYAN, weight="bold")
            cell.set_facecolor(CARD_DARK)
        else:
            cell.set_facecolor(PANEL_DARK)
            cell.set_text_props(color=TEXT_WHITE)
            if col == 3:
                txt = table_data[row-1][3]
                c = CRIMSON if "Bubble" in txt or "Dynamic" in txt else (EMERALD if "Full" in txt else TEXT_WHITE)
                cell.set_text_props(color=c, weight="bold")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig9_hazard_forwarding_truth_table.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 10: Spectre v1 Microarchitectural Timeline State
# ==============================================================================
def make_diagram10():
    fig, ax = plt.subplots(figsize=(12, 6.0), dpi=300)
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 95, "Spectre v1 Attack Timeline: Architectural vs Microarchitectural State Divergence", 
            ha="center", va="center", fontsize=13.5, fontweight="bold", color=CRIMSON)
    ax.text(50, 90, "Why Architectural Rollback Fails to Erase Microarchitectural SRAM Cache Footprints", 
            ha="center", va="center", fontsize=9.2, color=TEXT_MUTED)

    phases = [
        ("Cycle 1 - 4: Training", "Branch predictor trained\non valid in-bounds inputs;\nCounter saturated to WT/ST.", CYAN, 12),
        ("Cycle 5: Stalled Branch", "Untrusted index > bound.\nBranch waiting on DRAM.\nCPU speculates ahead!", AMBER, 35),
        ("Cycle 6 - 8: Leak & Warm", "Speculative LW reads secret byte.\nProbe LW warms L1 line 0x0940!\nspec_regs updated temporarily.", CRIMSON, 62),
        ("Cycle 9+: Rollback & Recovery", "Branch mispredict detected!\nspec_regs discarded (R4=0, R6=0).\nBUT L1 LINE 0x0940 REMAINS WARM!", VIOLET, 88),
    ]

    for p_title, p_desc, col, cx in phases:
        b = patches.FancyBboxPatch((cx - 10, 52), 20, 32, boxstyle="round,pad=0.8",
                                   facecolor=CARD_DARK, edgecolor=col, linewidth=1.8)
        ax.add_patch(b)
        ax.text(cx, 78, p_title, ha="center", va="center", fontsize=8.2, fontweight="bold", color=col)
        ax.text(cx, 64, p_desc, ha="center", va="center", fontsize=7.2, color=TEXT_WHITE, linespacing=1.3)

    for i in range(3):
        x1 = phases[i][3] + 10.5
        x2 = phases[i+1][3] - 10.5
        ax.annotate("", xy=(x2, 68), xytext=(x1, 68), 
                    arrowprops=dict(arrowstyle="->", color=TEXT_MUTED, lw=2, shrinkA=1, shrinkB=1))

    # Architectural State vs Microarchitectural State Divergence Comparison
    comp_box = patches.FancyBboxPatch((6, 10), 88, 34, boxstyle="round,pad=1",
                                      facecolor=PANEL_DARK, edgecolor=BORDER, linewidth=1.5)
    ax.add_patch(comp_box)

    ax.text(12, 38, "POST-ROLLBACK STATE DIVERGENCE (CYCLE 10)", fontsize=10.5, fontweight="bold", color=TEXT_WHITE)
    
    # Left: Architectural
    ax.text(12, 31, "Architectural Register State (Cleanly Restored):", fontsize=8.5, fontweight="bold", color=EMERALD)
    ax.text(12, 25, "· R4 (Secret Destination) = 0x00000000  [No architectural leak!]\n"
                    "· R6 (Probe Destination)  = 0x00000000  [No architectural leak!]\n"
                    "· Architectural Program Counter redirected to safe_exit handler", 
            fontsize=7.8, color=TEXT_MUTED, linespacing=1.3)

    # Right: Microarchitectural
    ax.text(54, 31, "Microarchitectural Cache State (Leaked Side-Channel):", fontsize=8.5, fontweight="bold", color=CRIMSON)
    ax.text(54, 25, "· L1 Cache Line 0x0940: VALID = 1, SPEC_WARM = 1  [WARMED!]\n"
                    "· Attacker probes Array[5*64] -> Latency = 1 Cycle (L1 Hit)\n"
                    "· Attacker probes Array[other] -> Latency = 13 Cycles (DRAM Miss)\n"
                    "· Secret Value '5' Extracted with 100% Deterministic Accuracy!", 
            fontsize=7.8, color=TEXT_WHITE, linespacing=1.3)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig10_spectre_timeline_state.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

# ==============================================================================
# Diagram 11: AMAT (Average Memory Access Time) & Cache Sensitivity
# ==============================================================================
def make_diagram11():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.0), dpi=300, facecolor=BG_DARK)

    # Left: AMAT vs Miss Rate for varying DRAM latencies
    ax1.set_facecolor(PANEL_DARK)
    miss_rates = np.linspace(0.0, 0.40, 50)
    # AMAT = HitTime (1) + MissRate * DRAM_Latency
    amat_fast = 1.0 + miss_rates * 8    # 8-cycle DRAM
    amat_med = 1.0 + miss_rates * 16    # 16-cycle DRAM
    amat_slow = 1.0 + miss_rates * 32   # 32-cycle DRAM

    ax1.plot(miss_rates * 100, amat_fast, color=EMERALD, linewidth=2.2, label="Fast DRAM (8c Latency)")
    ax1.plot(miss_rates * 100, amat_med, color=CYAN, linewidth=2.2, label="Standard DRAM (16c Latency)")
    ax1.plot(miss_rates * 100, amat_slow, color=CRIMSON, linewidth=2.2, label="Slow DRAM (32c Latency)")
    ax1.axvline(5.0, color=AMBER, linestyle="--", linewidth=1.2, label="Target L1 Miss Rate (<5%)")

    ax1.set_title("Average Memory Access Time (AMAT) vs Miss Rate\nAMAT = t_hit + (Miss_Rate * t_dram)", 
                  fontsize=10.5, fontweight="bold", color=TEXT_WHITE, pad=12)
    ax1.set_xlabel("L1 Cache Miss Rate (%)", fontsize=9, color=TEXT_WHITE)
    ax1.set_ylabel("AMAT (Effective Clock Cycles)", fontsize=9, color=TEXT_WHITE)
    ax1.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax1.spines.values():
        spine.set_color(BORDER)
    ax1.legend(loc="upper left", facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    # Right: Miss Rate breakdown across Cache Associativity
    ax2.set_facecolor(PANEL_DARK)
    associativities = ["1-Way (DM)", "2-Way", "4-Way", "8-Way", "Fully-Assoc"]
    compulsory = [2.0, 2.0, 2.0, 2.0, 2.0]
    conflict = [18.5, 6.2, 1.4, 0.3, 0.0]
    capacity = [4.5, 4.0, 3.8, 3.8, 3.8]

    x = np.arange(len(associativities))
    width = 0.55

    b1 = ax2.bar(x, compulsory, width, label="Compulsory Misses", color=CYAN, edgecolor=BORDER)
    b2 = ax2.bar(x, capacity, width, bottom=compulsory, label="Capacity Misses", color=AMBER, edgecolor=BORDER)
    bottom_c = np.array(compulsory) + np.array(capacity)
    b3 = ax2.bar(x, conflict, width, bottom=bottom_c, label="Conflict Misses", color=CRIMSON, edgecolor=BORDER)

    ax2.set_title("Cache 3Cs Miss Decomposition vs Associativity\n4-Way Eliminates ~93% of Conflict Misses", 
                  fontsize=10.5, fontweight="bold", color=TEXT_WHITE, pad=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(associativities, color=TEXT_WHITE, fontsize=8.5)
    ax2.set_ylabel("Total Miss Rate (%)", fontsize=9, color=TEXT_WHITE)
    ax2.tick_params(colors=TEXT_MUTED, labelsize=8)
    for spine in ax2.spines.values():
        spine.set_color(BORDER)
    ax2.legend(loc="upper right", facecolor=CARD_DARK, edgecolor=BORDER, labelcolor=TEXT_WHITE, fontsize=8)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig11_amat_cache_curves.png", dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    make_diagram8()
    make_diagram9()
    make_diagram10()
    make_diagram11()
    print("Additional 4 diagrams (Fig 8-11) generated successfully in", OUT_DIR)

