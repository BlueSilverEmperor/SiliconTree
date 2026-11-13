"""SpectreScope HUD overlay: red-alert leak banner, Flush+Reload timer bar, LFENCE toggle."""

from __future__ import annotations

from typing import Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton

from core_engine.clock import CycleSnapshot
from gui.overlays.base_overlay import BaseOverlay
from gui.theme import PALETTE, FontBank
from modes.spectrescope import SpectreScopeMode


class SpectreHUDOverlay(BaseOverlay):
    """HUD overlay for Mode 1: SpectreScope."""

    def __init__(
        self,
        ui_manager: pygame_gui.UIManager,
        rect: pygame.Rect,
        mode: SpectreScopeMode,
        fonts: FontBank,
    ) -> None:
        super().__init__(ui_manager, rect)
        self.mode = mode
        self.fonts = fonts
        self.btn_lfence: Optional[UIButton] = None
        self.btn_probe: Optional[UIButton] = None
        self.rebuild(rect)

    def kill(self) -> None:
        for btn in (self.btn_lfence, self.btn_probe):
            if btn is not None:
                btn.kill()
        self.btn_lfence = None
        self.btn_probe = None

    def rebuild(self, rect: pygame.Rect) -> None:
        self.kill()
        self.rect = rect
        lbl = "LFENCE: ON [SAFE]" if self.mode.lfence_enabled else "LFENCE: OFF [VULN]"
        self.btn_lfence = UIButton(
            pygame.Rect(rect.x + 12, rect.y + 10, 170, 30),
            lbl,
            self.ui_manager,
        )
        self.btn_probe = UIButton(
            pygame.Rect(rect.x + 12, rect.y + 46, 170, 30),
            "FLUSH+RELOAD PROBE",
            self.ui_manager,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.btn_lfence:
                state = self.mode.toggle_lfence(reset_sim=True)
                if self.btn_lfence is not None:
                    self.btn_lfence.set_text("LFENCE: ON [SAFE]" if state else "LFENCE: OFF [VULN]")
            elif event.ui_element == self.btn_probe:
                self.mode.run_flush_reload_probe()

    def render(self, surface: pygame.Surface, snapshot: CycleSnapshot, tick_progress: float) -> None:
        is_alert = self.mode.leak_detected
        border = PALETTE.crimson if is_alert else (PALETTE.emerald if self.mode.lfence_enabled else PALETTE.border_subtle)
        bg = (42, 14, 24) if is_alert else PALETTE.bg_panel

        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, border, self.rect, width=2 if is_alert else 1, border_radius=8)

        mono_md = self.fonts.get(12, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        # Status & Red-Alert text
        outcome = self.mode.check_victory()
        status_x = self.rect.x + 196
        if is_alert:
            alert_txt = f"RED ALERT: SPECULATIVE L1 LEAK @ {', '.join(f'0x{a:04X}' for a in self.mode.leaked_addresses)}"
            surface.blit(mono_md.render(alert_txt, True, PALETTE.crimson), (status_x, self.rect.y + 10))
        else:
            col = PALETTE.emerald if self.mode.lfence_enabled else PALETTE.amber
            surface.blit(mono_md.render(outcome.title.upper(), True, col), (status_x, self.rect.y + 10))

        surface.blit(mono_sm.render(outcome.message[:78], True, PALETTE.text_secondary), (status_x, self.rect.y + 28))

        # Flush+Reload cycle timer bar
        bar_x = status_x
        bar_y = self.rect.y + 48
        bar_w = max(240, self.rect.right - bar_x - 16)
        slots = int(self.mode.scenario_data.get("num_probe_slots", 8))
        slot_w = max(28, (bar_w - (slots - 1) * 6) // max(1, slots))

        for i in range(slots):
            sx = bar_x + i * (slot_w + 6)
            s_rect = pygame.Rect(sx, bar_y, slot_w, 28)
            pygame.draw.rect(surface, PALETTE.bg_card, s_rect, border_radius=4)

            if i in self.mode.probe_results:
                lat, is_hit = self.mode.probe_results[i]
                fill_col = PALETTE.crimson if is_hit else PALETTE.cyan
                fill_ratio = 0.25 if is_hit else 0.95
                fill_rect = pygame.Rect(sx + 2, bar_y + 16, int((slot_w - 4) * fill_ratio), 9)
                pygame.draw.rect(surface, fill_col, fill_rect, border_radius=2)
                lbl = f"#{i}:{lat}c{'!' if is_hit else ''}"
                surface.blit(mono_sm.render(lbl, True, fill_col), (sx + 4, bar_y + 2))
            else:
                pygame.draw.rect(surface, PALETTE.border_subtle, s_rect, width=1, border_radius=4)
                surface.blit(mono_sm.render(f"#{i}: --", True, PALETTE.text_muted), (sx + 6, bar_y + 7))

