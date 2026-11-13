"""5-stage RISC pipeline (IF, ID, EX, MEM, WB) with reverse-order execution, forwarding, hazards, and speculative rollback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core_engine.alu import ALU, BoothResult, DivisionResult, to_signed32, to_unsigned32
from core_engine.branch_predictor import BranchPredictor
from core_engine.bus_io import BusSubsystem
from core_engine.isa import (
    BRANCH_OPCODES,
    I_ALU_OPCODES,
    JUMP_OPCODES,
    LOAD_OPCODES,
    R_TYPE_OPCODES,
    STORE_OPCODES,
    Instruction,
    Opcode,
)
from core_engine.memory import MemoryAccessResult, MemorySubsystem


@dataclass(frozen=True)
class StageSlot:
    """Immutable snapshot of an instruction (or bubble) in a pipeline stage/latch."""

    instruction: Optional[Instruction] = None
    pc: int = 0
    is_bubble: bool = True
    stall_reason: str = ""
    is_speculative: bool = False
    spec_epoch: int = 0
    predicted_taken: bool = False
    predicted_target: int = 0
    rs1_val: int = 0
    rs2_val: int = 0
    alu_result: int = 0
    mem_addr: int = 0
    mem_value: int = 0
    mem_cycles_left: int = 0
    ex_cycles_left: int = 0
    branch_taken: bool = False
    branch_target: int = 0
    mispredicted: bool = False
    l1_warmed_speculatively: bool = False
    forwarded_from: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.is_bubble or self.instruction is None:
            return f"NOP ({self.stall_reason})" if self.stall_reason else "NOP"
        return self.instruction.raw_text or self.instruction.opcode.value


@dataclass(frozen=True)
class ForwardingPath:
    """Record of a data-forwarding bypass used during a cycle."""

    from_stage: str
    to_stage: str
    reg: int
    value: int


@dataclass(frozen=True)
class SpeculativeLeakEvent:
    """Recorded whenever speculative execution warms an L1 cache line."""

    cycle: int
    pc: int
    address: int
    l1_set: int
    l1_way: int
    l1_tag: int
    instruction_text: str


@dataclass(frozen=True)
class PendingBranch:
    """Unresolved branch waiting on a non-blocking MSHR load while younger instructions speculate."""

    branch_slot: StageSlot
    waiting_reg: int
    cycles_left: int
    resolved_reg_val: int


@dataclass(frozen=True)
class PendingMSHR:
    """Non-blocking load in flight when non_blocking_loads=True."""

    rd: int
    address: int
    cycles_left: int
    value: int
    is_byte: bool


@dataclass(frozen=True)
class PipelineSnapshot:
    """Frozen internal state of Pipeline for exact time-travel restore."""

    pc: int
    halted: bool
    regs: tuple[int, ...]
    spec_regs: tuple[int, ...]
    spec_reg_dirty: tuple[bool, ...]
    spec_epoch: int
    if_id: StageSlot
    id_ex: StageSlot
    ex_mem: StageSlot
    mem_wb: StageSlot
    if_view: StageSlot
    id_view: StageSlot
    ex_view: StageSlot
    mem_view: StageSlot
    wb_view: StageSlot
    instructions_retired: int
    stall_cycles: int
    speculative_flushes: int
    forwarding_enabled: bool
    speculative_execution: bool
    lfence_enforced: bool
    non_blocking_loads: bool
    pending_branch: Optional[PendingBranch]
    pending_mshrs: tuple[PendingMSHR, ...]
    leak_events: tuple[SpeculativeLeakEvent, ...]
    rtn_log: tuple[str, ...]
    last_alu_trace: Optional[BoothResult | DivisionResult]
    forwarding_events: tuple[ForwardingPath, ...]


@dataclass(frozen=True)
class PipelineTickReport:
    """Summary returned from a single Pipeline.step() tick."""

    retired_instruction: Optional[Instruction]
    forwarding_events: tuple[ForwardingPath, ...]
    leak_events: tuple[SpeculativeLeakEvent, ...]
    flushed: bool
    stalled: bool


def _bubble(reason: str = "") -> StageSlot:
    return StageSlot(is_bubble=True, stall_reason=reason)


def _inst_reads_regs(inst: Instruction) -> tuple[Optional[int], Optional[int]]:
    op = inst.opcode
    if op in R_TYPE_OPCODES:
        return inst.rs1, inst.rs2
    if op in I_ALU_OPCODES or op in LOAD_OPCODES:
        return inst.rs1, None
    if op in STORE_OPCODES or op in BRANCH_OPCODES:
        return inst.rs1, inst.rs2
    return None, None


def _inst_writes_reg(inst: Instruction) -> Optional[int]:
    if inst.opcode in (
        R_TYPE_OPCODES | I_ALU_OPCODES | LOAD_OPCODES | {Opcode.JAL}
    ):
        if inst.rd and inst.rd != 0:
            return inst.rd
    return None


class Pipeline:
    """5-stage pipelined RISC processor core evaluated in reverse order (WB -> MEM -> EX -> ID -> IF)."""

    def __init__(
        self,
        memory: MemorySubsystem,
        alu: Optional[ALU] = None,
        predictor: Optional[BranchPredictor] = None,
        bus: Optional[BusSubsystem] = None,
        forwarding_enabled: bool = True,
        speculative_execution: bool = True,
        lfence_enforced: bool = False,
        non_blocking_loads: bool = False,
    ) -> None:
        self.memory = memory
        self.alu = alu or ALU()
        self.predictor = predictor or BranchPredictor()
        self.bus = bus or BusSubsystem()

        self.forwarding_enabled = forwarding_enabled
        self.speculative_execution = speculative_execution
        self.lfence_enforced = lfence_enforced
        self.non_blocking_loads = non_blocking_loads

        self.program: dict[int, Instruction] = {}
        self.pc: int = 0
        self.halted: bool = False

        # 16 architectural registers (R0 hardwired to 0)
        self.regs: list[int] = [0] * 16
        self.spec_regs: list[int] = [0] * 16
        self.spec_reg_dirty: list[bool] = [False] * 16
        self.spec_epoch: int = 0

        # Inter-stage latches
        self.if_id: StageSlot = _bubble()
        self.id_ex: StageSlot = _bubble()
        self.ex_mem: StageSlot = _bubble()
        self.mem_wb: StageSlot = _bubble()

        # Per-cycle visible stage slots (for GUI / snapshot)
        self.if_view: StageSlot = _bubble()
        self.id_view: StageSlot = _bubble()
        self.ex_view: StageSlot = _bubble()
        self.mem_view: StageSlot = _bubble()
        self.wb_view: StageSlot = _bubble()

        # Speculative window helpers
        self.pending_branch: Optional[PendingBranch] = None
        self.pending_mshrs: list[PendingMSHR] = []

        # Counters & logs
        self.instructions_retired: int = 0
        self.stall_cycles: int = 0
        self.speculative_flushes: int = 0
        self.leak_events: list[SpeculativeLeakEvent] = []
        self.rtn_log: list[str] = []
        self.last_alu_trace: Optional[BoothResult | DivisionResult] = None
        self.last_forwarding_events: list[ForwardingPath] = []
        self._last_retired_slot: StageSlot = _bubble()

    def load_program(self, instructions: list[Instruction] | tuple[Instruction, ...], start_pc: int = 0) -> None:
        """Load assembled instructions into instruction memory and reset pipeline latches."""
        self.program = {inst.pc: inst for inst in instructions}
        self.pc = start_pc
        self.halted = False
        self.if_id = _bubble()
        self.id_ex = _bubble()
        self.ex_mem = _bubble()
        self.mem_wb = _bubble()
        self.if_view = _bubble()
        self.id_view = _bubble()
        self.ex_view = _bubble()
        self.mem_view = _bubble()
        self.wb_view = _bubble()
        self.pending_branch = None
        self.pending_mshrs = []
        self.spec_epoch = 0
        self.spec_reg_dirty = [False] * 16
        self.spec_regs = list(self.regs)

    def _read_reg(self, idx: Optional[int], speculative: bool) -> int:
        if idx is None or idx == 0:
            return 0
        if speculative and self.spec_reg_dirty[idx]:
            return self.spec_regs[idx]
        return self.regs[idx]

    def _write_reg(self, idx: Optional[int], val: int, speculative: bool) -> None:
        if idx is None or idx == 0:
            return
        masked = to_unsigned32(val)
        if speculative:
            self.spec_regs[idx] = masked
            self.spec_reg_dirty[idx] = True
        else:
            self.regs[idx] = masked
            if not self.spec_reg_dirty[idx]:
                self.spec_regs[idx] = masked

    def _discard_speculation(self) -> None:
        """Rollback speculative shadow registers without touching architectural registers."""
        self.spec_regs = list(self.regs)
        self.spec_reg_dirty = [False] * 16
        self.spec_epoch = 0
        self.pending_branch = None

    def _commit_speculation(self) -> None:
        """Promote speculative shadow registers when an unresolved branch confirms correct."""
        for i in range(1, 16):
            if self.spec_reg_dirty[i]:
                self.regs[i] = self.spec_regs[i]
                self.spec_reg_dirty[i] = False
        self.spec_epoch = 0
        self.pending_branch = None

    def _append_rtn(self, cycle: int, stage: str, text: str) -> None:
        self.rtn_log.append(f"[C{cycle:03d} {stage}] {text}")
        if len(self.rtn_log) > 200:
            self.rtn_log = self.rtn_log[-200:]

    def step(self, cycle: int) -> PipelineTickReport:
        """Execute one clock cycle strictly in reverse stage order: WB -> MEM -> EX -> ID -> IF."""
        if self.halted:
            self.bus.tick(self.memory)
            return PipelineTickReport(None, (), (), False, False)

        self.last_forwarding_events = []
        self._last_retired_slot = _bubble()
        cycle_leaks: list[SpeculativeLeakEvent] = []
        flushed_this_cycle = False

        # Advance non-blocking MSHRs and pending speculative branch if active
        mshr_resolved_flushed = self._tick_mshr_and_pending_branch(cycle)
        if mshr_resolved_flushed:
            flushed_this_cycle = True

        # 1. WB
        retired_inst = self._stage_wb(cycle)

        # 2. MEM
        mem_stalled, pending_flush_info, mem_leaks = self._stage_mem(cycle)
        cycle_leaks.extend(mem_leaks)

        # 3. EX (runs in parallel with MEM during this clock cycle; flush latches at end of cycle)
        ex_stalled, ex_leaks = self._stage_ex(cycle, downstream_stalled=mem_stalled)
        cycle_leaks.extend(ex_leaks)

        if pending_flush_info is not None:
            branch_target, branch_pc = pending_flush_info
            self._flush_speculative(cycle, branch_target, branch_pc)
            flushed_this_cycle = True

        # 4. ID
        id_stalled = False if flushed_this_cycle else self._stage_id(cycle, downstream_stalled=(mem_stalled or ex_stalled))

        # 5. IF
        if_stalled = self._stage_if(
            cycle,
            downstream_stalled=(mem_stalled or ex_stalled or id_stalled),
            flushed=flushed_this_cycle,
        )

        # Advance bus transfers & DMA cycle-stealing
        self.bus.tick(self.memory)

        # Poll unmasked IRQ if pipeline is not mid-flush
        if not flushed_this_cycle and not self.halted:
            irq = self.bus.poll_irq()
            if irq is not None:
                self._write_reg(15, self.pc, speculative=False)
                self.pc = irq.vector_pc
                self.if_id = _bubble("IRQ_REDIRECT")
                self._append_rtn(cycle, "IRQ", f"R15 <- PC; PC <- 0x{irq.vector_pc:04X} ({irq.name})")

        any_stall = mem_stalled or ex_stalled or id_stalled or if_stalled
        if any_stall:
            self.stall_cycles += 1

        self.leak_events.extend(cycle_leaks)
        return PipelineTickReport(
            retired_instruction=retired_inst,
            forwarding_events=tuple(self.last_forwarding_events),
            leak_events=tuple(cycle_leaks),
            flushed=flushed_this_cycle,
            stalled=any_stall,
        )

    def _tick_mshr_and_pending_branch(self, cycle: int) -> bool:
        """Advance in-flight non-blocking MSHRs and resolve parked speculative branch when ready."""
        still_pending: list[PendingMSHR] = []
        completed: dict[int, int] = {}
        for m in self.pending_mshrs:
            rem = m.cycles_left - 1
            if rem <= 0:
                completed[m.rd] = m.value
                self._write_reg(m.rd, m.value, speculative=False)
            else:
                still_pending.append(
                    PendingMSHR(
                        rd=m.rd,
                        address=m.address,
                        cycles_left=rem,
                        value=m.value,
                        is_byte=m.is_byte,
                    )
                )
        self.pending_mshrs = still_pending

        if self.pending_branch is None:
            return False

        pb = self.pending_branch
        rem = pb.cycles_left - 1
        if pb.waiting_reg in completed or rem <= 0:
            # Resolve parked branch now!
            slot = pb.branch_slot
            inst = slot.instruction
            assert inst is not None
            op1 = completed.get(inst.rs1, self.regs[inst.rs1]) if inst.rs1 is not None else 0
            op2 = completed.get(inst.rs2, self.regs[inst.rs2]) if inst.rs2 is not None else 0
            if pb.waiting_reg == inst.rs1 and pb.waiting_reg in completed:
                op1 = completed[pb.waiting_reg]
            if pb.waiting_reg == inst.rs2 and pb.waiting_reg in completed:
                op2 = completed[pb.waiting_reg]

            res = self.alu.execute(inst.opcode, op1, op2)
            actual_taken = bool(res.value)
            actual_target = inst.imm if actual_taken else inst.pc + 4
            mispredicted = (actual_taken != slot.predicted_taken) or (
                actual_taken and actual_target != slot.predicted_target
            )
            self.predictor.update(inst.pc, actual_taken, inst.imm, mispredicted)
            self.pending_branch = None

            if mispredicted:
                self._flush_speculative(cycle, actual_target, inst.pc)
                return True
            self._commit_speculation()
            return False

        self.pending_branch = PendingBranch(
            branch_slot=pb.branch_slot,
            waiting_reg=pb.waiting_reg,
            cycles_left=rem,
            resolved_reg_val=pb.resolved_reg_val,
        )
        return False

    def _flush_speculative(self, cycle: int, correct_pc: int, branch_pc: int) -> None:
        """Flush all speculative pipeline stages and restore architectural registers."""
        self.speculative_flushes += 1
        self.pc = correct_pc
        self.if_id = _bubble("BRANCH_FLUSH")
        self.id_ex = _bubble("BRANCH_FLUSH")
        self.ex_mem = _bubble("BRANCH_FLUSH")
        self.mem_wb = _bubble("BRANCH_FLUSH")
        self._discard_speculation()
        self._append_rtn(cycle, "FLUSH", f"Mispredict at 0x{branch_pc:04X}; PC <- 0x{correct_pc:04X}")

    def _stage_wb(self, cycle: int) -> Optional[Instruction]:
        slot = self.mem_wb
        self.wb_view = slot
        self._last_retired_slot = slot
        if slot.is_bubble or slot.instruction is None:
            return None

        inst = slot.instruction
        self.mem_wb = _bubble()

        # If speculative and branch still unresolved, write only to spec_regs and do not retire architecturally
        is_spec = self.spec_epoch > 0 and slot.spec_epoch > 0

        if inst.opcode == Opcode.HALT and not is_spec:
            self.halted = True
            self._append_rtn(cycle, "WB", "HALT -> CPU stopped")
            self.instructions_retired += 1
            return inst

        rd = _inst_writes_reg(inst)
        if rd is not None:
            val = slot.mem_value if inst.opcode in LOAD_OPCODES else slot.alu_result
            self._write_reg(rd, val, speculative=is_spec)
            self._append_rtn(cycle, "WB", f"R{rd} <- 0x{to_unsigned32(val):08X} ({'SPEC' if is_spec else 'ARCH'})")

        if not is_spec:
            self.instructions_retired += 1
        return None if is_spec else inst

    def _stage_mem(self, cycle: int) -> tuple[bool, Optional[tuple[int, int]], list[SpeculativeLeakEvent]]:
        """Evaluate MEM stage. Returns (stalled, pending_flush_info, leak_events)."""
        slot = self.ex_mem
        self.mem_view = slot
        leaks: list[SpeculativeLeakEvent] = []

        if slot.is_bubble or slot.instruction is None:
            self.mem_wb = _bubble()
            return False, None, leaks

        inst = slot.instruction
        is_spec = self.spec_epoch > 0 and slot.spec_epoch > 0

        # Check bus DMA cycle stealing for memory operations
        if inst.opcode in (LOAD_OPCODES | STORE_OPCODES) and not self.bus.can_cpu_use_data_bus():
            self.mem_view = StageSlot(**{**slot.__dict__, "stall_reason": "DMA_CYCLE_STEAL"})
            self.mem_wb = _bubble("DMA_CYCLE_STEAL")
            return True, None, leaks

        # Handle multi-cycle cache miss stall already in progress
        if slot.mem_cycles_left > 1:
            updated = StageSlot(
                **{
                    **slot.__dict__,
                    "mem_cycles_left": slot.mem_cycles_left - 1,
                    "stall_reason": "CACHE_MISS_WAIT",
                }
            )
            self.ex_mem = updated
            self.mem_view = updated
            self.mem_wb = _bubble("CACHE_MISS_WAIT")
            return True, None, leaks

        if slot.mem_cycles_left == 1:
            # Final cycle of cache miss wait: complete and push to MEM_WB
            finished = StageSlot(
                **{
                    **slot.__dict__,
                    "mem_cycles_left": 0,
                    "stall_reason": "",
                }
            )
            self.ex_mem = _bubble()
            self.mem_wb = finished
            return False, None, leaks

        # Handle branch resolution at MEM stage (allows 1 younger instruction in EX to speculatively prefetch!)
        if inst.opcode in BRANCH_OPCODES:
            self.ex_mem = _bubble()
            self.mem_wb = slot
            if slot.mispredicted:
                return False, (slot.branch_target, inst.pc), leaks
            if self.spec_epoch > 0 and not is_spec:
                self._commit_speculation()
            return False, None, leaks

        if inst.opcode in LOAD_OPCODES:
            res: MemoryAccessResult
            allow_fill = not self.lfence_enforced
            if inst.opcode == Opcode.LB:
                res = self.memory.read_byte(
                    slot.mem_addr, cycle, is_speculative=is_spec, allow_speculative_fill=allow_fill
                )
            else:
                res = self.memory.read_word(
                    slot.mem_addr, cycle, is_speculative=is_spec, allow_speculative_fill=allow_fill
                )

            bus_name = "SYSTEM_BUS" if self.bus.topology.value == "SINGLE_BUS" else "DATA_BUS"
            self.bus.emit_packet(
                bus_name=bus_name,
                src="RAM" if not res.l1_hit else "L1_CACHE",
                dst="CPU_MEM",
                kind="MEM_READ",
                address=res.address,
                data=res.value,
                cycles=min(4, res.latency_cycles),
            )

            if res.speculative_warmed:
                leaks.append(
                    SpeculativeLeakEvent(
                        cycle=cycle,
                        pc=inst.pc,
                        address=res.address,
                        l1_set=res.l1_set,
                        l1_way=res.l1_way,
                        l1_tag=res.l1_tag,
                        instruction_text=inst.raw_text,
                    )
                )

            self._append_rtn(
                cycle,
                "MEM",
                f"Load 0x{res.address:04X} -> 0x{res.value:08X} ({'L1 HIT' if res.l1_hit else f'MISS {res.latency_cycles}c'})",
            )

            # Non-blocking MSHR when enabled and miss occurs
            if not res.l1_hit and self.non_blocking_loads and inst.rd is not None and not is_spec:
                self.pending_mshrs.append(
                    PendingMSHR(
                        rd=inst.rd,
                        address=res.address,
                        cycles_left=max(1, res.latency_cycles - 1),
                        value=res.value,
                        is_byte=(inst.opcode == Opcode.LB),
                    )
                )
                self.ex_mem = _bubble()
                self.mem_wb = _bubble("MSHR_PENDING")
                return False, None, leaks

            if res.latency_cycles > 1:
                stalled_slot = StageSlot(
                    **{
                        **slot.__dict__,
                        "mem_value": res.value,
                        "mem_cycles_left": res.latency_cycles - 1,
                        "stall_reason": "CACHE_MISS_WAIT",
                        "l1_warmed_speculatively": res.speculative_warmed,
                    }
                )
                self.ex_mem = stalled_slot
                self.mem_view = stalled_slot
                self.mem_wb = _bubble("CACHE_MISS_WAIT")
                return True, None, leaks

            done_slot = StageSlot(
                **{
                    **slot.__dict__,
                    "mem_value": res.value,
                    "l1_warmed_speculatively": res.speculative_warmed,
                }
            )
            self.ex_mem = _bubble()
            self.mem_wb = done_slot
            return False, None, leaks

        if inst.opcode in STORE_OPCODES:
            if is_spec:
                # Speculative stores do NOT write architectural memory
                self.ex_mem = _bubble()
                self.mem_wb = slot
                return False, None, leaks

            if inst.opcode == Opcode.SB:
                res = self.memory.write_byte(slot.mem_addr, slot.rs2_val, cycle, is_speculative=False)
            else:
                res = self.memory.write_word(slot.mem_addr, slot.rs2_val, cycle, is_speculative=False)

            bus_name = "SYSTEM_BUS" if self.bus.topology.value == "SINGLE_BUS" else "DATA_BUS"
            self.bus.emit_packet(
                bus_name=bus_name,
                src="CPU_MEM",
                dst="L1_CACHE" if res.l1_hit else "RAM",
                kind="MEM_WRITE",
                address=res.address,
                data=slot.rs2_val,
                cycles=min(4, res.latency_cycles),
            )
            self._append_rtn(cycle, "MEM", f"Store 0x{res.address:04X} <- 0x{slot.rs2_val:08X}")
            if res.latency_cycles > 1:
                stalled_slot = StageSlot(
                    **{
                        **slot.__dict__,
                        "mem_cycles_left": res.latency_cycles - 1,
                        "stall_reason": "CACHE_MISS_WAIT",
                    }
                )
                self.ex_mem = stalled_slot
                self.mem_view = stalled_slot
                self.mem_wb = _bubble("CACHE_MISS_WAIT")
                return True, None, leaks

        self.ex_mem = _bubble()
        self.mem_wb = slot
        return False, None, leaks

    def _resolve_forwarded_operand(
        self,
        reg: Optional[int],
        fallback_val: int,
        is_spec: bool,
        forwarded_tags: list[str],
    ) -> int:
        if reg is None or reg == 0:
            return 0
        if not self.forwarding_enabled:
            return self._read_reg(reg, speculative=is_spec)

        # Priority 1: Producer just moved to MEM_WB this cycle (was in EX last cycle -> EX-to-EX bypass)
        mem_slot = self.mem_wb
        if not mem_slot.is_bubble and mem_slot.instruction is not None:
            m_rd = _inst_writes_reg(mem_slot.instruction)
            if m_rd == reg:
                val = mem_slot.mem_value if mem_slot.instruction.opcode in LOAD_OPCODES else mem_slot.alu_result
                self.last_forwarding_events.append(ForwardingPath("MEM_WB", "EX", reg, val))
                forwarded_tags.append(f"MEM_WB->R{reg}")
                return val

        # Priority 2: Producer just retired in WB this cycle (was in MEM last cycle -> MEM-to-EX bypass)
        wb_slot = self._last_retired_slot
        if not wb_slot.is_bubble and wb_slot.instruction is not None:
            w_rd = _inst_writes_reg(wb_slot.instruction)
            if w_rd == reg:
                val = wb_slot.mem_value if wb_slot.instruction.opcode in LOAD_OPCODES else wb_slot.alu_result
                self.last_forwarding_events.append(ForwardingPath("WB", "EX", reg, val))
                forwarded_tags.append(f"WB->R{reg}")
                return val

        return self._read_reg(reg, speculative=is_spec) if is_spec else fallback_val

    def _stage_ex(self, cycle: int, downstream_stalled: bool) -> tuple[bool, list[SpeculativeLeakEvent]]:
        slot = self.id_ex
        self.ex_view = slot
        leaks: list[SpeculativeLeakEvent] = []

        if downstream_stalled:
            return not slot.is_bubble, leaks

        if slot.is_bubble or slot.instruction is None:
            self.ex_mem = _bubble()
            return False, leaks

        inst = slot.instruction
        is_spec = self.spec_epoch > 0 and slot.spec_epoch > 0

        # Multi-cycle ALU continuation (e.g. Booth MUL / Non-restoring DIV)
        if slot.ex_cycles_left > 1:
            updated = StageSlot(
                **{
                    **slot.__dict__,
                    "ex_cycles_left": slot.ex_cycles_left - 1,
                    "stall_reason": f"ALU_{inst.opcode.value}",
                }
            )
            self.id_ex = updated
            self.ex_view = updated
            self.ex_mem = _bubble(f"ALU_{inst.opcode.value}")
            return True, leaks

        if slot.ex_cycles_left == 1:
            finished = StageSlot(**{**slot.__dict__, "ex_cycles_left": 0, "stall_reason": ""})
            self.id_ex = _bubble()
            self.ex_mem = finished
            return False, leaks

        forwarded_tags: list[str] = []
        op1 = self._resolve_forwarded_operand(inst.rs1, slot.rs1_val, is_spec, forwarded_tags)
        op2 = self._resolve_forwarded_operand(inst.rs2, slot.rs2_val, is_spec, forwarded_tags)

        # If branch depends on an in-flight non-blocking MSHR:
        if inst.opcode in BRANCH_OPCODES and self.pending_mshrs:
            mshr_map = {m.rd: m for m in self.pending_mshrs}
            waiting_mshr = mshr_map.get(inst.rs1) or mshr_map.get(inst.rs2)
            if waiting_mshr is not None:
                if self.speculative_execution and not self.lfence_enforced:
                    self.pending_branch = PendingBranch(
                        branch_slot=slot,
                        waiting_reg=waiting_mshr.rd,
                        cycles_left=waiting_mshr.cycles_left,
                        resolved_reg_val=waiting_mshr.value,
                    )
                    self.spec_epoch += 1
                    self.id_ex = _bubble()
                    self.ex_mem = _bubble()
                    self._append_rtn(cycle, "EX", f"Branch parked on R{waiting_mshr.rd} MSHR; speculative epoch {self.spec_epoch}")
                    return False, leaks
                # LFENCE or non-speculative: stall branch in EX until MSHR completes!
                self.ex_view = StageSlot(**{**slot.__dict__, "stall_reason": "LFENCE_MSHR_WAIT"})
                self.ex_mem = _bubble("LFENCE_MSHR_WAIT")
                return True, leaks

        if inst.opcode in R_TYPE_OPCODES:
            res = self.alu.execute(inst.opcode, op1, op2)
            if res.booth_trace is not None:
                self.last_alu_trace = res.booth_trace
            elif res.division_trace is not None:
                self.last_alu_trace = res.division_trace
            self.bus.emit_packet("INTERNAL", "REG_FILE", "ALU", "REG_ALU", inst.pc, res.value, cycles=1)
            self._append_rtn(cycle, "EX", f"{inst.rtn} => 0x{res.value:08X}")

            if res.cycles_required > 1:
                stalled_slot = StageSlot(
                    **{
                        **slot.__dict__,
                        "rs1_val": op1,
                        "rs2_val": op2,
                        "alu_result": res.value,
                        "ex_cycles_left": res.cycles_required - 1,
                        "stall_reason": f"ALU_{inst.opcode.value}",
                        "forwarded_from": tuple(forwarded_tags),
                    }
                )
                self.id_ex = stalled_slot
                self.ex_view = stalled_slot
                self.ex_mem = _bubble(f"ALU_{inst.opcode.value}")
                return True, leaks

            out_slot = StageSlot(
                **{
                    **slot.__dict__,
                    "rs1_val": op1,
                    "rs2_val": op2,
                    "alu_result": res.value,
                    "forwarded_from": tuple(forwarded_tags),
                }
            )
            self.id_ex = _bubble()
            self.ex_mem = out_slot
            return False, leaks

        if inst.opcode in I_ALU_OPCODES:
            mapped = {
                Opcode.ADDI: Opcode.ADD,
                Opcode.ANDI: Opcode.AND,
                Opcode.ORI: Opcode.OR,
                Opcode.XORI: Opcode.XOR,
                Opcode.SLTI: Opcode.SLT,
                Opcode.SLLI: Opcode.SLL,
                Opcode.SRLI: Opcode.SRL,
            }[inst.opcode]
            res = self.alu.execute(mapped, op1, inst.imm)
            self.bus.emit_packet("INTERNAL", "REG_FILE", "ALU", "REG_ALU", inst.pc, res.value, cycles=1)
            self._append_rtn(cycle, "EX", f"{inst.rtn} => 0x{res.value:08X}")
            out_slot = StageSlot(
                **{
                    **slot.__dict__,
                    "rs1_val": op1,
                    "alu_result": res.value,
                    "forwarded_from": tuple(forwarded_tags),
                }
            )
            self.id_ex = _bubble()
            self.ex_mem = out_slot
            return False, leaks

        if inst.opcode in (LOAD_OPCODES | STORE_OPCODES):
            eff_addr = to_unsigned32(op1 + inst.imm)
            warmed = False
            # Speculative L1 cache prefetch on address generation when speculative & not LFENCE-blocked
            if is_spec and inst.opcode in LOAD_OPCODES and self.speculative_execution and not self.lfence_enforced:
                prefetch = self.memory.read_word(
                    eff_addr, cycle, is_speculative=True, allow_speculative_fill=True
                )
                if prefetch.speculative_warmed:
                    warmed = True
                    leaks.append(
                        SpeculativeLeakEvent(
                            cycle=cycle,
                            pc=inst.pc,
                            address=prefetch.address,
                            l1_set=prefetch.l1_set,
                            l1_way=prefetch.l1_way,
                            l1_tag=prefetch.l1_tag,
                            instruction_text=inst.raw_text,
                        )
                    )
            self._append_rtn(cycle, "EX", f"Addr <- 0x{eff_addr:04X}")
            out_slot = StageSlot(
                **{
                    **slot.__dict__,
                    "rs1_val": op1,
                    "rs2_val": op2,
                    "mem_addr": eff_addr,
                    "l1_warmed_speculatively": warmed,
                    "forwarded_from": tuple(forwarded_tags),
                }
            )
            self.id_ex = _bubble()
            self.ex_mem = out_slot
            return False, leaks

        if inst.opcode in BRANCH_OPCODES:
            res = self.alu.execute(inst.opcode, op1, op2)
            actual_taken = bool(res.value)
            actual_target = inst.imm if actual_taken else inst.pc + 4
            mispredicted = (actual_taken != slot.predicted_taken) or (
                actual_taken and actual_target != slot.predicted_target
            )
            self.predictor.update(inst.pc, actual_taken, inst.imm, mispredicted)
            self._append_rtn(
                cycle,
                "EX",
                f"Branch {'TAKEN' if actual_taken else 'NOT TAKEN'} -> 0x{actual_target:04X}"
                + (" [MISPREDICT]" if mispredicted else ""),
            )
            out_slot = StageSlot(
                **{
                    **slot.__dict__,
                    "rs1_val": op1,
                    "rs2_val": op2,
                    "branch_taken": actual_taken,
                    "branch_target": actual_target,
                    "mispredicted": mispredicted,
                    "forwarded_from": tuple(forwarded_tags),
                }
            )
            self.id_ex = _bubble()
            self.ex_mem = out_slot
            return False, leaks

        if inst.opcode == Opcode.JAL:
            out_slot = StageSlot(**{**slot.__dict__, "alu_result": inst.pc + 4})
            self.id_ex = _bubble()
            self.ex_mem = out_slot
            return False, leaks

        # NOP, LFENCE, JMP, HALT
        self.id_ex = _bubble()
        self.ex_mem = slot
        return False, leaks

    def _has_unresolved_branch_ahead(self) -> bool:
        if self.pending_branch is not None:
            return True
        for s in (self.id_ex, self.ex_mem, self.mem_wb):
            if not s.is_bubble and s.instruction is not None and s.instruction.opcode in BRANCH_OPCODES:
                return True
        return False

    def _stage_id(self, cycle: int, downstream_stalled: bool) -> bool:
        slot = self.if_id
        self.id_view = slot

        if downstream_stalled:
            return not slot.is_bubble

        if slot.is_bubble or slot.instruction is None:
            self.id_ex = _bubble()
            return False

        inst = slot.instruction
        is_spec = self.spec_epoch > 0 and slot.spec_epoch > 0

        # LFENCE serialization barrier: stall ID if explicit LFENCE is ahead or lfence_enforced while branch unresolved
        if self.lfence_enforced and self._has_unresolved_branch_ahead():
            self.id_ex = _bubble("LFENCE_BARRIER")
            self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "LFENCE_BARRIER"})
            self._append_rtn(cycle, "ID", "LFENCE barrier stalled speculative decode")
            return True

        if not self.id_ex.is_bubble and self.id_ex.instruction and self.id_ex.instruction.opcode == Opcode.LFENCE:
            self.id_ex = _bubble("LFENCE_SERIALIZE")
            return True

        if inst.opcode == Opcode.LFENCE and self._has_unresolved_branch_ahead():
            self.id_ex = _bubble("LFENCE_SERIALIZE")
            self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "LFENCE_SERIALIZE"})
            return True

        # RAW Hazard detection against instructions currently ahead (in EX_MEM, MEM_WB, or pending MSHRs)
        rs1, rs2 = _inst_reads_regs(inst)
        needed = {r for r in (rs1, rs2) if r is not None and r != 0}

        if needed:
            # Check non-blocking MSHRs for non-branch instructions
            if inst.opcode not in BRANCH_OPCODES:
                for m in self.pending_mshrs:
                    if m.rd in needed:
                        self.id_ex = _bubble("RAW_MSHR_WAIT")
                        self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "RAW_MSHR_WAIT"})
                        return True

            # Check EX_MEM (just completed EX this cycle or stalled in MEM)
            ex_slot = self.ex_mem
            if not ex_slot.is_bubble and ex_slot.instruction is not None:
                ex_rd = _inst_writes_reg(ex_slot.instruction)
                if ex_rd in needed:
                    if ex_slot.instruction.opcode in LOAD_OPCODES:
                        # Load-use hazard requires 1-cycle stall even with forwarding
                        self.id_ex = _bubble("RAW_LOAD_USE")
                        self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "RAW_LOAD_USE"})
                        self._append_rtn(cycle, "ID", f"Load-Use RAW stall on R{ex_rd}")
                        return True
                    if not self.forwarding_enabled:
                        self.id_ex = _bubble("RAW_HAZARD")
                        self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "RAW_HAZARD"})
                        return True

            # Check MEM_WB when forwarding is disabled
            if not self.forwarding_enabled:
                mem_slot = self.mem_wb
                if not mem_slot.is_bubble and mem_slot.instruction is not None:
                    m_rd = _inst_writes_reg(mem_slot.instruction)
                    if m_rd in needed:
                        self.id_ex = _bubble("RAW_HAZARD")
                        self.id_view = StageSlot(**{**slot.__dict__, "stall_reason": "RAW_HAZARD"})
                        return True

        val1 = self._read_reg(rs1, speculative=is_spec)
        val2 = self._read_reg(rs2, speculative=is_spec)

        # Unconditional jump redirect at ID if not already redirected
        if inst.opcode in JUMP_OPCODES:
            self.pc = inst.imm

        out_slot = StageSlot(
            **{
                **slot.__dict__,
                "rs1_val": val1,
                "rs2_val": val2,
                "is_speculative": is_spec,
                "spec_epoch": self.spec_epoch if is_spec else 0,
            }
        )
        self.if_id = _bubble()
        self.id_ex = out_slot
        self._append_rtn(cycle, "ID", f"Decode {inst.opcode.value} ({inst.rtn})")
        return False

    def _stage_if(self, cycle: int, downstream_stalled: bool, flushed: bool) -> bool:
        if flushed:
            self.if_view = _bubble("BRANCH_FLUSH")
            return False

        if downstream_stalled:
            self.if_view = self.if_id
            return not self.if_id.is_bubble

        if not self.bus.can_cpu_use_inst_bus():
            self.if_id = _bubble("BUS_CONTENTION")
            self.if_view = self.if_id
            return True

        inst = self.program.get(self.pc)
        if inst is None:
            self.if_id = _bubble()
            self.if_view = _bubble()
            return False

        # If lfence_enforced and a branch is unresolved, block speculative fetch
        is_spec = self.spec_epoch > 0 or self._has_unresolved_branch_ahead()
        if is_spec and not self.speculative_execution:
            self.if_id = _bubble("SPEC_DISABLED")
            self.if_view = self.if_id
            return True
        if is_spec and self.lfence_enforced:
            self.if_id = _bubble("LFENCE_BARRIER")
            self.if_view = self.if_id
            return True

        bus_name = "SYSTEM_BUS" if self.bus.topology.value == "SINGLE_BUS" else "INST_BUS"
        self.bus.emit_packet(bus_name, "ICACHE", "CPU_IF", "IFETCH", inst.pc, 0, cycles=1)

        pred_taken = False
        pred_target = inst.pc + 4
        if inst.opcode in BRANCH_OPCODES:
            pred = self.predictor.predict(inst.pc, inst.pc + 4, known_target=inst.imm)
            pred_taken = pred.predicted_taken
            pred_target = pred.predicted_target
            if self.spec_epoch == 0:
                self.spec_epoch = 1
            self.pc = pred_target
        elif inst.opcode in JUMP_OPCODES:
            pred_taken = True
            pred_target = inst.imm
            self.pc = inst.imm
        elif inst.opcode == Opcode.HALT:
            # Don't advance PC past HALT
            pass
        else:
            self.pc = inst.pc + 4

        slot = StageSlot(
            instruction=inst,
            pc=inst.pc,
            is_bubble=False,
            is_speculative=is_spec,
            spec_epoch=self.spec_epoch if is_spec else 0,
            predicted_taken=pred_taken,
            predicted_target=pred_target,
        )
        self.if_id = slot
        self.if_view = slot
        self._append_rtn(cycle, "IF", f"Fetch 0x{inst.pc:04X}: {inst.raw_text}")
        return False

    def snapshot(self) -> PipelineSnapshot:
        """Export an immutable snapshot of all architectural, speculative, and latch state."""
        return PipelineSnapshot(
            pc=self.pc,
            halted=self.halted,
            regs=tuple(self.regs),
            spec_regs=tuple(self.spec_regs),
            spec_reg_dirty=tuple(self.spec_reg_dirty),
            spec_epoch=self.spec_epoch,
            if_id=self.if_id,
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            mem_wb=self.mem_wb,
            if_view=self.if_view,
            id_view=self.id_view,
            ex_view=self.ex_view,
            mem_view=self.mem_view,
            wb_view=self.wb_view,
            instructions_retired=self.instructions_retired,
            stall_cycles=self.stall_cycles,
            speculative_flushes=self.speculative_flushes,
            forwarding_enabled=self.forwarding_enabled,
            speculative_execution=self.speculative_execution,
            lfence_enforced=self.lfence_enforced,
            non_blocking_loads=self.non_blocking_loads,
            pending_branch=self.pending_branch,
            pending_mshrs=tuple(self.pending_mshrs),
            leak_events=tuple(self.leak_events),
            rtn_log=tuple(self.rtn_log),
            last_alu_trace=self.last_alu_trace,
            forwarding_events=tuple(self.last_forwarding_events),
        )

    def restore(self, snap: PipelineSnapshot) -> None:
        """Restore exact pipeline state from a PipelineSnapshot."""
        self.pc = snap.pc
        self.halted = snap.halted
        self.regs = list(snap.regs)
        self.spec_regs = list(snap.spec_regs)
        self.spec_reg_dirty = list(snap.spec_reg_dirty)
        self.spec_epoch = snap.spec_epoch
        self.if_id = snap.if_id
        self.id_ex = snap.id_ex
        self.ex_mem = snap.ex_mem
        self.mem_wb = snap.mem_wb
        self.if_view = snap.if_view
        self.id_view = snap.id_view
        self.ex_view = snap.ex_view
        self.mem_view = snap.mem_view
        self.wb_view = snap.wb_view
        self.instructions_retired = snap.instructions_retired
        self.stall_cycles = snap.stall_cycles
        self.speculative_flushes = snap.speculative_flushes
        self.forwarding_enabled = snap.forwarding_enabled
        self.speculative_execution = snap.speculative_execution
        self.lfence_enforced = snap.lfence_enforced
        self.non_blocking_loads = snap.non_blocking_loads
        self.pending_branch = snap.pending_branch
        self.pending_mshrs = list(snap.pending_mshrs)
        self.leak_events = list(snap.leak_events)
        self.rtn_log = list(snap.rtn_log)
        self.last_alu_trace = snap.last_alu_trace
        self.last_forwarding_events = list(snap.forwarding_events)
