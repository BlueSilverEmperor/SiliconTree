"""Reusable 60 FPS hardware visualization components."""

from gui.components.bus_animator import BusAnimator
from gui.components.cache_matrix import CacheMatrixView
from gui.components.control_deck import ControlDeck, ControlDeckActions
from gui.components.pipeline_view import PipelineView
from gui.components.register_file import RegisterFileView

__all__ = [
    "BusAnimator",
    "CacheMatrixView",
    "ControlDeck",
    "ControlDeckActions",
    "PipelineView",
    "RegisterFileView",
]

