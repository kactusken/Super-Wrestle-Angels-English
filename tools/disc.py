#!/usr/bin/env python3
"""The cartridge as a one-file "disc", so build.py, extract.py and check.py work unchanged.

  disc.py ls ROM          the one file
  disc.py check ROM       header and checksum

A SNES ROM has no file system: the whole (headerless) ROM is one file, ROM_FILE. Text steps get it
from build.py's Files, change it (snes.Rom maps CPU addresses to offsets) and put it back;
write_file() then fixes the internal checksum and keeps a copier header if the original had one.
The ROM may grow (snes.Rom.expand) up to what the map mode allows; build.py's "fits" test always
passes. Same interface as the PS1/PS2 disc.py: SECTOR, Disc(files/find/read_file/write_file/
allocated_sectors/is_empty/extract_file/close), companion_files, plus layout() for new_project.py.
"""
import sys

import snes

SECTOR = 1
ROM_FILE = '/rom.sfc'


class Entry:
    def __init__(self, path, size):
        self.path, self.size, self.lba, self.is_dir = path, size, 0, False


class Disc:
    def __init__(self, path, writable=False):
        self.own = not hasattr(path, 'read')
        self.f = open(path, 'r+b' if writable else 'rb') if self.own else path
        self.f.seek(0, 2)
        total = self.f.tell()
        self.copier = snes.COPIER if total % 0x8000 == snes.COPIER else 0
        self.f.seek(0)
        self.rom = snes.Rom(self._read())
        self.entry = Entry(ROM_FILE, total - self.copier)

    def _read(self):
        self.f.seek(self.copier)
        return self.f.read()

    def close(self):
        if self.own:
            self.f.close()

    def files(self):
        return [self.entry]

    def find(self, path):
        if '/' + path.lstrip('/') != ROM_FILE:
            raise FileNotFoundError(f'{path}: a SNES ROM has one file, {ROM_FILE}')
        return self.entry

    def allocated_sectors(self, e):
        return snes.MAX_SIZE[self.rom.mode]

    def read_file(self, e):
        return self._read()

    def is_empty(self, e):
        return False

    def extract_file(self, e, out):
        with open(out, 'wb') as o:
            o.write(self._read())

    def write_file(self, e, data, relocate=False, **_):
        """Write the whole ROM back with a corrected checksum. Only the bytes that differ from the
        current contents are written, so the build journal (tools/image.py) stays small."""
        if len(data) % 0x8000:
            raise SystemExit(f'{ROM_FILE}: {len(data):#x} bytes is not a multiple of 32 KB (use snes.Rom.expand)')
        if len(data) > snes.MAX_SIZE[self.rom.mode]:
            raise SystemExit(f'{ROM_FILE}: {len(data):#x} bytes is more than a {snes.MODE_NAMES[self.rom.mode]} cart maps')
        r = snes.Rom(data)
        r.header, r.mode = snes.Header(r.data, self.rom.header.at), self.rom.mode
        r.fix_checksum()
        old = self._read()
        new = bytes(r.data)
        if len(new) < len(old):
            raise SystemExit(f'{ROM_FILE}: a ROM can grow but not shrink ({len(old):#x} -> {len(new):#x})')
        i, n = 0, len(new)
        while i < n:
            if i < len(old) and new[i] == old[i]:
                i += 1
                continue
            j = i
            while j < n and (j >= len(old) or new[j] != old[j]):
                j += 1
            self.f.seek(self.copier + i)
            self.f.write(new[i:j])
            i = j
        self.rom, self.entry.size = r, n


def layout(path):
    """Markdown for docs/TECHNICAL.md: the header and memory map (new_project.py)."""
    d = Disc(path)
    r, h = d.rom, d.rom.header
    bank = 0x8000 if r.mode == snes.LOROM else 0x10000
    rows = ['| | |', '|---|---|',
            f'| Title | `{h.title}` |',
            f'| Map | {snes.MODE_NAMES[r.mode]}{" FastROM" if h.fast else ""} (`${h.map:02x}`), header at `{h.at:#x}` |',
            f'| Size | {len(r.data):#x} bytes ({len(r.data) * 8 // 0x100000} Mbit), {len(r.data) // bank} banks of {bank // 1024} KB'
            + (', +512-byte copier header' if d.copier else '') + ' |',
            f'| ROM | {snes.fmt(r.to_cpu(0))} - {snes.fmt(r.to_cpu(len(r.data) - 1))} |',
            f'| Cart | type `${h.cart_type:02x}`, SRAM {h.sram_kb} KB |',
            f'| Reset | {snes.fmt(h.reset)} |',
            f'| Checksum | `{h.checksum:#06x}` (fixed by tools/disc.py on every build) |']
    free = r.free_runs(0x400)
    if free:
        rows += ['', 'Runs of `$00`/`$FF` of 1 KB or more (free space candidates - verify nothing reads them):', '',
                 '| Offset | CPU | Bytes | Fill |', '|---|---|---|---|']
        rows += [f'| `{o:#08x}` | {snes.fmt(r.to_cpu(o))} | {n:#x} | `${r.data[o]:02x}` |' for o, n in free]
    d.close()
    return '\n'.join(rows)


def companion_files(image):
    """Nothing to write next to a cartridge image (CD images get a .cue)."""


def main(argv):
    if len(argv) == 2 and argv[0] in ('ls', 'check'):
        d = Disc(argv[1])
        if argv[0] == 'ls':
            print(f'{d.entry.path} {d.entry.size} bytes' + (' (+512-byte copier header)' if d.copier else ''))
        else:
            h, c = d.rom.header, d.rom.checksum()
            print(f'{h.title!r} {snes.MODE_NAMES[d.rom.mode]}: checksum {h.checksum:#06x}, computed {c:#06x} - '
                  f'{"ok" if c == h.checksum and h.checksum ^ h.complement == 0xffff else "BAD"}')
        d.close()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
