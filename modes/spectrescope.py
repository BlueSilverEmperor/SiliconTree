"""Mode 1: SpectreScope — Speculative leak detector, Flush+Reload timer, and LFENCE barrier toggle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from core_engine import (
    BranchPredictor,
    BusSubsystem,
    BusTopology,
    CacheConfig,
    CycleSnapshot,
    MemorySubsystem,
    Opcode,
    Pipeline,
    PredictorMode,
    SimulationClock,
    assemble_program,
)
from modes.base_mode import BaseMode, ModeOutcome


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "spectrescope.json"


class SpectreScopeMode(BaseMode):
    """Speculative execution side-channel analyzer and LFENCE defense lab."""

    mode_id = "spectrescope"
    display_name = "SpectreScope"
    subtitle = "Speculative Leak Detector, Flush+Reload & LFENCE Barrier"

    def __init__(self) -> None:
        super().__init__()
        self.lfence_enabled: bool = False
        self.leak_detected: bool = False
        self.leaked_addresses: list[int] = []
        self.probe_results: dict[int, tuple[int, bool]] = {}
        self.recovered_secret: Optional[int] = None
        self.pipeline: Optional[Pipeline] = None
        self.memory: Optional[MemorySubsystem] = None
        self._scenario_path: Optional[str] = None

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        self._scenario_path = scenario_path
        path = Path(scenario_path) if scenario_path else DEFAULT_SCENARIO
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.scenario_data = data

        l1_cfg = data.get("l1_config", {})
        mem = MemorySubsystem(
            l1_config=CacheConfig(
                name="L1",
                size_bytes=int(l1_cfg.get("size_bytes", 1024)),
                line_size=int(l1_cfg.get("line_size", 64)),
                associativity=int(l1_cfg.get("associativity", 2)),
                hit_latency=int(l1_cfg.get("hit_latency", 1)),
            ),
            dram_latency=int(data.get("dram_latency", 12)),
        )
        dram_words = {int(k): int(v) for k, v in data.get("dram_words", {}).items()}
        mem.load_dram_words(dram_words)

        asm_source = "\n".join(data.get("assembly", []))
        prog = assemble_program(asm_source)

        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=0)
        for inst in prog.instructions:
            if inst.opcode in (Opcode.BEQ, Opcode.BNE, Opcode.BLT, Opcode.BGE):
                pred.train_branch(inst.pc, inst.imm, taken=False)

        bus = BusSubsystem(BusTopology.MULTI_BUS)
        pipe = Pipeline(
            memory=mem,
            predictor=pred,
            bus=bus,
            forwarding_enabled=True,
            speculative_execution=True,
            lfence_enforced=self.lfence_enabled,
            non_blocking_loads=True,
        )
        pipe.load_program(prog.instructions)

        self.memory = mem
        self.pipeline = pipe
        self.clock = SimulationClock(pipe, mem, pred, bus)
        self.leak_detected = False
        self.leaked_addresses = []
        self.probe_results = {}
        self.recovered_secret = None

    def toggle_lfence(self, enabled: Optional[bool] = None, reset_sim: bool = True) -> bool:
        """Toggle LFENCE serialization barrier and optionally reset the scenario."""
        self.lfence_enabled = (not self.lfence_enabled) if enabled is None else enabled
        if reset_sim:
            self.load_scenario(self._scenario_path)
        elif self.pipeline is not None:
            self.pipeline.lfence_enforced = self.lfence_enabled
        return self.lfence_enabled

    def run_flush_reload_probe(self) -> dict[int, tuple[int, bool]]:
        """Measure access latency across candidate probe slots to detect warm L1 lines."""
        if self.memory is None or self.clock is None:
            return {}
        base = int(self.scenario_data.get("probe_base", 0x0800))
        stride = int(self.scenario_data.get("probe_stride", 64))
        slots = int(self.scenario_data.get("num_probe_slots", 8))
        cycle = self.clock.current_cycle

        results: dict[int, tuple[int, bool]] = {}
        recovered: Optional[int] = None
        for idx in range(slots):
            addr = base + idx * stride
            # Check warm status without mutating L1 permanently, or probe directly
            latency, is_hit = self.memory.probe_reload_time(addr, cycle)
            results[idx] = (latency, is_hit)
            if is_hit and recovered is None:
                recovered = idx
        self.probe_results = results
        self.recovered_secret = recovered
        return results

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        if snapshot.speculative_leak_events:
            self.leak_detected = True
            self.leaked_addresses = [ev.address for ev in snapshot.speculative_leak_events]

    def on_rewind(self, snapshot: CycleSnapshot) -> None:
        self.leak_detected = len(snapshot.speculative_leak_events) > 0
        self.leaked_addresses = [ev.address for ev in snapshot.speculative_leak_events]

    def check_victory(self) -> ModeOutcome:
        snap = self.get_clock().latest_snapshot()
        if self.lfence_enabled and snap.halted and not self.leak_detected:
            return ModeOutcome(
                finished=True,
                victory=True,
                title="LFENCE Mitigation Verified",
                message=f"Speculation serialized. 0 L1 leaks! CPI={snap.cpi:.2f}, Stalls={snap.stall_cycles}.",
            )
        if self.leak_detected and snap.halted:
            addr_str = ", ".join(f"0x{a:04X}" for a in self.leaked_addresses)
            return ModeOutcome(
                finished=True,
                victory=False,
                title="Side-Channel Leak Confirmed",
                message=f"Speculative load warmed L1 ({addr_str}). Toggle LFENCE ON to mitigate!",
            )
        return ModeOutcome(
            finished=False,
            victory=False,
            title="Monitoring Speculation",
            message="Step/Play to observe misprediction, or toggle LFENCE.",
        )

