"""Memory hierarchy: SRAM L1/L2 caches (Direct-Mapped & N-Way Set-Associative LRU) and DRAM."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for a single cache level."""

    name: str = "L1"
    size_bytes: int = 256
    line_size: int = 64
    associativity: int = 1
    hit_latency: int = 1


@dataclass(frozen=True)
class CacheLineSnapshot:
    """Immutable snapshot of a single cache line for GUI rendering and time-travel."""

    set_index: int
    way_index: int
    valid: bool
    dirty: bool
    tag: int
    last_used_cycle: int
    speculative_warm: bool
    last_access_type: str
    last_access_cycle: int
    data_words: tuple[int, ...]


@dataclass(frozen=True)
class MemoryAccessResult:
    """Detailed outcome of a memory read/write operation."""

    address: int
    is_write: bool
    l1_hit: bool
    l2_hit: Optional[bool]
    latency_cycles: int
    value: int
    l1_set: int
    l1_way: int
    l1_tag: int
    evicted_dirty: bool
    evicted_tag: Optional[int]
    speculative_warmed: bool
    conflict_miss: bool


@dataclass(frozen=True)
class CacheLevelState:
    """Frozen full state of a CacheLevel for exact time-travel restore."""

    lines: tuple[CacheLineSnapshot, ...]
    hits: int
    misses: int
    conflict_misses: int
    evictions: int
    seen_tags: frozenset[int]


@dataclass(frozen=True)
class MemorySnapshot:
    """Frozen full state of MemorySubsystem for exact time-travel restore."""

    l1_state: CacheLevelState
    l2_state: Optional[CacheLevelState]
    dram_words: tuple[tuple[int, int], ...]
    last_access: Optional[MemoryAccessResult]


class _CacheLine:
    """Mutable internal cache line."""

    __slots__ = (
        "valid",
        "dirty",
        "tag",
        "last_used_cycle",
        "speculative_warm",
        "last_access_type",
        "last_access_cycle",
        "data_words",
    )

    def __init__(self, words_per_line: int) -> None:
        self.valid: bool = False
        self.dirty: bool = False
        self.tag: int = 0
        self.last_used_cycle: int = -1
        self.speculative_warm: bool = False
        self.last_access_type: str = ""
        self.last_access_cycle: int = -1
        self.data_words: list[int] = [0] * words_per_line

    def to_snapshot(self, set_idx: int, way_idx: int) -> CacheLineSnapshot:
        return CacheLineSnapshot(
            set_index=set_idx,
            way_index=way_idx,
            valid=self.valid,
            dirty=self.dirty,
            tag=self.tag,
            last_used_cycle=self.last_used_cycle,
            speculative_warm=self.speculative_warm,
            last_access_type=self.last_access_type,
            last_access_cycle=self.last_access_cycle,
            data_words=tuple(self.data_words),
        )

    def restore_from(self, snap: CacheLineSnapshot) -> None:
        self.valid = snap.valid
        self.dirty = snap.dirty
        self.tag = snap.tag
        self.last_used_cycle = snap.last_used_cycle
        self.speculative_warm = snap.speculative_warm
        self.last_access_type = snap.last_access_type
        self.last_access_cycle = snap.last_access_cycle
        self.data_words = list(snap.data_words)


