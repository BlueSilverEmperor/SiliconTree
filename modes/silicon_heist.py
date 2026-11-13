"""Mode 2: Silicon Heist — Stealth puzzle via control hazards, cache locker touches, and DMA escape."""

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


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "silicon_heist.json"


class SiliconHeistMode(BaseMode):
    """Stealth infiltration mode: touch L1 lockers quietly and exfiltrate via DMA."""

    mode_id = "silicon_heist"
    display_name = "Silicon Heist"
    subtitle = "Control-Hazard Stealth, Cache Lockers & Cycle-Stealing DMA Escape"

    def __init__(self) -> None:
        super().__init__()
        self.stealth_state: str = "INFILTRATING"
        self.target_lockers: set[int] = set()
        self.alarm_addresses: set[int] = set()
        self.lockers_touched: set[int] = set()
        self.stealth_noise: int = 0
        self.max_noise: int = 5
        self.dma_triggered: bool = False
        self.escaped: bool = False
        self.bus: Optional[BusSubsystem] = None
        self.memory: Optional[MemorySubsystem] = None
        self._last_flushes: int = 0
        self._state_history: dict[int, tuple[str, set[int], int, bool, bool, int]] = {}

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        path = Path(scenario_path) if scenario_path else DEFAULT_SCENARIO
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.scenario_data = data

        self.target_lockers = {int(a) for a in data.get("target_lockers", [0x0300, 0x0340])}
        self.alarm_addresses = {int(a) for a in data.get("alarm_addresses", [0x0F00])}
        self.max_noise = int(data.get("max_noise", 5))
        self.lockers_touched = set()
        self.stealth_noise = 0
        self.stealth_state = "INFILTRATING"
        self.dma_triggered = False
        self.escaped = False
        self._last_flushes = 0

        l1_cfg = data.get("l1_config", {})
        mem = MemorySubsystem(
            l1_config=CacheConfig(
                name="L1",
                size_bytes=int(l1_cfg.get("size_bytes", 512)),
                line_size=int(l1_cfg.get("line_size", 64)),
                associativity=int(l1_cfg.get("associativity", 2)),
                hit_latency=int(l1_cfg.get("hit_latency", 1)),
            ),
            dram_latency=int(data.get("dram_latency", 4)),
        )
        mem.load_dram_words({int(k): int(v) for k, v in data.get("dram_words", {}).items()})

        prog = assemble_program("\n".join(data.get("assembly", [])))
        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=2)
        bus = BusSubsystem(BusTopology.SINGLE_BUS)
        pipe = Pipeline(memory=mem, predictor=pred, bus=bus, forwarding_enabled=True, speculative_execution=True)
        pipe.load_program(prog.instructions)

        self.memory = mem
        self.bus = bus
        self.clock = SimulationClock(pipe, mem, pred, bus)
        self._state_history = {0: (self.stealth_state, set(), 0, False, False, 0)}

    def trigger_dma_escape(self) -> bool:
        """Start cycle-stealing DMA transfer to exfiltrate locker contents."""
        if self.bus is None or self.stealth_state == "DETECTED":
            return False
        src = int(self.scenario_data.get("dma_src", 0x0300))
        dst = int(self.scenario_data.get("dma_dst", 0x0900))
        words = int(self.scenario_data.get("dma_words", 2))
        self.bus.start_dma(src_addr=src, dst_addr=dst, word_count=words, cycle_stealing=True)
        self.dma_triggered = True
        if self.stealth_state == "LOCKERS_BREACHED":
            self.stealth_state = "DMA_ESCAPING"
        return True

    def inject_alarm_noise(self, amount: int = 3) -> None:
        """Simulate sloppy timing noise that pushes stealth meter toward detection."""
        self.stealth_noise += amount
        if self.stealth_noise >= self.max_noise:
            self.stealth_state = "DETECTED"

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        if self.stealth_state == "DETECTED":
            self._save_history(snapshot.cycle)
            return

        # Check flush noise
        if snapshot.speculative_flushes > self._last_flushes:
            self.stealth_noise += (snapshot.speculative_flushes - self._last_flushes) * 2
            self._last_flushes = snapshot.speculative_flushes

        # Check memory accesses for locker touches or alarm traps
        acc = snapshot.last_mem_access
        if acc is not None:
            if acc.address in self.alarm_addresses:
                self.stealth_noise = self.max_noise
                self.stealth_state = "DETECTED"
                self._save_history(snapshot.cycle)
                return
            if acc.address in self.target_lockers:
                self.lockers_touched.add(acc.address)

        # Also check speculative leak events against alarm addresses
        for ev in snapshot.speculative_leak_events:
            if ev.address in self.alarm_addresses:
                self.stealth_noise = self.max_noise
                self.stealth_state = "DETECTED"
                self._save_history(snapshot.cycle)
                return

        if self.stealth_noise >= self.max_noise:
            self.stealth_state = "DETECTED"
        elif self.lockers_touched >= self.target_lockers:
            if self.dma_triggered and not snapshot.dma_active and snapshot.dma_words_transferred > 0:
                self.escaped = True
                self.stealth_state = "ESCAPED"
            elif self.dma_triggered:
                self.stealth_state = "DMA_ESCAPING"
            else:
                self.stealth_state = "LOCKERS_BREACHED"

        self._save_history(snapshot.cycle)

    def _save_history(self, cycle: int) -> None:
        self._state_history[cycle] = (
            self.stealth_state,
            set(self.lockers_touched),
            self.stealth_noise,
            self.dma_triggered,
            self.escaped,
            self._last_flushes,
        )

    def on_rewind(self, snapshot: CycleSnapshot) -> None:
        if snapshot.cycle in self._state_history:
            st, touched, noise, dma, esc, flushes = self._state_history[snapshot.cycle]
            self.stealth_state = st
            self.lockers_touched = set(touched)
            self.stealth_noise = noise
            self.dma_triggered = dma
            self.escaped = esc
            self._last_flushes = flushes

    def check_victory(self) -> ModeOutcome:
        if self.stealth_state == "DETECTED":
            return ModeOutcome(True, False, "Watchdog Triggered!", "Stealth noise exceeded threshold or alarm line touched.")
        if self.escaped:
            return ModeOutcome(True, True, "Heist Escaped!", "All L1 lockers touched & exfiltrated via cycle-stealing DMA.")
        if self.stealth_state == "LOCKERS_BREACHED":
            return ModeOutcome(False, False, "Lockers Breached", "Press DMA ESCAPE to exfiltrate payload.")
        return ModeOutcome(False, False, "Infiltrating", f"Touch lockers ({len(self.lockers_touched)}/{len(self.target_lockers)}).")

