"""Abstract base class for all SiliconTree game/simulation modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from core_engine.clock import CycleSnapshot, SimulationClock


@dataclass(frozen=True)
class ModeOutcome:
    """Evaluated status of a mode objective."""

    finished: bool
    victory: bool
    title: str
    message: str


class BaseMode(ABC):
    """Abstract interface implemented by all 5 SiliconTree branches."""

    mode_id: str = "base"
    display_name: str = "Base Mode"
    subtitle: str = ""

    def __init__(self) -> None:
        self.clock: Optional[SimulationClock] = None
        self.scenario_data: dict[str, Any] = {}

    @abstractmethod
    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        """Load JSON/built-in scenario and initialize core_engine subsystems."""

    @abstractmethod
    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        """Evaluate mode-specific rules/scoring after a clock cycle advances."""

    @abstractmethod
    def check_victory(self) -> ModeOutcome:
        """Return whether the scenario has been won, lost, or is still in progress."""

    def on_rewind(self, snapshot: CycleSnapshot) -> None:
        """Optional hook called when the user rewinds the simulation clock."""

    def get_clock(self) -> SimulationClock:
        if self.clock is None:
            raise RuntimeError(f"Mode '{self.mode_id}' has not called load_scenario()")
        return self.clock

