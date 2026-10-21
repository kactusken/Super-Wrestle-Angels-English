#!/usr/bin/env python3
"""The SNES cartridge: internal header, memory map (CPU address <-> file offset), checksum, expansion.

  snes.py info ROM                      header, map mode, sizes, checksum (stored and computed)
  snes.py addr ROM ADDR...              CPU address -> file offset ($C08000, C0:8000, 0xc08000)
  snes.py offset ROM OFFSET...          file offset -> CPU address

All offsets are into the headerless ROM: a 512-byte copier header (.smc) is dropped by read_rom()
and kept by tools/disc.py when it writes the ROM back.

Map modes (header byte $FFD5 & 0x0f): 0 LoROM, 1 HiROM, 5 ExHiROM. Bit 4 set = FastROM; CPU
addresses are then shown in the $80-$FF banks (the fast mirror), as the game's own code uses them.
"""
import struct
import sys
from pathlib import Path

COPIER = 0x200
LOROM, HIROM, EXHIROM = 0, 1, 5
HEADER_AT = {LOROM: 0x7fc0, HIROM: 0xffc0, EXHIROM: 0x40ffc0}
MODE_NAMES = {LOROM: 'LoROM', HIROM: 'HiROM', EXHIROM: 'ExHiROM'}
MAX_SIZE = {LOROM: 0x400000, HIROM: 0x400000, EXHIROM: 0x800000}


def read_rom(path):
    """(headerless ROM bytes, copier header bytes or b'')."""
    data = Path(path).read_bytes()
    if len(data) % 0x8000 == COPIER:
        return data[COPIER:], data[:COPIER]
    return data, b''


