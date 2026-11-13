"""Mode 5: Architect Tycoon — Die area budgeter, clock/power tuner, and client contract evaluator."""

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
    Pipeline,
    PredictorMode,
    SimulationClock,
    assemble_program,
)
from modes.base_mode import BaseMode, ModeOutcome


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "architect_tycoon.json"


class ArchitectTycoonMode(BaseMode):
    """Hardware architecture budgeter and synthetic client benchmark evaluator."""

    mode_id = "architect_tycoon"
    display_name = "Architect Tycoon"
    subtitle = "Die Area Budgeter, Clock/Power Tuner & Client Contract Benchmarks"

    def __init__(self) -> None:
        super().__init__()
        self.clock_ghz: float = 2.4
        self.l1_size_bytes: int = 256
        self.l1_associativity: int = 1
        self.forwarding_enabled: bool = True
        self.bus_topology: BusTopology = BusTopology.MULTI_BUS

        self.max_area_mm2: float = 42.0
        self.max_power_w: float = 18.0
        self.target_cpi: float = 2.8

        self.contract_evaluated: bool = False
        self.contract_passed: bool = False
        self.last_benchmark_cpi: float = 0.0
        self.eval_message: str = "Tune silicon parameters and click EVALUATE CONTRACT."

    def die_area_mm2(self) -> float:
        base_core = 14.0
        fwd_area = 3.0 if self.forwarding_enabled else 0.0
        bus_area = 4.0 if self.bus_topology == BusTopology.MULTI_BUS else 1.5
        cache_lines = self.l1_size_bytes / 64.0
        cache_area = cache_lines * (1.4 + 0.4 * self.l1_associativity)
        return round(base_core + fwd_area + bus_area + cache_area, 2)

    def power_watts(self) -> float:
        area = self.die_area_mm2()
        return round((area * 0.14) * (self.clock_ghz ** 1.35), 2)

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        path = Path(scenario_path) if scenario_path else DEFAULT_SCENARIO
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.scenario_data = data

        self.max_area_mm2 = float(data.get("max_area_mm2", 42.0))
        self.max_power_w = float(data.get("max_power_w", 18.0))
        self.target_cpi = float(data.get("target_cpi", 2.8))
        self.contract_evaluated = False
        self.contract_passed = False
        self.last_benchmark_cpi = 0.0
        self.eval_message = "Tune silicon parameters and click EVALUATE CONTRACT."
        self._rebuild_engine()

    def _rebuild_engine(self) -> None:
        data = self.scenario_data
        mem = MemorySubsystem(
            l1_config=CacheConfig(
                name="L1",
                size_bytes=self.l1_size_bytes,
                line_size=64,
                associativity=self.l1_associativity,
                hit_latency=1,
            ),
            dram_latency=int(data.get("dram_latency", 5)),
        )
        mem.load_dram_words({int(k): int(v) for k, v in data.get("dram_words", {}).items()})
        prog = assemble_program("\n".join(data.get("assembly", [])))
        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=2)
        bus = BusSubsystem(self.bus_topology)
        pipe = Pipeline(
            memory=mem,
            predictor=pred,
            bus=bus,
            forwarding_enabled=self.forwarding_enabled,
            speculative_execution=True,
        )
        pipe.load_program(prog.instructions)
        self.clock = SimulationClock(pipe, mem, pred, bus)

    def configure(
        self,
        clock_ghz: Optional[float] = None,
        l1_associativity: Optional[int] = None,
        forwarding_enabled: Optional[bool] = None,
        bus_topology: Optional[BusTopology] = None,
    ) -> None:
        if clock_ghz is not None:
            self.clock_ghz = max(1.0, min(4.5, clock_ghz))
        if l1_associativity is not None:
            self.l1_associativity = l1_associativity
        if forwarding_enabled is not None:
            self.forwarding_enabled = forwarding_enabled
        if bus_topology is not None:
            self.bus_topology = bus_topology
        self.contract_evaluated = False
        self._rebuild_engine()

    def evaluate_contract(self) -> ModeOutcome:
        """Run the synthetic client benchmark end-to-end and grade Area/Power/CPI."""
        self._rebuild_engine()
        clock = self.get_clock()
        for _ in range(150):
            snap = clock.step_cycle()
            if snap.halted:
                break

        final = clock.latest_snapshot()
        area = self.die_area_mm2()
        power = self.power_watts()
        # Normalize effective CPI by clock frequency relative to 2.0 GHz baseline
        eff_cpi = round(final.cpi * (2.0 / self.clock_ghz), 2) if final.cpi > 0 else 99.0
        self.last_benchmark_cpi = eff_cpi
        self.contract_evaluated = True

        area_ok = area <= self.max_area_mm2
        power_ok = power <= self.max_power_w
        cpi_ok = eff_cpi <= self.target_cpi
        self.contract_passed = area_ok and power_ok and cpi_ok

        if self.contract_passed:
            self.eval_message = f"CONTRACT WON! Area {area}mm2, {power}W, Eff-CPI {eff_cpi:.2f}"
        else:
            fails = []
            if not area_ok:
                fails.append(f"Area {area}>{self.max_area_mm2}")
            if not power_ok:
                fails.append(f"Power {power}>{self.max_power_w}W")
            if not cpi_ok:
                fails.append(f"CPI {eff_cpi:.2f}>{self.target_cpi}")
            self.eval_message = "FAILED: " + ", ".join(fails)
        return self.check_victory()

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        return

    def check_victory(self) -> ModeOutcome:
        client = self.scenario_data.get("client_name", "Client")
        if self.contract_evaluated:
            return ModeOutcome(
                finished=True,
                victory=self.contract_passed,
                title=f"{client}: {'ACCEPTED' if self.contract_passed else 'REJECTED'}",
                message=self.eval_message,
            )
        return ModeOutcome(
            finished=False,
            victory=False,
            title=f"{client} Contract",
            message=f"Limits: <= {self.max_area_mm2}mm2, <= {self.max_power_w}W, Eff-CPI <= {self.target_cpi}",
        )

