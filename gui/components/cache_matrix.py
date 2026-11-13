"""Interactive L1/L2 Cache Matrix visualization with hit/miss/speculative-warm flashes."""

from __future__ import annotations

from typing import Optional
import pygame

from core_engine.clock import CycleSnapshot
from core_engine.memory import CacheLineSnapshot
from gui.theme import PALETTE, FontBank


class CacheMatrixView:
    """Renders L1 (and optional L2) cache sets/ways with interactive line inspection."""

    def __init__(self, fonts: FontBank) -> None:
        self.fonts = fonts
        self.selected_key: Optional[tuple[str, int, int]] = None  # ("L1"|"L2", set_idx, way_idx)
        self._cell_rects: list[tuple[pygame.Rect, str, CacheLineSnapshot]] = []
        self._show_l2: bool = False
        self._toggle_rect: Optional[pygame.Rect] = None

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Select a cache line or toggle L1/L2 view on click."""
        if self._toggle_rect and self._toggle_rect.collidepoint(pos):
            self._show_l2 = not self._show_l2
            self.selected_key = None
            return True
        for rect, level, line in self._cell_rects:
            if rect.collidepoint(pos):
                self.selected_key = (level, line.set_index, line.way_index)
                return True
        return False

    def render(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        snapshot: CycleSnapshot,
        tick_progress: float,
    ) -> None:
        pygame.draw.rect(surface, PALETTE.bg_panel, rect, border_radius=8)
        pygame.draw.rect(surface, PALETTE.border_subtle, rect, width=1, border_radius=8)

        hdr_font = self.fonts.get(13, bold=True)
        mono_sm = self.fonts.get(11, bold=False)

        active_level = "L2" if (self._show_l2 and snapshot.l2_lines) else "L1"
        lines = snapshot.l2_lines if active_level == "L2" else snapshot.l1_lines

        title = hdr_font.render(f"{active_level} CACHE MATRIX", True, PALETTE.cyan)
        surface.blit(title, (rect.x + 12, rect.y + 8))

        if snapshot.l2_lines:
            tog = pygame.Rect(rect.x + 150, rect.y + 6, 78, 20)
            self._toggle_rect = tog
            pygame.draw.rect(surface, PALETTE.bg_elevated, tog, border_radius=4)
            pygame.draw.rect(surface, PALETTE.cyan, tog, width=1, border_radius=4)
            t_lbl = mono_sm.render("VIEW L1" if active_level == "L2" else "VIEW L2", True, PALETTE.cyan)
            surface.blit(t_lbl, (tog.centerx - t_lbl.get_width() // 2, tog.y + 3))
        else:
            self._toggle_rect = None

        total_acc = snapshot.l1_hits + snapshot.l1_misses
        hit_rate = (snapshot.l1_hits / total_acc * 100.0) if total_acc > 0 else 0.0
        stats = mono_sm.render(
            f"H:{snapshot.l1_hits} M:{snapshot.l1_misses} ({hit_rate:.0f}%) CM:{snapshot.l1_conflict_misses}",
            True,
            PALETTE.text_secondary,
        )
        surface.blit(stats, (rect.right - stats.get_width() - 12, rect.y + 10))

        self._cell_rects.clear()
        if not lines:
            empty = mono_sm.render("No cache lines configured.", True, PALETTE.text_muted)
            surface.blit(empty, (rect.x + 14, rect.y + 44))
            return

        sets = sorted({ln.set_index for ln in lines})
        ways = sorted({ln.way_index for ln in lines})
        num_sets = len(sets)
        num_ways = len(ways)

        grid_top = rect.y + 34
        inspector_h = 46
        grid_h = max(60, rect.height - 42 - inspector_h)
        pad_x = 12
        grid_w = rect.width - 2 * pad_x

        col_gap = 6
        row_gap = 6
        cell_w = max(56, (grid_w - col_gap * max(0, num_ways - 1)) // max(1, num_ways))
        cell_h = max(26, min(46, (grid_h - row_gap * max(0, num_sets - 1)) // max(1, num_sets)))

        selected_line: Optional[CacheLineSnapshot] = None
        flash_alpha = max(0.0, 1.0 - tick_progress * 1.4)

        for ln in lines:
            cx = rect.x + pad_x + ln.way_index * (cell_w + col_gap)
            cy = grid_top + ln.set_index * (cell_h + row_gap)
            if cy + cell_h > rect.bottom - inspector_h - 4:
                continue
            cell = pygame.Rect(cx, cy, cell_w, cell_h)
            self._cell_rects.append((cell, active_level, ln))

            is_sel = self.selected_key == (active_level, ln.set_index, ln.way_index)
            if is_sel:
                selected_line = ln

            recently_touched = ln.last_access_cycle == snapshot.cycle and snapshot.cycle > 0
            if ln.speculative_warm and ln.valid:
                bg = (58, 16, 36)
                border = PALETTE.crimson
                tag_col = PALETTE.crimson
            elif recently_touched and ln.last_access_type in ("HIT", "SPEC_HIT"):
                g_boost = int(38 * flash_alpha)
                bg = (18, 42 + g_boost, 34)
                border = PALETTE.emerald
                tag_col = PALETTE.emerald
            elif recently_touched and ln.last_access_type in ("MISS", "SPEC_FILL"):
                r_boost = int(45 * flash_alpha)
                bg = (45 + r_boost, 20, 28)
                border = PALETTE.amber
                tag_col = PALETTE.amber
            elif ln.valid:
                bg = PALETTE.bg_card
                border = PALETTE.cyan if is_sel else PALETTE.border_subtle
                tag_col = PALETTE.text_primary
            else:
                bg = PALETTE.bg_root
                border = PALETTE.border_subtle
                tag_col = PALETTE.text_muted

            if is_sel:
                border = PALETTE.cyan

            pygame.draw.rect(surface, bg, cell, border_radius=4)
            pygame.draw.rect(surface, border, cell, width=2 if (is_sel or (ln.speculative_warm and ln.valid)) else 1, border_radius=4)

            v_bit = "V" if ln.valid else "-"
            d_bit = "D" if ln.dirty else "-"
            spec_tag = "!" if (ln.speculative_warm and ln.valid) else ""
            top_txt = f"S{ln.set_index}W{ln.way_index} [{v_bit}{d_bit}{spec_tag}]"
            t_surf = mono_sm.render(top_txt, True, tag_col)
            surface.blit(t_surf, (cell.x + 5, cell.y + 3))

            if cell_h >= 34:
                val_txt = f"TAG 0x{ln.tag:X}" if ln.valid else "EMPTY"
                v_surf = mono_sm.render(val_txt, True, PALETTE.text_secondary if ln.valid else PALETTE.text_muted)
                surface.blit(v_surf, (cell.x + 5, cell.y + 17))

        # Bottom line inspector
        insp_rect = pygame.Rect(rect.x + 10, rect.bottom - inspector_h, rect.width - 20, inspector_h - 6)
        pygame.draw.rect(surface, PALETTE.bg_card, insp_rect, border_radius=5)
        pygame.draw.rect(surface, PALETTE.border_subtle, insp_rect, width=1, border_radius=5)
        if selected_line is not None and selected_line.valid:
            words_preview = " ".join(f"{w:08X}" for w in selected_line.data_words[:4])
            lbl = f"S{selected_line.set_index}W{selected_line.way_index} TAG=0x{selected_line.tag:X} SPEC={selected_line.speculative_warm} | {words_preview}"
            surface.blit(mono_sm.render(lbl, True, PALETTE.text_primary), (insp_rect.x + 8, insp_rect.y + 12))
        else:
            hint = "Click any cache line to inspect words | [!] = Speculatively Warmed (Side-Channel)"
            surface.blit(mono_sm.render(hint, True, PALETTE.text_secondary), (insp_rect.x + 8, insp_rect.y + 12))

