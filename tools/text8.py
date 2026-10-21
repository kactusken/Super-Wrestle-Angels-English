#!/usr/bin/env python3
"""Text in the 8x8 UI font (block $84:EE4C): one byte per character - ASCII capitals and digits,
JIS X 0201 half-width katakana (and a few kana/kanji tiles of the game's own).

  text8.py dump        (re)write translation/text/moves8.csv and labels8.csv (keeps english)
  text8.py check       English that doesn't fit or uses characters the font lacks
  text8.py scan        8x8 strings the window bytecode prints (opcode $0E + 16-bit pointer, same
                       bank) that contain kana or kanji tiles and are in no table yet

Two tables so far:
  moves8.csv   the move records at $88:851B (file 0x4051b): 41 bytes each, a 12-byte name padded
               with spaces, then the move's ID (1, 2, ...) and data. Wrestler data screens.
  labels8.csv  label lists (LABEL_RUNS: data screen, financial statement, title holders, a stats
               panel, training AP): strings ending in $FF; each keeps its length (English is padded with spaces).
  finish8.csv  the finishing holds shown with match results (tournament): 21 records of 10 bytes
               at file 0x19efc, centred with spaces.
  hints8.csv   the command shown under a wrestler's portrait in a match (Down cycles it): two
               tables of 4 records of 8 bytes at file 0x28606 ($85:8606, $85:8626), copied by
               $85:85C0.. (the second when $7E:5AFE & 7 = 6).
The font has no lowercase: English is in capitals.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

MOVES_AT, MOVE_SIZE, NAME = 0x4051b, 41, 12
# runs of $FF-terminated labels: (file offset, count) - data screen, statement, title holders, stats,
# the training screen's AP labels (two rows)
LABEL_RUNS = [(0x1b4e3, 20), (0x5443a, 20), (0x5df75, 4), (0x8959e, 11), (0x45434, 2),
              # found by `text8.py scan` (opcode $0E of the window bytecode): a stats panel,
              # move difficulty AP, points, a morale / popularity table
              (0x2952c, 4), (0x46174, 1), (0x50fd9, 1), (0x5bd23, 2),
              (0x508dc, 1)]   # にんき over the year-end ranks' regions
FINISH_AT, FINISH_SIZE, FINISH_COUNT = 0x19efc, 10, 21   # finishing holds in match results (10 bytes)
FINISH_CSV = paths.TEXT / 'finish8.csv'
HINTS_AT, HINTS_SIZE, HINTS_COUNT = 0x28606, 8, 8           # match commands (two tables of 4)
HINTS_CSV = paths.TEXT / 'hints8.csv'
MOVES_CSV = paths.TEXT / 'moves8.csv'
LABELS_CSV = paths.TEXT / 'labels8.csv'
OK = set(range(0x20, 0x5b)) | {0x5f}       # space, punctuation, digits, capitals


HIRA = dict(zip([0x06, 0x0c, 0x0d, 0x0e, 0x0f] + list(range(0x11, 0x20)) + list(range(0x80, 0x9e)),
                'をゃゅょっ' + 'あいうえおかきくけこさしすせそ' + 'たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん'))
TILES = {0x5b: '投', 0x5c: '極', 0x5d: '打', 0x5e: '飛', 0x5f: '攻', 0x60: '人', 0x61: '第', 0x62: '戦', 0x63: '試',
         0x64: '合', 0x7b: '防', 0x7c: '評', 0x7d: '価', 0x7e: '値', 0x9e: '分'}


def decode(b):
    out = []
    for x in b:
        if x in HIRA or x in TILES:
            out.append(HIRA.get(x) or TILES[x])
        elif 0xa1 <= x <= 0xdf:
            out.append(bytes([x]).decode('cp932'))
        elif 0x20 <= x < 0x7f:
            out.append(chr(x))
        else:
            out.append(f'[{x:02x}]')
    return ''.join(out)


def moves(data):
    out, k = [], 0
    while data[MOVES_AT + MOVE_SIZE * k + NAME] == k + 1:
        out.append(MOVES_AT + MOVE_SIZE * k)
        k += 1
    return out


def labels(data):
    out = []
    for at, count in LABEL_RUNS:
        for _ in range(count):
            end = data.index(0xff, at)
            out.append((at, end - at))
            at = end + 1
    return out


def read(path):
    if not path.exists():
        return {}
    with open(path, encoding='utf-8', newline='') as f:
        return {r['offset']: r for r in csv.DictReader(f)}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['offset', 'size', 'japanese', 'english'], lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def encode(text, size):
    b = text.encode('ascii')
    if len(b) > size or any(x not in OK for x in b):
        raise ValueError(f'{text!r}: at most {size} capitals, digits, spaces or punctuation')
    return b.ljust(size, b' ')


def tables(data):
    yield MOVES_CSV, [(a, NAME) for a in moves(data)]
    yield LABELS_CSV, labels(data)
    yield FINISH_CSV, [(FINISH_AT + FINISH_SIZE * k, FINISH_SIZE) for k in range(FINISH_COUNT)]
    yield HINTS_CSV, [(HINTS_AT + HINTS_SIZE * k, HINTS_SIZE) for k in range(HINTS_COUNT)]


def scan(data):
    """[(offset, bytes, references)] of untabled strings named by print opcodes ($80:97D7 table,
    opcode $0E -> $80:9AB8 -> $80:A574). Single characters are usually chance matches."""
    kana = set(range(0xa6, 0xe0)) | set(HIRA) | set(TILES)
    ok = kana | OK | {0xa1, 0xa2, 0xa3, 0xa4, 0xa5}
    known = set()
    for _, entries in tables(data):
        for at, size in entries:
            known |= set(range(at, at + size + 1))
    found = {}
    i = data.find(0x0e)
    while 0 <= i < len(data) - 2:
        p = data[i + 1] | data[i + 2] << 8
        if p >= 0x8000:
            t = (i & ~0x7fff) | (p & 0x7fff)
            e = data.find(0xff, t, t + 64)
            s = data[t:e] if e >= 0 else b''
            if s and all(b in ok for b in s) and any(b in kana for b in s) and t not in known:
                found.setdefault(t, [s, 0])[1] += 1
        i = data.find(0x0e, i + 1)
    return [(t, s, n) for t, (s, n) in sorted(found.items())]


def build(rom, data, quiet=False):
    n = 0
    for path, entries in tables(data):
        rows = read(path)
        for at, size in entries:
            r = rows.get(f'{at:06x}')
            if r and r['english'].strip():
                rom[at:at + size] = encode(r['english'], size)
                n += 1
    if not quiet:
        print(f'text8: {n} strings')


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    if argv == ['dump']:
        for path, entries in tables(data):
            old = read(path)
            rows = [{'offset': f'{a:06x}', 'size': s, 'japanese': decode(data[a:a + s]).rstrip(),
                     'english': old.get(f'{a:06x}', {}).get('english', '')} for a, s in entries]
            write(path, rows)
            print(f'{paths.show(path)}: {len(rows)}')
    elif argv == ['scan']:
        for t, s, n in scan(data):
            if len(s) > 1:
                print(f'{t:06x} x{n} {decode(s)}')
    elif argv == ['check']:
        bad = 0
        for path, entries in tables(data):
            for r in read(path).values():
                try:
                    if r['english']:
                        encode(r['english'], int(r['size']))
                except ValueError as e:
                    print(f'{paths.show(path)} {r["offset"]}: {e}')
                    bad += 1
        print(f'{bad} problem(s)')
        return 1 if bad else 0
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
