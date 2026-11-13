"""Silicon Heist HUD overlay: stealth noise bar, locker checklist, DMA escape trigger."""

from __future__ import annotations

from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton

from core_engine.clock import CycleSnapshot
from gui.overlays.base_overlay import BaseOverlay
from gui.theme import PALETTE, FontBank
from modes.silicon_heist import SiliconHeistMode


class HeistHUDOverlay(BaseOverlay):
    """HUD overlay for Mode 2: Silicon Heist."""

    def __init__(
        self,
        ui_manager: pygame_gui.UIManager,
        rect: pygame.Rect,
        mode: SiliconHeistMode,
        fonts: FontBank,
    ) -> None:
        super().__init__(ui_manager, rect)
        self.mode = mode
        self.fonts = fonts
        self.btn_dma: Optional[UIButton] = None
        self.rebuild(rect)

    def kill(self) -> None:
        if self.btn_dma is not None:
            self.btn_dma.kill()
            self.btn_dma = None

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        self.btn_dma = UIButton(
            pygame.Rect(rect.x + 12, rect.y + 24, 170, 36),
            "TRIGGER DMA ESCAPE",
            self.ui_manager,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == self.btn_dma:
            self.mode.trigger_dma_escape()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        outcome = self.mode.check_victory()
        border = PALETTE.crimson if self.mode.stealth_state == "DETECTED" else (
            PALETTE.emerald if self.mode.escaped else PALETTE.magenta
        )
        pygame.draw.rect(surface, PALETTE.bg_panel, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if outcome.finished else 1, border_radius=8)

        mono_md = self.fonts.get(12, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        x0 = self.rect.x + 196
        surface.blit(mono_md.render(f"STEALTH: {self.mode.stealth_state} | {outcome.title}", True, border), (x0, self.rect.y + 10))
        surface.blit(mono_sm.render(outcome.message[:75], True, PALETTE.text_secondary), (x0, self.rect.y + 30))

        # Stealth noise bar & locker status
        bar_rect = pygame.Rect(x0, self.rect.y + 50, 220, 18)
        pygame.draw.rect(surface, PALETTE.bg_root, bar_rect, border_radius=4)
        ratio = min(1.0, self.mode.stealth_noise / max(1, self.mode.max_noise))
        fill_col = PALETTE.crimson if ratio >= 0.8 else (PALETTE.amber if ratio >= 0.4 else PALETTE.emerald)
        pygame.draw.rect(surface, fill_col, pygame.Rect(bar_rect.x + 2, bar_rect.y + 2, int((bar_rect.width - 4) * ratio), 14), border_radius=3)
        surface.blit(mono_sm.render(f"NOISE {self.mode.stealth_noise}/{self.mode.max_noise}", True, PALETTE.text_primary), (bar_rect.right + 12, self.rect.y + 52))

        lockers = f"LOCKERS: {len(self.mode.lockers_touched)}/{len(self.mode.target_lockers)} | DMA: {snapshot.dma_words_transferred}w"
        surface.blit(mono_sm.render(lockers, True, PALETTE.cyan), (bar_rect.right + 120, self.rect.y + 52))

