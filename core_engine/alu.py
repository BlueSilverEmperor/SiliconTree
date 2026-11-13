"""Arithmetic Logic Unit with Booth multiplication, bit-pair recoding, and restoring/non-restoring division."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core_engine.isa import Opcode


def to_unsigned32(val: int) -> int:
    """Mask integer to 32-bit unsigned representation."""
    return val & 0xFFFFFFFF


def to_signed32(val: int) -> int:
    """Convert 32-bit value to Python signed integer in [-2^31, 2^31 - 1]."""
    masked = val & 0xFFFFFFFF
    if masked & 0x80000000:
        return masked - 0x100000000
    return masked


def _to_signed_n(val: int, bits: int) -> int:
    mask = (1 << bits) - 1
    masked = val & mask
    sign_bit = 1 << (bits - 1)
    if masked & sign_bit:
        return masked - (1 << bits)
    return masked


@dataclass(frozen=True)
class BoothStep:
    """Single iteration of Booth or Bit-Pair multiplication."""

    step_index: int
    a_reg: int
    q_reg: int
    q_minus_1: int
    recoded_digit: Optional[int]
    operation: str
    comment: str


@dataclass(frozen=True)
class BoothResult:
    """Full result and step trace for Booth / Bit-Pair multiplication."""

    multiplicand: int
    multiplier: int
    product_64: int
    product_low32: int
    algorithm: str
    steps: tuple[BoothStep, ...]
    bit_pair_digits: tuple[int, ...]
    cycles_taken: int


@dataclass(frozen=True)
class DivisionStep:
    """Single iteration of restoring or non-restoring division."""

    step_index: int
    a_reg: int
    q_reg: int
    operation: str
    comment: str


@dataclass(frozen=True)
class DivisionResult:
    """Full result and step trace for restoring / non-restoring division."""

    dividend: int
    divisor: int
    quotient: int
    remainder: int
    algorithm: str
    steps: tuple[DivisionStep, ...]
    cycles_taken: int
    divide_by_zero: bool = False


@dataclass(frozen=True)
class ALUResult:
    """Output of a single ALU execution."""

    value: int
    zero: bool
    negative: bool
    cycles_required: int
    booth_trace: Optional[BoothResult] = None
    division_trace: Optional[DivisionResult] = None


class ALU:
    """Pure-Python 32-bit ALU supporting Booth, Bit-Pair, Restoring, and Non-Restoring algorithms."""

    def __init__(self, mul_algo: str = "booth", div_algo: str = "non_restoring", bits: int = 32) -> None:
        self.mul_algo = mul_algo
        self.div_algo = div_algo
        self.bits = bits

    def booth_multiply(self, multiplicand: int, multiplier: int, bits: int = 32) -> BoothResult:
        """Signed 2's-complement Booth's multiplication algorithm."""
        mask = (1 << bits) - 1
        m_signed = _to_signed_n(multiplicand, bits)
        a_reg = 0
        q_reg = multiplier & mask
        q_minus_1 = 0
        steps: list[BoothStep] = []

        for step in range(bits):
            q0 = q_reg & 1
            op_desc = "HOLD"
            comment = f"Q0={q0}, Q-1={q_minus_1}: no add/sub"
            if q0 == 1 and q_minus_1 == 0:
                a_reg = _to_signed_n(a_reg - m_signed, bits)
                op_desc = "A <- A - M"
                comment = "Q0Q-1=10: subtract multiplicand"
            elif q0 == 0 and q_minus_1 == 1:
                a_reg = _to_signed_n(a_reg + m_signed, bits)
                op_desc = "A <- A + M"
                comment = "Q0Q-1=01: add multiplicand"

            # Arithmetic right shift of combined (A, Q, Q_-1)
            combined = ((a_reg & mask) << (bits + 1)) | (q_reg << 1) | q_minus_1
            sign = (a_reg >> (bits - 1)) & 1
            shifted = (combined >> 1) | (sign << (2 * bits))
            a_reg = _to_signed_n((shifted >> (bits + 1)) & mask, bits)
            q_reg = (shifted >> 1) & mask
            q_minus_1 = shifted & 1

            steps.append(
                BoothStep(
                    step_index=step,
                    a_reg=a_reg & mask,
                    q_reg=q_reg,
                    q_minus_1=q_minus_1,
                    recoded_digit=None,
                    operation=f"{op_desc}; ASR",
                    comment=comment,
                )
            )

        raw_64 = ((a_reg & mask) << bits) | q_reg
        signed_64 = _to_signed_n(raw_64, 2 * bits)
        # Keep cycle latency realistic for pipeline simulation while full trace is preserved
        cycles = max(2, bits // 8)
        return BoothResult(
            multiplicand=m_signed,
            multiplier=_to_signed_n(multiplier, bits),
            product_64=signed_64,
            product_low32=to_unsigned32(signed_64),
            algorithm="booth",
            steps=tuple(steps),
            bit_pair_digits=(),
            cycles_taken=cycles,
        )

    def bit_pair_multiply(self, multiplicand: int, multiplier: int, bits: int = 32) -> BoothResult:
        """Radix-4 Modified Booth (Bit-Pair Recoding) multiplication."""
        if bits % 2 != 0:
            raise ValueError("bit_pair_multiply requires an even bit width")
        mask = (1 << bits) - 1
        m_signed = _to_signed_n(multiplicand, bits)
        q_signed = _to_signed_n(multiplier, bits)

        # Recode multiplier bits in overlapping triples (q_{2i+1}, q_{2i}, q_{2i-1})
        q_ext = (multiplier & mask) << 1
        recoded: list[int] = []
        steps: list[BoothStep] = []
        accumulator = 0

        for pair_idx in range(bits // 2):
            triple = (q_ext >> (2 * pair_idx)) & 0b111
            digit_map = {
                0b000: 0,
                0b001: 1,
                0b010: 1,
                0b011: 2,
                0b100: -2,
                0b101: -1,
                0b110: -1,
                0b111: 0,
            }
            digit = digit_map[triple]
            recoded.append(digit)
            partial = (digit * m_signed) << (2 * pair_idx)
            accumulator += partial

            steps.append(
                BoothStep(
                    step_index=pair_idx,
                    a_reg=to_unsigned32(accumulator >> bits),
                    q_reg=to_unsigned32(accumulator),
                    q_minus_1=(triple & 1),
                    recoded_digit=digit,
                    operation=f"ACC += ({digit:+d} * M) << {2 * pair_idx}",
                    comment=f"Triple {triple:03b} -> digit {digit:+d}",
                )
            )

        exact_product = m_signed * q_signed
        cycles = max(2, bits // 16)
        return BoothResult(
            multiplicand=m_signed,
            multiplier=q_signed,
            product_64=exact_product,
            product_low32=to_unsigned32(exact_product),
            algorithm="bit_pair",
            steps=tuple(steps),
            bit_pair_digits=tuple(recoded),
            cycles_taken=cycles,
        )

    def restoring_divide(self, dividend: int, divisor: int, bits: int = 32) -> DivisionResult:
        """Restoring division algorithm (unsigned magnitude + sign restoration)."""
        d_signed = _to_signed_n(dividend, bits)
        v_signed = _to_signed_n(divisor, bits)
        if v_signed == 0:
            return DivisionResult(
                dividend=d_signed,
                divisor=0,
                quotient=0xFFFFFFFF,
                remainder=d_signed,
                algorithm="restoring",
                steps=(),
                cycles_taken=1,
                divide_by_zero=True,
            )

        neg_q = (d_signed < 0) ^ (v_signed < 0)
        neg_r = d_signed < 0
        q_reg = abs(d_signed) & ((1 << bits) - 1)
        m_val = abs(v_signed)
        a_reg = 0
        mask = (1 << bits) - 1
        steps: list[DivisionStep] = []

        for step in range(bits):
            # Shift left (A, Q)
            msb_q = (q_reg >> (bits - 1)) & 1
            a_reg = ((a_reg << 1) | msb_q)
            q_reg = (q_reg << 1) & mask

            a_sub = a_reg - m_val
            if a_sub < 0:
                # Restore A and set Q0 = 0
                op_desc = "SHL; A <- A - M (<0); Restore A; Q0 <- 0"
                comment = "Negative remainder: restored"
            else:
                a_reg = a_sub
                q_reg |= 1
                op_desc = "SHL; A <- A - M (>=0); Q0 <- 1"
                comment = "Non-negative remainder: kept"

            steps.append(
                DivisionStep(
                    step_index=step,
                    a_reg=a_reg,
                    q_reg=q_reg,
                    operation=op_desc,
                    comment=comment,
                )
            )

        quotient = -q_reg if neg_q else q_reg
        remainder = -a_reg if neg_r else a_reg
        return DivisionResult(
            dividend=d_signed,
            divisor=v_signed,
            quotient=to_unsigned32(quotient),
            remainder=to_unsigned32(remainder),
            algorithm="restoring",
            steps=tuple(steps),
            cycles_taken=max(2, bits // 8),
        )

    def non_restoring_divide(self, dividend: int, divisor: int, bits: int = 32) -> DivisionResult:
        """Non-restoring division algorithm (unsigned magnitude + final sign adjustment)."""
        d_signed = _to_signed_n(dividend, bits)
        v_signed = _to_signed_n(divisor, bits)
        if v_signed == 0:
            return DivisionResult(
                dividend=d_signed,
                divisor=0,
                quotient=0xFFFFFFFF,
                remainder=d_signed,
                algorithm="non_restoring",
                steps=(),
                cycles_taken=1,
                divide_by_zero=True,
            )

        neg_q = (d_signed < 0) ^ (v_signed < 0)
        neg_r = d_signed < 0
        q_reg = abs(d_signed) & ((1 << bits) - 1)
        m_val = abs(v_signed)
        a_reg = 0
        mask = (1 << bits) - 1
        steps: list[DivisionStep] = []

        for step in range(bits):
            msb_q = (q_reg >> (bits - 1)) & 1
            a_reg = (a_reg << 1) | msb_q
            q_reg = (q_reg << 1) & mask

            if a_reg >= 0:
                a_reg = a_reg - m_val
                op_desc = "SHL; A <- A - M"
            else:
                a_reg = a_reg + m_val
                op_desc = "SHL; A <- A + M"

            if a_reg >= 0:
                q_reg |= 1
                comment = "A >= 0 -> Q0 <- 1"
            else:
                comment = "A < 0 -> Q0 <- 0"

            steps.append(
                DivisionStep(
                    step_index=step,
                    a_reg=a_reg & mask,
                    q_reg=q_reg,
                    operation=op_desc,
                    comment=comment,
                )
            )

        if a_reg < 0:
            a_reg += m_val

        quotient = -q_reg if neg_q else q_reg
        remainder = -a_reg if neg_r else a_reg
        return DivisionResult(
            dividend=d_signed,
            divisor=v_signed,
            quotient=to_unsigned32(quotient),
            remainder=to_unsigned32(remainder),
            algorithm="non_restoring",
            steps=tuple(steps),
            cycles_taken=max(2, bits // 8),
        )

    def execute(self, opcode: Opcode, op1: int, op2: int = 0) -> ALUResult:
        """Execute an ALU operation and return value, flags, latency, and optional multi-cycle trace."""
        u1 = to_unsigned32(op1)
        u2 = to_unsigned32(op2)
        s1 = to_signed32(op1)
        s2 = to_signed32(op2)

        booth_trace: Optional[BoothResult] = None
        div_trace: Optional[DivisionResult] = None
        cycles = 1
        val = 0

        if opcode in (Opcode.ADD, Opcode.ADDI, Opcode.LW, Opcode.LB, Opcode.SW, Opcode.SB):
            val = to_unsigned32(u1 + u2)
        elif opcode == Opcode.SUB:
            val = to_unsigned32(u1 - u2)
        elif opcode in (Opcode.AND, Opcode.ANDI):
            val = u1 & u2
        elif opcode in (Opcode.OR, Opcode.ORI):
            val = u1 | u2
        elif opcode in (Opcode.XOR, Opcode.XORI):
            val = u1 ^ u2
        elif opcode in (Opcode.SLT, Opcode.SLTI):
            val = 1 if s1 < s2 else 0
        elif opcode in (Opcode.SLL, Opcode.SLLI):
            val = to_unsigned32(u1 << (u2 & 0x1F))
        elif opcode in (Opcode.SRL, Opcode.SRLI):
            val = u1 >> (u2 & 0x1F)
        elif opcode == Opcode.MUL:
            if self.mul_algo == "bit_pair":
                booth_trace = self.bit_pair_multiply(s1, s2, bits=self.bits)
            else:
                booth_trace = self.booth_multiply(s1, s2, bits=self.bits)
            val = booth_trace.product_low32
            cycles = booth_trace.cycles_taken
        elif opcode == Opcode.DIV:
            if self.div_algo == "restoring":
                div_trace = self.restoring_divide(s1, s2, bits=self.bits)
            else:
                div_trace = self.non_restoring_divide(s1, s2, bits=self.bits)
            val = div_trace.quotient
            cycles = div_trace.cycles_taken
        elif opcode == Opcode.BEQ:
            val = 1 if u1 == u2 else 0
        elif opcode == Opcode.BNE:
            val = 1 if u1 != u2 else 0
        elif opcode == Opcode.BLT:
            val = 1 if s1 < s2 else 0
        elif opcode == Opcode.BGE:
            val = 1 if s1 >= s2 else 0

        return ALUResult(
            value=to_unsigned32(val),
            zero=(to_unsigned32(val) == 0),
            negative=(to_signed32(val) < 0),
            cycles_required=cycles,
            booth_trace=booth_trace,
            division_trace=div_trace,
        )

