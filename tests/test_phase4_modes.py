"""Phase 4 Verification Suite for Mode 2 (Silicon Heist) and Mode 3 (Silicon Deathmatch)."""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modes.silicon_deathmatch import SiliconDeathmatchMode
from modes.silicon_heist import SiliconHeistMode


def test_silicon_heist_win_and_loss() -> None:
    # Win path: touch both lockers and trigger cycle-stealing DMA escape
    heist = SiliconHeistMode()
    heist.load_scenario()
    clock = heist.get_clock()

    for _ in range(40):
        snap = clock.step_cycle()
        heist.evaluate_tick(snap)
        if heist.stealth_state == "LOCKERS_BREACHED" and not heist.dma_triggered:
            heist.trigger_dma_escape()
        if heist.escaped:
            break

    outcome = heist.check_victory()
    assert outcome.finished and outcome.victory, f"Expected heist escape, got {outcome}"
    assert heist.memory.read_dram_word_direct(0x0900) == 0xDEADBEEF

    # Loss path: watchdog alarm triggered
    heist_loss = SiliconHeistMode()
    heist_loss.load_scenario()
    heist_loss.inject_alarm_noise(5)
    loss_out = heist_loss.check_victory()
    assert loss_out.finished and not loss_out.victory


def test_silicon_deathmatch_upgrade_reduces_conflict_damage() -> None:
    # Run Wave 2 (Strided Cache Thrashing) WITHOUT 4-way upgrade (Direct-Mapped)
    dm_base = SiliconDeathmatchMode()
    dm_base.load_scenario()
    dm_base.start_next_wave()  # Jump to Wave 2 (Strided Cache Thrashing)
    hp_before_dm = dm_base.thermal_hp
    clock_dm = dm_base.get_clock()
    for _ in range(180):
        snap = clock_dm.step_cycle()
        dm_base.evaluate_tick(snap)
        if snap.halted or dm_base.thermal_meltdown:
            break
    cm_dm = clock_dm.latest_snapshot().l1_conflict_misses
    dmg_dm = hp_before_dm - dm_base.thermal_hp

    # Run Wave 2 WITH 4-Way Set-Associative upgrade
    dm_up = SiliconDeathmatchMode()
    dm_up.load_scenario()
    assert dm_up.apply_upgrade("CACHE_4WAY")
    dm_up.start_next_wave()  # Wave 2 with 4-way L1
    hp_before_up = dm_up.thermal_hp
    clock_up = dm_up.get_clock()
    for _ in range(180):
        snap = clock_up.step_cycle()
        dm_up.evaluate_tick(snap)
        if snap.halted or dm_up.thermal_meltdown:
            break
    cm_up = clock_up.latest_snapshot().l1_conflict_misses
    dmg_up = hp_before_up - dm_up.thermal_hp

    assert cm_up < cm_dm, f"Expected 4-way L1 conflict misses ({cm_up}) < Direct-Mapped ({cm_dm})"
    assert dmg_up < dmg_dm, f"Expected 4-way thermal damage ({dmg_up:.1f}) < Direct-Mapped ({dmg_dm:.1f})"