class CacheLevel:
    """Direct-Mapped (associativity=1) or N-Way Set-Associative Cache with LRU replacement."""

    def __init__(self, config: CacheConfig) -> None:
        if config.line_size < 4 or (config.line_size & (config.line_size - 1)) != 0:
            raise ValueError("line_size must be a power of 2 >= 4")
        num_lines = config.size_bytes // config.line_size
        if num_lines < config.associativity or num_lines % config.associativity != 0:
            raise ValueError("size_bytes / line_size must be divisible by associativity")

        self.config = config
        self.num_sets = num_lines // config.associativity
        self.associativity = config.associativity
        self.line_size = config.line_size
        self.words_per_line = config.line_size // 4
        self.offset_bits = int(math.log2(config.line_size))
        self.index_bits = int(math.log2(self.num_sets)) if self.num_sets > 1 else 0

        self.sets: list[list[_CacheLine]] = [
            [_CacheLine(self.words_per_line) for _ in range(self.associativity)]
            for _ in range(self.num_sets)
        ]
        self.hits: int = 0
        self.misses: int = 0
        self.conflict_misses: int = 0
        self.evictions: int = 0
        self.seen_tags: set[int] = set()

    def decompose_address(self, address: int) -> tuple[int, int, int]:
        """Return (tag, set_index, byte_offset) for a 32-bit byte address."""
        addr = address & 0xFFFFFFFF
        offset_mask = self.line_size - 1
        offset = addr & offset_mask
        line_addr = addr >> self.offset_bits
        if self.index_bits > 0:
            set_mask = self.num_sets - 1
            set_index = line_addr & set_mask
        else:
            set_index = 0
        tag = line_addr >> self.index_bits
        return tag, set_index, offset

    def line_base_address(self, tag: int, set_index: int) -> int:
        """Reconstruct aligned base address from tag and set_index."""
        line_addr = (tag << self.index_bits) | set_index
        return line_addr << self.offset_bits

    def lookup(self, address: int) -> tuple[Optional[int], int, int, int]:
        """Return (way_idx_or_None, tag, set_index, word_offset)."""
        tag, set_idx, byte_offset = self.decompose_address(address)
        word_offset = byte_offset >> 2
        for way_idx, line in enumerate(self.sets[set_idx]):
            if line.valid and line.tag == tag:
                return way_idx, tag, set_idx, word_offset
        return None, tag, set_idx, word_offset

    def is_line_warm(self, address: int) -> bool:
        """Check whether the cache line containing address is currently valid."""
        way_idx, _, _, _ = self.lookup(address)
        return way_idx is not None

    def select_victim_way(self, set_index: int) -> int:
        """Return an invalid way first, otherwise LRU way index."""
        lines = self.sets[set_index]
        for idx, line in enumerate(lines):
            if not line.valid:
                return idx
        lru_idx = min(range(len(lines)), key=lambda i: lines[i].last_used_cycle)
        return lru_idx

    def flush_line(self, address: int) -> bool:
        """Invalidate the cache line holding address. Returns True if a line was flushed."""
        way_idx, _, set_idx, _ = self.lookup(address)
        if way_idx is None:
            return False
        line = self.sets[set_idx][way_idx]
        line.valid = False
        line.dirty = False
        line.speculative_warm = False
        line.last_access_type = "FLUSH"
        return True

    def flush_all(self) -> None:
        """Invalidate all cache lines."""
        for cache_set in self.sets:
            for line in cache_set:
                line.valid = False
                line.dirty = False
                line.speculative_warm = False
                line.last_access_type = ""

    def export_snapshots(self) -> tuple[CacheLineSnapshot, ...]:
        """Return immutable snapshots of all cache lines ordered by set then way."""
        out: list[CacheLineSnapshot] = []
        for s_idx, cache_set in enumerate(self.sets):
            for w_idx, line in enumerate(cache_set):
                out.append(line.to_snapshot(s_idx, w_idx))
        return tuple(out)

    def export_state(self) -> CacheLevelState:
        return CacheLevelState(
            lines=self.export_snapshots(),
            hits=self.hits,
            misses=self.misses,
            conflict_misses=self.conflict_misses,
            evictions=self.evictions,
            seen_tags=frozenset(self.seen_tags),
        )

    def restore_state(self, state: CacheLevelState) -> None:
        for snap in state.lines:
            self.sets[snap.set_index][snap.way_index].restore_from(snap)
        self.hits = state.hits
        self.misses = state.misses
        self.conflict_misses = state.conflict_misses
        self.evictions = state.evictions
        self.seen_tags = set(state.seen_tags)


