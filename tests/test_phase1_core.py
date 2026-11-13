"""Phase 1 Verification Suite for SiliconTree core_engine."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_engine import (
    ALU,
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
    parse_assembly,
)


def test_strict_mvc_decoupling_no_pygame_imports() -> None:
    core_dir = ROOT / "core_engine"
    forbidden = {"pygame", "pygame_gui", "gui", "modes"}
    for py_file in core_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden, f"{py_file.name} imports forbidden module {top}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top not in forbidden, f"{py_file.name} imports forbidden module {top}"


def test_alu_booth_bitpair_and_division() -> None:
    alu = ALU()
    for a, b in [(7, 3), (-6, 5), (12, -4), (-9, -9), (0, 42)]:
        booth = alu.booth_multiply(a, b, bits=16)
        bitpair = alu.bit_pair_multiply(a, b, bits=16)
        assert booth.product_64 == a * b
        assert bitpair.product_64 == a * b
        assert len(bitpair.steps) == 8
        assert len(booth.steps) == 16

    for dividend, divisor in [(47, 5), (-47, 5), (47, -5), (-47, -5), (100, 10)]:
        r_div = alu.restoring_divide(dividend, divisor, bits=16)
        nr_div = alu.non_restoring_divide(dividend, divisor, bits=16)
        # Truncation toward zero semantics
        exp_q = int(dividend / divisor)
        exp_r = dividend - exp_q * divisor
        assert (r_div.quotient & 0xFFFF) == (exp_q & 0xFFFF)
        assert (r_div.remainder & 0xFFFF) == (exp_r & 0xFFFF)
        assert (nr_div.quotient & 0xFFFF) == (exp_q & 0xFFFF)
        assert (nr_div.remainder & 0xFFFF) == (exp_r & 0xFFFF)


def test_cache_conflict_miss_and_associativity_upgrade() -> None:
    # Direct-mapped 128B cache with 64B lines => 2 sets (addr 0x0000 and 0x0080 map to set 0!)
    dm_mem = MemorySubsystem(CacheConfig("L1", size_bytes=128, line_size=64, associativity=1), dram_latency=10)
    dm_mem.load_dram_words({0x0000: 111, 0x0080: 222})

    r1 = dm_mem.read_word(0x0000, cycle=1)
    assert not r1.l1_hit
    r2 = dm_mem.read_word(0x0080, cycle=2)
    assert not r2.l1_hit and r2.conflict_miss
    # 0x0000 was evicted by 0x0080 -> misses again!
    r3 = dm_mem.read_word(0x0000, cycle=3)
    assert not r3.l1_hit and r3.conflict_miss

    # 2-Way Set-Associative 128B cache: holds both 0x0000 and 0x0080 without conflict!
    sa_mem = MemorySubsystem(CacheConfig("L1", size_bytes=128, line_size=64, associativity=2), dram_latency=10)
    sa_mem.load_dram_words({0x0000: 111, 0x0080: 222})
    sa_mem.read_word(0x0000, cycle=1)
    sa_mem.read_word(0x0080, cycle=2)
    r_hit = sa_mem.read_word(0x0000, cycle=3)
    assert r_hit.l1_hit


def test_bus_dma_cycle_stealing_and_irq() -> None:
    mem = MemorySubsystem()
    mem.load_dram_words({0x1000: 0xDEADBEEF, 0x1004: 0xCAFEBABE})
    bus = BusSubsystem(topology=BusTopology.SINGLE_BUS)
    bus.start_dma(src_addr=0x1000, dst_addr=0x2000, word_count=2, cycle_stealing=True)
    assert not bus.can_cpu_use_data_bus()
    assert not bus.can_cpu_use_inst_bus()
    bus.tick(mem)
    bus.tick(mem)
    assert not bus.dma_active
    assert mem.read_dram_word_direct(0x2000) == 0xDEADBEEF
    assert mem.read_dram_word_direct(0x2004) == 0xCAFEBABE

    bus.raise_irq(irq_id=3, name="TIMER", vector_pc=0x0100)
    irq = bus.poll_irq()
    assert irq is not None and irq.vector_pc == 0x0100


def test_phase1_verification_gate_program_and_rewind() -> None:
    """
    Phase 1 Gate:
    Program includes:
      - RAW data hazards (ALU->ALU forwarding & Load-Use stall)
      - Booth multiplication (MUL)
      - Cache conflict miss (two addresses in same direct-mapped set)
      - Mispredicted branch followed by a speculative load warming L1 before rollback
    """
    asm = """
    ; Setup addresses for conflict miss in 128B DM cache (64B lines -> set 0 = 0x200, 0x280)
    ADDI R1, R0, 0x200     ; addr A (set 0)
    ADDI R2, R0, 0x280     ; addr B (set 0 -> conflict with A)
    ADDI R3, R0, 6
    ADDI R4, R0, 7
    MUL  R5, R3, R4        ; Booth multiplication: R5 <- 42
    ADD  R6, R5, R3        ; RAW ALU->ALU hazard on R5 -> R6 = 48
    LW   R7, 0(R1)         ; Miss #1: loads 0x200 (111) into L1 set 0
    ADD  R8, R7, R5        ; RAW Load-Use hazard on R7 -> R8 = 153
    LW   R9, 0(R2)         ; Conflict Miss #2: evicts 0x200, loads 0x280 (222)
    LW   R10, 0(R1)        ; Conflict Miss #3: 0x200 was evicted!
    ; Mispredicted branch: Predictor pre-trained NOT TAKEN, but R10 (111) >= R5 (42) IS TAKEN!
    ADDI R11, R0, 0x300    ; Target probe line (set 0 or set 1, completely cold)
    BGE  R10, R5, safe_exit
    LW   R12, 0(R11)       ; Speculative load! Warms 0x300 in L1, MUST NOT commit R12!
    ADDI R13, R0, 999      ; Should also be flushed!
    safe_exit:
    ADDI R14, R0, 77
    HALT
    """
    prog = assemble_program(asm)
    mem = MemorySubsystem(
        l1_config=CacheConfig("L1", size_bytes=256, line_size=64, associativity=1, hit_latency=1),
        dram_latency=5,
    )
    # Use 128B L1 so 0x200 and 0x280 collide in set 0! (0x200>>6=8 -> set 0, 0x280>>6=10 -> set 0 in 2-set cache)
    mem = MemorySubsystem(
        l1_config=CacheConfig("L1", size_bytes=128, line_size=64, associativity=1, hit_latency=1),
        dram_latency=5,
    )
    mem.load_dram_words({0x200: 111, 0x280: 222, 0x300: 0xCAFE})

    predictor = BranchPredictor(mode=PredictorMode.TWO_BIT_SATURATING, initial_state=0)
    # Find branch PC and ensure predictor predicts NOT TAKEN (state=0)
    branch_inst = [i for i in prog.instructions if i.opcode.value == "BGE"][0]
    predictor.train_branch(branch_inst.pc, branch_inst.imm, taken=False)

    pipe = Pipeline(memory=mem, predictor=predictor, forwarding_enabled=True, speculative_execution=True)
    pipe.load_program(prog.instructions)
    clock = SimulationClock(pipe, mem, predictor)

    # Track when speculative leak occurs and capture snapshot around it
    leak_observed_cycle = None
    for _ in range(120):
        snap = clock.step_cycle()
        assert isinstance(snap, CycleSnapshot)
        if snap.speculative_leak_events and leak_observed_cycle is None:
            leak_observed_cycle = snap.cycle
        if snap.halted:
            break

    final = clock.latest_snapshot()
    assert final.halted
    # Architectural checks
    assert final.regs[5] == 42, f"Expected Booth MUL 6*7=42, got {final.regs[5]}"
    assert final.regs[6] == 48, f"Expected RAW forwarded 42+6=48, got {final.regs[6]}"
    assert final.regs[7] == 111
    assert final.regs[8] == 153
    assert final.regs[9] == 222
    assert final.regs[10] == 111
    assert final.regs[14] == 77
    # Conflict misses occurred
    assert final.l1_conflict_misses >= 2
    # Speculative rollback cleared architectural registers R12 and R13!
    assert final.regs[12] == 0, f"Speculative load leaked into architectural R12={final.regs[12]}"
    assert final.regs[13] == 0, f"Speculative ADDI leaked into architectural R13={final.regs[13]}"
    # Speculative execution warmed L1 cache line 0x300 BEFORE rollback!
    assert leak_observed_cycle is not None, "Expected speculative leak event"
    assert any(ev.address == 0x300 for ev in final.speculative_leak_events)
    assert mem.l1.is_line_warm(0x300), "L1 cache line 0x300 should remain warm after rollback!"

    # Test time-travel rewind by 3 cycles!
    target_cycle = final.cycle - 3
    expected_snap = clock.get_snapshot(target_cycle)
    assert expected_snap is not None
    rewound = clock.rewind(3)
    assert rewound.cycle == target_cycle
    assert rewound.regs == expected_snap.regs
    assert rewound.l1_lines == expected_snap.l1_lines
    assert tuple(pipe.regs) == expected_snap.regs
    assert mem.l1.export_snapshots() == expected_snap.l1_lines

    # Rewind all the way before the speculative leak and confirm 0x300 is cold again!
    pre_leak_cycle = max(0, leak_observed_cycle - 2)
    clock.scrub_to(pre_leak_cycle)
    assert not mem.l1.is_line_warm(0x300), "Rewinding before speculative load must restore cold L1 cache!"


def test_spectre_v1_gadget_and_lfence_mitigation() -> None:
    """Verify multi-instruction Spectre v1 gadget leaks secret via L1 and LFENCE stops it."""
    asm = """
    ADDI R1, R0, 0x0500    ; R1 = untrusted index addr (points out of bounds!)
    ADDI R2, R0, 0x0400    ; R2 = pointer to array_bound (slow DRAM load)
    LW   R3, 0(R2)         ; R3 = bound (16) -> MSHR miss
    BGE  R1, R3, safe_exit ; mispredicted NOT TAKEN (trained in-bounds)
    LW   R4, 0(R1)         ; speculative read secret = 5
    SLLI R5, R4, 6         ; scale secret * 64 (cache line size)
    LW   R6, 0x0800(R5)    ; speculative probe load: warms 0x0800 + 5*64 = 0x0940!
    safe_exit:
    ADDI R7, R0, 1
    HALT
    """
    for lfence_on in (False, True):
        prog = assemble_program(asm)
        mem = MemorySubsystem(
            l1_config=CacheConfig("L1", size_bytes=1024, line_size=64, associativity=2, hit_latency=1),
            dram_latency=12,
        )
        mem.load_dram_words({0x0400: 16, 0x0500: 5, 0x0940: 0xAA})
        pred = BranchPredictor(PredictorMode.TWO_BIT_SATURATING, initial_state=0)
        bge = [i for i in prog.instructions if i.opcode.value == "BGE"][0]
        pred.train_branch(bge.pc, bge.imm, taken=False)

        pipe = Pipeline(
            memory=mem,
            predictor=pred,
            speculative_execution=True,
            lfence_enforced=lfence_on,
            non_blocking_loads=True,
        )
        pipe.load_program(prog.instructions)
        clock = SimulationClock(pipe, mem, pred)
        for _ in range(80):
            snap = clock.step_cycle()
            if snap.halted:
                break

        final = clock.latest_snapshot()
        assert final.halted
        assert final.regs[4] == 0
        assert final.regs[6] == 0
        if lfence_on:
            assert not mem.l1.is_line_warm(0x0940), "LFENCE must prevent warming secret probe line"
            assert len(final.speculative_leak_events) == 0
        else:
            assert mem.l1.is_line_warm(0x0940), "Spectre v1 gadget should warm 0x0940 in L1!"
            assert any(ev.address == 0x0940 for ev in final.speculative_leak_events)

