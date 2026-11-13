"""Dark silicon & cyberpunk color palette, typography, and pygame-gui theme builder."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import pygame


@dataclass(frozen=True)
class SiliconPalette:
    """High-contrast dark silicon color tokens."""

    bg_root: tuple[int, int, int] = (10, 14, 23)
    bg_panel: tuple[int, int, int] = (16, 23, 36)
    bg_card: tuple[int, int, int] = (23, 32, 48)
    bg_elevated: tuple[int, int, int] = (31, 43, 64)
    border_subtle: tuple[int, int, int] = (46, 62, 88)
    border_active: tuple[int, int, int] = (0, 229, 255)

    text_primary: tuple[int, int, int] = (230, 240, 255)
    text_secondary: tuple[int, int, int] = (148, 168, 196)
    text_muted: tuple[int, int, int] = (92, 110, 138)

    cyan: tuple[int, int, int] = (0, 229, 255)
    emerald: tuple[int, int, int] = (34, 211, 138)
    amber: tuple[int, int, int] = (255, 184, 48)
    crimson: tuple[int, int, int] = (255, 72, 96)
    magenta: tuple[int, int, int] = (224, 64, 251)
    violet: tuple[int, int, int] = (139, 92, 246)


PALETTE = SiliconPalette()


class FontBank:
    """Lazy-initialized monospace and UI font cache."""

    def __init__(self) -> None:
        self._fonts: dict[tuple[str, int, bool], pygame.font.Font] = {}

    def get(self, size: int = 14, bold: bool = False, mono: bool = True) -> pygame.font.Font:
        key = ("mono" if mono else "sans", size, bold)
        if key not in self._fonts:
            if not pygame.font.get_init():
                pygame.font.init()
            candidates = (
                ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"]
                if mono
                else ["Segoe UI", "Inter", "DejaVu Sans", "Arial"]
            )
            matched = pygame.font.match_font(",".join(candidates), bold=bold)
            self._fonts[key] = pygame.font.Font(matched, size)
        return self._fonts[key]


def write_pygame_gui_theme(path: Path) -> Path:
    """Write a dark silicon pygame-gui JSON theme file and return its path."""
    theme = {
        "defaults": {
            "colours": {
                "normal_bg": "#172030",
                "hovered_bg": "#1f2b40",
                "disabled_bg": "#101724",
                "selected_bg": "#005f73",
                "active_bg": "#0a9396",
                "normal_text": "#e6f0ff",
                "hovered_text": "#00e5ff",
                "selected_text": "#ffffff",
                "disabled_text": "#5c6e8a",
                "normal_border": "#2e3e58",
                "hovered_border": "#00e5ff",
                "selected_border": "#00e5ff",
                "dark_bg": "#0a0e17",
            }
        },
        "button": {
            "misc": {
                "border_width": "1",
                "shape": "rounded_rectangle",
                "shape_corner_radius": "5",
            }
        },
        "horizontal_slider": {
            "colours": {
                "normal_bg": "#101724",
                "filled_bar": "#00e5ff",
                "sliding_button": "#22d38a",
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(theme, indent=2), encoding="utf-8")
    return path

