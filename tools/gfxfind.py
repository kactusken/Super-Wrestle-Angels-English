#!/usr/bin/env python3
"""Find where graphics seen in VRAM come from: every ROM offset where the game's decompressor
(tools/pack8.py) would produce the given bytes. The two bytes before them in VRAM give the
decompressor's starting state, so a match can start in the middle of a block (on a group).

  gfxfind.py VRAM.bin OFFSET [LENGTH]    LENGTH bytes (default 32) at byte OFFSET of a VRAM dump

Prints file offsets and CPU addresses. Uncompressed copies are listed too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import snes  # noqa: E402


def find(data, want, prev=(0, 0)):
    """Offsets where unpacking yields `want` (a multiple of 8 bytes) from state `prev`."""
    out = []
    n = len(want)
    for i in range(len(data) - n):
        regs = [prev[0], prev[1]]
        j, k, ok = i, 0, True
        while k < n:
            ctrl = data[j]
            j += 1
            for b in range(8):
                r = k & 1
                if ctrl & (0x80 >> b):
                    regs[r] = data[j]
                    j += 1
                if regs[r] != want[k]:
                    ok = False
                    break
                k += 1
            if not ok:
                break
        if ok:
            out.append(i)
    return out


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if len(argv) not in (2, 3):
        sys.exit(__doc__)
    vram = Path(argv[0]).read_bytes()
    off = int(argv[1], 0)
    n = int(argv[2], 0) if len(argv) > 2 else 32
    want = vram[off:off + n]
    prev = (vram[off - 2], vram[off - 1]) if off >= 2 else (0, 0)
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    r = snes.Rom(data)
    for i in find(data, want, prev):
        print(f'packed  {i:#08x}  ${r.to_cpu(i):06X}')
    i = data.find(want)
    while i >= 0:
        print(f'plain   {i:#08x}  ${r.to_cpu(i):06X}')
        i = data.find(want, i + 1)


if __name__ == '__main__':
    sys.exit(main())
