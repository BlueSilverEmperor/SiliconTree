"""Interpolated Bus & I/O packet animator (Registers, ALU, Cache, RAM, DMA, IRQ)."""

from __future__ import annotations

import pygame

from core_engine.bus_io import BusPacket
from core_engine.clock import CycleSnapshot
from gui.theme import PALETTE, FontBank


PACKET_COLORS = {
    "IFETCH": PALETTE.cyan,
    "MEM_READ": PALETTE.emerald,
    "MEM_WRITE": PALETTE.amber,
    "REG_ALU": PALETTE.violet,
    "DMA": PALETTE.magenta,
    "IRQ": PALETTE.crimson,
}


class BusAnimator:
    """Renders system bus topology and interpolates active BusPackets at 60 FPS."""

    def __init__(self, fonts: FontBank) -> None:
        self.fonts = fonts

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

        title = hdr_font.render(f"BUS FABRIC  [{snapshot.bus_topology}]", True, PALETTE.cyan)
        surface.blit(title, (rect.x + 12, rect.y + 8))

        dma_lbl = "DMA: ACTIVE (CYCLE STEAL)" if snapshot.dma_active else f"DMA XFER: {snapshot.dma_words_transferred}w"
        dma_col = PALETTE.magenta if snapshot.dma_active else PALETTE.text_secondary
        dma_surf = mono_sm.render(dma_lbl, True, dma_col)
        surface.blit(dma_surf, (rect.right - dma_surf.get_width() - 12, rect.y + 10))

        # Node layout normalized inside rect
        y_top = rect.y + 42
        y_mid = rect.y + rect.height // 2 + 6
        y_bot = rect.bottom - 34

        x_left = rect.x + 56
        x_mid_l = rect.x + int(rect.width * 0.34)
        x_mid_r = rect.x + int(rect.width * 0.66)
        x_right = rect.right - 56

        nodes: dict[str, tuple[int, int]] = {
            "REG_FILE": (x_left, y_top),
            "ALU": (x_mid_l, y_top),
            "CPU_IF": (x_left, y_mid),
            "ICACHE": (x_mid_l, y_mid),
            "CPU_MEM": (x_mid_l, y_bot),
            "L1_CACHE": (x_mid_r, y_mid),
            "RAM": (x_right, y_mid),
            "DMA": (x_mid_r, y_bot),
            "IRQ_CTRL": (x_right, y_top),
            "CPU_PC": (x_mid_r, y_top),
        }

        # Draw bus tracks
        tracks = [
            ("REG_FILE", "ALU", PALETTE.border_subtle),
            ("CPU_IF", "ICACHE", PALETTE.border_subtle),
            ("CPU_MEM", "L1_CACHE", PALETTE.border_subtle),
            ("L1_CACHE", "RAM", PALETTE.border_subtle),
            ("DMA", "RAM", PALETTE.magenta if snapshot.dma_active else PALETTE.border_subtle),
            ("IRQ_CTRL", "CPU_PC", PALETTE.border_subtle),
        ]
        for a, b, col in tracks:
            pygame.draw.line(surface, col, nodes[a], nodes[b], 2)

        # Draw hardware endpoint chips
        for name, (nx, ny) in nodes.items():
            chip = pygame.Rect(nx - 38, ny - 13, 76, 26)
            is_dma = name == "DMA" and snapshot.dma_active
            pygame.draw.rect(surface, PALETTE.bg_card, chip, border_radius=5)
            pygame.draw.rect(surface, PALETTE.magenta if is_dma else PALETTE.border_subtle, chip, width=1, border_radius=5)
            lbl = mono_sm.render(name[:9], True, PALETTE.text_primary)
            surface.blit(lbl, (chip.centerx - lbl.get_width() // 2, chip.centery - lbl.get_height() // 2))

        # Interpolate packets along src -> dst
        clamped_t = min(1.0, max(0.0, tick_progress))
        for pkt in snapshot.bus_packets:
            self._draw_packet(surface, pkt, nodes, clamped_t, mono_sm)

    def _draw_packet(
        self,
        surface: pygame.Surface,
        pkt: BusPacket,
        nodes: dict[str, tuple[int, int]],
        tick_progress: float,
        mono_sm: pygame.font.Font,
    ) -> None:
        src_pt = nodes.get(pkt.src)
        dst_pt = nodes.get(pkt.dst)
        if src_pt is None or dst_pt is None:
            return
        completed_cycles = max(0, pkt.cycles_total - pkt.cycles_remaining)
        frac = min(1.0, (completed_cycles + tick_progress) / max(1, pkt.cycles_total))
        px = int(src_pt[0] + (dst_pt[0] - src_pt[0]) * frac)
        py = int(src_pt[1] + (dst_pt[1] - src_pt[1]) * frac)
        col = PACKET_COLORS.get(pkt.kind, PALETTE.cyan)

        pygame.draw.circle(surface, col, (px, py), 6)
        pygame.draw.circle(surface, PALETTE.text_primary, (px, py), 2)
        tag = mono_sm.render(f"{pkt.kind[:4]} 0x{pkt.address:X}", True, col)
        surface.blit(tag, (px - tag.get_width() // 2, py - 18))