def mirror_sum(data, size):
    """Sum of `data` mirrored up to `size` bytes, the way the cartridge bus repeats a ROM whose size
    isn't a power of two (12 Mbit = 8 Mbit + the last 4 Mbit twice)."""
    n = len(data)
    if n == 0:
        return 0
    if n & (n - 1) == 0:
        return sum(data) * (size // n)
    p = 1 << (n.bit_length() - 1)
    return sum(data[:p]) + mirror_sum(data[p:], size - p)


def checksum(data):
    n = len(data)
    size = n if n & (n - 1) == 0 else 1 << n.bit_length()
    return mirror_sum(data, size) & 0xffff


class Header:
    def __init__(self, data, at):
        h = data[at:at + 0x40]
        self.at = at
        self.title = h[0:21].decode('ascii', 'replace').rstrip()
        self.map = h[0x15]
        self.mode = self.map & 0x0f
        self.fast = bool(self.map & 0x10)
        self.cart_type = h[0x16]
        self.rom_kb = 1 << h[0x17] if h[0x17] < 16 else 0
        self.sram_kb = 1 << h[0x18] if 0 < h[0x18] < 16 else 0
        self.region, self.licensee, self.version = h[0x19], h[0x1a], h[0x1b]
        self.complement, self.checksum = struct.unpack('<HH', h[0x1c:0x20])
        self.reset = struct.unpack('<H', h[0x3c:0x3e])[0]

    def score(self, data):
        s = 0
        expect = {0x7fc0: LOROM, 0xffc0: HIROM, 0x40ffc0: EXHIROM}[self.at]
        s += 4 if self.mode in (expect, expect | 2) else 0       # | 2: SA-1 / ExLoROM variants
        s += 4 if self.complement ^ self.checksum == 0xffff else 0
        s += 2 if self.reset >= 0x8000 else 0
        s += 1 if all(0x20 <= c < 0x7f for c in data[self.at:self.at + 21]) else 0
        return s


class Rom:
    """A headerless ROM image with its header and memory map."""

    def __init__(self, data):
        self.data = bytearray(data)
        best = None
        for at in HEADER_AT.values():
            if at + 0x40 <= len(self.data):
                h = Header(self.data, at)
                if best is None or h.score(self.data) > best.score(self.data):
                    best = h
        if best is None:
            raise ValueError('too small for a SNES ROM')
        self.header = best
        self.mode = {0x7fc0: LOROM, 0xffc0: HIROM, 0x40ffc0: EXHIROM}[best.at]

    @classmethod
    def open(cls, path):
        return cls(read_rom(path)[0])

    # --- memory map
    def to_file(self, addr):
        """File offset of CPU address `addr` (24-bit: bank << 16 | address)."""
        bank, a = addr >> 16 & 0xff, addr & 0xffff
        if self.mode == LOROM:
            if bank in (0x7e, 0x7f) or (a < 0x8000 and (bank & 0x7f) < 0x40):
                raise ValueError(f'${addr:06x} is not ROM in LoROM (RAM or I/O)')
            if a < 0x8000:
                raise ValueError(f'${addr:06x}: low half of a LoROM bank (SRAM or a mirror) - use $8000-$FFFF')
            off = (bank & 0x7f) << 15 | (a & 0x7fff)
        elif self.mode == HIROM:
            if bank in (0x7e, 0x7f) or (a < 0x8000 and (bank & 0x7f) < 0x40):
                raise ValueError(f'${addr:06x} is not ROM in HiROM')
            off = (bank & 0x3f) << 16 | a
        else:
            if bank in (0x7e, 0x7f) or (a < 0x8000 and (bank & 0x7f) < 0x40):
                raise ValueError(f'${addr:06x} is not ROM in ExHiROM')
            off = (bank & 0x3f) << 16 | a | (0 if bank & 0x80 else 0x400000)
        if off >= len(self.data):
            raise ValueError(f'${addr:06x} -> offset {off:#x} is past the end of the ROM ({len(self.data):#x})')
        return off

    def to_cpu(self, off):
        """CPU address of file offset `off` (FastROM mirror for FastROM games)."""
        if self.mode == LOROM:
            return ((off >> 15) | (0x80 if self.header.fast else 0)) << 16 | 0x8000 | (off & 0x7fff)
        if self.mode == HIROM:
            return (0xc0 | off >> 16) << 16 | (off & 0xffff)
        return ((0xc0 if off < 0x400000 else 0x40) | (off >> 16 & 0x3f)) << 16 | (off & 0xffff)

    def bank_bounds(self, off):
        """(start, end) file offsets of the ROM bank holding `off`: code with 16-bit pointers can't cross them."""
        size = 0x8000 if self.mode == LOROM else 0x10000
        start = off - off % size
        return start, min(start + size, len(self.data))

    def read_cpu(self, addr, n):
        off = self.to_file(addr)
        return bytes(self.data[off:off + n])

    # --- checksum and size
    def checksum(self):
        return checksum(self.data)

    def fix_checksum(self):
        """Write the checksum and its complement into the header. Any complementary pair adds
        0x1fe to the sum, so the sum is taken with the pair reset first."""
        at = self.header.at
        self.data[at + 0x1c:at + 0x20] = struct.pack('<HH', 0xffff, 0x0000)
        c = checksum(self.data)
        self.data[at + 0x1c:at + 0x20] = struct.pack('<HH', c ^ 0xffff, c)
        self.header = Header(self.data, at)
        return c

    def expand(self, size, fill=0xff):
        """Grow the ROM to `size` bytes (a multiple of 32 KB) and update the header's size byte.
        LoROM games: banks above the original size become free space at $xx:8000-$FFFF; check that
        the game doesn't rely on the mirror the original size produced (some read past the end)."""
        if size % 0x8000 or size <= len(self.data):
            raise ValueError(f'expand to {size:#x}: must be a multiple of 0x8000 and larger than {len(self.data):#x}')
        if size > MAX_SIZE[self.mode]:
            raise ValueError(f'{MODE_NAMES[self.mode]} carts map at most {MAX_SIZE[self.mode]:#x} bytes')
        self.data += bytes([fill]) * (size - len(self.data))
        kb, b = size // 1024, 0
        while (1 << b) < kb:
            b += 1
        self.data[self.header.at + 0x17] = b
        self.header = Header(self.data, self.header.at)

    def free_runs(self, minimum=256, fill=(0x00, 0xff)):
        """[(offset, length)] of runs of a fill byte at least `minimum` long - candidate free space
        (verify in an emulator that nothing reads it: some games keep zero-filled tables)."""
        out, i, n = [], 0, len(self.data)
        while i < n:
            b = self.data[i]
            if b in fill:
                j = i
                while j < n and self.data[j] == b:
                    j += 1
                if j - i >= minimum:
                    out.append((i, j - i))
                i = j
            else:
                i += 1
        return out


def parse_addr(s):
    s = s.strip().lower().replace(':', '').replace('$', '')
    return int(s, 16) if not s.startswith('0x') else int(s, 0)


def fmt(addr):
    return f'${addr >> 16:02X}:{addr & 0xffff:04X}'


def main(argv):
    if len(argv) >= 2 and argv[0] == 'info':
        data, copier = read_rom(argv[1])
        r = Rom(data)
        h = r.header
        print(f'title      {h.title!r}')
        print(f'map        {MODE_NAMES[r.mode]}{" FastROM" if h.fast else ""} (${h.map:02x}), header at {h.at:#x}'
              f'{", 512-byte copier header" if copier else ""}')
        print(f'size       {len(data):#x} bytes ({len(data) * 8 // 0x100000} Mbit); header says {h.rom_kb} KB')
        print(f'cart type  ${h.cart_type:02x}, SRAM {h.sram_kb} KB, region {h.region}, version 1.{h.version}')
        print(f'reset      {fmt(h.reset)} (emulation mode, bank $00)')
        print(f'checksum   stored {h.checksum:#06x} (complement {h.complement:#06x}), computed {r.checksum():#06x}'
              f' - {"ok" if h.checksum == r.checksum() else "MISMATCH"}')
        free = r.free_runs(0x1000)
        if free:
            print(f'free runs  {len(free)} of 4 KB or more, {sum(n for _, n in free):#x} bytes in all; largest:')
            for off, n in sorted(free, key=lambda x: -x[1])[:8]:
                print(f'           {off:#08x} {fmt(r.to_cpu(off))} {n:#x} bytes of {r.data[off]:#04x}')
    elif len(argv) >= 3 and argv[0] in ('addr', 'offset'):
        r = Rom.open(argv[1])
        for s in argv[2:]:
            if argv[0] == 'addr':
                print(f'{fmt(parse_addr(s))} -> {r.to_file(parse_addr(s)):#08x}')
            else:
                print(f'{int(s, 0):#08x} -> {fmt(r.to_cpu(int(s, 0)))}')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
