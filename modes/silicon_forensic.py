"""Mode 4: Silicon Forensic — Crash dump loader, timeline scrubber, and dirty-tag evidence validator."""

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


DEFAULT_SCENARIO = Path(__file__).resolve().parents[1] / "scenarios" / "silicon_forensic.json"


class SiliconForensicMode(BaseMode):
    """Post-mortem crash dump timeline scrubber and dirty-tag evidence validator."""

    mode_id = "silicon_forensic"
    display_name = "Silicon Forensic"
    subtitle = "Crash Dump Timeline Scrubber & Dirty-Tag Evidence Validator"

    def __init__(self) -> None:
        super().__init__()
        self.crash_cycle: int = 0
        self.inspected_cycle: int = 0
        self.culprit_tag: int = 2
        self.culprit_cycle_min: int = 1
        self.culprit_cycle_max: int = 999
        self.evidence_submitted: bool = False
        self.evidence_verified: bool = False
        self.status_message: str = "Scrub timeline to locate the dirty L1 tag."

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        path = Path(scenario_path) if scenario_path else DEFAULT_SCENARIO
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self.scenario_data = data

        self.culprit_tag = int(data.get("culprit_tag", 2))
        self.culprit_cycle_min = int(data.get("culprit_cycle_min", 1))
        self.culprit_cycle_max = int(data.get("culprit_cycle_max", 999))
        self.evidence_submitted = False
        self.evidence_verified = False
        self.status_message = f"Scrub timeline to find dirty L1 tag 0x{self.culprit_tag:X}."

        l1_cfg = data.get("l1_config", {})
        mem = MemorySubsystem(
            l1_config=CacheConfig(
                name="L1",
                size_bytes=int(l1_cfg.get("size_bytes", 256)),
                line_size=int(l1_cfg.get("line_size", 64)),
                associativity=int(l1_cfg.get("associativity", 1)),
                hit_latency=int(l1_cfg.get("hit_latency", 1)),
            ),
            dram_latency=int(data.get("dram_latency", 4)),
        )
        mem.load_dram_words({int(k): int(v) for k, v in data.get("dram_words", {}).items()})

        prog = assemble_program("\n".join(data.get("assembly", [])))
        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=1)
        bus = BusSubsystem(BusTopology.MULTI_BUS)
        pipe = Pipeline(memory=mem, predictor=pred, bus=bus, forwarding_enabled=True, speculative_execution=True)
        pipe.load_program(prog.instructions)

        clock = SimulationClock(pipe, mem, pred, bus)
        for _ in range(60):
            snap = clock.step_cycle()
            if snap.halted:
                break

        self.clock = clock
        self.crash_cycle = clock.current_cycle
        self.inspected_cycle = self.crash_cycle

    def scrub_cycle(self, target_cycle: int) -> CycleSnapshot:
        """Restore live view to any historical cycle without erasing future crash dump frames."""
        clock = self.get_clock()
        clamped = max(0, min(self.crash_cycle, target_cycle))
        snap = clock.get_snapshot(clamped)
        if snap is not None:
            clock.restore_snapshot(snap)
            self.inspected_cycle = snap.cycle
            return snap
        return clock.latest_snapshot()

    def submit_evidence(self, tag: Optional[int] = None) -> bool:
        """Validate whether inspected cycle contains the culprit dirty L1 cache line."""
        clock = self.get_clock()
        snap = clock.get_snapshot(self.inspected_cycle) or clock.latest_snapshot()
        self.evidence_submitted = True

        dirty_tags = [ln.tag for ln in snap.l1_lines if ln.valid and ln.dirty]
        target_tag = self.culprit_tag if tag is None else tag

        in_window = self.culprit_cycle_min <= snap.cycle <= self.culprit_cycle_max
        if target_tag in dirty_tags and in_window:
            self.evidence_verified = True
            self.status_message = f"Verified! Dirty tag 0x{target_tag:X} isolated at cycle {snap.cycle}."
            return True

        self.evidence_verified = False
        self.status_message = f"No matching dirty tag 0x{target_tag:X} at cycle {snap.cycle}. Keep scrubbing!"
        return False

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        self.inspected_cycle = snapshot.cycle

    def on_rewind(self, snapshot: CycleSnapshot) -> None:
        self.inspected_cycle = snapshot.cycle

    def check_victory(self) -> ModeOutcome:
        if self.evidence_verified:
            return ModeOutcome(True, True, "Evidence Verified!", self.status_message)
        return ModeOutcome(False, False, f"Crash @ Cycle {self.crash_cycle}", self.status_message)

