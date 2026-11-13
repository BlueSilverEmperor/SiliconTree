"""Phase 3 Verification Suite for Mode 1: SpectreScope."""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modes.spectrescope import SpectreScopeMode


def test_spectrescope_attack_and_lfence_mitigation() -> None:
    mode = SpectreScopeMode()
    mode.load_scenario()
    clock = mode.get_clock()

    # 1. Run with LFENCE OFF (vulnerable)
    for _ in range(80):
        snap = clock.step_cycle()
        mode.evaluate_tick(snap)
        if snap.halted:
            break

    vuln_snap = clock.latest_snapshot()
    assert vuln_snap.halted
    assert mode.leak_detected, "Expected speculative L1 cache leak with LFENCE OFF"

    # Flush+Reload probe should recover secret byte = 5 (fast 1-cycle L1 hit!)
    probe = mode.run_flush_reload_probe()
    assert mode.recovered_secret == 5
    lat_5, hit_5 = probe[5]
    assert hit_5 and lat_5 == 1
    lat_0, hit_0 = probe[0]
    assert not hit_0 and lat_0 > lat_5

    vuln_stalls = vuln_snap.stall_cycles
    vuln_cpi = vuln_snap.cpi

    # 2. Toggle LFENCE ON (protected) and re-run
    assert mode.toggle_lfence(True, reset_sim=True) is True
    clock = mode.get_clock()
    for _ in range(80):
        snap = clock.step_cycle()
        mode.evaluate_tick(snap)
        if snap.halted:
            break

    safe_snap = clock.latest_snapshot()
    assert safe_snap.halted
    assert not mode.leak_detected, "LFENCE must prevent speculative L1 cache leak"
    assert safe_snap.stall_cycles > vuln_stalls, "LFENCE must insert pipeline stall cycles"
    assert safe_snap.cpi > vuln_cpi, "LFENCE serialization must increase CPI"

    probe_safe = mode.run_flush_reload_probe()
    assert mode.recovered_secret is None
    assert all(not is_hit for _, is_hit in probe_safe.values())
    outcome = mode.check_victory()
    assert outcome.finished and outcome.victory

