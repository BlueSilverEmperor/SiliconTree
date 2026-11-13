"""Base HUD overlay interface for SiliconTree simulation modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
import pygame
import pygame_gui

from core_engine.clock import CycleSnapshot


class BaseOverlay(ABC):
    """Abstract overlay rendered in the mode HUD dock on top of/beside core components."""

    def __init__(self, ui_manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self.ui_manager = ui_manager
        self.rect = rect

    @abstractmethod
    def rebuild(self, rect: pygame.Rect) -> None:
        """Reposition pygame-gui elements when window resizes."""

    @abstractmethod
    def kill(self) -> None:
        """Destroy any owned pygame-gui elements when switching modes."""

    def handle_event(self, event: pygame.event.Event) -> None:
        """Optional pygame / pygame_gui event handler."""

    @abstractmethod
    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        """Render mode-specific HUD widgets."""

