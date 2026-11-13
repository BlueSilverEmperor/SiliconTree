"""SimulationClock, CPI metrics, and immutable CycleSnapshot time-travel history buffer."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from core_engine.alu import BoothResult, DivisionResult
from core_engine.branch_predictor import BranchPredictor, BranchPredictorSnapshot
from core_engine.bus_io import BusPacket, BusSnapshot, BusSubsystem
from core_engine.memory import CacheLineSnapshot, MemoryAccessResult, MemorySnapshot, MemorySubsystem
from core_engine.pipeline import (
    ForwardingPath,
    Pipeline,
    PipelineSnapshot,
    SpeculativeLeakEvent,
    StageSlot,
)


@dataclass(frozen=True)
class EngineRestoreBundle:
    """Frozen bundle of all subsystem internal states for exact cycle rewind."""

    pipeline: PipelineSnapshot
    memory: MemorySnapshot
    predictor: BranchPredictorSnapshot
    bus: BusSnapshot


@dataclass(frozen=True)
class CycleSnapshot:
    """Immutable snapshot of complete processor state at a single clock cycle."""

    cycle: int
    instructions_retired: int
    cpi: float
    pc: int
    halted: bool
    regs: tuple[int, ...]
    spec_regs: tuple[int, ...]
    stages: Mapping[str, StageSlot]
    forwarding_events: tuple[ForwardingPath, ...]
    stall_cycles: int
    speculative_flushes: int
    l1_lines: tuple[CacheLineSnapshot, ...]
    l2_lines: tuple[CacheLineSnapshot, ...]
    l1_hits: int
    l1_misses: int
    l1_conflict_misses: int
    dram_snapshot: tuple[tuple[int, int], ...]
    bus_packets: tuple[BusPacket, ...]
    dma_active: bool
    dma_words_transferred: int
    bus_topology: str
    predictor_mode: str
    predictor_mispredictions: int
    last_mem_access: Optional[MemoryAccessResult]
    last_alu_trace: Optional[BoothResult | DivisionResult]
    rtn_log: tuple[str, ...]
    speculative_leak_events: tuple[SpeculativeLeakEvent, ...]
    _engine_state: EngineRestoreBundle


class SimulationClock:
    """Master clock driving the CPU pipeline and storing immutable CycleSnapshots for rewind."""

    def __init__(
        self,
        pipeline: Pipeline,
        memory: Optional[MemorySubsystem] = None,
        predictor: Optional[BranchPredictor] = None,
        bus: Optional[BusSubsystem] = None,
        max_history: int = 2000,
    ) -> None:
        self.pipeline = pipeline
        self.memory = memory or pipeline.memory
        self.predictor = predictor or pipeline.predictor
        self.bus = bus or pipeline.bus

        self.current_cycle: int = 0
        self.max_history = max_history
        self.history: deque[CycleSnapshot] = deque(maxlen=max_history)
        self._push_snapshot()

    def _build_snapshot(self) -> CycleSnapshot:
        retired = self.pipeline.instructions_retired
        cpi = round(self.current_cycle / retired, 3) if retired > 0 else 0.0
        stages_map = MappingProxyType(
            {
                "IF": self.pipeline.if_view,
                "ID": self.pipeline.id_view,
                "EX": self.pipeline.ex_view,
                "MEM": self.pipeline.mem_view,
                "WB": self.pipeline.wb_view,
            }
        )
        bundle = EngineRestoreBundle(
            pipeline=self.pipeline.snapshot(),
            memory=self.memory.snapshot(),
            predictor=self.predictor.snapshot(),
            bus=self.bus.snapshot(),
        )
        return CycleSnapshot(
            cycle=self.current_cycle,
            instructions_retired=retired,
            cpi=cpi,
            pc=self.pipeline.pc,
            halted=self.pipeline.halted,
            regs=tuple(self.pipeline.regs),
            spec_regs=tuple(self.pipeline.spec_regs),
            stages=stages_map,
            forwarding_events=tuple(self.pipeline.last_forwarding_events),
            stall_cycles=self.pipeline.stall_cycles,
            speculative_flushes=self.pipeline.speculative_flushes,
            l1_lines=self.memory.l1.export_snapshots(),
            l2_lines=self.memory.l2.export_snapshots() if self.memory.l2 is not None else (),
            l1_hits=self.memory.l1.hits,
            l1_misses=self.memory.l1.misses,
            l1_conflict_misses=self.memory.l1.conflict_misses,
            dram_snapshot=tuple(sorted(self.memory.dram.items())),
            bus_packets=tuple(self.bus.active_packets),
            dma_active=self.bus.dma_active,
            dma_words_transferred=self.bus.dma_words_transferred,
            bus_topology=self.bus.topology.value,
            predictor_mode=self.predictor.mode.value,
            predictor_mispredictions=self.predictor.mispredictions,
            last_mem_access=self.memory.last_access,
            last_alu_trace=self.pipeline.last_alu_trace,
            rtn_log=tuple(self.pipeline.rtn_log),
            speculative_leak_events=tuple(self.pipeline.leak_events),
            _engine_state=bundle,
        )

    def _push_snapshot(self) -> CycleSnapshot:
        snap = self._build_snapshot()
        self.history.append(snap)
        return snap

    def latest_snapshot(self) -> CycleSnapshot:
        """Return the most recent CycleSnapshot without advancing the clock."""
        if not self.history:
            return self._push_snapshot()
        return self.history[-1]

    def step_cycle(self) -> CycleSnapshot:
        """Advance simulation by 1 clock cycle and record an immutable CycleSnapshot."""
        self.current_cycle += 1
        self.pipeline.step(self.current_cycle)
        return self._push_snapshot()

    def restore_snapshot(self, snap: CycleSnapshot) -> CycleSnapshot:
        """Restore all hardware subsystems to the exact state stored in `snap`."""
        bundle = snap._engine_state
        self.pipeline.restore(bundle.pipeline)
        self.memory.restore(bundle.memory)
        self.predictor.restore(bundle.predictor)
        self.bus.restore(bundle.bus)
        self.current_cycle = snap.cycle
        return snap

    def rewind(self, steps: int = 1) -> CycleSnapshot:
        """Rewind `steps` cycles, popping newer snapshots and restoring exact state."""
        if steps <= 0 or len(self.history) <= 1:
            return self.latest_snapshot()
        pops = min(steps, len(self.history) - 1)
        for _ in range(pops):
            self.history.pop()
        target = self.history[-1]
        return self.restore_snapshot(target)

    def get_snapshot(self, cycle: int) -> Optional[CycleSnapshot]:
        """Look up a historical CycleSnapshot without altering live history."""
        for snap in self.history:
            if snap.cycle == cycle:
                return snap
        return None

    def scrub_to(self, target_cycle: int) -> CycleSnapshot:
        """Rewind or advance to `target_cycle` when present in history."""
        for idx, snap in enumerate(self.history):
            if snap.cycle == target_cycle:
                while len(self.history) - 1 > idx:
                    self.history.pop()
                return self.restore_snapshot(snap)
        return self.latest_snapshot()

    def reset_history(self) -> CycleSnapshot:
        """Clear history and record cycle 0 from current hardware state."""
        self.current_cycle = 0
        self.history.clear()
        return self._push_snapshot()

