#!/usr/bin/env python3
"""The game's graphics compression (decompressor at $80:BDD7), both directions.

  pack8.py unpack ADDR GROUPS OUT.bin     decompress GROUPS*8 bytes from CPU address ADDR
  pack8.py pack IN.bin OUT.bin            compress (length must be a multiple of 8)

Format: groups of 8 output bytes. Each group starts with a control byte, read MSB first: a 1 bit
takes a new byte from the stream, a 0 bit repeats the byte two positions back (the routine keeps
two values in A and B and swaps them after every byte - the two bitplanes of a tile row). Both
start as the 16-bit A the caller passes (0 in every call seen). The caller gives the source in
DB:X, the number of groups in Y, and the destination through the WRAM port ($2181-$2183).
Blocks follow each other and some callers continue from where the last one ended (X), so a changed
block must keep its packed length: pack_exact().
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import snes  # noqa: E402


def unpack(data, off, groups, init=0):
    """(output bytes, bytes read)."""
    regs = [init & 0xff, init >> 8]
    out = bytearray()
    i = off
    for _ in range(groups):
        ctrl = data[i]
        i += 1
        for k in range(8):
            r = k & 1
            if ctrl & (0x80 >> k):
                regs[r] = data[i]
                i += 1
            out.append(regs[r])
    return bytes(out), i - off


def pack(raw, init=0):
    if len(raw) % 8:
        raise ValueError('length must be a multiple of 8')
    regs = [init & 0xff, init >> 8]
    out = bytearray()
    for g in range(0, len(raw), 8):
        ctrl, lits = 0, bytearray()
        for k in range(8):
            r, b = k & 1, raw[g + k]
            if b != regs[r]:
                ctrl |= 0x80 >> k
                lits.append(b)
                regs[r] = b
        out.append(ctrl)
        out += lits
    return bytes(out)


def pack_exact(raw, size, init=0):
    """pack() grown to exactly `size` bytes by turning repeats into literals of the same byte (the
    output is unchanged). Blocks are read back to back - the next block starts where this one ends,
    so a relettered block must keep its length. None if even the smallest packing is too big."""
    small = pack(raw, init)
    if len(small) > size:
        return None
    need = size - len(small)
    if need > len(raw) - (len(small) - len(raw) // 8):
        raise ValueError('cannot pad to that size')
    regs = [init & 0xff, init >> 8]
    out = bytearray()
    for g in range(0, len(raw), 8):
        ctrl, lits = 0, bytearray()
        for k in range(8):
            r, b = k & 1, raw[g + k]
            if b != regs[r] or need:
                if b == regs[r]:
                    need -= 1
                ctrl |= 0x80 >> k
                lits.append(b)
                regs[r] = b
        out.append(ctrl)
        out += lits
    return bytes(out)


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if len(argv) == 4 and argv[0] == 'unpack':
        rom = snes.Rom.open(paths.ROM)
        raw, used = unpack(rom.data, rom.to_file(snes.parse_addr(argv[1])), int(argv[2], 0))
        Path(argv[3]).write_bytes(raw)
        print(f'{argv[3]}: {len(raw)} bytes from {used} compressed')
    elif len(argv) == 3 and argv[0] == 'pack':
        Path(argv[2]).write_bytes(pack(Path(argv[1]).read_bytes()))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
