"""Branch predictor: Static and 2-bit saturating counter with BTB and speculative rollback tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PredictorMode(str, Enum):
    """Supported branch prediction policies."""

    STATIC_NOT_TAKEN = "STATIC_NOT_TAKEN"
    STATIC_TAKEN = "STATIC_TAKEN"
    TWO_BIT_SATURATING = "TWO_BIT_SATURATING"


@dataclass(frozen=True)
class BranchPrediction:
    """Prediction outcome returned at IF/ID."""

    predicted_taken: bool
    predicted_target: int
    counter_state: int


@dataclass(frozen=True)
class BranchPredictorSnapshot:
    """Immutable snapshot of branch predictor state."""

    mode: PredictorMode
    counters: tuple[tuple[int, int], ...]
    btb: tuple[tuple[int, int], ...]
    predictions: int
    mispredictions: int
    flushes: int


class BranchPredictor:
    """Configurable branch predictor with 2-bit saturating counters and BTB."""

    # 2-bit FSM states: 0=SNT, 1=WNT, 2=WT, 3=ST
    STATE_LABELS = {
        0: "SNT (00)",
        1: "WNT (01)",
        2: "WT  (10)",
        3: "ST  (11)",
    }

    def __init__(self, mode: PredictorMode = PredictorMode.TWO_BIT_SATURATING, initial_state: int = 1) -> None:
        self.mode = mode
        self.initial_state = max(0, min(3, initial_state))
        self.counters: dict[int, int] = {}
        self.btb: dict[int, int] = {}
        self.predictions: int = 0
        self.mispredictions: int = 0
        self.flushes: int = 0

    def train_branch(self, pc: int, target: int, taken: bool = True) -> None:
        """Pre-train predictor (e.g., to simulate Spectre branch-predictor poisoning)."""
        self.btb[pc] = target
        self.counters[pc] = 3 if taken else 0

    def get_counter(self, pc: int) -> int:
        return self.counters.get(pc, self.initial_state)

    def predict(self, pc: int, fallthrough_pc: int, known_target: Optional[int] = None) -> BranchPrediction:
        """Predict whether a branch at `pc` is taken and return its target."""
        self.predictions += 1
        target = known_target if known_target is not None else self.btb.get(pc, fallthrough_pc)

        if self.mode == PredictorMode.STATIC_NOT_TAKEN:
            return BranchPrediction(predicted_taken=False, predicted_target=fallthrough_pc, counter_state=0)

        if self.mode == PredictorMode.STATIC_TAKEN:
            taken = known_target is not None or pc in self.btb
            return BranchPrediction(
                predicted_taken=taken,
                predicted_target=target if taken else fallthrough_pc,
                counter_state=3 if taken else 0,
            )

        state = self.counters.get(pc, self.initial_state)
        predicted_taken = state >= 2
        if predicted_taken and (known_target is None and pc not in self.btb):
            predicted_taken = False
        return BranchPrediction(
            predicted_taken=predicted_taken,
            predicted_target=target if predicted_taken else fallthrough_pc,
            counter_state=state,
        )

    def update(self, pc: int, actual_taken: bool, actual_target: int, was_mispredicted: bool) -> None:
        """Update predictor FSM and BTB on branch resolution."""
        if actual_taken:
            self.btb[pc] = actual_target

        state = self.counters.get(pc, self.initial_state)
        if actual_taken:
            state = min(3, state + 1)
        else:
            state = max(0, state - 1)
        self.counters[pc] = state

        if was_mispredicted:
            self.mispredictions += 1
            self.flushes += 1

    def snapshot(self) -> BranchPredictorSnapshot:
        return BranchPredictorSnapshot(
            mode=self.mode,
            counters=tuple(sorted(self.counters.items())),
            btb=tuple(sorted(self.btb.items())),
            predictions=self.predictions,
            mispredictions=self.mispredictions,
            flushes=self.flushes,
        )

    def restore(self, snap: BranchPredictorSnapshot) -> None:
        self.mode = snap.mode
        self.counters = dict(snap.counters)
        self.btb = dict(snap.btb)
        self.predictions = snap.predictions
        self.mispredictions = snap.mispredictions
        self.flushes = snap.flushes

