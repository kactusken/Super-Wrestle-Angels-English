#!/usr/bin/env python3
"""Reletter the game's boxed 4bpp UI labels (menu bar, stat panels) in English.

  labels.py preview OUT.png        original | English for every label in LABELS (Pillow)

Each label is a box 16 pixels tall inside a compressed graphics block (tools/pack8.py) whose tiles
are laid out 16 to a row: a label at (x, band) covers pixels x..x+w-1 of tile rows 2*band and
2*band+1. Relettering keeps the border, replaces the text by the background of each pixel row (the
background is a vertical gradient with a dithered row; the most common background colour per row
and column parity), and draws capitals from tools/halffont.py in the original text colours by row.

build.py calls build(rom): every block is unpacked from the original ROM, relettered, packed and
written back in place with exactly its old packed length: blocks are read back to back.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import halffont  # noqa: E402
import pack8  # noqa: E402
import paths  # noqa: E402
import snes  # noqa: E402
import snesgfx  # noqa: E402

# block CPU address: (groups, [(x, band, width, Japanese, English)])
BLOCKS = {
    0x8E8002: (0x200, [
        (0, 1, 48, '能力値', 'STATS'), (48, 1, 48, '所属選手', 'ROSTER'),
        ([(96, 1, 32), (112, 0, 16)], None, 48, '戻る', 'BACK'),   # 戻 here, る at the end of band 0
        (0, 2, 32, '人事', 'STAFF'), (32, 2, 32, '練習', 'TRAIN'), (64, 2, 32, '運営', 'ADMIN'),
        (96, 2, 32, '指導', 'COACH'),
        (0, 3, 32, '殴込', 'RAID'), (32, 3, 32, '評価', 'INFO'), (64, 3, 32, '終了', 'END'),
    ]),
}
# boxes not on the 16-pixel grid: block -> [(x, y, width, Japanese, English, 3x5 font)]
BOXES = {
    0x8E8CF2: [(0, 8, 16, '投', 'THR', True), (16, 8, 16, '極', 'LCK', True), (32, 8, 16, '打', 'STK', True),
               (48, 8, 16, '飛', 'FLY', True), (64, 8, 16, '他', 'OTH', True), (80, 8, 48, '技習得', 'LEARN', False),
               (0, 24, 32, '形式', 'TYPE', False), (32, 24, 32, '反転', 'FLIP', False),
               (0, 40, 48, '終了', 'END', False)],
}
TEXT = {0x9, 0xc, 0xd, 0xe}   # text colours (and the left border's 0xc - skipped by column)
ROW_COLOUR = [None, None, 0xe, 0xe, 0xe, 0xe, 0xe, 0xe, 0xd, 0xd, 0xd, 0xd, 0xc, 0xc, None, None]


def reletter(rows, x0, band, w, text, y0=None, tiny=False):
    y0 = band * 16 if y0 is None else y0
    # background per pixel row and column parity, from the interior's non-text pixels
    bg = {}
    for y in range(1, 15):
        for par in (0, 1):
            c = Counter(rows[y0 + y][x] for x in range(x0 + 1, x0 + w - 1) if x % 2 == par
                        and rows[y0 + y][x] not in TEXT)
            bg[y, par] = c.most_common(1)[0][0] if c else rows[y0 + y][x0 + 1]
    for y in range(1, 15):
        for x in range(x0 + 1, x0 + w - 1):
            rows[y0 + y][x] = bg[y, x % 2]
    if tiny:      # 3x5 capitals, 4-pixel pitch, rows 5-9
        left = x0 + (w - (4 * len(text) - 1)) // 2
        for k, ch in enumerate(text):
            for gy, line in enumerate(TINY[ch]):
                for gx, px in enumerate(line):
                    if px == '#':
                        y, x = 5 + gy, left + 4 * k + gx
                        rows[y0 + y][x] = 0xe if y < 8 else 0xd
                        if y + 1 < 14 and x + 1 < x0 + w - 1 and rows[y0 + y + 1][x + 1] not in (0xd, 0xe):
                            rows[y0 + y + 1][x + 1] = 0x9
        return rows
    # capitals: rows 1-7 of the half-width letters, 7 pixels tall, drawn at label rows 4-10
    width = 6 * len(text) - 1
    left = x0 + (w - width) // 2
    for k, ch in enumerate(text):
        g = halffont.FONT[ch]
        for gy in range(1, 8):
            for gx in range(5):
                if g[gy][gx]:
                    y = 3 + gy
                    colour = ROW_COLOUR[y + 1] if y + 1 < 16 and ROW_COLOUR[y + 1] else 0xe
                    rows[y0 + y][left + 6 * k + gx] = colour
                    sx, sy = left + 6 * k + gx + 1, y + 1      # shadow down-right, as the kanji have
                    if sy < 14 and sx < x0 + w - 1 and rows[y0 + sy][sx] not in TEXT:
                        rows[y0 + sy][sx] = 0x9
    return rows


def relettered(original, addr):
    groups, labels = BLOCKS[addr]
    r = snes.Rom(original)
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    rows = snesgfx.sheet(raw, 4, 16)
    for x0, band, w, jp, en in labels:
        if isinstance(x0, list):        # a label split over several places of the sheet
            virtual = [[] for _ in range(16)]
            for sx, sb, sw in x0:
                for y in range(16):
                    virtual[y] += rows[sb * 16 + y][sx:sx + sw]
            reletter(virtual, 0, 0, w, en)
            at = 0
            for sx, sb, sw in x0:
                for y in range(16):
                    rows[sb * 16 + y][sx:sx + sw] = virtual[y][at:at + sw]
                at += sw
        elif band is None:                # (x, None, w, jp, en, y, tiny): a box at any height
            pass
        else:
            reletter(rows, x0, band, w, en)
    for x0, y0, w, jp, en, tiny in BOXES.get(addr, []):
        reletter(rows, x0, 0, w, en, y0=y0, tiny=tiny)
    return raw, snesgfx.unsheet(rows, 4, 16), used


# The title menu: 2bpp tiles in $81:A64E, loaded at BG3 tile $100; each word is a row of top
# tiles and a row of bottom tiles (from the title screen's tilemap). Tiles $114 and $14F are used
# twice in bottom rows, so the English is drawn into the top row (white, red outline) and only the
# outline's last row reaches the bottom tiles. A shared tile gets the union of what its places need:
# EXHIBITION sits 2 pixels left of centre so both its $114 places need the same row (left blank,
# the outline under "HI" was missing: play-test, 2026-10-21); $14F (TOURNAMENT, SYSTEM)
# takes both rows, a pixel or two of extra outline.
TITLE_BLOCK = (0x81A64E, 0xDC)
TITLE_WORDS = [
    ('エキシビション', 'EXHIBITION', list(range(0x101, 0x10f)),
     [0x10f, 0x110, 0x111, 0x112, 0x113, 0x114, 0x115, 0x116, 0x117, 0x114, 0x118, 0x119, 0x11a, 0x11b]),
    ('団体経営', 'PROMOTER', list(range(0x11d, 0x125)), list(range(0x125, 0x12d))),
    ('ミニ・リーグ戦', 'LEAGUE', list(range(0x12d, 0x135)), list(range(0x135, 0x13d))),
    ('トーナメント', 'TOURNAMENT', list(range(0x13d, 0x149)), list(range(0x149, 0x155))),
    ('システム', 'SYSTEM', list(range(0x155, 0x15d)), [0x15d, 0x15e, 0x14f, 0x15f, 0x160, 0x161, 0x162, 0x163]),
]
SHARED = {0x114, 0x14f}
TITLE_LEFT = {'EXHIBITION': 24}


def title_tiles(raw):
    """The title menu block with the words redrawn."""
    tiles = [snesgfx.decode_tile(raw[16 * k:16 * k + 16], 2) for k in range(len(raw) // 16)]
    shared = {t: [[0] * 8 for _ in range(8)] for t in SHARED}
    for jp, en, top, bottom in TITLE_WORDS:
        w = 8 * len(top)
        pix = [[0] * w for _ in range(16)]
        left = TITLE_LEFT.get(en, (w - (6 * len(en) - 1)) // 2)
        for k, ch in enumerate(en):
            g = halffont.FONT[ch]
            for gy in range(1, 8):
                for gx in range(5):
                    if g[gy][gx]:
                        pix[gy][left + 6 * k + gx] = 1
        for y in range(16):          # red outline around the white strokes
            for x in range(w):
                if pix[y][x] == 0 and any(0 <= y + dy < 16 and 0 <= x + dx < w and pix[y + dy][x + dx] == 1
                                          for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    pix[y][x] = 2
        for col, (t, b) in enumerate(zip(top, bottom)):
            tiles[t - 0x100] = [row[8 * col:8 * col + 8] for row in pix[0:8]]
            cell = [row[8 * col:8 * col + 8] for row in pix[8:16]]
            if b not in SHARED:
                tiles[b - 0x100] = cell
            else:
                shared[b] = [[max(p, q) for p, q in zip(r0, r1)] for r0, r1 in zip(shared[b], cell)]
    for t, cell in shared.items():
        tiles[t - 0x100] = cell
    return b''.join(snesgfx.encode_tile(t, 2) for t in tiles)


# The small プロレス drawn after promotion names (BG1 tiles $B8-$BB on the main screen): tiles
# $38-$3B of $8E:8CF2, 6 rows tall, colour $E with a $1 shadow. Redrawn as a small "PRO".
SMALL = (0x8E8CF2, 0x200, 0x38, 4, 'PRO')
# the tile row above it ($FB $8A $8B $8A on screen = block tiles $7B $0A $0B): only the tops of
# プ ロ レ ス in their last rows, left as a "-" after PRO (play-test, 2026-10-20) - blanked
SMALL_TOPS = (0x7b, 0x0a, 0x0b)


def small_caps(ch):
    """6-row capitals: the 7-row ones without one middle row."""
    rows = halffont.FONT[ch][1:8]
    drop = 3 if ch in 'OQUCGDSJ' else 2
    return rows[:drop] + rows[drop + 1:]


def small_tiles(raw):
    addr, groups, first, n, text = SMALL
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    w = 8 * n
    pix = [[0] * w for _ in range(8)]
    for k, ch in enumerate(text):
        g = small_caps(ch)
        for y in range(6):
            for x in range(5):
                if g[y][x]:
                    pix[y][3 + 6 * k + x] = 0xe
    for y in range(7, -1, -1):        # shadow down-right
        for x in range(w - 1, -1, -1):
            if pix[y][x] == 0 and y > 0 and x > 0 and pix[y - 1][x - 1] == 0xe:
                pix[y][x] = 1
    for c in range(n):
        tiles[first + c] = [row[8 * c:8 * c + 8] for row in pix]
    for t in SMALL_TOPS:
        tiles[t] = [[0] * 8 for _ in range(8)]
    date_tiles(tiles, DATE_MAIN, 0xf, 0x1)
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# 年 / 月 after the date numbers: one 8x16 tile column each -> YR / MO in 3x5 capitals, on the
# kanji's baseline, with its shadow colour. Main screen header: $8E:8CF2 tiles $56/$66, $57/$67;
# show schedule: $A4:F9DF (0x80 groups) tiles $1A/$1C, $1B/$1D.
DATE_MAIN = [(0x56, 0x66, 'YR'), (0x57, 0x67, 'MO')]
DATE_SCHEDULE = (0xA4F9DF, 0x80, [(0x1a, 0x1c, 'YR'), (0x1b, 0x1d, 'MO')])


def date_tiles(tiles, cells, ink, shadow):
    for top, bottom, text in cells:
        rows = [[0] * 8 for _ in range(16)]
        for k, ch in enumerate(text):
            for gy, line in enumerate(TINY[ch]):
                for gx, px in enumerate(line):
                    if px == '#':
                        rows[9 + gy][4 * k + gx] = ink
        for y in range(15, 0, -1):
            for x in range(7, 0, -1):
                if rows[y][x] == 0 and rows[y - 1][x - 1] == ink:
                    rows[y][x] = shadow
        tiles[top], tiles[bottom] = rows[:8], rows[8:]


# 3x5 capitals for the stat buttons (4-pixel pitch, 6 letters in a 24-pixel button)
TINY = {
    'A': ['.#.', '#.#', '###', '#.#', '#.#'], 'B': ['##.', '#.#', '##.', '#.#', '##.'],
    'C': ['.##', '#..', '#..', '#..', '.##'], 'D': ['##.', '#.#', '#.#', '#.#', '##.'],
    'E': ['###', '#..', '##.', '#..', '###'], 'F': ['###', '#..', '##.', '#..', '#..'],
    'G': ['.##', '#..', '#.#', '#.#', '.##'], 'H': ['#.#', '#.#', '###', '#.#', '#.#'],
    'I': ['###', '.#.', '.#.', '.#.', '###'], 'K': ['#.#', '#.#', '##.', '#.#', '#.#'],
    'L': ['#..', '#..', '#..', '#..', '###'], 'M': ['#.#', '###', '###', '#.#', '#.#'],
    'N': ['##.', '#.#', '#.#', '#.#', '#.#'], 'O': ['.#.', '#.#', '#.#', '#.#', '.#.'],
    'P': ['##.', '#.#', '##.', '#..', '#..'], 'R': ['##.', '#.#', '##.', '#.#', '#.#'],
    'S': ['.##', '#..', '.#.', '..#', '##.'], 'T': ['###', '.#.', '.#.', '.#.', '.#.'],
    'U': ['#.#', '#.#', '#.#', '#.#', '###'], 'V': ['#.#', '#.#', '#.#', '#.#', '.#.'],
    'W': ['#.#', '#.#', '###', '###', '#.#'], 'Y': ['#.#', '#.#', '.#.', '.#.', '.#.'],
    '.': ['...', '...', '...', '...', '.#.'], ' ': ['...'] * 5,
}

# Stat buttons (rankings, wrestler data): 3x2 cells of BG1 tiles $100-$17F = $8E:98F2 tiles 0-$7F.
# Tiles are shared: the attack/defence buttons are a left cap per move type, a middle tile and a
# right cap per attack/defence, so the English keeps that split (T. | AT | K). 体力 and 筋力 share
# their right tile: both stay within two tiles.
STAT_BLOCK = (0x8E98F2, 0x200)
STAT_BUTTONS = [
    ((0x47, 0x48, 0x49), '評価', 'RATING'), ((0x4a, 0x4b, 0x4c), '信頼', 'TRUST'),
    ((0x6a, 0x6b, 0x6c), 'モラル', 'MORALE'), ((0x4d, 0x4e, 0x4f), '人気', 'FANS'),
    ((0x6d, 0x6e, 0x6f), 'HP', 'HP'), ((0x67, 0x68, 0x2d), '体力', 'STA'),
    ((0x25, 0x26, 0x27), '回復', 'RECOV'), ((0x28, 0x29, 0x2a), '速さ', 'SPEED'),
    ((0x2b, 0x2c, 0x2d), '筋力', 'STR'), ((0x2e, 0x2f, 0x69), '耐久', 'ENDUR'),
    ((0x40, 0x43, 0x42), '投攻', 'T.ATK'), ((0x40, 0x63, 0x62), '投防', 'T.DEF'),
    ((0x60, 0x44, 0x42), '極攻', 'L.ATK'), ((0x60, 0x64, 0x62), '極防', 'L.DEF'),
    ((0x41, 0x45, 0x42), '打攻', 'S.ATK'), ((0x41, 0x65, 0x62), '打防', 'S.DEF'),
    ((0x61, 0x46, 0x42), '飛攻', 'F.ATK'), ((0x61, 0x66, 0x62), '飛防', 'F.DEF'),
]


def stat_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    made = {}
    for cols, jp, en in STAT_BUTTONS:
        # the button as 24x16 pixels: top tiles, bottom tiles 16 below
        virtual = [[0] * 24 for _ in range(16)]
        for c, t in enumerate(cols):
            for half, tt in ((0, t), (1, t + 0x10)):
                for y in range(8):
                    virtual[8 * half + y][8 * c:8 * c + 8] = tiles[tt][y]
        # clear the text to the background (as reletter(), whole width: borders are in other tiles)
        bg = {}
        for y in range(16):
            for par in (0, 1):
                cnt = Counter(virtual[y][x] for x in range(24) if x % 2 == par and virtual[y][x] not in TEXT | {7, 0xb})
                bg[y, par] = cnt.most_common(1)[0][0] if cnt else virtual[y][par]
        for y in range(2, 14):
            for x in range(24):
                if virtual[y][x] in TEXT | {7, 0xb}:
                    virtual[y][x] = bg[y, x % 2]
        shared = [sum(t in c2 for c2, _, _ in STAT_BUTTONS) > 1 for t in cols]
        left = (24 - (4 * len(en) - 1)) // 2
        if shared == [False, False, True]:      # only the right tile shared (STA, STR): keep out of it
            left = min(left, 16 - 4 * len(en))
        elif any(shared):                       # caps shared by type: same letter positions
            left = 2
        for k, ch in enumerate(en):
            for gy, line in enumerate(TINY[ch]):
                for gx, px in enumerate(line):
                    if px == '#':
                        y = 5 + gy
                        virtual[y][left + 4 * k + gx] = 0xe if y < 8 else 0xd
                        if y + 1 < 14 and left + 4 * k + gx + 1 < 24 and virtual[y + 1][left + 4 * k + gx + 1] not in (0xd, 0xe):
                            virtual[y + 1][left + 4 * k + gx + 1] = 0x9
        for c, t in enumerate(cols):
            for half, tt in ((0, t), (1, t + 0x10)):
                px = [virtual[8 * half + y][8 * c:8 * c + 8] for y in range(8)]
                if tt in made and made[tt] != px:
                    raise SystemExit(f'labels: stat tile {tt:#x} needed twice with different pixels ({en})')
                made[tt] = px
                tiles[tt] = px
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# The exhibition start button (試合開始): BG1 tiles in $8F:C166, top row $3A-$41, bottom row
# $43 $44 $45 $45(mirrored) $46-$49. The English goes in the top row (3x5 capitals) and the bottom
# row is cleared to its background, so the mirrored tile stays symmetric.
START_BLOCK = (0x8FC166, 0x200)
START_TOP = [0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f, 0x40, 0x41]
START_BOTTOM = [0x43, 0x44, 0x45, 0x40, 0x46, 0x47, 0x48, 0x49]
START_TEXT = 'START'
# The button's tilemap template (compressed, file 0x1ee46.. inside a run of templates): the
# bottom row's 4th entry was $45 mirrored, which can't hold different letters. With START centred
# the 2nd and 7th top tiles are only border and background, so the 7th now uses $3B and $40 is
# free for the bottom. Each edit keeps the packed length (control byte, then the new bytes).
START_MAP = [(0x1ee41, bytes.fromhex('aa3e3f4041'), bytes.fromhex('aa3e3f3b41')),
             (0x1ee46, bytes.fromhex('a943444550'), bytes.fromhex('aa43444540'))]

# 5x11 capitals for the 16-pixel buttons (START, WATCH, SKIP), rows 2-12
TALL = {
    'S': ['.####', '#....', '#....', '#....', '#....', '.###.', '....#', '....#', '....#', '....#', '####.'],
    'T': ['#####'] + ['..#..'] * 10,
    'A': ['.###.', '#...#', '#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#', '#...#', '#...#'],
    'R': ['####.', '#...#', '#...#', '#...#', '#...#', '####.', '#.#..', '#..#.', '#..#.', '#...#', '#...#'],
    'W': ['#...#'] * 7 + ['#.#.#', '#.#.#', '##.##', '#...#'],
    'C': ['.###.', '#...#'] + ['#....'] * 7 + ['#...#', '.###.'],
    'H': ['#...#'] * 5 + ['#####'] + ['#...#'] * 5,
    'K': ['#...#', '#...#', '#..#.', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#..#.', '#...#', '#...#'],
    'I': ['.###.'] + ['..#..'] * 9 + ['.###.'],
    'P': ['####.', '#...#', '#...#', '#...#', '#...#', '####.'] + ['#....'] * 5,
    'B': ['####.', '#...#', '#...#', '#...#', '#...#', '####.', '#...#', '#...#', '#...#', '#...#', '####.'],
    'D': ['####.'] + ['#...#'] * 9 + ['####.'],
    'E': ['#####'] + ['#....'] * 4 + ['####.'] + ['#....'] * 4 + ['#####'],
    'J': ['....#'] * 8 + ['#...#', '#...#', '.###.'],
    'N': ['#...#', '#...#', '##..#', '##..#', '#.#.#', '#.#.#', '#.#.#', '#..##', '#..##', '#...#', '#...#'],
    'M': ['#...#', '##.##', '##.##', '#.#.#', '#.#.#'] + ['#...#'] * 6,
    'O': ['.###.'] + ['#...#'] * 9 + ['.###.'],
    'L': ['#....'] * 10 + ['#####'],
    'U': ['#...#'] * 10 + ['.###.'],
    'F': ['#####'] + ['#....'] * 4 + ['####.'] + ['#....'] * 5,
    'G': ['.###.', '#...#', '#....', '#....', '#....', '#.###', '#...#', '#...#', '#...#', '#...#', '.###.'],
    'V': ['#...#'] * 7 + ['.#.#.', '.#.#.', '.#.#.', '..#..'],
    'Y': ['#...#'] * 4 + ['.#.#.', '.#.#.'] + ['..#..'] * 5,
}


def tall_word(rows, word, w):
    """Clear the old text (colours $E/$F) inside a 16-row button w pixels wide, draw word centred."""
    for y in range(1, 15):
        bgc = Counter(v for v in rows[y][1:w - 1] if v not in (0xe, 0xf)).most_common(1)[0][0]
        for x in range(1, w - 1):
            if rows[y][x] in (0xe, 0xf):
                rows[y][x] = bgc
    left = (w - (6 * len(word) - 1)) // 2
    for k, ch in enumerate(word):
        for gy, line in enumerate(TALL[ch]):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[2 + gy][left + 6 * k + gx] = 0xf


def start_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    bottom = [0x43, 0x44, 0x45, None, 0x46, 0x47, 0x48, 0x49]       # as the original map has it
    rows = [sum((tiles[t][y] for t in START_TOP), []) for y in range(8)]
    rows += [sum((tiles[t][y] if t is not None else tiles[0x45][y][::-1] for t in bottom), []) for y in range(8)]
    w = 8 * len(START_TOP)
    tall_word(rows, START_TEXT, w)
    if [r[8:16] for r in rows[:8]] != [r[48:56] for r in rows[:8]]:
        raise SystemExit('labels: START button - top tiles 2 and 7 differ, tile $40 is not free')
    for c, t in enumerate(START_TOP):
        if c != 6:
            tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
    for c, t in enumerate(START_BOTTOM):
        tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]
    for top, bottom, word in BUTTONS:
        button(tiles, top, bottom, word)
    cpu_box(tiles)
    show_header(tiles)
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# The match screen of a show (a play-test savestate, 2026-10-20): 第 [n] 戦 above the card - 第 becomes
# "No." (outlined like the original: $F, edge $E, on transparent 0), 戦 blank - and the 超満員札止
# (sold out) banner, dark $4 text in a $C box, "SOLD OUT".
SHOW_NO = ([0x5f, 0x60], [0x61, 0x62])
SHOW_BAN = ([0x63, 0x64], [0x65, 0x66])
SOLD_OUT = (list(range(0x67, 0x6f)), list(range(0x77, 0x7f)))


def show_header(tiles):
    def strip(top, bottom):
        return [sum((tiles[t][y] for t in top), []) for y in range(8)] + \
               [sum((tiles[t][y] for t in bottom), []) for y in range(8)]

    def put(rows, top, bottom):
        for c, t in enumerate(top):
            tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
        for c, t in enumerate(bottom):
            tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]

    rows = [[0] * 16 for _ in range(16)]
    outlined(rows, 'No.', 0)
    put(rows, *SHOW_NO)
    put([[0] * 16 for _ in range(16)], *SHOW_BAN)
    top, bottom = SOLD_OUT
    rows = strip(top, bottom)
    w = 8 * len(top)
    for y in range(2, 14):
        for xx in range(6, w - 6):
            if rows[y][xx] in (0x4, 0x6):
                rows[y][xx] = 0xc
    text = 'SOLD OUT'
    left = (w - (6 * len(text) - 1)) // 2
    for k, ch in enumerate(text):
        for gy, line in enumerate(TALL.get(ch, ['.....'] * 11)):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[3 + gy][left + 6 * k + gx] = 0x4
    put(rows, top, bottom)


def start_map(rom, original):
    for off, old, new in START_MAP:
        if original[off:off + len(old)] != old:
            raise SystemExit(f'labels: START button map at {off:#x} is not {old.hex()}')
        rom[off:off + len(new)] = new


# The tournament bracket's 観戦する / 観戦しない buttons (same block and style, no shared tiles).
# Found with the a play-test savestate, 2026-10-20.
BUTTONS = [(list(range(0x1a, 0x22)), list(range(0x2a, 0x32)), 'WATCH'),
           (list(range(0x22, 0x2a)), list(range(0x32, 0x3a)), 'SKIP')]


def button(tiles, top, bottom, word):
    rows = [sum((tiles[t][y] for t in top), []) for y in range(8)] + \
           [sum((tiles[t][y] for t in bottom), []) for y in range(8)]
    tall_word(rows, word, 8 * len(top))
    for c, t in enumerate(top):
        tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
    for c, t in enumerate(bottom):
        tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]


# The bracket's オート box (who plays a match: オート / 1P / 2P), 16x16 at tiles $4B $4C / $56 $57:
# CPU in 3x12 capitals like the 1P box's digits (text $A on background $4, rows 2-13).
CPU_TILES = (0x4b, 0x4c, 0x56, 0x57)
CPU_GLYPHS = {
    'C': ['###'] + ['#..'] * 10 + ['###'],
    'P': ['###'] + ['#.#'] * 5 + ['###'] + ['#..'] * 5,
    'U': ['#.#'] * 11 + ['###'],
}


def cpu_box(tiles):
    a, b, c, d = CPU_TILES
    rows = [tiles[a][y] + tiles[b][y] for y in range(8)] + [tiles[c][y] + tiles[d][y] for y in range(8)]
    for y in range(1, 15):
        for x in range(1, 15):
            if rows[y][x] == 0xa:
                rows[y][x] = 0x4
    for k, ch in enumerate('CPU'):
        for gy, line in enumerate(CPU_GLYPHS[ch]):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[2 + gy][3 + 4 * k + gx] = 0xa
    tiles[a], tiles[b] = [r[:8] for r in rows[:8]], [r[8:] for r in rows[:8]]
    tiles[c], tiles[d] = [r[:8] for r in rows[8:]], [r[8:] for r in rows[8:]]


# Name entry (new promotion): the six mode buttons, 40x16 each (5 tiles over 5 tiles, text $F on
# a gradient) and 団体名 after "P1" in the field label, in $85:A9A0 (found with tools/gfxfind.py).
# 漢字 -> PAIRS: that page holds letter pairs now (tools/namepage.py).
NAME_BLOCK = (0x85A9A0, 0x200)
NAME_BUTTONS = [(range(0x01, 0x06), range(0x11, 0x16), 'HIRA'), (range(0x21, 0x26), range(0x30, 0x35), 'KANA'),
                (range(0x06, 0x0b), range(0x16, 0x1b), 'ABC'), (range(0x0b, 0x10), range(0x1b, 0x20), 'PAIRS'),
                (range(0x26, 0x2b), range(0x35, 0x3a), 'SPACE'), (range(0x2b, 0x30), range(0x3a, 0x3f), 'END')]
# background $1, text $F: 団体名 after "P1" in the label; 選手名 (naming a wrestler: a mask) shares
# its 名 tiles $4D/$5A, so both read NAME from the same x; プロレス after the name being typed
NAME_LABELS = [([0x4a, 0x4b, 0x4c, 0x4d], [0x57, 0x58, 0x59, 0x5a], 'NAME', 2),
               ([0x5c, 0x5d, 0x5e, 0x4d], [0x66, 0x67, 0x68, 0x5a], 'NAME', 2),
               (list(range(0x44, 0x4a)), list(range(0x51, 0x57)), 'PRO', 4)]
# the second name screen's 略称名 (short name): tiles $9F-$A6 of VRAM, $1F-$26 of $85:B45D
SHORT_BLOCK = (0x85B45D, 0x9c)
SHORT_LABELS = [([0x1f, 0x20, 0x21, 0x22], [0x23, 0x24, 0x25, 0x26], 'SHORT', 2)]


def field_labels(tiles, labels_):
    for top, bottom, word, left in labels_:
        rows = [[0x1] * 8 * len(top) for _ in range(16)]
        for k, ch in enumerate(word):
            for gy, line in enumerate(TALL[ch]):
                for gx, px in enumerate(line):
                    if px == '#':
                        rows[3 + gy][left + 6 * k + gx] = 0xf
        for c, t in enumerate(top):
            tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
        for c, t in enumerate(bottom):
            tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]


def name_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    for top, bottom, word in NAME_BUTTONS:
        button(tiles, list(top), list(bottom), word)
    field_labels(tiles, NAME_LABELS)
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


def short_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    field_labels(tiles, SHORT_LABELS)
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# Match card setup (show booking, play-test savestate, 2026-10-20): BG1 tiles of $8F:9209. Buttons
# オート 全オート クリア 全クリア (32x16, 全 and ト tiles shared) and tabs タイトルマッチ 終了, in the
# menu bar's colours (text $E/$D/$C by row on a $9/$8/$7/$6 gradient). Two lines of 3x5 capitals,
# all starting at x=8 so the shared tiles stay identical. Starts at $8F:920A (the logged load; $9209
# also decodes the same but is one byte early - repacking from there garbled the screen).
CARD_SETUP = (0x8F920A, 0x200)
CARD_BUTTONS = [
    ([0x41, 0x42, 0x43, 0x44], [0x4f, 0x50, 0x51, 0x52], ['ONE', 'AUTO'], 8),
    ([0x3d, 0x45, 0x46, 0x44], [0x4b, 0x53, 0x54, 0x52], ['ALL', 'AUTO'], 8),
    ([0x39, 0x3a, 0x3b, 0x3c], [0x47, 0x48, 0x49, 0x4a], ['ONE', 'CLEAR'], 8),
    ([0x3d, 0x3e, 0x3f, 0x40], [0x4b, 0x4c, 0x4d, 0x4e], ['ALL', 'CLEAR'], 8),
    (list(range(0x03, 0x0a)), list(range(0x10, 0x17)), ['TITLE', 'MATCH'], None),
    ([0x01, 0x0a, 0x0b, 0x0c, 0x0d, 0x02], [0x0e, 0x17, 0x18, 0x19, 0x1a, 0x0f], ['DONE'], None),
]
CARD_TEXT = {0xa, 0xb, 0xc, 0xd, 0xe}


def card_setup_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    for top, bottom, lines, left in CARD_BUTTONS:
        rows = [sum((tiles[t][y] for t in top), []) for y in range(8)] + \
               [sum((tiles[t][y] for t in bottom), []) for y in range(8)]
        w = 8 * len(top)
        for y in range(1, 15):
            for par in (0, 1):
                c = Counter(rows[y][x] for x in range(1, w - 1) if x % 2 == par and rows[y][x] not in CARD_TEXT)
                bgc = c.most_common(1)[0][0]
                for x in range(1, w - 1):
                    if x % 2 == par and rows[y][x] in CARD_TEXT:
                        rows[y][x] = bgc
        y0 = 5 if len(lines) == 1 else 2
        for n, text in enumerate(lines):
            x0 = left if left is not None else (w - (4 * len(text) - 1)) // 2
            for k, ch in enumerate(text):
                for gy, line in enumerate(TINY[ch]):
                    for gx, px in enumerate(line):
                        if px == '#':
                            y = y0 + 6 * n + gy
                            rows[y][x0 + 4 * k + gx] = 0xe if y < 7 else 0xd if y < 10 else 0xc
        for c, t in enumerate(top):
            tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
        for c, t in enumerate(bottom):
            tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# The show's match screen, continued: tiles $80+ there are $8F:CAC8 (0x98 groups, unpacked with
# A = 7). 最終 of 最終戦 (the last match) is its tiles $0A-$0D / $15-$18 -> "FINAL", outlined;
# the short banner 超満員 (full house) is $8F:C166 $6F-$76 over $7F + $8F:CAC8 $00-$05 -> "PACKED".
SHOW_B = (0x8FCAC8, 0x98, 7)
FINAL = ([(SHOW_B, t) for t in (0x0a, 0x0b, 0x0c, 0x0d)], [(SHOW_B, t) for t in (0x15, 0x16, 0x17, 0x18)])
PACKED = ([(START_BLOCK, t) for t in range(0x6f, 0x76)],
          [(START_BLOCK, 0x7f)] + [(SHOW_B, t) for t in range(0x00, 0x06)])
# The plain 満員 banner (満, two fill tiles $89, then 員 in $74 $75 - shared with 超満員, so PACKED
# showed through as "満 :D"): its template (file 0x1efc1, 8x2) now has fill in place of $74 $75 /
# $84 $85, and FULL is written in its own tiles $86-$88 / $92-$94 in 3-pixel capitals (18 pixels
# between the border and the fill). Same packed length: only literal bytes change.
FULL = ([(SHOW_B, t) for t in (0x06, 0x07, 0x08)], [(SHOW_B, t) for t in (0x12, 0x13, 0x14)])
FULL_MAP = [(0x1efcc, bytes.fromhex('2a7475'), bytes.fromhex('2a8989')),
            (0x1efd6, bytes.fromhex('3b840c85'), bytes.fromhex('3b898c89'))]
NARROW = {'F': ['###'] + ['#..'] * 4 + ['##.'] + ['#..'] * 6, 'U': ['#.#'] * 11 + ['###'],
          'L': ['#..'] * 11 + ['###']}


def outlined(rows, text, x0):
    """Half-width capitals in $F with an $E edge on transparent 0 (as 第 戦 最終)."""
    h, w = len(rows), len(rows[0])
    x = x0
    for ch in text:
        g = halffont.FONT[ch]
        for gy in range(10):
            for gx in range(5):
                if g[gy][gx] and 0 <= x + gx < w:
                    rows[3 + gy][x + gx] = 0xf
        x += 6
    for y in range(h):
        for xx in range(w):
            if rows[y][xx] == 0 and any(0 <= y + dy < h and 0 <= xx + dx < w and rows[y + dy][xx + dx] == 0xf
                                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                rows[y][xx] = 0xe


def show_screen(rom, original):
    r, o = snes.Rom(rom), snes.Rom(original)
    blocks = {START_BLOCK: (START_BLOCK[0], START_BLOCK[1], 0), SHOW_B: SHOW_B}
    tiles, used = {}, {}
    for key, (addr, groups, init) in blocks.items():
        raw, _ = pack8.unpack(r.data, r.to_file(addr), groups, init)
        _, used[key] = pack8.unpack(o.data, o.to_file(addr), groups, init)
        tiles[key] = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]

    def strip(top, bottom):
        return [sum((tiles[b][t][y] for b, t in top), []) for y in range(8)] + \
               [sum((tiles[b][t][y] for b, t in bottom), []) for y in range(8)]

    def put(rows, top, bottom):
        for half, cells in ((0, top), (1, bottom)):
            for c, (b, t) in enumerate(cells):
                tiles[b][t] = [rows[8 * half + y][8 * c:8 * c + 8] for y in range(8)]

    rows = [[0] * 32 for _ in range(16)]
    outlined(rows, 'FINAL', 1)
    put(rows, *FINAL)
    rows = strip(*PACKED)
    w = len(rows[0])
    for y in range(2, 14):
        for x in range(6, w):
            if rows[y][x] in (0x4, 0x6):
                rows[y][x] = 0xc
    text = 'PACKED'
    left = 6 + (w - 6 - (6 * len(text) - 1)) // 2
    for k, ch in enumerate(text):
        for gy, line in enumerate(TALL[ch]):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[3 + gy][left + 6 * k + gx] = 0x4
    put(rows, *PACKED)
    rows = strip(*FULL)
    for y in range(1, 15):
        for x in range(6, 24):
            rows[y][x] = 0xc
    for k, ch in enumerate('FULL'):
        for gy, line in enumerate(NARROW[ch]):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[2 + gy][7 + 4 * k + gx] = 0x4
    put(rows, *FULL)
    for off, old, new in FULL_MAP:
        if original[off:off + len(old)] != old:
            raise SystemExit(f'labels: 満員 banner map at {off:#x} is not {old.hex()}')
        rom[off:off + len(new)] = new
    for key, (addr, groups, init) in blocks.items():
        packed = pack8.pack_exact(b''.join(snesgfx.encode_tile(t, 4) for t in tiles[key]), used[key], init)
        if packed is None:
            raise SystemExit(f'labels: ${addr:06X} packs to more than {used[key]} bytes')
        rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed


# The ending's award screens (Mesen, 2026-10-21): ribbon banners over each ranking, text $3 with a
# $5 shadow on the right, on $F. BG1 tiles 0-$7F are $A6:CBA9 and $80-$E5 $A6:D791 (it continues
# from CBA9's end); 興行数 uses tiles of both. (word, top tiles, bottom tiles, first and last
# pixel inside the border). The 4-tile banners have plain end tiles ($C5 / $D4) shared by all.
AWARD_BLOCKS = [(0xA6CBA9, 0x200), (0xA6D791, 0x198)]
AWARDS = [('OVERALL', range(0xbb, 0xc1), range(0xca, 0xd0), 0, 47),     # 総合 (between end tiles)
          ('RATING', range(0x9f, 0xa5), range(0xaf, 0xb5), 2, 45),      # 評価値
          ('FANS', range(0xc1, 0xc5), range(0xd0, 0xd4), 0, 31),        # 人気
          ('ROSTER', range(0xa5, 0xab), range(0xb5, 0xbb), 2, 45),      # 選手層
          ('DOJO', range(0xc6, 0xca), range(0xd5, 0xd9), 0, 31),        # 設備 (道場設備)
          ('SHOWS', [0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x7b], [0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x8d], 2, 45),  # 興行数
          ('FUNDS', range(0x9b, 0x9f), range(0xab, 0xaf), 0, 31)]       # 資金


def awards(rom, original):
    r, o = snes.Rom(rom), snes.Rom(original)
    tiles, used = [], []
    for addr, groups in AWARD_BLOCKS:
        raw, _ = pack8.unpack(r.data, r.to_file(addr), groups)
        used.append(pack8.unpack(o.data, o.to_file(addr), groups)[1])
        tiles += [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    for word, top, bottom, x0, x1 in AWARDS:
        top, bottom = list(top), list(bottom)
        rows = [sum((tiles[t][y] for t in top), []) for y in range(8)] + \
               [sum((tiles[t][y] for t in bottom), []) for y in range(8)]
        for y in range(1, 15):
            for x in range(x0, x1 + 1):
                rows[y][x] = 0xf
        left = x0 + (x1 + 1 - x0 - (6 * len(word) - 1)) // 2
        for k, ch in enumerate(word):
            for gy, line in enumerate(TALL[ch]):
                for gx, px in enumerate(line):
                    if px == '#':
                        rows[3 + gy][left + 6 * k + gx] = 0x3
        for y in range(16):
            for x in range(x1, x0, -1):
                if rows[y][x] == 0xf and rows[y][x - 1] == 0x3:
                    rows[y][x] = 0x5
        for c, t in enumerate(top):
            tiles[t] = [rows[y][8 * c:8 * c + 8] for y in range(8)]
        for c, t in enumerate(bottom):
            tiles[t] = [rows[8 + y][8 * c:8 * c + 8] for y in range(8)]
    start = 0
    for (addr, groups), n in zip(AWARD_BLOCKS, used):
        count = groups * 8 // 32
        packed = pack8.pack_exact(b''.join(snesgfx.encode_tile(t, 4) for t in tiles[start:start + count]), n)
        if packed is None:
            raise SystemExit(f'labels: ${addr:06X} packs to more than {n} bytes')
        rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
        start += count


# Year-end promotion ranks (the April report of a multi-year game; Mesen 2026-10-21): 18 buttons
# of 5x2 tiles, each with its own small tilemap ($8A:A0C5.., 0x15 apart, 3 groups: 10 entries and
# a 2-word trailer). The tiles are $8A:9191 (BG1 0-$7F) and $8A:9DE7 ($80-$9D, continuing from
# it). The Japanese shared tiles between labels (東, 中, 国, the blank middle $20/$21), so the
# English labels are drawn whole, identical tiles merged, and given the label tiles $14-$9D again;
# the small maps are rewritten to match. Text is the background colour + 9 (as the kanji).
RANK_BLOCKS = [(0x8A9191, 0x200), (0x8A9DE7, 0x78)]
RANK_MAPS = 0x8AA0C5        # 18 maps, 0x15 bytes apart
RANK_WORDS = ['TOTAL', 'RATING', 'ROSTER', 'FUNDS', 'DOJO', 'SHOWS', 'JAPAN',    # 総合 評価値 選手層 資金 設備 興業数 全国
              'HOKKAIDO', 'TOHOKU', 'HOKURIKU', 'KANTO', 'CHUBU', 'TOKAI', 'KINKI', 'CHUGOKU',
              'SHIKOKU', 'KYUSHU', 'END']
# 3x11 capitals for the names too long for 5-pixel letters (40-pixel buttons)
SLIM = {'H': ['#.#'] * 5 + ['###'] + ['#.#'] * 5, 'O': ['###'] + ['#.#'] * 9 + ['###'],
        'K': ['#.#'] * 3 + ['##.'] * 2 + ['#..'] + ['##.'] * 2 + ['#.#'] * 3,
        'A': ['###'] + ['#.#'] * 4 + ['###'] + ['#.#'] * 5, 'I': ['###'] + ['.#.'] * 9 + ['###'],
        'D': ['##.'] + ['#.#'] * 9 + ['##.'], 'U': ['#.#'] * 10 + ['###'],
        'R': ['##.'] + ['#.#'] * 4 + ['##.'] + ['#.#'] * 5, 'C': ['###'] + ['#..'] * 9 + ['###'],
        'G': ['###'] + ['#..'] * 4 + ['#.#'] * 5 + ['###'],
        'S': ['###'] + ['#..'] * 4 + ['###'] + ['..#'] * 4 + ['###']}


def rank_labels(data):
    """(tiles, maps): the two blocks' tiles with the labels redrawn, and the 18 maps' new bytes."""
    r = snes.Rom(data)
    tiles = []
    for addr, groups in RANK_BLOCKS:
        raw, _ = pack8.unpack(data, r.to_file(addr), groups)
        tiles += [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    maps, pool = [], set()
    for k in range(len(RANK_WORDS)):
        m, _ = pack8.unpack(data, r.to_file(RANK_MAPS) + 0x15 * k, 3)
        maps.append([m[i] | m[i + 1] << 8 for i in range(0, 24, 2)])
        pool |= {w & 0x3ff for w in maps[-1][:10]}
    mid_top, mid_bottom = tiles[0x20], tiles[0x21]          # plain button background
    drawn = []
    for word, words in zip(RANK_WORDS, maps):
        first, last = words[0] & 0x3ff, words[4] & 0x3ff
        rows = []
        for y in range(16):
            mid = (mid_top if y < 8 else mid_bottom)[y % 8]
            row = [mid[x % 8] for x in range(40)]
            row[0] = tiles[first if y < 8 else words[5] & 0x3ff][y % 8][0]
            row[39] = tiles[last if y < 8 else words[9] & 0x3ff][y % 8][7]
            rows.append(row)
        font, step = (TALL, 6) if len(word) <= 6 else (SLIM, 4)
        width = step * len(word) - (step - len(next(iter(font.values()))[0]))
        left = (40 - width) // 2 - (step == 4)    # slim names 1 pixel left: more tiles then match
        for k, ch in enumerate(word):
            for gy, line in enumerate(font[ch]):
                for gx, px in enumerate(line):
                    if px == '#' and 2 <= rows[2 + gy][left + step * k + gx] <= 5:
                        rows[2 + gy][left + step * k + gx] += 9
        drawn.append([[rows[8 * h + y][8 * c:8 * c + 8] for y in range(8)] for h in (0, 1) for c in range(5)])
    free = sorted(pool)
    ids, new_maps = {}, []
    for (word, words), cells in zip(zip(RANK_WORDS, maps), drawn):
        entries = []
        for cell in cells:
            key = tuple(map(tuple, cell))
            if key not in ids:
                if not free:
                    raise SystemExit(f'labels: year-end rank labels need more than {len(pool)} tiles')
                ids[key] = free.pop(0)
                tiles[ids[key]] = cell
            entries.append((words[0] & 0xfc00) | ids[key])
        new_maps.append(entries + words[10:])
    return tiles, new_maps, len(ids), len(pool)


# League results tables (singles and tag; a play-test savestate, 2026-10-21): the last column's header
# 計 (total: the wins, counted in ○) is one 8-pixel column, tiles $54 / $64 of $8E:A4C6 (BG1
# $180+): a W in the 2-pixel strokes of the A B C D beside it (text $F on $5, rows 4-13).
LEAGUE_BLOCK = (0x8EA4C6, 0x200)
LEAGUE_TOTAL = (0x54, 0x64)
LEAGUE_W = ['##...##', '##...##', '##...##', '##...##', '##.#.##', '##.#.##', '#######', '#######',
            '###.###', '##...##']


def league_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    top, bottom = LEAGUE_TOTAL
    rows = [list(r) for r in tiles[top]] + [list(r) for r in tiles[bottom]]
    for y in range(1, 16):
        for x in range(7):
            rows[y][x] = 0x5
    for gy, line in enumerate(LEAGUE_W):
        for gx, px in enumerate(line):
            if px == '#':
                rows[4 + gy][gx] = 0xf
    tiles[top], tiles[bottom] = rows[:8], rows[8:]
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# League / tournament winner certificate (Mesen, 2026-10-21): 優勝 (champion) between the two
# WINNERs, in a frame: inner tiles $55-$5A / $61-$66 / $69-$6E of $8F:AFA6 (BG1 0-$7F), 48x24,
# text $2 on $F. CHAMP in 7x16 capitals of 2-pixel strokes like the kanji.
WINNER_BLOCK = (0x8FAFA6, 0x200)
WINNER_ROWS = [range(0x55, 0x5b), range(0x61, 0x67), range(0x69, 0x6f)]
BOLD = {
    'C': ['.#####.', '#######', '##...##'] + ['##.....'] * 10 + ['##...##', '#######', '.#####.'],
    'H': ['##...##'] * 7 + ['#######'] * 2 + ['##...##'] * 7,
    'A': ['.#####.', '#######'] + ['##...##'] * 5 + ['#######'] * 2 + ['##...##'] * 7,
    'M': ['##...##', '###.###', '#######', '##.#.##', '##.#.##'] + ['##...##'] * 11,
    'P': ['######.', '#######'] + ['##...##'] * 5 + ['#######', '######.'] + ['##.....'] * 7,
}


def winner_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    rows = [[0xf] * 48 for _ in range(24)]
    word = 'CHAMP'
    left = (48 - (8 * len(word) - 1)) // 2
    for k, ch in enumerate(word):
        for gy, line in enumerate(BOLD[ch]):
            for gx, px in enumerate(line):
                if px == '#':
                    rows[4 + gy][left + 8 * k + gx] = 0x2
    for band, cells in enumerate(WINNER_ROWS):
        for c, t in enumerate(cells):
            tiles[t] = [rows[8 * band + y][8 * c:8 * c + 8] for y in range(8)]
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# Wrestler training screen tabs (BG1, Mesen 2026-10-20): 必殺技 and 技難易度 are 48x16 tabs in the
# menu bar's style made of tiles scattered over $8E:8002 (BG1 tiles 0-$7F) and $8E:8CF2 ($80-$FF).
MENU_A, MENU_B = 0x8E8002, 0x8E8CF2
TABS = [
    ('SPECIAL', [(MENU_B, t) for t in (0x4e, 0x4f, 0x6c, 0x6d, 0x6e, 0x6f)],
                [(MENU_B, t) for t in (0x5e, 0x5f, 0x7c, 0x7d, 0x7e, 0x7f)]),
    ('MOVE LV', [(MENU_A, 0x6c), (MENU_A, 0x6d), (MENU_A, 0x6e), (MENU_A, 0x6f), (MENU_B, 0x3c), (MENU_B, 0x3d)],
                [(MENU_A, 0x7c), (MENU_A, 0x7d), (MENU_A, 0x7e), (MENU_A, 0x7f), (MENU_B, 0x3e), (MENU_B, 0x3f)]),
]


def tabs(rom, original):
    """Reletter TABS in the already relettered blocks of rom, repacked to their original length."""
    r, o = snes.Rom(rom), snes.Rom(original)
    tiles, used = {}, {}
    for addr in (MENU_A, MENU_B):
        raw, _ = pack8.unpack(r.data, r.to_file(addr), 0x200)
        _, used[addr] = pack8.unpack(o.data, o.to_file(addr), 0x200)
        tiles[addr] = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    for text, top, bottom in TABS:
        rows = [sum((tiles[a][t][y] for a, t in top), []) for y in range(8)] + \
               [sum((tiles[a][t][y] for a, t in bottom), []) for y in range(8)]
        reletter(rows, 0, 0, 8 * len(top), text)
        for half, cells in ((0, top), (1, bottom)):
            for c, (a, t) in enumerate(cells):
                tiles[a][t] = [rows[8 * half + y][8 * c:8 * c + 8] for y in range(8)]
    for addr in (MENU_A, MENU_B):
        packed = pack8.pack_exact(b''.join(snesgfx.encode_tile(t, 4) for t in tiles[addr]), used[addr])
        if packed is None:
            raise SystemExit(f'labels: ${addr:06X} with the tabs packs to more than {used[addr]} bytes')
        rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed


# The match HUD (BG2 tiles of $84:A38B): 投 極 打 飛 他 over the stat columns and 攻 / 防 beside
# the two rows of numbers, one 8x8 tile each, colour $F with a $8 shadow. Single capitals.
HUD_BLOCK = (0x84A38B, 0xF8)
HUD_LETTERS = {0x0a: 'T', 0x0b: 'L', 0x0c: 'S', 0x0d: 'F', 0x29: 'O', 0x0e: 'A', 0x0f: 'D',     # top HUD, shadow $8
               0x19: 'T', 0x1a: 'L', 0x1b: 'S', 0x1c: 'F', 0x28: 'O', 0x1d: 'A', 0x1e: 'D'}     # bottom, shadow $3
HUD_SHADOW = {t: 0x3 for t in (0x19, 0x1a, 0x1b, 0x1c, 0x28, 0x1d, 0x1e)}


def hud_tiles(raw):
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    for t, ch in HUD_LETTERS.items():
        g = halffont.FONT[ch][1:8]
        px = [[0] * 8 for _ in range(8)]
        for y in range(7):
            for x in range(5):
                if g[y][x]:
                    px[1 + y][1 + x] = 0xf
        for y in range(8):
            for x in range(8):
                if px[y][x] == 0 and x > 0 and px[y][x - 1] == 0xf:
                    px[y][x] = HUD_SHADOW.get(t, 0x8)
        tiles[t] = px
    return b''.join(snesgfx.encode_tile(t, 4) for t in tiles)


# The move cards played in a match (sprite tiles of $84:923E): five card faces 24 pixels wide in
# tile rows 0-1, a 12x16 white area at x 6-17 with the move type's kanji (投 極 打 飛 他) in the
# card's colour. Replaced by the HUD's capitals at double size.
CARD_BLOCK = (0x84923E, 0x200)
CARD_LETTERS = 'TLSFO'


def card_tiles(raw):
    rows = snesgfx.sheet(raw, 4, 16)
    for k, ch in enumerate(CARD_LETTERS):
        x0 = 24 * k + 6
        ink = Counter(rows[y][x] for y in range(16) for x in range(x0, x0 + 12) if rows[y][x] != 0xf)
        colour = ink.most_common(1)[0][0]
        for y in range(16):
            for x in range(x0, x0 + 12):
                rows[y][x] = 0xf
        g = halffont.FONT[ch][1:8]
        for y in range(7):
            for x in range(5):
                if g[y][x]:
                    for dy in (0, 1):
                        for dx in (0, 1):
                            rows[1 + 2 * y + dy][x0 + 1 + 2 * x + dx] = colour
    return snesgfx.unsheet(rows, 4, 16)


# The 8x8 UI font ($84:EE4C, 2bpp): 分 and 秒 after match times (tournament results) become copies
# of the font's own M and S, and the small プロレス after promotion names (schedule, statement) PRO.
FONT8_BLOCK = (0x84EE4C, 0x200)
FONT8_COPIES = {0x9e: 0x4d, 0x9f: 0x53,
                0xfb: 0x50, 0xfc: 0x52, 0xfd: 0x4f, 0xfe: 0x20,   # small プロレス after names -> PRO
                0x60: 0x20}                                       # 人 after counts (statement) -> blank


def unlogged():
    """Changed blocks whose start the game was never seen loading (translation/work/gfx_blocks.csv,
    tools/gfxsurvey.py): a block packed from the wrong start byte garbles its screen."""
    import csv
    path = paths.TRANSLATION / 'work/gfx_blocks.csv'
    if not path.exists():
        return []
    with open(path, encoding='utf-8', newline='') as f:
        logged = {int(r['address'], 16) for r in csv.DictReader(f)}
    mine = set(BLOCKS) | {SMALL[0], STAT_BLOCK[0], FONT8_BLOCK[0], CARD_BLOCK[0], HUD_BLOCK[0], START_BLOCK[0],
                          TITLE_BLOCK[0], NAME_BLOCK[0], SHORT_BLOCK[0], CARD_SETUP[0], SHOW_B[0], DATE_SCHEDULE[0]}
    mine |= {a for a, _ in AWARD_BLOCKS + RANK_BLOCKS} | {LEAGUE_BLOCK[0], WINNER_BLOCK[0]}
    return sorted(mine - logged)


def build(rom, original, quiet=False):
    for addr in unlogged():
        print(f'labels: WARNING ${addr:06X} is not a logged load start - check it (gfxsurvey.py)')
    for addr in BLOCKS:
        _, new, used = relettered(original, addr)
        packed = pack8.pack_exact(new, used)     # the next block starts where this one ends
        if packed is None:
            raise SystemExit(f'labels: block ${addr:06X} packs to {len(pack8.pack(new))} bytes, {used} available')
        off = snes.Rom(rom).to_file(addr)
        rom[off:off + len(packed)] = packed
        if not quiet:
            print(f'labels: ${addr:06X} {len(BLOCKS[addr][1])} labels ({len(packed)}/{used} bytes)')
    addr, groups = SMALL[:2]
    r = snes.Rom(original)
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    rows = snesgfx.sheet(small_tiles(raw), 4, 16)
    for x0, y0, w, jp, en, tiny in BOXES.get(addr, []):
        reletter(rows, x0, 0, w, en, y0=y0, tiny=tiny)
    packed = pack8.pack_exact(snesgfx.unsheet(rows, 4, 16), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: small PRO in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = STAT_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(stat_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: {len(STAT_BUTTONS)} stat buttons in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = FONT8_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    new = bytearray(raw)
    for dst, src in FONT8_COPIES.items():
        new[16 * dst:16 * dst + 16] = raw[16 * src:16 * src + 16]
    packed = pack8.pack_exact(bytes(new), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: 8x8 font tiles in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = CARD_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(card_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: move cards in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = HUD_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(hud_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: match HUD in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = START_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(start_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    start_map(rom, original)
    if not quiet:
        print(f'labels: start button in ${addr:06X} ({len(packed)}/{used} bytes)')
    tabs(rom, original)
    if not quiet:
        print(f'labels: {len(TABS)} training screen tabs')
    addr, groups, cells = DATE_SCHEDULE
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    tiles = [snesgfx.decode_tile(raw[32 * k:32 * k + 32], 4) for k in range(len(raw) // 32)]
    date_tiles(tiles, cells, 0x1, 0x2)
    packed = pack8.pack_exact(b''.join(snesgfx.encode_tile(t, 4) for t in tiles), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    show_screen(rom, original)
    if not quiet:
        print('labels: show match screen (FINAL, PACKED, FULL)')
    tiles, maps, n, pool = rank_labels(original)
    start = 0
    for addr, groups in RANK_BLOCKS:
        _, used = pack8.unpack(original, r.to_file(addr), groups)
        count = groups * 8 // 32
        packed = pack8.pack_exact(b''.join(snesgfx.encode_tile(t, 4) for t in tiles[start:start + count]), used)
        if packed is None:
            raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
        rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
        start += count
    for k, words in enumerate(maps):
        at = r.to_file(RANK_MAPS) + 0x15 * k
        _, used = pack8.unpack(original, at, 3)
        packed = pack8.pack_exact(b''.join(w.to_bytes(2, 'little') for w in words), used)
        if packed is None:
            raise SystemExit(f'labels: year-end rank map {k} packs to more than {used} bytes')
        rom[at:at + len(packed)] = packed
    if not quiet:
        print(f'labels: {len(maps)} year-end rank buttons ({n}/{pool} tiles)')
    awards(rom, original)
    if not quiet:
        print(f'labels: {len(AWARDS)} ending award banners')
    addr, groups = CARD_SETUP
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(card_setup_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: match card setup buttons in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = NAME_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(name_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: name entry buttons in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = WINNER_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(winner_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: winner certificate in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = LEAGUE_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(league_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: league table header in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = SHORT_BLOCK
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(short_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: ${addr:06X} packs to more than {used} bytes')
    rom[r.to_file(addr):r.to_file(addr) + len(packed)] = packed
    if not quiet:
        print(f'labels: short name label in ${addr:06X} ({len(packed)}/{used} bytes)')
    addr, groups = TITLE_BLOCK
    r = snes.Rom(original)
    raw, used = pack8.unpack(r.data, r.to_file(addr), groups)
    packed = pack8.pack_exact(title_tiles(raw), used)
    if packed is None:
        raise SystemExit(f'labels: title menu packs to more than {used} bytes')
    off = r.to_file(addr)
    rom[off:off + len(packed)] = packed
    if not quiet:
        print(f'labels: title menu ({len(packed)}/{used} bytes)')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == 'preview':
        import paths
        from PIL import Image
        original = (paths.EXTRACTED / 'rom.sfc').read_bytes()
        pal = [(0, 0, 0), (40, 40, 60), (70, 70, 110), (90, 90, 150), (110, 110, 190), (130, 130, 220),
               (0, 0, 0), (0, 0, 0), (0, 0, 0), (40, 40, 40), (250, 250, 250), (200, 200, 200),
               (170, 170, 230), (200, 200, 250), (255, 255, 255), (0, 0, 0)]
        ims = []
        for addr in BLOCKS:
            raw, new, _ = relettered(original, addr)
            for data in (raw, new):
                rows = snesgfx.sheet(data, 4, 16)
                im = Image.new('RGB', (128, len(rows)))
                for y, row in enumerate(rows):
                    for x, v in enumerate(row):
                        im.putpixel((x, y), pal[v])
                ims.append(im.resize((512, len(rows) * 4), Image.NEAREST))
        out = Image.new('RGB', (1040, sum(i.height for i in ims[::2]) + 10))
        y = 0
        for a, b in zip(ims[::2], ims[1::2]):
            out.paste(a, (0, y))
            out.paste(b, (528, y))
            y += a.height + 10
        out.save(argv[1])
        print(argv[1])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
