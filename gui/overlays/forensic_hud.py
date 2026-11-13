"""Silicon Forensic HUD overlay: timeline scrubber slider and dirty-tag evidence submission."""

from __future__ import annotations

from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIHorizontalSlider

from core_engine.clock import CycleSnapshot
from gui.overlays.base_overlay import BaseOverlay
from gui.theme import PALETTE, FontBank
from modes.silicon_forensic import SiliconForensicMode


class ForensicHUDOverlay(BaseOverlay):
    """HUD overlay for Mode 4: Silicon Forensic."""

    def __init__(
        self,
        ui_manager: pygame_gui.UIManager,
        rect: pygame.Rect,
        mode: SiliconForensicMode,
        fonts: FontBank,
    ) -> None:
        super().__init__(ui_manager, rect)
        self.mode = mode
        self.fonts = fonts
        self.scrubber: Optional[UIHorizontalSlider] = None
        self.btn_submit: Optional[UIButton] = None
        self.rebuild(rect)

    def kill(self) -> None:
        if self.scrubber is not None:
            self.scrubber.kill()
            self.scrubber = None
        if self.btn_submit is not None:
            self.btn_submit.kill()
            self.btn_submit = None

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        max_c = max(1, self.mode.crash_cycle)
        self.scrubber = UIHorizontalSlider(
            pygame.Rect(rect.x + 14, rect.y + 46, max(240, rect.width - 230), 26),
            start_value=float(self.mode.inspected_cycle),
            value_range=(0.0, float(max_c)),
            manager=self.ui_manager,
        )
        self.btn_submit = UIButton(
            pygame.Rect(rect.right - 196, rect.y + 38, 182, 34),
            "SUBMIT DIRTY TAG",
            self.ui_manager,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and event.ui_element == self.scrubber:
            self.mode.scrub_cycle(int(round(event.value)))
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == self.btn_submit:
            self.mode.submit_evidence()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        outcome = self.mode.check_victory()
        border = PALETTE.emerald if self.mode.evidence_verified else PALETTE.cyan
        pygame.draw.rect(surface, PALETTE.bg_panel, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if self.mode.evidence_verified else 1, border_radius=8)

        mono_md = self.fonts.get(12, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        dirty_tags = [f"0x{ln.tag:X}" for ln in snapshot.l1_lines if ln.valid and ln.dirty]
        dirty_str = ", ".join(dirty_tags) if dirty_tags else "NONE"
        surface.blit(
            mono_md.render(f"FORENSIC SCRUBBER  |  CYCLE {self.mode.inspected_cycle}/{self.mode.crash_cycle}  |  DIRTY L1 TAGS: {dirty_str}", True, border),
            (self.rect.x + 14, self.rect.y + 10),
        )
        surface.blit(mono_sm.render(outcome.message[:90], True, PALETTE.text_secondary), (self.rect.x + 14, self.rect.y + 27))

