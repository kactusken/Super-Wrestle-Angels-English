#!/usr/bin/env python3
"""SNES tile graphics: planar 1/2/4/8bpp and Mode 7 tiles, BGR555 palettes, PNG sheets.

  snesgfx.py view ROM OFFSET [COUNT] [--bpp 2] [--cols 16] [--pal OFFSET] [--scale 2] [--out PNG]
      draw COUNT 8x8 tiles from file OFFSET (hex ok: 0x...) as a sheet - for finding fonts and
      menu graphics. Without --pal the colours are a grey ramp.
  snesgfx.py scan ROM [--bpp 1,2,4] [--bank-size 0x8000] [--out DIR]
      one sheet per bank and depth, to skim the whole ROM for uncompressed graphics.

Formats (per 8x8 tile):
  1bpp  8 bytes, one row per byte
  2bpp  16 bytes: rows as (plane 0, plane 1) pairs
  4bpp  32 bytes: planes 0/1 for 8 rows, then planes 2/3
  8bpp  64 bytes: plane pairs 0/1, 2/3, 4/5, 6/7, 16 bytes each
  m7    64 bytes, one byte per pixel (Mode 7)
Leftmost pixel = bit 7. Palettes: 16-bit little-endian 0bbbbbgg gggrrrrr. Colour 0 of every
background palette is transparent. Graphics stored compressed won't show here: find the
decompressor in the code first (docs/PLATFORM.md).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngio  # noqa: E402
import snes  # noqa: E402

TILE_BYTES = {1: 8, 2: 16, 3: 24, 4: 32, 8: 64, 'm7': 64}


def decode_tile(data, bpp):
    """8 rows of 8 colour indices."""
    if bpp == 'm7':
        return [list(data[y * 8:y * 8 + 8]) for y in range(8)]
    rows = []
    for y in range(8):
        row = []
        for x in range(8):
            bit, v = 7 - x, 0
            if bpp == 1:
                v = data[y] >> bit & 1
            elif bpp == 3:    # 2bpp planes then a third plane (some games' own format)
                v = (data[2 * y] >> bit & 1) | (data[2 * y + 1] >> bit & 1) << 1 | (data[16 + y] >> bit & 1) << 2
            else:
                for p in range(bpp):
                    v |= (data[(p // 2) * 16 + 2 * y + (p & 1)] >> bit & 1) << p
            row.append(v)
        rows.append(row)
    return rows


def encode_tile(rows, bpp):
    if bpp == 'm7':
        return bytes(v for row in rows for v in row)
    out = bytearray(TILE_BYTES[bpp])
    for y in range(8):
        for x in range(8):
            v, bit = rows[y][x], 7 - x
            if bpp == 1:
                out[y] |= (v & 1) << bit
            elif bpp == 3:
                out[2 * y] |= (v & 1) << bit
                out[2 * y + 1] |= (v >> 1 & 1) << bit
                out[16 + y] |= (v >> 2 & 1) << bit
            else:
                for p in range(bpp):
                    out[(p // 2) * 16 + 2 * y + (p & 1)] |= (v >> p & 1) << bit
    return bytes(out)


def decode_palette(data, count=None):
    """[(r, g, b)] from BGR555 words."""
    n = len(data) // 2 if count is None else count
    out = []
    for i in range(n):
        w = data[2 * i] | data[2 * i + 1] << 8
        out.append(tuple((w >> s & 31) * 255 // 31 for s in (0, 5, 10)))
    return out


def encode_palette(colours):
    out = bytearray()
    for r, g, b in colours:
        w = (r * 31 + 127) // 255 | ((g * 31 + 127) // 255) << 5 | ((b * 31 + 127) // 255) << 10
        out += w.to_bytes(2, 'little')
    return bytes(out)


def grey(bpp):
    n = 256 if bpp in (8, 'm7') else 1 << bpp
    return [(i * 255 // (n - 1),) * 3 for i in range(n)]


def sheet(data, bpp, cols=16):
    """Indexed rows for every whole tile in `data`, `cols` tiles across."""
    size = TILE_BYTES[bpp]
    count = len(data) // size
    lines = (count + cols - 1) // cols
    rows = [[0] * (cols * 8) for _ in range(lines * 8)]
    for t in range(count):
        tile = decode_tile(data[t * size:(t + 1) * size], bpp)
        ox, oy = (t % cols) * 8, (t // cols) * 8
        for y in range(8):
            rows[oy + y][ox:ox + 8] = tile[y]
    return rows


def unsheet(rows, bpp, cols=16):
    """The inverse of sheet(): tile bytes, left to right, top to bottom."""
    out = bytearray()
    for ty in range(len(rows) // 8):
        for tx in range(cols):
            out += encode_tile([rows[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)], bpp)
    return bytes(out)


def scaled(rows, k):
    return [[v for v in row for _ in range(k)] for row in rows for _ in range(k)]


def write_png(path, rows, palette, scale=1):
    pngio.write(path, scaled(rows, scale) if scale > 1 else rows, palette)


def parse_bpp(s):
    return 'm7' if s == 'm7' else int(s)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('view')
    v.add_argument('rom')
    v.add_argument('offset', type=lambda s: int(s, 0))
    v.add_argument('count', type=lambda s: int(s, 0), nargs='?', default=256)
    v.add_argument('--bpp', type=parse_bpp, default=2)
    v.add_argument('--cols', type=int, default=16)
    v.add_argument('--pal', type=lambda s: int(s, 0), help='file offset of a BGR555 palette')
    v.add_argument('--scale', type=int, default=2)
    v.add_argument('--out', type=Path)
    s = sub.add_parser('scan')
    s.add_argument('rom')
    s.add_argument('--bpp', default='1,2,4')
    s.add_argument('--bank-size', type=lambda s: int(s, 0), default=0x8000)
    s.add_argument('--cols', type=int, default=32)
    s.add_argument('--out', type=Path, default=Path('review/gfx-scan'))
    args = ap.parse_args(argv)
    data = snes.read_rom(args.rom)[0]
    if args.cmd == 'view':
        chunk = data[args.offset:args.offset + args.count * TILE_BYTES[args.bpp]]
        pal = grey(args.bpp)
        if args.pal is not None:
            n = 256 if args.bpp in (8, 'm7') else 1 << args.bpp
            pal = decode_palette(data[args.pal:args.pal + 2 * n])
        out = args.out or Path(f'gfx_{args.offset:06x}_{args.bpp}bpp.png')
        write_png(out, sheet(chunk, args.bpp, args.cols), pal, args.scale)
        print(f'{out}: {len(chunk) // TILE_BYTES[args.bpp]} tiles')
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        for bpp in map(parse_bpp, args.bpp.split(',')):
            for start in range(0, len(data), args.bank_size):
                out = args.out / f'{start:06x}_{bpp}bpp.png'
                write_png(out, sheet(data[start:start + args.bank_size], bpp, args.cols), grey(bpp))
        print(f'{args.out}: {len(data) // args.bank_size} banks x {args.bpp}')


if __name__ == '__main__':
    main()
