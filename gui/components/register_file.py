"""Live Register File table (hex/binary) and RTN micro-operation log."""

from __future__ import annotations

import pygame

from core_engine.clock import CycleSnapshot
from gui.theme import PALETTE, FontBank


class RegisterFileView:
    """Renders R0..R15 architectural & speculative shadow values plus RTN log."""

    def __init__(self, fonts: FontBank) -> None:
        self.fonts = fonts
        self._prev_regs: tuple[int, ...] = (0,) * 16

    def render(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        snapshot: CycleSnapshot,
    ) -> None:
        pygame.draw.rect(surface, PALETTE.bg_panel, rect, border_radius=8)
        pygame.draw.rect(surface, PALETTE.border_subtle, rect, width=1, border_radius=8)

        hdr_font = self.fonts.get(13, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        title = hdr_font.render("REGISTER FILE  &  RTN MICRO-OP LOG", True, PALETTE.cyan)
        surface.blit(title, (rect.x + 12, rect.y + 8))

        # Split vertically: top 56% registers (2 columns of 8), bottom 44% RTN log
        reg_area_h = int((rect.height - 38) * 0.56)
        col_w = (rect.width - 28) // 2
        row_h = max(18, reg_area_h // 8)

        for idx in range(16):
            col = idx // 8
            row = idx % 8
            rx = rect.x + 12 + col * (col_w + 6)
            ry = rect.y + 32 + row * row_h

            val = snapshot.regs[idx]
            spec_val = snapshot.spec_regs[idx]
            spec_diff = spec_val != val
            changed = val != self._prev_regs[idx]

            cell = pygame.Rect(rx, ry, col_w, row_h - 2)
            bg = (22, 46, 38) if changed else ((46, 26, 36) if spec_diff else PALETTE.bg_card)
            pygame.draw.rect(surface, bg, cell, border_radius=3)

            r_lbl = f"R{idx:<2}"
            alias = "SP" if idx == 14 else ("RA" if idx == 15 else ("ZR" if idx == 0 else "  "))
            hex_str = f"0x{val:08X}"
            low_bin = f"{val & 0xFF:08b}"
            txt = f"{r_lbl} {alias} {hex_str} [{low_bin}]"
            if spec_diff:
                txt = f"{r_lbl} {alias} {hex_str} (S:{spec_val:X})"

            text_col = PALETTE.amber if spec_diff else (PALETTE.emerald if changed else PALETTE.text_primary)
            t_surf = mono_sm.render(txt[:28], True, text_col)
            surface.blit(t_surf, (cell.x + 6, cell.y + 2))

        self._prev_regs = snapshot.regs

        # RTN log box
        log_top = rect.y + 36 + reg_area_h
        log_rect = pygame.Rect(rect.x + 12, log_top, rect.width - 24, max(40, rect.bottom - log_top - 10))
        pygame.draw.rect(surface, PALETTE.bg_root, log_rect, border_radius=5)
        pygame.draw.rect(surface, PALETTE.border_subtle, log_rect, width=1, border_radius=5)

        max_lines = max(1, (log_rect.height - 8) // 15)
        recent = snapshot.rtn_log[-max_lines:]
        for i, line in enumerate(recent):
            col = PALETTE.crimson if "FLUSH" in line else (PALETTE.amber if "SPEC" in line else PALETTE.text_secondary)
            l_surf = mono_sm.render(line[:54], True, col)
            surface.blit(l_surf, (log_rect.x + 8, log_rect.y + 4 + i * 15))

