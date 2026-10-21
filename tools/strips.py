#!/usr/bin/env python3
"""Reletter pre-rendered text strips: 2bpp tiles drawn in the 12x12 font's style plus small
tilemaps that place them (both compressed, tools/pack8.py).

  strips.py preview OUT.png       original | English strips (Pillow)

A strip is two tile rows of a tilemap block. English is drawn with tools/halffont.py letters
(colour 1) across both rows; tiles that would need two different contents, or that end up blank,
are sorted out by the builder: blank ones point at the blank tile, and the freed tiles take the
second copy of a shared one. Every block is repacked to its old length (pack8.pack_exact).

STRIPS: one entry per screen - the tile block, its first tile number, and its tilemap blocks with
(row width in entries, [(first column, columns, English)]).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import halffont  # noqa: E402
import pack8  # noqa: E402
import snes  # noqa: E402
import snesgfx  # noqa: E402

STRIPS = [
    {   # exhibition and tournament: header button and the match type tabs (Mesen, 2026-10-20)
        'tiles': (0x8FD6D9, 0xF6), 'first': 0, 'blank': 0,   # map entries count from the block's first tile
        'maps': [
            (0x83EE9C, 0x06, 12, [(0, 12, 'Back to Menu')]),
            (0x83EEF7, 0x0F, 30, [(0, 7, 'Single'), (7, 6, 'Tag'), (14, 7, 'Trios'), (21, 8, 'Load Data')]),
            # the tournament's tabs use the same tiles (and 決定 = OK)
            (0x83E1FB, 0x0F, 30, [(0, 7, 'Single'), (7, 6, 'Tag'), (14, 8, 'Load Data'), (24, 5, 'OK')]),
            # league setup: 参加チーム数 (number of teams) before the count
            (0x83E3C8, 0x05, 9, [(0, 9, 'No. of Teams')]),
        ],
    },
]


def render(text, cols):
    """16 rows of cols*8 pixels: the text centred, letters at rows 3-12. Text that would come
    within 3 pixels of the edges steps 4 pixels (not 6) after spaces and full stops."""
    w = 8 * cols
    pix = [[0] * w for _ in range(16)]
    narrow = 6 * len(text) - 1 > w - 6
    steps = [4 if narrow and ch in ' .' else 6 for ch in text]
    x = max(0, (w - (sum(steps) - 1)) // 2)
    for ch, step in zip(text, steps):
        g = halffont.FONT[ch]
        for gy in range(10):
            for gx in range(5):
                if g[gy][gx] and x + gx < w:
                    pix[2 + gy][x + gx] = 1
        x += step
    return pix


def apply(rom_data, strip):
    """{file offset: packed bytes} for the strip's tile block and tilemaps."""
    r = snes.Rom(rom_data)
    taddr, tgroups = strip['tiles']
    raw, tused = pack8.unpack(r.data, r.to_file(taddr), tgroups)
    tiles = [snesgfx.decode_tile(raw[16 * k:16 * k + 16], 2) for k in range(len(raw) // 16)]
    first, blank = strip['first'], strip['blank']
    maps = []
    for addr, groups, width, labels in strip['maps']:
        mraw, mused = pack8.unpack(r.data, r.to_file(addr), groups)
        entries = [mraw[i] | mraw[i + 1] << 8 for i in range(0, len(mraw), 2)]
        maps.append((addr, mused, width, labels, entries, len(mraw)))
    want = {}      # (map index, entry index) -> 8x8 pixels
    for m, (addr, used, width, labels, entries, size) in enumerate(maps):
        for col, ncols, text in labels:
            pix = render(text, ncols)
            for row in (0, 1):
                for c in range(ncols):
                    want[m, row * width + col + c] = [line[8 * c:8 * c + 8] for line in pix[8 * row:8 * row + 8]]
    # each position: blank -> the blank tile; otherwise the original tile for its first use, a
    # spare (a tile all of whose uses became blank) for further different contents
    def empty(px):
        return not any(any(row) for row in px)
    by_tile = {}
    for key in sorted(want):
        by_tile.setdefault(maps[key[0]][4][key[1]] & 0x3ff, []).append(key)
    spare = [t for t, keys in by_tile.items() if t != blank and all(empty(want[k]) for k in keys)]
    assign, need = {}, []
    for t, keys in by_tile.items():
        contents = {}
        for k in keys:
            if empty(want[k]):
                assign[k] = blank
                continue
            sig = tuple(map(tuple, want[k]))
            if sig in contents:
                assign[k] = contents[sig]
            elif t != blank and t not in contents.values() and t not in spare:
                contents[sig] = assign[k] = t
                tiles[t - first] = want[k]
            else:
                need.append((k, sig))
    placed = {}
    for k, sig in need:
        if sig not in placed:
            if not spare:
                raise SystemExit('strips: not enough spare tiles')
            placed[sig] = spare.pop(0)
            tiles[placed[sig] - first] = want[k]
        assign[k] = placed[sig]
    out = {}
    for m, (addr, used, width, labels, entries, size) in enumerate(maps):
        for (mm, i), t in assign.items():
            if mm == m:
                entries[i] = (entries[i] & ~0x3ff) | t
        new = b''.join(e.to_bytes(2, 'little') for e in entries)
        packed = pack8.pack_exact(new, used)
        if packed is None:
            raise SystemExit(f'strips: map ${addr:06X} packs to more than {used} bytes')
        out[r.to_file(addr)] = packed
    newraw = b''.join(snesgfx.encode_tile(t, 2) for t in tiles)
    packed = pack8.pack_exact(newraw, tused)
    if packed is None:
        raise SystemExit(f'strips: tiles ${taddr:06X} pack to {len(pack8.pack(newraw))} bytes, {tused} available')
    out[r.to_file(taddr)] = packed
    return out


def build(rom, original, quiet=False):
    for strip in STRIPS:
        for off, data in apply(original, strip).items():
            rom[off:off + len(data)] = data
        if not quiet:
            print(f'strips: ${strip["tiles"][0]:06X} ({sum(len(m[3]) for m in strip["maps"])} labels)')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == 'preview':
        import paths
        from PIL import Image
        original = (paths.EXTRACTED / 'rom.sfc').read_bytes()
        out = Image.new('RGB', (2 * 256 + 16, 40 * len(STRIPS) * 2), (60, 60, 90))
        y = 0
        for strip in STRIPS:
            new = bytearray(original)
            for off, data in apply(original, strip).items():
                new[off:off + len(data)] = data
            for k, data in enumerate((original, bytes(new))):
                r = snes.Rom(data)
                raw, _ = pack8.unpack(r.data, r.to_file(strip['tiles'][0]), strip['tiles'][1])
                tl = [snesgfx.decode_tile(raw[16 * i:16 * i + 16], 2) for i in range(len(raw) // 16)]
                yy = y
                for addr, groups, width, labels in strip['maps']:
                    mraw, _ = pack8.unpack(r.data, r.to_file(addr), groups)
                    ent = [mraw[i] | mraw[i + 1] << 8 for i in range(0, len(mraw), 2)]
                    for i, e in enumerate(ent):
                        t = tl[(e & 0x3ff) - strip['first']] if 0 <= (e & 0x3ff) - strip['first'] < len(tl) else None
                        if t is None:
                            continue
                        cx, cy = (i % width) * 8, (i // width) * 8
                        for py in range(8):
                            for px in range(8):
                                if t[py][px]:
                                    out.putpixel((k * 272 + cx + px, yy + cy + py),
                                                 (255, 255, 255) if t[py][px] == 1 else (150, 150, 200))
                    yy += 8 * (len(ent) // width) + 4
            y = yy + 8
        out.resize((out.width * 2, out.height * 2), Image.NEAREST).save(argv[1])
        print(argv[1])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
