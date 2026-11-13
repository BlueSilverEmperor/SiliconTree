"""Architect Tycoon HUD overlay: clock/power tuner, cache associativity toggle, contract evaluator."""

from __future__ import annotations

from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider

from core_engine.clock import CycleSnapshot
from gui.overlays.base_overlay import BaseOverlay
from gui.theme import PALETTE, FontBank
from modes.architect_tycoon import ArchitectTycoonMode


class TycoonHUDOverlay(BaseOverlay):
    """HUD overlay for Mode 5: Architect Tycoon."""

    def __init__(
        self,
        ui_manager: pygame_gui.UIManager,
        rect: pygame.Rect,
        mode: ArchitectTycoonMode,
        fonts: FontBank,
    ) -> None:
        super().__init__(ui_manager, rect)
        self.mode = mode
        self.fonts = fonts
        self.clk_slider: Optional[UIHorizontalSlider] = None
        self.btn_assoc: Optional[UIButton] = None
        self.btn_fwd: Optional[UIButton] = None
        self.btn_eval: Optional[UIButton] = None
        self.rebuild(rect)

    def kill(self) -> None:
        for elem in (self.clk_slider, self.btn_assoc, self.btn_fwd, self.btn_eval):
            if elem is not None:
                elem.kill()
        self.clk_slider = None
        self.btn_assoc = None
        self.btn_fwd = None
        self.btn_eval = None

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        self.clk_slider = UIHorizontalSlider(
            pygame.Rect(rect.x + 14, rect.y + 48, 170, 24),
            start_value=self.mode.clock_ghz,
            value_range=(1.0, 4.5),
            manager=self.ui_manager,
        )
        self.btn_assoc = UIButton(
            pygame.Rect(rect.x + 196, rect.y + 44, 128, 30),
            f"L1: {self.mode.l1_associativity}-WAY",
            self.ui_manager,
        )
        self.btn_fwd = UIButton(
            pygame.Rect(rect.x + 332, rect.y + 44, 128, 30),
            f"FWD: {'ON' if self.mode.forwarding_enabled else 'OFF'}",
            self.ui_manager,
        )
        self.btn_eval = UIButton(
            pygame.Rect(rect.right - 196, rect.y + 42, 182, 34),
            "EVALUATE CONTRACT",
            self.ui_manager,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and event.ui_element == self.clk_slider:
            self.mode.configure(clock_ghz=float(event.value))
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.btn_assoc:
                nxt = {1: 2, 2: 4, 4: 1}.get(self.mode.l1_associativity, 1)
                self.mode.configure(l1_associativity=nxt)
                if self.btn_assoc:
                    self.btn_assoc.set_text(f"L1: {nxt}-WAY")
            elif event.ui_element == self.btn_fwd:
                nxt_fwd = not self.mode.forwarding_enabled
                self.mode.configure(forwarding_enabled=nxt_fwd)
                if self.btn_fwd:
                    self.btn_fwd.set_text(f"FWD: {'ON' if nxt_fwd else 'OFF'}")
            elif event.ui_element == self.btn_eval:
                self.mode.evaluate_contract()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        outcome = self.mode.check_victory()
        border = PALETTE.emerald if (outcome.finished and outcome.victory) else (
            PALETTE.crimson if outcome.finished else PALETTE.cyan
        )
        pygame.draw.rect(surface, PALETTE.bg_panel, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if outcome.finished else 1, border_radius=8)

        mono_md = self.fonts.get(12, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        area = self.mode.die_area_mm2()
        power = self.mode.power_watts()
        hdr = (
            f"{outcome.title}  |  CLK: {self.mode.clock_ghz:.2f} GHz  |  "
            f"AREA: {area}/{self.mode.max_area_mm2} mm2  |  POWER: {power}/{self.mode.max_power_w} W"
        )
        surface.blit(mono_md.render(hdr, True, border), (self.rect.x + 14, self.rect.y + 10))
        surface.blit(mono_sm.render(outcome.message[:86], True, PALETTE.text_secondary), (self.rect.x + 14, self.rect.y + 27))

