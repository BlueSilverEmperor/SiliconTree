"""Phase 2 Verification Suite for SiliconTree GUI."""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame
from gui.app_window import SiliconTreeApp


def test_gui_headless_120_frames_and_controls() -> None:
    app = SiliconTreeApp(width=1280, height=720, headless=True)
    try:
        # Render hub for 5 frames
        for _ in range(5):
            app.update(1.0 / 60.0)
            app.render()

        # Run 120 frames of sandbox mode (includes an internal rewind at frame 30)
        snap = app.headless_dry_run("sandbox", frames=120)
        assert snap.cycle >= 1

        # Verify Step (+1) and Rewind (-1) controls
        c_before = app.active_mode.get_clock().latest_snapshot().cycle
        app.step_once()
        c_after_step = app.active_mode.get_clock().latest_snapshot().cycle
        assert c_after_step == c_before + 1

        app.rewind_once()
        c_after_rewind = app.active_mode.get_clock().latest_snapshot().cycle
        assert c_after_rewind == c_before

        # Verify layout bounds at 1280x720 and 1440x900
        for w, h in [(1280, 720), (1440, 900)]:
            app._on_resize(w, h)
            rects = app._layout_rects
            for name, r in rects.items():
                assert r.left >= 0 and r.top >= 0, f"{name} negative origin"
                assert r.right <= w and r.bottom <= h, f"{name} exceeds window ({w}x{h})"
                assert r.width > 50 and r.height > 30, f"{name} collapsed"
    finally:
        pygame.quit()

