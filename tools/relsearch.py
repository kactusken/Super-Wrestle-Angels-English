#!/usr/bin/env python3
"""Relative search: find text whose encoding is unknown, from a word you can see on screen.

  relsearch.py ROM WORD [--order gojuon|unicode] [--width 1|2] [--context 24]

Most SNES games use their own character codes, but keep the kana in a standard order, so the
*differences* between a word's codes are the same as between its letters' positions in that order.
This finds every place in the ROM where they are, and prints the code the first letter would have
(the table's base) plus a decoded preview using that guess.

Orders:
  gojuon   あいうえお かきくけこ ... わをん (no small or voiced kana) - the common game order
  unicode  the Unicode kana block: ぁあぃいぅう...かがきぎ... (small and voiced kana in between)
  ascii    A-Z a-z 0-9 by code
Katakana count like hiragana. With --order gojuon, use a word without small or voiced kana
(ゃ, っ, が...): many games draw the dakuten as a separate mark. --width 2 searches 16-bit
little-endian codes. Write the kana you find into a .tbl (tools/tbl.py) and widen it from there.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snes  # noqa: E402

GOJUON = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'


def hira(c):
    return chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c


def positions(word, order):
    if order == 'ascii':
        return [ord(c) for c in word]
    out = []
    for c in map(hira, word):
        if order == 'gojuon':
            if c not in GOJUON:
                raise SystemExit(f'{c!r} is not in the gojuon order (no small or voiced kana): pick another word '
                                 f'or use --order unicode')
            out.append(GOJUON.index(c))
        else:
            if not 'ぁ' <= c <= 'ゖ':
                raise SystemExit(f'{c!r} is not a kana')
            out.append(ord(c) - ord('ぁ'))
    return out


def search(data, pos, width=1):
    """[(offset, base)]: where codes differ like `pos`; base = the code of position 0 of the order."""
    deltas = [p - pos[0] for p in pos]
    n, step, hits = len(pos), width, []
    mask = (1 << (8 * width)) - 1
    end = len(data) - n * step + 1
    for i in range(0, end):
        first = int.from_bytes(data[i:i + step], 'little')
        for k in range(1, n):
            if (int.from_bytes(data[i + k * step:i + (k + 1) * step], 'little') - first) & mask != deltas[k] & mask:
                break
        else:
            hits.append((i, (first - pos[0]) & mask))
    return hits


def preview(data, off, base, order, width, context):
    alphabet = GOJUON if order == 'gojuon' else ''.join(chr(c) for c in range(ord('ぁ'), ord('ゖ') + 1))
    out = []
    for i in range(off, min(len(data), off + context * width), width):
        v = int.from_bytes(data[i:i + width], 'little') - base
        if order == 'ascii':
            out.append(chr(v + base) if 0x20 <= v + base < 0x7f else '·')
        else:
            out.append(alphabet[v] if 0 <= v < len(alphabet) else '·')
    return ''.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    ap.add_argument('rom')
    ap.add_argument('word')
    ap.add_argument('--order', choices=('gojuon', 'unicode', 'ascii'), default='gojuon')
    ap.add_argument('--width', type=int, choices=(1, 2), default=1)
    ap.add_argument('--context', type=int, default=24)
    ap.add_argument('--max', type=int, default=50)
    args = ap.parse_args(argv)
    if len(args.word) < 3:
        sys.exit('use a word of at least 3 letters (4+ gives far fewer false hits)')
    data = snes.read_rom(args.rom)[0]
    rom = snes.Rom(data)
    pos = positions(args.word, args.order)
    hits = search(data, pos, args.width)
    for off, base in hits[:args.max]:
        print(f'{off:#08x} {snes.fmt(rom.to_cpu(off))}  base {base:#04x}  '
              f'{data[off:off + len(pos) * args.width].hex(" ")}  {preview(data, off, base, args.order, args.width, args.context)}')
    print(f'{len(hits)} hit(s)' + (f', first {args.max} shown' if len(hits) > args.max else ''))


if __name__ == '__main__':
    main()