class MemorySubsystem:
    """Unified L1 -> optional L2 -> DRAM hierarchy with speculative cache-fill tracking."""

    def __init__(
        self,
        l1_config: Optional[CacheConfig] = None,
        l2_config: Optional[CacheConfig] = None,
        dram_latency: int = 20,
    ) -> None:
        self.l1 = CacheLevel(l1_config or CacheConfig(name="L1", size_bytes=256, line_size=64, associativity=1, hit_latency=1))
        self.l2: Optional[CacheLevel] = CacheLevel(l2_config) if l2_config else None
        self.dram_latency = dram_latency
        self.dram: dict[int, int] = {}
        self.last_access: Optional[MemoryAccessResult] = None

    def load_dram_words(self, words: dict[int, int] | list[tuple[int, int]]) -> None:
        """Populate initial DRAM words (keys normalized to 4-byte aligned addresses)."""
        items = words.items() if isinstance(words, dict) else words
        for addr, val in items:
            self.dram[addr & ~0x3] = val & 0xFFFFFFFF

    def read_dram_word_direct(self, addr: int) -> int:
        """Read directly from backing DRAM without touching caches."""
        return self.dram.get(addr & ~0x3, 0)

    def write_dram_word_direct(self, addr: int, value: int) -> None:
        """Write directly to backing DRAM (used by DMA or initialization)."""
        self.dram[addr & ~0x3] = value & 0xFFFFFFFF

    def _read_line_from_dram(self, line_base: int, words_per_line: int) -> list[int]:
        return [self.dram.get((line_base + i * 4) & 0xFFFFFFFF, 0) for i in range(words_per_line)]

    def _write_line_to_dram(self, line_base: int, words: list[int]) -> None:
        for i, val in enumerate(words):
            self.dram[(line_base + i * 4) & 0xFFFFFFFF] = val & 0xFFFFFFFF

    def _access_l2_read_line(self, line_base: int, cycle: int) -> tuple[bool, int, list[int]]:
        """Read a cache line from L2 (or DRAM on L2 miss). Returns (l2_hit, latency, words)."""
        if self.l2 is None:
            words = self._read_line_from_dram(line_base, self.l1.words_per_line)
            return False, self.dram_latency, words

        way_idx, tag, set_idx, _ = self.l2.lookup(line_base)
        if way_idx is not None:
            line = self.l2.sets[set_idx][way_idx]
            line.last_used_cycle = cycle
            line.last_access_type = "HIT"
            line.last_access_cycle = cycle
            self.l2.hits += 1
            word_count = self.l1.words_per_line
            return True, self.l2.config.hit_latency, list(line.data_words[:word_count])

        # L2 miss -> fetch from DRAM
        self.l2.misses += 1
        victim_way = self.l2.select_victim_way(set_idx)
        victim = self.l2.sets[set_idx][victim_way]
        if victim.valid:
            self.l2.evictions += 1
            if victim.dirty:
                evict_base = self.l2.line_base_address(victim.tag, set_idx)
                self._write_line_to_dram(evict_base, victim.data_words)

        words = self._read_line_from_dram(line_base, self.l2.words_per_line)
        victim.valid = True
        victim.dirty = False
        victim.tag = tag
        victim.data_words = list(words)
        victim.last_used_cycle = cycle
        victim.last_access_type = "MISS"
        victim.last_access_cycle = cycle
        self.l2.seen_tags.add((set_idx << 24) | tag)
        return False, self.l2.config.hit_latency + self.dram_latency, list(words[: self.l1.words_per_line])

    def access(
        self,
        address: int,
        is_write: bool,
        cycle: int,
        write_value: int = 0,
        is_speculative: bool = False,
        allow_speculative_fill: bool = True,
    ) -> MemoryAccessResult:
        """Perform a 32-bit word memory access through L1 -> (L2) -> DRAM."""
        aligned = address & ~0x3 & 0xFFFFFFFF
        way_idx, tag, set_idx, word_off = self.l1.lookup(aligned)
        line_key = (aligned >> self.l1.offset_bits)

        if way_idx is not None:
            line = self.l1.sets[set_idx][way_idx]
            line.last_used_cycle = cycle
            line.last_access_cycle = cycle
            self.l1.hits += 1
            if is_write and not is_speculative:
                line.data_words[word_off] = write_value & 0xFFFFFFFF
                line.dirty = True
                line.last_access_type = "HIT"
            else:
                line.last_access_type = "SPEC_HIT" if is_speculative else "HIT"

            res = MemoryAccessResult(
                address=aligned,
                is_write=is_write,
                l1_hit=True,
                l2_hit=None,
                latency_cycles=self.l1.config.hit_latency,
                value=line.data_words[word_off],
                l1_set=set_idx,
                l1_way=way_idx,
                l1_tag=tag,
                evicted_dirty=False,
                evicted_tag=None,
                speculative_warmed=False,
                conflict_miss=False,
            )
            self.last_access = res
            return res

        # L1 Miss
        self.l1.misses += 1
        line_base = self.l1.line_base_address(tag, set_idx)

        if is_speculative and not allow_speculative_fill:
            # Blocked by serialization barrier; read value without warming L1
            val = self.dram.get(aligned, 0)
            res = MemoryAccessResult(
                address=aligned,
                is_write=is_write,
                l1_hit=False,
                l2_hit=False,
                latency_cycles=self.l1.config.hit_latency + self.dram_latency,
                value=val,
                l1_set=set_idx,
                l1_way=-1,
                l1_tag=tag,
                evicted_dirty=False,
                evicted_tag=None,
                speculative_warmed=False,
                conflict_miss=False,
            )
            self.last_access = res
            return res

        l2_hit, lower_latency, line_words = self._access_l2_read_line(line_base, cycle)
        total_latency = self.l1.config.hit_latency + lower_latency

        # Conflict miss check: line was previously cached (now missing) AND set is full
        all_occupied = all(l.valid for l in self.l1.sets[set_idx])
        is_conflict = all_occupied or (line_key in self.l1.seen_tags)
        if is_conflict:
            self.l1.conflict_misses += 1

        victim_way = self.l1.select_victim_way(set_idx)
        victim = self.l1.sets[set_idx][victim_way]
        evicted_dirty = False
        evicted_tag: Optional[int] = None

        if victim.valid:
            self.l1.evictions += 1
            evicted_tag = victim.tag
            if victim.dirty:
                evicted_dirty = True
                evict_base = self.l1.line_base_address(victim.tag, set_idx)
                self._write_line_to_dram(evict_base, victim.data_words)
                if self.l2 is not None:
                    l2_way, _, l2_set, _ = self.l2.lookup(evict_base)
                    if l2_way is not None:
                        self.l2.sets[l2_set][l2_way].data_words[: self.l1.words_per_line] = list(victim.data_words)
                        self.l2.sets[l2_set][l2_way].dirty = True

        victim.valid = True
        victim.tag = tag
        victim.data_words = list(line_words)
        victim.last_used_cycle = cycle
        victim.last_access_cycle = cycle
        victim.speculative_warm = is_speculative
        victim.last_access_type = "SPEC_FILL" if is_speculative else "MISS"
        self.l1.seen_tags.add(line_key)

        if is_write and not is_speculative:
            victim.data_words[word_off] = write_value & 0xFFFFFFFF
            victim.dirty = True
        else:
            victim.dirty = False

        res = MemoryAccessResult(
            address=aligned,
            is_write=is_write,
            l1_hit=False,
            l2_hit=l2_hit if self.l2 is not None else None,
            latency_cycles=total_latency,
            value=victim.data_words[word_off],
            l1_set=set_idx,
            l1_way=victim_way,
            l1_tag=tag,
            evicted_dirty=evicted_dirty,
            evicted_tag=evicted_tag,
            speculative_warmed=is_speculative,
            conflict_miss=is_conflict,
        )
        self.last_access = res
        return res

    def read_word(self, address: int, cycle: int, is_speculative: bool = False, allow_speculative_fill: bool = True) -> MemoryAccessResult:
        return self.access(
            address=address,
            is_write=False,
            cycle=cycle,
            is_speculative=is_speculative,
            allow_speculative_fill=allow_speculative_fill,
        )

    def read_byte(self, address: int, cycle: int, is_speculative: bool = False, allow_speculative_fill: bool = True) -> MemoryAccessResult:
        res = self.read_word(address, cycle, is_speculative=is_speculative, allow_speculative_fill=allow_speculative_fill)
        shift = (address & 0x3) * 8
        byte_val = (res.value >> shift) & 0xFF
        return MemoryAccessResult(
            address=address & 0xFFFFFFFF,
            is_write=False,
            l1_hit=res.l1_hit,
            l2_hit=res.l2_hit,
            latency_cycles=res.latency_cycles,
            value=byte_val,
            l1_set=res.l1_set,
            l1_way=res.l1_way,
            l1_tag=res.l1_tag,
            evicted_dirty=res.evicted_dirty,
            evicted_tag=res.evicted_tag,
            speculative_warmed=res.speculative_warmed,
            conflict_miss=res.conflict_miss,
        )

    def write_word(self, address: int, value: int, cycle: int, is_speculative: bool = False) -> MemoryAccessResult:
        return self.access(
            address=address,
            is_write=True,
            cycle=cycle,
            write_value=value,
            is_speculative=is_speculative,
        )

    def write_byte(self, address: int, value: int, cycle: int, is_speculative: bool = False) -> MemoryAccessResult:
        res = self.read_word(address, cycle, is_speculative=is_speculative)
        if is_speculative:
            return res
        shift = (address & 0x3) * 8
        mask = ~(0xFF << shift) & 0xFFFFFFFF
        new_word = (res.value & mask) | ((value & 0xFF) << shift)
        return self.write_word(address, new_word, cycle, is_speculative=False)

    def probe_reload_time(self, address: int, cycle: int) -> tuple[int, bool]:
        """Flush+Reload timing probe: returns (latency_cycles, was_l1_hit) without modifying spec state."""
        res = self.read_word(address, cycle, is_speculative=False)
        return res.latency_cycles, res.l1_hit

    def flush_line(self, address: int) -> bool:
        """Flush address from L1 (and L2 if present)."""
        f1 = self.l1.flush_line(address)
        f2 = self.l2.flush_line(address) if self.l2 is not None else False
        return f1 or f2

    def snapshot(self) -> MemorySnapshot:
        """Return an immutable snapshot of all caches and DRAM."""
        return MemorySnapshot(
            l1_state=self.l1.export_state(),
            l2_state=self.l2.export_state() if self.l2 is not None else None,
            dram_words=tuple(sorted(self.dram.items())),
            last_access=self.last_access,
        )

    def restore(self, snap: MemorySnapshot) -> None:
        """Restore exact cache and DRAM state from an immutable MemorySnapshot."""
        self.l1.restore_state(snap.l1_state)
        if self.l2 is not None and snap.l2_state is not None:
            self.l2.restore_state(snap.l2_state)
        self.dram = dict(snap.dram_words)
        self.last_access = snap.last_access

