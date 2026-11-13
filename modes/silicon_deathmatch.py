"""Mode 3: Silicon Deathmatch — Wave survival, thermal HP, and hardware upgrade drafting."""

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


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "silicon_deathmatch.json"

UPGRADE_CATALOG: dict[str, str] = {
    "CACHE_4WAY": "4-Way Set-Assoc L1 (Cuts Conflict Misses)",
    "COOLING_SINK": "Vapor-Chamber Sink (+35 HP, -25% Heat)",
    "PREDICTOR_2BIT": "2-Bit Branch Predictor",
}


class SiliconDeathmatchMode(BaseMode):
    """Wave-based architecture survival with thermal HP and hardware drafting."""

    mode_id = "silicon_deathmatch"
    display_name = "Silicon Deathmatch"
    subtitle = "Workload Wave Survival, Thermal HP & Hardware Upgrades"

    def __init__(self) -> None:
        super().__init__()
        self.max_thermal_hp: float = 100.0
        self.thermal_hp: float = 100.0
        self.heat_multiplier: float = 1.0
        self.wave_index: int = 0
        self.waves: list[dict[str, Any]] = []
        self.upgrade_draft_open: bool = False
        self.applied_upgrades: list[str] = []
        self.thermal_meltdown: bool = False
        self.all_waves_cleared: bool = False

        self.l1_associativity: int = 1
        self.memory: Optional[MemorySubsystem] = None
        self.pipeline: Optional[Pipeline] = None
        self.predictor: Optional[BranchPredictor] = None
        self.bus: Optional[BusSubsystem] = None

        self._last_cm: int = 0
        self._last_stalls: int = 0
        self._last_retired: int = 0
        self._hp_history: dict[int, tuple[float, int, int, int]] = {}

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        path = Path(scenario_path) if scenario_path else DEFAULT_SCENARIO
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.scenario_data = data

        self.max_thermal_hp = float(data.get("max_thermal_hp", 100.0))
        self.thermal_hp = self.max_thermal_hp
        self.heat_multiplier = 1.0
        self.waves = list(data.get("waves", []))
        self.wave_index = 0
        self.upgrade_draft_open = False
        self.applied_upgrades = []
        self.thermal_meltdown = False
        self.all_waves_cleared = False

        l1_cfg = data.get("initial_l1", {})
        self.l1_associativity = int(l1_cfg.get("associativity", 1))
        self._init_hardware_for_wave(0)

    def _init_hardware_for_wave(self, wave_idx: int) -> None:
        data = self.scenario_data
        l1_cfg = data.get("initial_l1", {})
        mem = MemorySubsystem(
            l1_config=CacheConfig(
                name="L1",
                size_bytes=int(l1_cfg.get("size_bytes", 256)),
                line_size=int(l1_cfg.get("line_size", 64)),
                associativity=self.l1_associativity,
                hit_latency=int(l1_cfg.get("hit_latency", 1)),
            ),
            dram_latency=int(data.get("dram_latency", 4)),
        )
        mem.load_dram_words({int(k): int(v) for k, v in data.get("dram_words", {}).items()})

        pred_mode = PredictorMode.TWO_BIT_SATURATING if "PREDICTOR_2BIT" in self.applied_upgrades else PredictorMode.STATIC_NOT_TAKEN
        pred = BranchPredictor(pred_mode, initial_state=2)
        bus = BusSubsystem(BusTopology.MULTI_BUS)
        pipe = Pipeline(memory=mem, predictor=pred, bus=bus, forwarding_enabled=True, speculative_execution=True)

        wave = self.waves[wave_idx]
        prog = assemble_program("\n".join(wave.get("assembly", [])))
        pipe.load_program(prog.instructions)

        self.memory = mem
        self.pipeline = pipe
        self.predictor = pred
        self.bus = bus
        self.clock = SimulationClock(pipe, mem, pred, bus)
        self._last_cm = 0
        self._last_stalls = 0
        self._last_retired = 0
        self._hp_history = {0: (self.thermal_hp, 0, 0, 0)}

    def apply_upgrade(self, upgrade_id: str) -> bool:
        """Apply a drafted hardware upgrade between waves."""
        if upgrade_id not in UPGRADE_CATALOG:
            return False
        if upgrade_id not in self.applied_upgrades:
            self.applied_upgrades.append(upgrade_id)
        if upgrade_id == "CACHE_4WAY":
            self.l1_associativity = 4
            if self.memory is not None and self.pipeline is not None:
                l1_cfg = self.scenario_data.get("initial_l1", {})
                new_mem = MemorySubsystem(
                    l1_config=CacheConfig(
                        name="L1",
                        size_bytes=int(l1_cfg.get("size_bytes", 256)),
                        line_size=int(l1_cfg.get("line_size", 64)),
                        associativity=4,
                        hit_latency=int(l1_cfg.get("hit_latency", 1)),
                    ),
                    dram_latency=int(self.scenario_data.get("dram_latency", 4)),
                )
                new_mem.load_dram_words({int(k): int(v) for k, v in self.scenario_data.get("dram_words", {}).items()})
                self.memory = new_mem
                self.pipeline.memory = new_mem
                if self.clock is not None:
                    self.clock.memory = new_mem
        elif upgrade_id == "COOLING_SINK":
            self.thermal_hp = min(self.max_thermal_hp, self.thermal_hp + 35.0)
            self.heat_multiplier = 0.75
        elif upgrade_id == "PREDICTOR_2BIT" and self.predictor is not None:
            self.predictor.mode = PredictorMode.TWO_BIT_SATURATING
        return True

    def start_next_wave(self) -> bool:
        """Advance to the next wave keeping thermal HP and applied upgrades."""
        if self.wave_index + 1 >= len(self.waves):
            self.all_waves_cleared = True
            self.upgrade_draft_open = False
            return False
        self.wave_index += 1
        self.upgrade_draft_open = False
        self._init_hardware_for_wave(self.wave_index)
        return True

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        if self.thermal_meltdown or self.all_waves_cleared:
            return

        cm_dmg = float(self.scenario_data.get("conflict_miss_damage", 6.0))
        stall_dmg = float(self.scenario_data.get("stall_heat", 0.4))
        cool = float(self.scenario_data.get("retire_cooling", 0.2))

        d_cm = max(0, snapshot.l1_conflict_misses - self._last_cm)
        d_st = max(0, snapshot.stall_cycles - self._last_stalls)
        d_ret = max(0, snapshot.instructions_retired - self._last_retired)

        self.thermal_hp -= (d_cm * cm_dmg + d_st * stall_dmg) * self.heat_multiplier
        self.thermal_hp = min(self.max_thermal_hp, self.thermal_hp + d_ret * cool)

        self._last_cm = snapshot.l1_conflict_misses
        self._last_stalls = snapshot.stall_cycles
        self._last_retired = snapshot.instructions_retired

        if self.thermal_hp <= 0.0:
            self.thermal_hp = 0.0
            self.thermal_meltdown = True
        elif snapshot.halted:
            if self.wave_index + 1 >= len(self.waves):
                self.all_waves_cleared = True
            else:
                self.upgrade_draft_open = True

        self._hp_history[snapshot.cycle] = (self.thermal_hp, self._last_cm, self._last_stalls, self._last_retired)

    def on_rewind(self, snapshot: CycleSnapshot) -> None:
        if snapshot.cycle in self._hp_history:
            hp, cm, st, ret = self._hp_history[snapshot.cycle]
            self.thermal_hp = hp
            self._last_cm = cm
            self._last_stalls = st
            self._last_retired = ret
            self.thermal_meltdown = hp <= 0.0
            self.upgrade_draft_open = False

    def check_victory(self) -> ModeOutcome:
        if self.thermal_meltdown:
            return ModeOutcome(True, False, "Thermal Meltdown!", "Conflict misses & stalls overheated the die.")
        if self.all_waves_cleared:
            return ModeOutcome(True, True, "Arena Survived!", f"Cleared all {len(self.waves)} waves with {self.thermal_hp:.1f} HP.")
        wave_name = self.waves[self.wave_index]["name"] if self.waves else "Wave"
        if self.upgrade_draft_open:
            return ModeOutcome(False, False, f"{wave_name} Cleared!", "Draft a hardware upgrade and start next wave.")
        return ModeOutcome(False, False, wave_name, f"Thermal HP: {self.thermal_hp:.1f}/{self.max_thermal_hp:.0f} | L1 {self.l1_associativity}-Way")

