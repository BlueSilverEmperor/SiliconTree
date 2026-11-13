"""Main 60 FPS Pygame-CE window, scene router, layout engine, and clock scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
import pygame
import pygame_gui
from pygame_gui.elements import UIButton

from core_engine import (
    BranchPredictor,
    BusSubsystem,
    BusTopology,
    CacheConfig,
    CycleSnapshot,
    MemorySubsystem,
    Pipeline,
    PredictorMode,
    SimulationClock,
    assemble_program,
)
from gui.components import (
    BusAnimator,
    CacheMatrixView,
    ControlDeck,
    PipelineView,
    RegisterFileView,
)
from gui.overlays import (
    BaseOverlay,
    DeathmatchHUDOverlay,
    ForensicHUDOverlay,
    HeistHUDOverlay,
    SpectreHUDOverlay,
    TycoonHUDOverlay,
)
from gui.theme import PALETTE, FontBank, write_pygame_gui_theme
from modes import (
    ArchitectTycoonMode,
    BaseMode,
    ModeOutcome,
    SiliconDeathmatchMode,
    SiliconForensicMode,
    SiliconHeistMode,
    SpectreScopeMode,
)


@dataclass(frozen=True)
class ModeDescriptor:
    """Metadata and factory for a selectable SiliconTree branch."""

    mode_id: str
    title: str
    tag: str
    description: str
    accent: tuple[int, int, int]
    factory: Callable[[], BaseMode]
    overlay_factory: Optional[Callable[[pygame_gui.UIManager, pygame.Rect, BaseMode, FontBank], BaseOverlay]] = None


class _SandboxDemoMode(BaseMode):
    """Built-in interactive architecture sandbox (used in Phase 2 and free-play)."""

    mode_id = "sandbox"
    display_name = "Architecture Sandbox"
    subtitle = "RAW Hazards, Booth MUL, Cache Conflict & Speculative Rollback"

    def load_scenario(self, scenario_path: Optional[str] = None) -> None:
        asm = """
        ADDI R1, R0, 0x0200
        ADDI R2, R0, 0x0280
        ADDI R3, R0, 6
        ADDI R4, R0, 7
        MUL  R5, R3, R4
        ADD  R6, R5, R3
        LW   R7, 0(R1)
        ADD  R8, R7, R5
        LW   R9, 0(R2)
        LW   R10, 0(R1)
        ADDI R11, R0, 0x0300
        BGE  R10, R5, safe_exit
        LW   R12, 0(R11)
        ADDI R13, R0, 999
        safe_exit:
        ADDI R14, R0, 77
        HALT
        """
        prog = assemble_program(asm)
        mem = MemorySubsystem(
            l1_config=CacheConfig("L1", size_bytes=128, line_size=64, associativity=1, hit_latency=1),
            l2_config=CacheConfig("L2", size_bytes=512, line_size=64, associativity=2, hit_latency=4),
            dram_latency=8,
        )
        mem.load_dram_words({0x0200: 111, 0x0280: 222, 0x0300: 0xCAFEBABE})
        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=0)
        bus = BusSubsystem(BusTopology.MULTI_BUS)
        pipe = Pipeline(memory=mem, predictor=pred, bus=bus, forwarding_enabled=True, speculative_execution=True)
        pipe.load_program(prog.instructions)
        self.clock = SimulationClock(pipe, mem, pred, bus)

    def evaluate_tick(self, snapshot: CycleSnapshot) -> None:
        return

    def check_victory(self) -> ModeOutcome:
        snap = self.get_clock().latest_snapshot()
        if snap.halted:
            return ModeOutcome(True, True, "Sandbox Complete", f"Program halted in {snap.cycle} cycles (CPI {snap.cpi:.2f}).")
        return ModeOutcome(False, False, "Running", "Stepping through RISC pipeline.")


class SiliconTreeApp:
    """Top-level 60 FPS application window and scene router."""

    def __init__(self, width: int = 1280, height: int = 720, headless: bool = False) -> None:
        self.width = max(1024, width)
        self.height = max(640, height)
        self.headless = headless

        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        flags = pygame.RESIZABLE if not headless else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        if not headless:
            pygame.display.set_caption("SiliconTree — Computer Architecture & Hardware Security Suite")

        theme_path = write_pygame_gui_theme(Path(__file__).resolve().parent / "_runtime_theme.json")
        self.ui_manager = pygame_gui.UIManager((self.width, self.height), str(theme_path))
        self.fonts = FontBank()
        self.clock_fps = pygame.time.Clock()

        self.scene: str = "HUB"
        self.modes: dict[str, ModeDescriptor] = {}
        self.active_descriptor: Optional[ModeDescriptor] = None
        self.active_mode: Optional[BaseMode] = None
        self.active_overlay: Optional[BaseOverlay] = None

        # Simulation scheduling
        self.is_playing: bool = False
        self.speed_hz: float = 4.0
        self.tick_accumulator: float = 0.0

        # Components
        self.pipeline_view = PipelineView(self.fonts)
        self.cache_view = CacheMatrixView(self.fonts)
        self.bus_animator = BusAnimator(self.fonts)
        self.register_view = RegisterFileView(self.fonts)
        self.control_deck: Optional[ControlDeck] = None

        # Hub UI buttons
        self._hub_buttons: dict[UIButton, str] = {}
        self._layout_rects: dict[str, pygame.Rect] = {}

        self._register_default_modes()
        self._build_hub_ui()

    def _register_default_modes(self) -> None:
        defaults = [
            ModeDescriptor(
                mode_id="spectrescope",
                title="SpectreScope",
                tag="MODE 1 // SECURITY",
                description="Speculative leak detector, Flush+Reload timer & LFENCE barrier.",
                accent=PALETTE.crimson,
                factory=SpectreScopeMode,
                overlay_factory=lambda ui, r, m, f: SpectreHUDOverlay(ui, r, m, f),  # type: ignore[arg-type]
            ),
            ModeDescriptor(
                mode_id="silicon_heist",
                title="Silicon Heist",
                tag="MODE 2 // STEALTH",
                description="Infiltrate L1 lockers via control hazards & escape over cycle-stealing DMA.",
                accent=PALETTE.magenta,
                factory=SiliconHeistMode,
                overlay_factory=lambda ui, r, m, f: HeistHUDOverlay(ui, r, m, f),  # type: ignore[arg-type]
            ),
            ModeDescriptor(
                mode_id="silicon_deathmatch",
                title="Silicon Deathmatch",
                tag="MODE 3 // SURVIVAL",
                description="Survive workload waves, manage thermal HP & draft cache/ALU upgrades.",
                accent=PALETTE.amber,
                factory=SiliconDeathmatchMode,
                overlay_factory=lambda ui, r, m, f: DeathmatchHUDOverlay(ui, r, m, f),  # type: ignore[arg-type]
            ),
            ModeDescriptor(
                mode_id="silicon_forensic",
                title="Silicon Forensic",
                tag="MODE 4 // FORENSICS",
                description="Scrub crash-dump snapshots & isolate corrupted dirty L1 cache tags.",
                accent=PALETTE.cyan,
                factory=SiliconForensicMode,
                overlay_factory=lambda ui, r, m, f: ForensicHUDOverlay(ui, r, m, f),  # type: ignore[arg-type]
            ),
            ModeDescriptor(
                mode_id="architect_tycoon",
                title="Architect Tycoon",
                tag="MODE 5 // DESIGN",
                description="Balance die area, clock/power budgets & synthetic client benchmarks.",
                accent=PALETTE.emerald,
                factory=ArchitectTycoonMode,
                overlay_factory=lambda ui, r, m, f: TycoonHUDOverlay(ui, r, m, f),  # type: ignore[arg-type]
            ),
            ModeDescriptor(
                mode_id="sandbox",
                title="Architecture Sandbox",
                tag="FREE PLAY // CORE",
                description="Interactive 5-stage pipeline, Booth MUL, L1/L2 cache & rollback.",
                accent=PALETTE.violet,
                factory=_SandboxDemoMode,
            ),
        ]
        for desc in defaults:
            self.modes[desc.mode_id] = desc

    def register_mode(self, descriptor: ModeDescriptor) -> None:
        self.modes[descriptor.mode_id] = descriptor
        if self.scene == "HUB":
            self._build_hub_ui()

    def _clear_scene_ui(self) -> None:
        for btn in list(self._hub_buttons.keys()):
            btn.kill()
        self._hub_buttons.clear()
        if self.control_deck is not None:
            self.control_deck.kill()
            self.control_deck = None
        if self.active_overlay is not None:
            self.active_overlay.kill()
            self.active_overlay = None

    def _compute_sim_layout(self, w: int, h: int) -> dict[str, pygame.Rect]:
        pad = 10
        top_h = 46
        pipeline_h = max(140, int((h - top_h - pad * 4) * 0.25))
        overlay_h = 84 if self.active_overlay is not None else 0

        y_pipe = pad + top_h + pad
        y_mid = y_pipe + pipeline_h + pad
        mid_h = h - y_mid - pad - (overlay_h + pad if overlay_h else 0)

        left_w = int((w - pad * 3) * 0.56)
        right_w = w - pad * 3 - left_w
        cache_h = int(mid_h * 0.56)
        bus_h = mid_h - cache_h - pad

        rects = {
            "control": pygame.Rect(pad, pad, w - pad * 2, top_h),
            "pipeline": pygame.Rect(pad, y_pipe, w - pad * 2, pipeline_h),
            "cache": pygame.Rect(pad, y_mid, left_w, cache_h),
            "bus": pygame.Rect(pad, y_mid + cache_h + pad, left_w, bus_h),
            "registers": pygame.Rect(pad * 2 + left_w, y_mid, right_w, mid_h),
        }
        if overlay_h > 0:
            rects["overlay"] = pygame.Rect(pad, h - pad - overlay_h, w - pad * 2, overlay_h)
        return rects

    def _build_hub_ui(self) -> None:
        self._clear_scene_ui()
        self.scene = "HUB"
        self.is_playing = False

        cards = list(self.modes.values())
        cols = 3
        card_w = min(360, (self.width - 120) // cols)
        card_h = 132
        gap_x = 24
        gap_y = 22
        total_w = cols * card_w + (cols - 1) * gap_x
        start_x = (self.width - total_w) // 2
        start_y = 160

        for idx, desc in enumerate(cards):
            r = idx // cols
            c = idx % cols
            cx = start_x + c * (card_w + gap_x)
            cy = start_y + r * (card_h + gap_y)
            btn_rect = pygame.Rect(cx + 16, cy + card_h - 42, card_w - 32, 30)
            btn = UIButton(btn_rect, f"LAUNCH {desc.title.upper()}", self.ui_manager)
            self._hub_buttons[btn] = desc.mode_id

    def launch_mode(self, mode_id: str, scenario_path: Optional[str] = None) -> None:
        """Switch to a simulation mode and initialize its scenario and HUD."""
        if mode_id not in self.modes:
            raise KeyError(f"Unknown mode_id '{mode_id}'")

        self._clear_scene_ui()
        desc = self.modes[mode_id]
        mode = desc.factory()
        mode.load_scenario(scenario_path)

        self.active_descriptor = desc
        self.active_mode = mode
        self.scene = "SIMULATION"
        self.is_playing = False
        self.tick_accumulator = 0.0

        # Build overlay first if present so layout reserves space cleanly
        temp_rects = self._compute_sim_layout(self.width, self.height)
        if desc.overlay_factory is not None:
            dummy_rect = pygame.Rect(10, self.height - 94, self.width - 20, 84)
            self.active_overlay = desc.overlay_factory(self.ui_manager, dummy_rect, mode, self.fonts)

        self._layout_rects = self._compute_sim_layout(self.width, self.height)
        self.control_deck = ControlDeck(self.ui_manager, self._layout_rects["control"], self.fonts)
        if self.active_overlay is not None and "overlay" in self._layout_rects:
            self.active_overlay.rebuild(self._layout_rects["overlay"])

    def _on_resize(self, new_w: int, new_h: int) -> None:
        self.width = max(1024, new_w)
        self.height = max(640, new_h)
        self.ui_manager.set_window_resolution((self.width, self.height))
        if self.scene == "HUB":
            self._build_hub_ui()
        else:
            self._layout_rects = self._compute_sim_layout(self.width, self.height)
            if self.control_deck is not None:
                self.control_deck.rebuild(self._layout_rects["control"])
            if self.active_overlay is not None and "overlay" in self._layout_rects:
                self.active_overlay.rebuild(self._layout_rects["overlay"])

    def step_once(self) -> Optional[CycleSnapshot]:
        if self.active_mode is None:
            return None
        snap = self.active_mode.get_clock().step_cycle()
        self.active_mode.evaluate_tick(snap)
        if snap.halted:
            self.is_playing = False
            if self.control_deck is not None:
                self.control_deck.set_playing(False)
        return snap

    def rewind_once(self) -> Optional[CycleSnapshot]:
        if self.active_mode is None:
            return None
        self.is_playing = False
        if self.control_deck is not None:
            self.control_deck.set_playing(False)
        snap = self.active_mode.get_clock().rewind(1)
        self.active_mode.on_rewind(snap)
        return snap

    def reset_mode(self) -> None:
        if self.active_descriptor is not None:
            self.launch_mode(self.active_descriptor.mode_id)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a single pygame event. Returns False if quit requested."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            self._on_resize(event.w, event.h)

        self.ui_manager.process_events(event)

        if self.scene == "HUB":
            if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element in self._hub_buttons:
                self.launch_mode(self._hub_buttons[event.ui_element])
            return True

        # Simulation scene events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if "cache" in self._layout_rects and self._layout_rects["cache"].collidepoint(event.pos):
                self.cache_view.handle_click(event.pos)

        if self.control_deck is not None:
            actions = self.control_deck.handle_event(event)
            if actions.back_to_hub:
                self._build_hub_ui()
                return True
            if actions.toggle_play:
                self.is_playing = not self.is_playing
                self.control_deck.set_playing(self.is_playing)
            if actions.step_forward:
                self.is_playing = False
                self.control_deck.set_playing(False)
                self.step_once()
                self.tick_accumulator = 0.0
            if actions.rewind_one:
                self.rewind_once()
                self.tick_accumulator = 0.0
            if actions.reset:
                self.reset_mode()
                return True
            if actions.new_speed_hz is not None:
                self.speed_hz = actions.new_speed_hz

        if self.active_overlay is not None:
            self.active_overlay.handle_event(event)

        return True

    def update(self, dt: float) -> None:
        self.ui_manager.update(dt)
        if self.scene == "SIMULATION" and self.is_playing and self.active_mode is not None:
            tick_interval = 1.0 / max(0.5, self.speed_hz)
            self.tick_accumulator += dt
            while self.tick_accumulator >= tick_interval and self.is_playing:
                self.tick_accumulator -= tick_interval
                self.step_once()

    def render(self) -> None:
        self.screen.fill(PALETTE.bg_root)
        if self.scene == "HUB":
            self._render_hub()
        else:
            self._render_simulation()
        self.ui_manager.draw_ui(self.screen)
        if not self.headless:
            pygame.display.flip()

    def _render_hub(self) -> None:
        title_font = self.fonts.get(28, bold=True, mono=False)
        sub_font = self.fonts.get(14, bold=False, mono=False)
        card_title = self.fonts.get(16, bold=True, mono=False)
        mono_sm = self.fonts.get(11, bold=True)

        title = title_font.render("SILICONTREE", True, PALETTE.cyan)
        sub = sub_font.render(
            "Pure-Python 60 FPS Computer Architecture & Hardware Security Simulation Suite",
            True,
            PALETTE.text_secondary,
        )
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 48))
        self.screen.blit(sub, (self.width // 2 - sub.get_width() // 2, 88))

        cards = list(self.modes.values())
        cols = 3
        card_w = min(360, (self.width - 120) // cols)
        card_h = 132
        gap_x = 24
        gap_y = 22
        total_w = cols * card_w + (cols - 1) * gap_x
        start_x = (self.width - total_w) // 2
        start_y = 160

        for idx, desc in enumerate(cards):
            r = idx // cols
            c = idx % cols
            cx = start_x + c * (card_w + gap_x)
            cy = start_y + r * (card_h + gap_y)
            card_rect = pygame.Rect(cx, cy, card_w, card_h)
            pygame.draw.rect(self.screen, PALETTE.bg_panel, card_rect, border_radius=10)
            pygame.draw.rect(self.screen, desc.accent, card_rect, width=1, border_radius=10)

            tag_surf = mono_sm.render(desc.tag, True, desc.accent)
            self.screen.blit(tag_surf, (cx + 16, cy + 12))
            t_surf = card_title.render(desc.title, True, PALETTE.text_primary)
            self.screen.blit(t_surf, (cx + 16, cy + 30))

            # Simple 2-line wrap for description
            words = desc.description.split()
            line1, line2 = "", ""
            for w in words:
                if len(line1) + len(w) + 1 <= 44:
                    line1 = f"{line1} {w}".strip()
                else:
                    line2 = f"{line2} {w}".strip()
            self.screen.blit(sub_font.render(line1, True, PALETTE.text_secondary), (cx + 16, cy + 56))
            if line2:
                self.screen.blit(sub_font.render(line2[:46], True, PALETTE.text_secondary), (cx + 16, cy + 72))

    def _render_simulation(self) -> None:
        if self.active_mode is None:
            return
        snapshot = self.active_mode.get_clock().latest_snapshot()
        tick_interval = 1.0 / max(0.5, self.speed_hz)
        tick_progress = (self.tick_accumulator / tick_interval) if self.is_playing else 1.0

        if self.control_deck is not None:
            self.control_deck.render(self.screen, snapshot, self.active_mode.display_name)
        if "pipeline" in self._layout_rects:
            self.pipeline_view.render(self.screen, self._layout_rects["pipeline"], snapshot, tick_progress)
        if "cache" in self._layout_rects:
            self.cache_view.render(self.screen, self._layout_rects["cache"], snapshot, tick_progress)
        if "bus" in self._layout_rects:
            self.bus_animator.render(self.screen, self._layout_rects["bus"], snapshot, tick_progress)
        if "registers" in self._layout_rects:
            self.register_view.render(self.screen, self._layout_rects["registers"], snapshot)
        if self.active_overlay is not None and "overlay" in self._layout_rects:
            self.active_overlay.render(self.screen, snapshot, tick_progress)

    def run(self) -> None:
        """Run interactive 60 FPS main loop."""
        running = True
        while running:
            dt = self.clock_fps.tick(60) / 1000.0
            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
                    break
            self.update(dt)
            self.render()
        pygame.quit()

    def headless_dry_run(self, mode_id: str = "sandbox", frames: int = 120) -> CycleSnapshot:
        """Render `frames` frames in headless mode for automated verification."""
        self.launch_mode(mode_id)
        self.is_playing = True
        for i in range(frames):
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(1.0 / 60.0)
            self.render()
            if i == 30:
                self.rewind_once()
                self.is_playing = True
        return self.active_mode.get_clock().latest_snapshot()  # type: ignore[union-attr]
