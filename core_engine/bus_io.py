"""System bus arbitration (Single vs Multi-Bus), DMA cycle-stealing, and Interrupt controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core_engine.memory import MemorySubsystem


class BusTopology(str, Enum):
    """Bus architecture variants."""

    SINGLE_BUS = "SINGLE_BUS"
    MULTI_BUS = "MULTI_BUS"


@dataclass(frozen=True)
class BusPacket:
    """Immutable descriptor of a bus transfer for simulation & GUI interpolation."""

    packet_id: int
    bus_name: str
    src: str
    dst: str
    kind: str  # IFETCH, MEM_READ, MEM_WRITE, REG_ALU, DMA, IRQ
    address: int
    data: int
    cycles_total: int
    cycles_remaining: int


@dataclass(frozen=True)
class InterruptRequest:
    """Pending or active hardware interrupt."""

    irq_id: int
    name: str
    vector_pc: int
    priority: int = 1


@dataclass(frozen=True)
class DMAChannelState:
    """Immutable DMA state snapshot."""

    active: bool
    src_addr: int
    dst_addr: int
    words_remaining: int
    words_transferred: int
    cycle_stealing: bool


@dataclass(frozen=True)
class BusSnapshot:
    """Immutable snapshot of BusSubsystem for time-travel rewind."""

    topology: BusTopology
    next_packet_id: int
    active_packets: tuple[BusPacket, ...]
    dma_state: DMAChannelState
    pending_irqs: tuple[InterruptRequest, ...]
    irq_masked: bool
    bus_busy_cycles: int
    dma_stolen_cycles: int


class BusSubsystem:
    """Arbitrates Single vs Multi-bus traffic, DMA cycle-stealing, and IRQs."""

    def __init__(self, topology: BusTopology = BusTopology.MULTI_BUS) -> None:
        self.topology = topology
        self._next_packet_id: int = 1
        self.active_packets: list[BusPacket] = []

        # DMA state
        self.dma_active: bool = False
        self.dma_src: int = 0
        self.dma_dst: int = 0
        self.dma_words_remaining: int = 0
        self.dma_words_transferred: int = 0
        self.dma_cycle_stealing: bool = True

        # Interrupts
        self.pending_irqs: list[InterruptRequest] = []
        self.irq_masked: bool = False

        # Metrics
        self.bus_busy_cycles: int = 0
        self.dma_stolen_cycles: int = 0

    def start_dma(
        self,
        src_addr: int,
        dst_addr: int,
        word_count: int,
        cycle_stealing: bool = True,
    ) -> None:
        """Initiate a DMA block transfer."""
        if word_count <= 0:
            return
        self.dma_active = True
        self.dma_src = src_addr & ~0x3
        self.dma_dst = dst_addr & ~0x3
        self.dma_words_remaining = word_count
        self.dma_words_transferred = 0
        self.dma_cycle_stealing = cycle_stealing

    def raise_irq(self, irq_id: int, name: str, vector_pc: int, priority: int = 1) -> None:
        """Queue an interrupt request."""
        self.pending_irqs.append(
            InterruptRequest(irq_id=irq_id, name=name, vector_pc=vector_pc, priority=priority)
        )
        self.pending_irqs.sort(key=lambda r: r.priority, reverse=True)

    def poll_irq(self) -> Optional[InterruptRequest]:
        """Pop highest-priority unmasked IRQ if available."""
        if self.irq_masked or not self.pending_irqs:
            return None
        irq = self.pending_irqs.pop(0)
        self.emit_packet(
            bus_name="CTRL_BUS",
            src="IRQ_CTRL",
            dst="CPU_PC",
            kind="IRQ",
            address=irq.vector_pc,
            data=irq.irq_id,
            cycles=1,
        )
        return irq

    def emit_packet(
        self,
        bus_name: str,
        src: str,
        dst: str,
        kind: str,
        address: int,
        data: int,
        cycles: int = 1,
    ) -> BusPacket:
        """Register a visual/architectural bus transfer packet."""
        pkt = BusPacket(
            packet_id=self._next_packet_id,
            bus_name=bus_name,
            src=src,
            dst=dst,
            kind=kind,
            address=address & 0xFFFFFFFF,
            data=data & 0xFFFFFFFF,
            cycles_total=max(1, cycles),
            cycles_remaining=max(1, cycles),
        )
        self._next_packet_id += 1
        self.active_packets.append(pkt)
        return pkt

    def can_cpu_use_data_bus(self) -> bool:
        """Return False if DMA is stealing the data/system bus this cycle."""
        if not self.dma_active:
            return True
        if self.dma_cycle_stealing:
            return False
        return False

    def can_cpu_use_inst_bus(self) -> bool:
        """In SINGLE_BUS mode, DMA or MEM traffic contends with IFETCH; MULTI_BUS has separate I-bus."""
        if self.topology == BusTopology.MULTI_BUS:
            return True
        if self.dma_active:
            return False
        for pkt in self.active_packets:
            if pkt.kind in ("MEM_READ", "MEM_WRITE", "DMA") and pkt.cycles_remaining > 0:
                return False
        return True

    def tick(self, memory: Optional[MemorySubsystem] = None) -> None:
        """Advance active bus packets by 1 cycle and perform 1 DMA cycle-steal word transfer if active."""
        updated: list[BusPacket] = []
        for pkt in self.active_packets:
            rem = pkt.cycles_remaining - 1
            if rem > 0:
                updated.append(
                    BusPacket(
                        packet_id=pkt.packet_id,
                        bus_name=pkt.bus_name,
                        src=pkt.src,
                        dst=pkt.dst,
                        kind=pkt.kind,
                        address=pkt.address,
                        data=pkt.data,
                        cycles_total=pkt.cycles_total,
                        cycles_remaining=rem,
                    )
                )
        self.active_packets = updated

        if self.dma_active and self.dma_words_remaining > 0:
            self.dma_stolen_cycles += 1
            self.bus_busy_cycles += 1
            val = 0
            if memory is not None:
                val = memory.read_dram_word_direct(self.dma_src)
                memory.write_dram_word_direct(self.dma_dst, val)
                # Invalidate stale cache copy on destination if present
                memory.flush_line(self.dma_dst)

            self.emit_packet(
                bus_name="SYSTEM_BUS" if self.topology == BusTopology.SINGLE_BUS else "DATA_BUS",
                src="DMA",
                dst="RAM",
                kind="DMA",
                address=self.dma_dst,
                data=val,
                cycles=1,
            )
            self.dma_src += 4
            self.dma_dst += 4
            self.dma_words_remaining -= 1
            self.dma_words_transferred += 1
            if self.dma_words_remaining == 0:
                self.dma_active = False
        elif self.active_packets:
            self.bus_busy_cycles += 1

    def snapshot(self) -> BusSnapshot:
        return BusSnapshot(
            topology=self.topology,
            next_packet_id=self._next_packet_id,
            active_packets=tuple(self.active_packets),
            dma_state=DMAChannelState(
                active=self.dma_active,
                src_addr=self.dma_src,
                dst_addr=self.dma_dst,
                words_remaining=self.dma_words_remaining,
                words_transferred=self.dma_words_transferred,
                cycle_stealing=self.dma_cycle_stealing,
            ),
            pending_irqs=tuple(self.pending_irqs),
            irq_masked=self.irq_masked,
            bus_busy_cycles=self.bus_busy_cycles,
            dma_stolen_cycles=self.dma_stolen_cycles,
        )

    def restore(self, snap: BusSnapshot) -> None:
        self.topology = snap.topology
        self._next_packet_id = snap.next_packet_id
        self.active_packets = list(snap.active_packets)
        self.dma_active = snap.dma_state.active
        self.dma_src = snap.dma_state.src_addr
        self.dma_dst = snap.dma_state.dst_addr
        self.dma_words_remaining = snap.dma_state.words_remaining
        self.dma_words_transferred = snap.dma_state.words_transferred
        self.dma_cycle_stealing = snap.dma_state.cycle_stealing
        self.pending_irqs = list(snap.pending_irqs)
        self.irq_masked = snap.irq_masked
        self.bus_busy_cycles = snap.bus_busy_cycles
        self.dma_stolen_cycles = snap.dma_stolen_cycles

