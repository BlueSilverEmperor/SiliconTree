"""Control Deck using pygame-gui: Play, Pause, Step (+1), Rewind (-1), Reset, and Clock Speed slider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider, UILabel

from core_engine.clock import CycleSnapshot
from gui.theme import PALETTE, FontBank


@dataclass(frozen=True)
class ControlDeckActions:
    """Events emitted by ControlDeck on a UI frame."""

    toggle_play: bool = False
    step_forward: bool = False
    rewind_one: bool = False
    reset: bool = False
    back_to_hub: bool = False
    new_speed_hz: Optional[float] = None


class ControlDeck:
    """Bottom/top simulation transport controls built with pygame-gui."""

    def __init__(self, ui_manager: pygame_gui.UIManager, rect: pygame.Rect, fonts: FontBank) -> None:
        self.ui_manager = ui_manager
        self.fonts = fonts
        self.rect = rect
        self.is_playing: bool = False
        self.speed_hz: float = 4.0

        self.btn_hub: Optional[UIButton] = None
        self.btn_rewind: Optional[UIButton] = None
        self.btn_play: Optional[UIButton] = None
        self.btn_step: Optional[UIButton] = None
        self.btn_reset: Optional[UIButton] = None
        self.speed_slider: Optional[UIHorizontalSlider] = None
        self.speed_label: Optional[UILabel] = None

        self.rebuild(rect)

    def kill(self) -> None:
        for elem in (
            self.btn_hub,
            self.btn_rewind,
            self.btn_play,
            self.btn_step,
            self.btn_reset,
            self.speed_slider,
            self.speed_label,
        ):
            if elem is not None:
                elem.kill()

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        y = rect.y + 8
        h = max(28, rect.height - 16)
        x = rect.x + 10

        self.btn_hub = UIButton(pygame.Rect(x, y, 78, h), "HUB", self.ui_manager)
        x += 86
        self.btn_rewind = UIButton(pygame.Rect(x, y, 92, h), "<< -1 CYC", self.ui_manager)
        x += 98
        self.btn_play = UIButton(pygame.Rect(x, y, 86, h), "PAUSE" if self.is_playing else "PLAY", self.ui_manager)
        x += 92
        self.btn_step = UIButton(pygame.Rect(x, y, 92, h), "+1 CYC >>", self.ui_manager)
        x += 98
        self.btn_reset = UIButton(pygame.Rect(x, y, 76, h), "RESET", self.ui_manager)
        x += 88

        self.speed_slider = UIHorizontalSlider(
            pygame.Rect(x, y + 4, 150, h - 8),
            start_value=self.speed_hz,
            value_range=(1.0, 30.0),
            manager=self.ui_manager,
        )
        x += 158
        self.speed_label = UILabel(
            pygame.Rect(x, y, 88, h),
            f"{self.speed_hz:.0f} Hz",
            self.ui_manager,
        )

    def set_playing(self, playing: bool) -> None:
        self.is_playing = playing
        if self.btn_play is not None:
            self.btn_play.set_text("PAUSE" if playing else "PLAY")

    def handle_event(self, event: pygame.event.Event) -> ControlDeckActions:
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.btn_play:
                return ControlDeckActions(toggle_play=True)
            if event.ui_element == self.btn_step:
                return ControlDeckActions(step_forward=True)
            if event.ui_element == self.btn_rewind:
                return ControlDeckActions(rewind_one=True)
            if event.ui_element == self.btn_reset:
                return ControlDeckActions(reset=True)
            if event.ui_element == self.btn_hub:
                return ControlDeckActions(back_to_hub=True)

        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and event.ui_element == self.speed_slider:
            self.speed_hz = float(event.value)
            if self.speed_label is not None:
                self.speed_label.set_text(f"{self.speed_hz:.0f} Hz")
            return ControlDeckActions(new_speed_hz=self.speed_hz)

        return ControlDeckActions()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, mode_title: str) -> None:
        pygame.draw.rect(surface, PALETTE.bg_panel, self.rect, border_radius=8)
        pygame.draw.rect(surface, PALETTE.border_subtle, self.rect, width=1, border_radius=8)

        mono_md = self.fonts.get(13, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        metrics_txt = (
            f"{mode_title}  |  CYCLE: {snapshot.cycle:04d}  |  "
            f"RETIRED: {snapshot.instructions_retired}  |  "
            f"CPI: {snapshot.cpi:.2f}  |  "
            f"{'HALTED' if snapshot.halted else ('RUNNING' if self.is_playing else 'PAUSED')}"
        )
        col = PALETTE.emerald if not snapshot.halted else PALETTE.amber
        m_surf = mono_md.render(metrics_txt, True, col)
        rx = self.rect.right - m_surf.get_width() - 14
        ry = self.rect.y + 8
        if rx > (self.speed_label.rect.right + 8 if self.speed_label else self.rect.x + 700):
            surface.blit(m_surf, (rx, ry))
        else:
            compact = f"C:{snapshot.cycle} RET:{snapshot.instructions_retired} CPI:{snapshot.cpi:.2f}"
            c_surf = mono_sm.render(compact, True, col)
            surface.blit(c_surf, (self.rect.right - c_surf.get_width() - 12, self.rect.y + 14))

