"""Flask application and strict-MVC state serializer for SiliconTree."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional
from flask import Flask, jsonify, render_template, request

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
from modes import (
    ArchitectTycoonMode,
    BaseMode,
    ModeOutcome,
    SiliconDeathmatchMode,
    SiliconForensicMode,
    SiliconHeistMode,
    SpectreScopeMode,
)


class _SandboxMode(BaseMode):
    """Built-in interactive architecture sandbox."""

    mode_id = "sandbox"
    display_name = "Architecture Sandbox"
    subtitle = "5-Stage Pipeline, Booth MUL, Cache Conflict & Speculative Rollback"

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
            return ModeOutcome(True, True, "Sandbox Complete", f"Halted in {snap.cycle} cycles (CPI {snap.cpi:.2f}).")
        return ModeOutcome(False, False, "Running", "Stepping through RISC pipeline.")


MODE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "spectrescope",
        "title": "SpectreScope",
        "category": "Hardware Security",
        "description": "Speculative leak detector, Flush+Reload timer & LFENCE serialization barrier.",
        "factory": SpectreScopeMode,
    },
    {
        "id": "silicon_heist",
        "title": "Silicon Heist",
        "category": "Stealth Puzzle",
        "description": "Infiltrate L1 lockers via control hazards & escape over cycle-stealing DMA.",
        "factory": SiliconHeistMode,
    },
    {
        "id": "silicon_deathmatch",
        "title": "Silicon Deathmatch",
        "category": "Thermal Survival",
        "description": "Survive workload waves, manage thermal HP & draft cache/ALU upgrades.",
        "factory": SiliconDeathmatchMode,
    },
    {
        "id": "silicon_forensic",
        "title": "Silicon Forensic",
        "category": "Post-Mortem",
        "description": "Scrub crash-dump snapshots & isolate corrupted dirty L1 cache tags.",
        "factory": SiliconForensicMode,
    },
    {
        "id": "architect_tycoon",
        "title": "Architect Tycoon",
        "category": "SoC Design",
        "description": "Balance die area, clock/power budgets & synthetic client benchmarks.",
        "factory": ArchitectTycoonMode,
    },
    {
        "id": "sandbox",
        "title": "Architecture Sandbox",
        "category": "Free Play",
        "description": "Interactive 5-stage pipeline, Booth MUL, L1/L2 cache & speculative rollback.",
        "factory": _SandboxMode,
    },
]


class SimulationSession:
    """Holds the active mode and serializes CycleSnapshot state for the Flask UI."""

    def __init__(self) -> None:
        self._factories = {item["id"]: item["factory"] for item in MODE_CATALOG}
        self.active_mode_id: str = "spectrescope"
        self.mode: BaseMode = SpectreScopeMode()
        self.mode.load_scenario()

    def switch_mode(self, mode_id: str) -> None:
        if mode_id not in self._factories:
            raise KeyError(f"Unknown mode '{mode_id}'")
        self.active_mode_id = mode_id
        self.mode = self._factories[mode_id]()
        self.mode.load_scenario()

    def step(self, count: int = 1) -> None:
        clock = self.mode.get_clock()
        for _ in range(max(1, min(50, count))):
            snap = clock.step_cycle()
            self.mode.evaluate_tick(snap)
            if snap.halted:
                break

    def rewind(self, count: int = 1) -> None:
        snap = self.mode.get_clock().rewind(max(1, count))
        self.mode.on_rewind(snap)

    def reset(self) -> None:
        self.mode.load_scenario()

    def serialize(self) -> dict[str, Any]:
        snap = self.mode.get_clock().latest_snapshot()
        outcome = self.mode.check_victory()

        stages_out: dict[str, Any] = {}
        for name in ("IF", "ID", "EX", "MEM", "WB"):
            slot = snap.stages[name]
            inst = slot.instruction
            stages_out[name] = {
                "pc": slot.pc,
                "is_bubble": slot.is_bubble,
                "stall_reason": slot.stall_reason,
                "is_speculative": slot.is_speculative,
                "mispredicted": slot.mispredicted,
                "l1_warmed_speculatively": slot.l1_warmed_speculatively,
                "mem_cycles_left": slot.mem_cycles_left,
                "ex_cycles_left": slot.ex_cycles_left,
                "forwarded_from": list(slot.forwarded_from),
                "text": inst.raw_text if inst else (f"NOP ({slot.stall_reason})" if slot.stall_reason else "NOP"),
                "rtn": inst.rtn if inst else "",
                "opcode": inst.opcode.value if inst else "NOP",
            }

        mode_hud: dict[str, Any] = {}
        if isinstance(self.mode, SpectreScopeMode):
            mode_hud = {
                "lfence_enabled": self.mode.lfence_enabled,
                "leak_detected": self.mode.leak_detected,
                "leaked_addresses": [f"0x{a:04X}" for a in self.mode.leaked_addresses],
                "recovered_secret": self.mode.recovered_secret,
                "probe_results": [
                    {"slot": k, "latency": v[0], "hit": v[1]}
                    for k, v in sorted(self.mode.probe_results.items())
                ],
                "num_probe_slots": int(self.mode.scenario_data.get("num_probe_slots", 8)),
            }
        elif isinstance(self.mode, SiliconHeistMode):
            mode_hud = {
                "stealth_state": self.mode.stealth_state,
                "stealth_noise": self.mode.stealth_noise,
                "max_noise": self.mode.max_noise,
                "lockers_touched": len(self.mode.lockers_touched),
                "total_lockers": len(self.mode.target_lockers),
                "dma_triggered": self.mode.dma_triggered,
                "escaped": self.mode.escaped,
            }
        elif isinstance(self.mode, SiliconDeathmatchMode):
            mode_hud = {
                "thermal_hp": round(self.mode.thermal_hp, 1),
                "max_thermal_hp": self.mode.max_thermal_hp,
                "wave_index": self.mode.wave_index,
                "total_waves": len(self.mode.waves),
                "wave_name": self.mode.waves[self.mode.wave_index]["name"] if self.mode.waves else "",
                "upgrade_draft_open": self.mode.upgrade_draft_open,
                "applied_upgrades": list(self.mode.applied_upgrades),
                "l1_associativity": self.mode.l1_associativity,
            }
        elif isinstance(self.mode, SiliconForensicMode):
            dirty_tags = [f"0x{ln.tag:X}" for ln in snap.l1_lines if ln.valid and ln.dirty]
            mode_hud = {
                "crash_cycle": self.mode.crash_cycle,
                "inspected_cycle": self.mode.inspected_cycle,
                "culprit_tag": f"0x{self.mode.culprit_tag:X}",
                "dirty_tags": dirty_tags,
                "evidence_verified": self.mode.evidence_verified,
            }
        elif isinstance(self.mode, ArchitectTycoonMode):
            mode_hud = {
                "clock_ghz": self.mode.clock_ghz,
                "l1_associativity": self.mode.l1_associativity,
                "forwarding_enabled": self.mode.forwarding_enabled,
                "bus_topology": self.mode.bus_topology.value,
                "die_area_mm2": self.mode.die_area_mm2(),
                "max_area_mm2": self.mode.max_area_mm2,
                "power_watts": self.mode.power_watts(),
                "max_power_w": self.mode.max_power_w,
                "target_cpi": self.mode.target_cpi,
                "last_benchmark_cpi": self.mode.last_benchmark_cpi,
                "contract_evaluated": self.mode.contract_evaluated,
                "contract_passed": self.mode.contract_passed,
            }

        return {
            "mode_id": self.active_mode_id,
            "mode_title": self.mode.display_name,
            "mode_subtitle": self.mode.subtitle,
            "catalog": [
                {"id": m["id"], "title": m["title"], "category": m["category"], "description": m["description"]}
                for m in MODE_CATALOG
            ],
            "outcome": asdict(outcome),
            "mode_hud": mode_hud,
            "snapshot": {
                "cycle": snap.cycle,
                "instructions_retired": snap.instructions_retired,
                "cpi": snap.cpi,
                "pc": snap.pc,
                "halted": snap.halted,
                "stall_cycles": snap.stall_cycles,
                "speculative_flushes": snap.speculative_flushes,
                "bus_topology": snap.bus_topology,
                "dma_active": snap.dma_active,
                "dma_words_transferred": snap.dma_words_transferred,
                "predictor_mode": snap.predictor_mode,
                "predictor_mispredictions": snap.predictor_mispredictions,
                "regs": list(snap.regs),
                "spec_regs": list(snap.spec_regs),
                "stages": stages_out,
                "forwarding_events": [asdict(f) for f in snap.forwarding_events],
                "l1_hits": snap.l1_hits,
                "l1_misses": snap.l1_misses,
                "l1_conflict_misses": snap.l1_conflict_misses,
                "l1_lines": [asdict(ln) for ln in snap.l1_lines],
                "l2_lines": [asdict(ln) for ln in snap.l2_lines],
                "bus_packets": [asdict(p) for p in snap.bus_packets],
                "rtn_log": list(snap.rtn_log[-18:]),
                "speculative_leak_events": [asdict(ev) for ev in snap.speculative_leak_events],
            },
        }


def create_flask_app() -> Flask:
    """Create and configure the SiliconTree Flask application."""
    base_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    session = SimulationSession()

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/state")
    def api_state() -> Any:
        return jsonify(session.serialize())

    @app.post("/api/mode/<mode_id>")
    def api_switch_mode(mode_id: str) -> Any:
        try:
            session.switch_mode(mode_id)
        except KeyError:
            return jsonify({"error": f"Unknown mode '{mode_id}'"}), 404
        return jsonify(session.serialize())

    @app.post("/api/step")
    def api_step() -> Any:
        body = request.get_json(silent=True) or {}
        session.step(int(body.get("count", 1)))
        return jsonify(session.serialize())

    @app.post("/api/rewind")
    def api_rewind() -> Any:
        body = request.get_json(silent=True) or {}
        session.rewind(int(body.get("count", 1)))
        return jsonify(session.serialize())

    @app.post("/api/reset")
    def api_reset() -> Any:
        session.reset()
        return jsonify(session.serialize())

    # Mode-specific actions
    @app.post("/api/spectre/lfence")
    def api_spectre_lfence() -> Any:
        if not isinstance(session.mode, SpectreScopeMode):
            return jsonify({"error": "Not in SpectreScope mode"}), 400
        body = request.get_json(silent=True) or {}
        enabled = body.get("enabled", None)
        session.mode.toggle_lfence(enabled=enabled, reset_sim=True)
        return jsonify(session.serialize())

    @app.post("/api/spectre/probe")
    def api_spectre_probe() -> Any:
        if not isinstance(session.mode, SpectreScopeMode):
            return jsonify({"error": "Not in SpectreScope mode"}), 400
        session.mode.run_flush_reload_probe()
        return jsonify(session.serialize())

    @app.post("/api/heist/dma")
    def api_heist_dma() -> Any:
        if not isinstance(session.mode, SiliconHeistMode):
            return jsonify({"error": "Not in Silicon Heist mode"}), 400
        session.mode.trigger_dma_escape()
        return jsonify(session.serialize())

    @app.post("/api/deathmatch/upgrade")
    def api_deathmatch_upgrade() -> Any:
        if not isinstance(session.mode, SiliconDeathmatchMode):
            return jsonify({"error": "Not in Silicon Deathmatch mode"}), 400
        body = request.get_json(silent=True) or {}
        session.mode.apply_upgrade(str(body.get("upgrade_id", "")))
        return jsonify(session.serialize())

    @app.post("/api/deathmatch/next_wave")
    def api_deathmatch_next_wave() -> Any:
        if not isinstance(session.mode, SiliconDeathmatchMode):
            return jsonify({"error": "Not in Silicon Deathmatch mode"}), 400
        session.mode.start_next_wave()
        return jsonify(session.serialize())

    @app.post("/api/forensic/scrub")
    def api_forensic_scrub() -> Any:
        if not isinstance(session.mode, SiliconForensicMode):
            return jsonify({"error": "Not in Silicon Forensic mode"}), 400
        body = request.get_json(silent=True) or {}
        session.mode.scrub_cycle(int(body.get("cycle", 0)))
        return jsonify(session.serialize())

    @app.post("/api/forensic/submit")
    def api_forensic_submit() -> Any:
        if not isinstance(session.mode, SiliconForensicMode):
            return jsonify({"error": "Not in Silicon Forensic mode"}), 400
        session.mode.submit_evidence()
        return jsonify(session.serialize())

    @app.post("/api/tycoon/configure")
    def api_tycoon_configure() -> Any:
        if not isinstance(session.mode, ArchitectTycoonMode):
            return jsonify({"error": "Not in Architect Tycoon mode"}), 400
        body = request.get_json(silent=True) or {}
        bus_topo = BusTopology(body["bus_topology"]) if "bus_topology" in body else None
        session.mode.configure(
            clock_ghz=float(body["clock_ghz"]) if "clock_ghz" in body else None,
            l1_associativity=int(body["l1_associativity"]) if "l1_associativity" in body else None,
            forwarding_enabled=bool(body["forwarding_enabled"]) if "forwarding_enabled" in body else None,
            bus_topology=bus_topo,
        )
        return jsonify(session.serialize())

    @app.post("/api/tycoon/evaluate")
    def api_tycoon_evaluate() -> Any:
        if not isinstance(session.mode, ArchitectTycoonMode):
            return jsonify({"error": "Not in Architect Tycoon mode"}), 400
        session.mode.evaluate_contract()
        return jsonify(session.serialize())

    return app

