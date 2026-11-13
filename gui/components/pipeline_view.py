"""Animated 5-stage pipeline conveyor view with forwarding arcs and NOP stall bubbles."""

from __future__ import annotations

import pygame

from core_engine.clock import CycleSnapshot
from core_engine.pipeline import StageSlot
from gui.theme import PALETTE, FontBank


STAGE_ORDER = ("IF", "ID", "EX", "MEM", "WB")
STAGE_TITLES = {
    "IF": "IF  FETCH",
    "ID": "ID  DECODE",
    "EX": "EX  EXECUTE",
    "MEM": "MEM  MEMORY",
    "WB": "WB  WRITEBACK",
}


class PipelineView:
    """Renders the 5-stage pipeline state from an immutable CycleSnapshot."""

    def __init__(self, fonts: FontBank) -> None:
        self.fonts = fonts
        self._last_cycle: int = -1
        self._slide_progress: float = 1.0

    def render(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        snapshot: CycleSnapshot,
        tick_progress: float,
    ) -> None:
        pygame.draw.rect(surface, PALETTE.bg_panel, rect, border_radius=8)
        pygame.draw.rect(surface, PALETTE.border_subtle, rect, width=1, border_radius=8)

        header_font = self.fonts.get(13, bold=True)
        mono_sm = self.fonts.get(11, bold=False)
        mono_md = self.fonts.get(12, bold=True)

        title = header_font.render("5-STAGE PIPELINE CONVEYOR  [WB -> MEM -> EX -> ID -> IF]", True, PALETTE.cyan)
        surface.blit(title, (rect.x + 12, rect.y + 8))

        # Status pills on top right
        spec_count = sum(1 for s in STAGE_ORDER if snapshot.stages[s].is_speculative and not snapshot.stages[s].is_bubble)
        badge_text = f"PC 0x{snapshot.pc:04X} | STALLS {snapshot.stall_cycles} | FLUSHES {snapshot.speculative_flushes}"
        if spec_count > 0:
            badge_text += f" | SPEC IN-FLIGHT {spec_count}"
        badge_surf = mono_sm.render(badge_text, True, PALETTE.amber if spec_count else PALETTE.text_secondary)
        surface.blit(badge_surf, (rect.right - badge_surf.get_width() - 12, rect.y + 10))

        # Compute 5 stage box rects
        inner_top = rect.y + 34
        inner_h = rect.height - 46
        pad_x = 12
        gap = 18
        total_w = rect.width - 2 * pad_x - 4 * gap
        box_w = max(90, total_w // 5)
        box_h = max(72, inner_h - 24)

        stage_rects: dict[str, pygame.Rect] = {}
        ease = min(1.0, max(0.0, tick_progress * 2.2))

        for idx, stage_name in enumerate(STAGE_ORDER):
            bx = rect.x + pad_x + idx * (box_w + gap)
            by = inner_top + 18
            box = pygame.Rect(bx, by, box_w, box_h)
            stage_rects[stage_name] = box

            slot: StageSlot = snapshot.stages[stage_name]
            self._draw_stage_box(surface, box, stage_name, slot, ease, mono_md, mono_sm)

            # Conveyor arrow to next stage
            if idx < len(STAGE_ORDER) - 1:
                ax1 = box.right + 2
                ax2 = box.right + gap - 2
                ay = box.centery
                pygame.draw.line(surface, PALETTE.border_subtle, (ax1, ay), (ax2 - 4, ay), 2)
                pygame.draw.polygon(
                    surface,
                    PALETTE.cyan,
                    [(ax2, ay), (ax2 - 6, ay - 4), (ax2 - 6, ay + 4)],
                )

        # Draw forwarding arcs (EX->EX / MEM_WB->EX / WB->EX)
        self._draw_forwarding_arcs(surface, stage_rects, snapshot, mono_sm)

    def _draw_stage_box(
        self,
        surface: pygame.Surface,
        box: pygame.Rect,
        stage_name: str,
        slot: StageSlot,
        ease: float,
        mono_md: pygame.font.Font,
        mono_sm: pygame.font.Font,
    ) -> None:
        if slot.is_bubble or slot.instruction is None:
            if slot.stall_reason:
                border_col = PALETTE.crimson
                bg_col = (44, 18, 28)
                tag_col = PALETTE.crimson
            else:
                border_col = PALETTE.border_subtle
                bg_col = PALETTE.bg_card
                tag_col = PALETTE.text_muted
        elif slot.is_speculative:
            border_col = PALETTE.magenta if slot.l1_warmed_speculatively else PALETTE.amber
            bg_col = (48, 22, 48) if slot.l1_warmed_speculatively else (42, 34, 18)
            tag_col = border_col
        else:
            border_col = PALETTE.cyan if stage_name in ("IF", "ID") else PALETTE.emerald
            bg_col = PALETTE.bg_card
            tag_col = border_col

        # Subtle horizontal pulse on active transition
        slide_offset = int((1.0 - ease) * -6) if not slot.is_bubble else 0
        draw_rect = box.move(slide_offset, 0)

        pygame.draw.rect(surface, bg_col, draw_rect, border_radius=6)
        pygame.draw.rect(surface, border_col, draw_rect, width=2 if not slot.is_bubble else 1, border_radius=6)

        # Header strip
        hdr = pygame.Rect(draw_rect.x + 1, draw_rect.y + 1, draw_rect.width - 2, 20)
        pygame.draw.rect(surface, PALETTE.bg_elevated, hdr, border_top_left_radius=5, border_top_right_radius=5)
        lbl = mono_sm.render(STAGE_TITLES[stage_name], True, tag_col)
        surface.blit(lbl, (draw_rect.x + 7, draw_rect.y + 4))

        if slot.is_bubble or slot.instruction is None:
            bubble_txt = "BUBBLE / NOP" if not slot.stall_reason else slot.stall_reason[:18]
            b_surf = mono_md.render(bubble_txt, True, tag_col)
            surface.blit(b_surf, (draw_rect.x + 8, draw_rect.y + 34))
            return

        inst = slot.instruction
        op_txt = f"0x{inst.pc:04X}: {inst.raw_text[:20]}"
        op_surf = mono_md.render(op_txt, True, PALETTE.text_primary)
        surface.blit(op_surf, (draw_rect.x + 8, draw_rect.y + 28))

        rtn_surf = mono_sm.render(inst.rtn[:24], True, PALETTE.text_secondary)
        surface.blit(rtn_surf, (draw_rect.x + 8, draw_rect.y + 48))

        # Status badge (SPEC / FWD / STALL)
        badges: list[str] = []
        if slot.is_speculative:
            badges.append("SPEC")
        if slot.l1_warmed_speculatively:
            badges.append("L1-WARM!")
        if slot.mispredicted:
            badges.append("MISPRED")
        if slot.forwarded_from:
            badges.append("FWD")
        if slot.mem_cycles_left > 0:
            badges.append(f"MEM:{slot.mem_cycles_left}c")
        if slot.ex_cycles_left > 0:
            badges.append(f"ALU:{slot.ex_cycles_left}c")

        if badges:
            b_str = " ".join(badges)[:22]
            b_surf = mono_sm.render(b_str, True, tag_col)
            surface.blit(b_surf, (draw_rect.x + 8, draw_rect.bottom - 18))

    def _draw_forwarding_arcs(
        self,
        surface: pygame.Surface,
        stage_rects: dict[str, pygame.Rect],
        snapshot: CycleSnapshot,
        mono_sm: pygame.font.Font,
    ) -> None:
        if not snapshot.forwarding_events:
            return
        ex_rect = stage_rects["EX"]
        for i, fwd in enumerate(snapshot.forwarding_events[:2]):
            src_stage = "MEM" if fwd.from_stage == "MEM_WB" else "WB"
            src_rect = stage_rects.get(src_stage)
            if src_rect is None:
                continue
            start_pt = (src_rect.centerx, src_rect.top)
            end_pt = (ex_rect.centerx + (i * 12), ex_rect.top)
            arc_y = ex_rect.top - 14 - (i * 10)
            pts = [
                start_pt,
                (start_pt[0], arc_y),
                (end_pt[0], arc_y),
                end_pt,
            ]
            pygame.draw.lines(surface, PALETTE.cyan, False, pts, 2)
            pygame.draw.circle(surface, PALETTE.cyan, end_pt, 4)
            txt = mono_sm.render(f"FWD R{fwd.reg}=0x{fwd.value:X}", True, PALETTE.cyan)
            surface.blit(txt, ((start_pt[0] + end_pt[0]) // 2 - txt.get_width() // 2, arc_y - 13))

