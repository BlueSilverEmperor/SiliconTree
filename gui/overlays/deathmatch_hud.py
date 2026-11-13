"""Silicon Deathmatch HUD overlay: thermal HP bar, wave indicator, and upgrade drafting."""

from __future__ import annotations

from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton

from core_engine.clock import CycleSnapshot
from gui.overlays.base_overlay import BaseOverlay
from gui.theme import PALETTE, FontBank
from modes.silicon_deathmatch import SiliconDeathmatchMode


class DeathmatchHUDOverlay(BaseOverlay):
    """HUD overlay for Mode 3: Silicon Deathmatch."""

    def __init__(
        self,
        ui_manager: pygame_gui.UIManager,
        rect: pygame.Rect,
        mode: SiliconDeathmatchMode,
        fonts: FontBank,
    ) -> None:
        super().__init__(ui_manager, rect)
        self.mode = mode
        self.fonts = fonts
        self.btn_4way: Optional[UIButton] = None
        self.btn_cool: Optional[UIButton] = None
        self.btn_next: Optional[UIButton] = None
        self.rebuild(rect)

    def kill(self) -> None:
        for btn in (self.btn_4way, self.btn_cool, self.btn_next):
            if btn is not None:
                btn.kill()
        self.btn_4way = None
        self.btn_cool = None
        self.btn_next = None

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        bx = rect.right - 520
        self.btn_4way = UIButton(pygame.Rect(bx, rect.y + 42, 165, 32), "DRAFT: 4-WAY L1", self.ui_manager)
        self.btn_cool = UIButton(pygame.Rect(bx + 172, rect.y + 42, 165, 32), "DRAFT: COOL SINK", self.ui_manager)
        self.btn_next = UIButton(pygame.Rect(bx + 344, rect.y + 42, 165, 32), "NEXT WAVE >>", self.ui_manager)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.btn_4way:
                self.mode.apply_upgrade("CACHE_4WAY")
            elif event.ui_element == self.btn_cool:
                self.mode.apply_upgrade("COOLING_SINK")
            elif event.ui_element == self.btn_next and self.mode.upgrade_draft_open:
                self.mode.start_next_wave()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        outcome = self.mode.check_victory()
        hp_ratio = max(0.0, min(1.0, self.mode.thermal_hp / max(1.0, self.mode.max_thermal_hp)))
        border = PALETTE.crimson if self.mode.thermal_meltdown else (
            PALETTE.emerald if self.mode.all_waves_cleared else PALETTE.amber
        )
        pygame.draw.rect(surface, PALETTE.bg_panel, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if outcome.finished else 1, border_radius=8)

        mono_md = self.fonts.get(12, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        surface.blit(mono_md.render(f"WAVE {self.mode.wave_index + 1}/{len(self.mode.waves)} — {outcome.title}", True, border), (self.rect.x + 14, self.rect.y + 10))
        surface.blit(mono_sm.render(outcome.message[:68], True, PALETTE.text_secondary), (self.rect.x + 14, self.rect.y + 28))

        # Thermal HP bar
        bar_rect = pygame.Rect(self.rect.x + 14, self.rect.y + 50, 260, 20)
        pygame.draw.rect(surface, PALETTE.bg_root, bar_rect, border_radius=4)
        hp_col = PALETTE.emerald if hp_ratio > 0.6 else (PALETTE.amber if hp_ratio > 0.3 else PALETTE.crimson)
        pygame.draw.rect(surface, hp_col, pygame.Rect(bar_rect.x + 2, bar_rect.y + 2, int((bar_rect.width - 4) * hp_ratio), 16), border_radius=3)
        surface.blit(mono_sm.render(f"THERMAL HP {self.mode.thermal_hp:.1f}%", True, PALETTE.text_primary), (bar_rect.right + 10, self.rect.y + 53))

