"""RISC Instruction Set Architecture (ISA), RTN generator, and assembly parser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional


class Opcode(str, Enum):
    """Supported RISC opcodes across arithmetic, memory, branch, and barrier ops."""

    # R-type arithmetic / logic
    ADD = "ADD"
    SUB = "SUB"
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    SLT = "SLT"
    SLL = "SLL"
    SRL = "SRL"
    MUL = "MUL"
    DIV = "DIV"

    # I-type arithmetic / logic
    ADDI = "ADDI"
    ANDI = "ANDI"
    ORI = "ORI"
    XORI = "XORI"
    SLTI = "SLTI"
    SLLI = "SLLI"
    SRLI = "SRLI"

    # Memory access
    LW = "LW"
    LB = "LB"
    SW = "SW"
    SB = "SB"

    # Control flow
    BEQ = "BEQ"
    BNE = "BNE"
    BLT = "BLT"
    BGE = "BGE"
    JMP = "JMP"
    JAL = "JAL"

    # Barriers & system
    NOP = "NOP"
    LFENCE = "LFENCE"
    HALT = "HALT"


R_TYPE_OPCODES = frozenset({
    Opcode.ADD,
    Opcode.SUB,
    Opcode.AND,
    Opcode.OR,
    Opcode.XOR,
    Opcode.SLT,
    Opcode.SLL,
    Opcode.SRL,
    Opcode.MUL,
    Opcode.DIV,
})

I_ALU_OPCODES = frozenset({
    Opcode.ADDI,
    Opcode.ANDI,
    Opcode.ORI,
    Opcode.XORI,
    Opcode.SLTI,
    Opcode.SLLI,
    Opcode.SRLI,
})

LOAD_OPCODES = frozenset({Opcode.LW, Opcode.LB})
STORE_OPCODES = frozenset({Opcode.SW, Opcode.SB})
BRANCH_OPCODES = frozenset({Opcode.BEQ, Opcode.BNE, Opcode.BLT, Opcode.BGE})
JUMP_OPCODES = frozenset({Opcode.JMP, Opcode.JAL})


REG_ALIASES: dict[str, int] = {
    **{f"R{i}": i for i in range(16)},
    **{f"X{i}": i for i in range(16)},
    "ZERO": 0,
    "SP": 14,
    "RA": 15,
}


def reg_name(idx: Optional[int]) -> str:
    """Format a register index as a canonical register name."""
    if idx is None:
        return "R?"
    return f"R{idx}"


@dataclass(frozen=True)
class Instruction:
    """Immutable decoded RISC instruction."""

    pc: int
    opcode: Opcode
    rd: Optional[int] = None
    rs1: Optional[int] = None
    rs2: Optional[int] = None
    imm: int = 0
    label_target: Optional[str] = None
    raw_text: str = ""
    rtn: str = ""


@dataclass(frozen=True)
class AssembledProgram:
    """Assembled instruction stream with resolved labels and initial data words."""

    instructions: tuple[Instruction, ...]
    labels: tuple[tuple[str, int], ...]
    data_words: tuple[tuple[int, int], ...]


def generate_rtn(inst: Instruction) -> str:
    """Generate Register Transfer Notation (RTN) micro-operation string."""
    op = inst.opcode
    rd = reg_name(inst.rd)
    rs1 = reg_name(inst.rs1)
    rs2 = reg_name(inst.rs2)

    rtn_map: dict[Opcode, str] = {
        Opcode.ADD: f"{rd} <- {rs1} + {rs2}",
        Opcode.SUB: f"{rd} <- {rs1} - {rs2}",
        Opcode.AND: f"{rd} <- {rs1} & {rs2}",
        Opcode.OR: f"{rd} <- {rs1} | {rs2}",
        Opcode.XOR: f"{rd} <- {rs1} ^ {rs2}",
        Opcode.SLT: f"{rd} <- ({rs1} < {rs2}) ? 1 : 0",
        Opcode.SLL: f"{rd} <- {rs1} << ({rs2} & 0x1F)",
        Opcode.SRL: f"{rd} <- ({rs1} >> ({rs2} & 0x1F)) [logical]",
        Opcode.MUL: f"{rd} <- BoothMul({rs1}, {rs2})",
        Opcode.DIV: f"{rd} <- NonRestDiv({rs1}, {rs2})",
        Opcode.ADDI: f"{rd} <- {rs1} + {inst.imm}",
        Opcode.ANDI: f"{rd} <- {rs1} & {inst.imm}",
        Opcode.ORI: f"{rd} <- {rs1} | {inst.imm}",
        Opcode.XORI: f"{rd} <- {rs1} ^ {inst.imm}",
        Opcode.SLTI: f"{rd} <- ({rs1} < {inst.imm}) ? 1 : 0",
        Opcode.SLLI: f"{rd} <- {rs1} << {inst.imm & 0x1F}",
        Opcode.SRLI: f"{rd} <- ({rs1} >> {inst.imm & 0x1F}) [logical]",
        Opcode.LW: f"{rd} <- Mem32[{rs1} + {inst.imm}]",
        Opcode.LB: f"{rd} <- Mem8[{rs1} + {inst.imm}]",
        Opcode.SW: f"Mem32[{rs1} + {inst.imm}] <- {rs2}",
        Opcode.SB: f"Mem8[{rs1} + {inst.imm}] <- {rs2}[7:0]",
        Opcode.BEQ: f"if ({rs1} == {rs2}) PC <- 0x{inst.imm:04X}",
        Opcode.BNE: f"if ({rs1} != {rs2}) PC <- 0x{inst.imm:04X}",
        Opcode.BLT: f"if ({rs1} < {rs2}) PC <- 0x{inst.imm:04X}",
        Opcode.BGE: f"if ({rs1} >= {rs2}) PC <- 0x{inst.imm:04X}",
        Opcode.JMP: f"PC <- 0x{inst.imm:04X}",
        Opcode.JAL: f"R15 <- PC + 4; PC <- 0x{inst.imm:04X}",
        Opcode.NOP: "No Operation (Bubble)",
        Opcode.LFENCE: "Serialize Speculation Barrier",
        Opcode.HALT: "CPU <- HALTED",
    }
    return rtn_map.get(op, op.value)


def _parse_reg(token: str) -> int:
    clean = token.strip().upper().lstrip("$")
    if clean not in REG_ALIASES:
        raise ValueError(f"Invalid register '{token}'")
    return REG_ALIASES[clean]


def _parse_imm(token: str, labels: Optional[dict[str, int]] = None) -> int:
    clean = token.strip()
    if labels and clean in labels:
        return labels[clean]
    return int(clean, 0)


def _strip_comment(line: str) -> str:
    for marker in (";", "#"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line.strip()


def _parse_mem_operand(tokens: list[str]) -> tuple[int, int]:
    """Parse either 'offset(base)' or 'base, offset'."""
    if len(tokens) == 1:
        m = re.fullmatch(r"([+-]?(?:0x[0-9a-fA-F]+|\d+))\(([^)]+)\)", tokens[0].strip())
        if not m:
            raise ValueError(f"Invalid memory operand '{tokens[0]}'")
        offset = int(m.group(1), 0)
        base_reg = _parse_reg(m.group(2))
        return base_reg, offset
    if len(tokens) == 2:
        return _parse_reg(tokens[0]), _parse_imm(tokens[1])
    raise ValueError(f"Invalid memory operand tokens: {tokens}")


def assemble_program(source: str, base_addr: int = 0) -> AssembledProgram:
    """Two-pass assembler supporting labels, .data directives, and RISC opcodes."""
    labels: dict[str, int] = {}
    data_words: list[tuple[int, int]] = []
    raw_instructions: list[tuple[int, str]] = []

    section = "text"
    pc = base_addr
    data_ptr = 0x0400

    for raw_line in source.splitlines():
        line = _strip_comment(raw_line)
        if not line:
            continue

        # Support inline labels like "loop: ADD R1, R1, R2"
        while ":" in line:
            label_part, rest = line.split(":", 1)
            label = label_part.strip()
            if not label:
                raise ValueError(f"Empty label in line: {raw_line}")
            labels[label] = data_ptr if section == "data" else pc
            line = rest.strip()
            if not line:
                break

        if not line:
            continue

        lower = line.lower()
        if lower == ".text":
            section = "text"
            continue
        if lower.startswith(".data"):
            section = "data"
            parts = line.split()
            if len(parts) > 1:
                data_ptr = int(parts[1], 0)
            continue
        if section == "data":
            if lower.startswith(".word"):
                vals = [int(v.strip(), 0) for v in line[5:].split(",") if v.strip()]
                for val in vals:
                    data_words.append((data_ptr, val & 0xFFFFFFFF))
                    data_ptr += 4
                continue
            raise ValueError(f"Unsupported directive in .data section: {line}")

        raw_instructions.append((pc, line))
        pc += 4

    instructions: list[Instruction] = []
    for inst_pc, text in raw_instructions:
        inst = _decode_line(inst_pc, text, labels)
        instructions.append(inst)

    return AssembledProgram(
        instructions=tuple(instructions),
        labels=tuple(labels.items()),
        data_words=tuple(data_words),
    )


def parse_assembly(source: str, base_addr: int = 0) -> list[Instruction]:
    """Assemble RISC assembly source into a list of Instruction objects."""
    return list(assemble_program(source, base_addr=base_addr).instructions)


def _decode_line(pc: int, line: str, labels: dict[str, int]) -> Instruction:
    parts = [p.strip() for p in re.split(r"[\s,]+", line.strip()) if p.strip()]
    if not parts:
        raise ValueError(f"Empty instruction at PC 0x{pc:04X}")

    op_str = parts[0].upper()
    try:
        op = Opcode(op_str)
    except ValueError as exc:
        raise ValueError(f"Unknown opcode '{op_str}' at PC 0x{pc:04X}") from exc

    args = parts[1:]
    rd: Optional[int] = None
    rs1: Optional[int] = None
    rs2: Optional[int] = None
    imm = 0
    label_target: Optional[str] = None

    if op in (Opcode.NOP, Opcode.LFENCE, Opcode.HALT):
        if args:
            raise ValueError(f"{op.value} takes no operands, got {args}")
    elif op in R_TYPE_OPCODES:
        if len(args) != 3:
            raise ValueError(f"{op.value} requires 3 registers, got {args}")
        rd = _parse_reg(args[0])
        rs1 = _parse_reg(args[1])
        rs2 = _parse_reg(args[2])
    elif op in I_ALU_OPCODES:
        if len(args) != 3:
            raise ValueError(f"{op.value} requires rd, rs1, imm, got {args}")
        rd = _parse_reg(args[0])
        rs1 = _parse_reg(args[1])
        imm = _parse_imm(args[2], labels)
    elif op in LOAD_OPCODES:
        if len(args) < 2 or len(args) > 3:
            raise ValueError(f"{op.value} requires rd, offset(rs1), got {args}")
        rd = _parse_reg(args[0])
        rs1, imm = _parse_mem_operand(args[1:])
    elif op in STORE_OPCODES:
        if len(args) < 2 or len(args) > 3:
            raise ValueError(f"{op.value} requires rs2, offset(rs1), got {args}")
        rs2 = _parse_reg(args[0])
        rs1, imm = _parse_mem_operand(args[1:])
    elif op in BRANCH_OPCODES:
        if len(args) != 3:
            raise ValueError(f"{op.value} requires rs1, rs2, target, got {args}")
        rs1 = _parse_reg(args[0])
        rs2 = _parse_reg(args[1])
        target_tok = args[2]
        if target_tok in labels:
            label_target = target_tok
            imm = labels[target_tok]
        else:
            imm = int(target_tok, 0)
    elif op in JUMP_OPCODES:
        if len(args) != 1:
            raise ValueError(f"{op.value} requires 1 target, got {args}")
        target_tok = args[0]
        if target_tok in labels:
            label_target = target_tok
            imm = labels[target_tok]
        else:
            imm = int(target_tok, 0)
        if op == Opcode.JAL:
            rd = 15

    base = Instruction(
        pc=pc,
        opcode=op,
        rd=rd,
        rs1=rs1,
        rs2=rs2,
        imm=imm,
        label_target=label_target,
        raw_text=line,
    )
    return Instruction(
        pc=base.pc,
        opcode=base.opcode,
        rd=base.rd,
        rs1=base.rs1,
        rs2=base.rs2,
        imm=base.imm,
        label_target=base.label_target,
        raw_text=base.raw_text,
        rtn=generate_rtn(base),
    )

