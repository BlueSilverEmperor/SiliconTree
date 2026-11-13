"""Phase 5 Verification Suite: Silicon Forensic, Architect Tycoon, and Full 5-Mode Hub Integration."""

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
from modes.architect_tycoon import ArchitectTycoonMode
from modes.silicon_forensic import SiliconForensicMode


def test_silicon_forensic_scrub_and_evidence() -> None:
    forensic = SiliconForensicMode()
    forensic.load_scenario()
    assert forensic.crash_cycle > 6

    # Cycle 0 has no dirty lines -> evidence submission fails
    forensic.scrub_cycle(0)
    assert forensic.submit_evidence() is False
    assert not forensic.evidence_verified

    # Scrub forward to find cycle where tag 0x02 is dirty
    found_cycle = None
    for c in range(forensic.culprit_cycle_min, forensic.crash_cycle + 1):
        snap = forensic.scrub_cycle(c)
        if any(ln.valid and ln.dirty and ln.tag == forensic.culprit_tag for ln in snap.l1_lines):
            found_cycle = c
            break

    assert found_cycle is not None, "Expected dirty tag 0x02 in crash dump history"
    assert forensic.submit_evidence() is True
    out = forensic.check_victory()
    assert out.finished and out.victory


def test_architect_tycoon_budget_and_contract() -> None:
    tycoon = ArchitectTycoonMode()
    tycoon.load_scenario()

    # Balanced config should pass Kestrel Robotics contract
    tycoon.configure(clock_ghz=2.4, l1_associativity=2, forwarding_enabled=True)
    win_out = tycoon.evaluate_contract()
    assert win_out.finished and win_out.victory, f"Expected contract win, got {win_out}"

    # Overclocked + 4-way should exceed power/area budget
    tycoon.configure(clock_ghz=4.5, l1_associativity=4, forwarding_enabled=True)
    fail_out = tycoon.evaluate_contract()
    assert fail_out.finished and not fail_out.victory, "Expected over-budget config to fail"


def test_full_hub_integration_all_5_modes() -> None:
    app = SiliconTreeApp(width=1280, height=720, headless=True)
    try:
        expected_modes = [
            "spectrescope",
            "silicon_heist",
            "silicon_deathmatch",
            "silicon_forensic",
            "architect_tycoon",
            "sandbox",
        ]
        assert list(app.modes.keys()) == expected_modes

        for mode_id in expected_modes:
            app.launch_mode(mode_id)
            assert app.scene == "SIMULATION"
            assert app.active_mode is not None
            assert app.active_mode.mode_id == mode_id

            # Step forward 3 cycles, render frames, then rewind 1 cycle
            start_cycle = app.active_mode.get_clock().latest_snapshot().cycle
            for _ in range(3):
                app.step_once()
                app.update(1.0 / 60.0)
                app.render()
            assert app.active_mode.get_clock().latest_snapshot().cycle == start_cycle + 3

            app.rewind_once()
            assert app.active_mode.get_clock().latest_snapshot().cycle == start_cycle + 2

            # Return to HUB and verify clean teardown
            app._build_hub_ui()
            assert app.scene == "HUB"
            assert app.active_overlay is None
            assert app.control_deck is None
            app.update(1.0 / 60.0)
            app.render()
    finally:
        pygame.quit()

