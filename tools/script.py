#!/usr/bin/env python3
"""The game's text: 16-bit glyph codes (glyph * 18) ending in $FFFF, with control words $9x00.

  script.py dump [--force]     ROM -> translation/script/bank_XX.txt (keeps files that exist;
                               --force rewrites them, keeping EN lines and comments by id)
  script.py show OFFSET        decode one string (file offset, hex ok)
  script.py check [FILE...]    translated blocks that don't fit (words, line widths, codes)
  script.py check-part PART    the same for a translator's part file (@ id + EN lines)
  script.py merge PART...      copy the EN lines of part files into translation/script/

Text encoding (docs/TECHNICAL.md "Text"): every word is a glyph code - the glyph's byte offset in
the 12x12 font at $82:8000, glyph number * 18 - or a control word. In the block files:

  {wait}   $9100  wait for a button (▼)          {box}    $9200  clear the window, next page
  {start}  $9D00  start of a conversation        {name}   $9B00  a string variable (name, prefecture);
                                                   {name1}..{name7} $9B01-$9B07 further variables
  {9E}     $9E00  (unknown, before some pages)   {9400} {9600} {9900} {9A00}  match variables
  line breaks ($9F00) are the lines of the block; a line ending in '\\' continues without a break

A '# namewidth=N' comment line in a block sets the width the checker counts for {name} (default 8).

The @ line: offset, words available (without the terminator), and how the string is reached
(table = pointer table entries, which the inserter may move; inplace = must stay where it is).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

FONT_TSV = paths.TRANSLATION / 'tables' / 'font.tsv'
END = 0xFFFF
BREAK = 0x9F00
CONTROL = {0x9100: '{wait}', 0x9200: '{box}', 0x9D00: '{start}', 0x9B00: '{name}', 0x9E00: '{9E}',
           0x9400: '{9400}', 0x9600: '{9600}', 0x9900: '{9900}', 0x9A00: '{9A00}'}
CONTROL.update({0x9B00 + n: '{name%d}' % n for n in range(1, 8)})   # further string variables
CONTROL.update({0x9040: '{9040}', 0x9060: '{9060}', 0x9080: '{9080}'})   # match commentary (pauses?)
CONTROL.update({0x9C00 + n: '{9C%02X}' % n for n in range(256)})   # event commands with a parameter (9C10, 9C20 seen)
TOKENS = {v: k for k, v in CONTROL.items()}
LAST_GLYPH = 1446   # the font ends here; past it bank $82 holds other data


def font_table():
    t = {}
    for line in FONT_TSV.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        n, code, ch, conf = line.split('\t')
        t[int(n)] = ch
    return t


def words(data, off):
    """The words of the string at `off`, without the terminator."""
    out = []
    while True:
        v = data[off] | data[off + 1] << 8
        if v == END:
            return out
        out.append(v)
        off += 2


def is_glyph(v):
    return v % 18 == 0 and v // 18 <= LAST_GLYPH


def decode(ws, table):
    """Lines of text (a $9F00 ends a line)."""
    lines, cur = [], []
    for v in ws:
        if v == BREAK:
            lines.append(''.join(cur))
            cur = []
        elif is_glyph(v):
            cur.append(table.get(v // 18, '{g%d}' % (v // 18)))
        else:
            cur.append(CONTROL.get(v, '{%04X}' % v))
    if cur or not lines:
        lines.append(''.join(cur) + '\\')    # no break at the end
    return lines


# --- English: two half-width letters per glyph ------------------------------------------------

DIALOGUE_LINE = 17   # glyphs per line in the conversation windows
COMMENTARY_LINE = 14   # match commentary window (a 15th glyph sits on the border and stays there)
KEEP_GLYPHS = 270    # 0-269 (ASCII, kana, punctuation) stay: code and untranslated text use them
# Which glyph each letter pair is drawn in, kept from build to build: wrestler and promotion names
# are copied into WRAM and the battery save as glyph codes, so a pair that moved to another glyph
# would garble the names in saves made with an earlier patch. New pairs take free glyphs; pairs no
# longer used keep theirs until the font runs out.
GLYPH_PAIRS = paths.TRANSLATION / 'work/glyph_pairs.tsv'


def read_pairs():
    if not GLYPH_PAIRS.exists():
        return {}
    out = {}
    for line in GLYPH_PAIRS.read_text(encoding='utf-8').splitlines()[1:]:
        g, pair = line.split('\t')
        out[pair.strip('|')] = int(g)
    return out


def write_pairs(saved):
    GLYPH_PAIRS.parent.mkdir(parents=True, exist_ok=True)
    rows = ['glyph\tpair'] + [f'{g}\t|{p}|' for p, g in sorted(saved.items(), key=lambda kv: kv[1])]
    GLYPH_PAIRS.write_text('\n'.join(rows) + '\n', encoding='utf-8')
NAME_GLYPHS = 8      # room counted for {name} (longest English ring name, 16 letters)


def segments(line):
    """[(kind, value)]: ('text', str) runs and ('code', word) tokens of one English line."""
    out, i, buf = [], 0, ''
    while i < len(line):
        if line[i] == '{':
            j = line.index('}', i)
            tok = line[i:j + 1]
            if tok not in TOKENS:
                raise ValueError(f'unknown code {tok}')
            if buf:
                out.append(('text', buf))
                buf = ''
            out.append(('code', TOKENS[tok]))
            i = j + 1
        else:
            buf += line[i]
            i += 1
    if buf:
        out.append(('text', buf))
    return out


def pairs(text):
    """The letter pairs of a text run (an odd run ends in a space)."""
    if len(text) % 2:
        text += ' '
    return [text[k:k + 2] for k in range(0, len(text), 2)]


def english_units(lines):
    """[('pair', 'ab') | ('code', word)] for a block's EN lines, line breaks included."""
    units = []
    for n, line in enumerate(lines):
        cont = line.endswith('\\')
        if cont:
            line = line[:-1]
        for kind, v in segments(line):
            units += [('pair', p) for p in pairs(v)] if kind == 'text' else [('code', v)]
        if not cont:
            units.append(('code', BREAK))
    return units


# {9Cxx} prints a number (years, months, millions of yen): a line over the window's width with the
# digits printed froze the game at bankruptcy (2026-10-21), so count them.
NUMBER_GLYPHS = 2


def line_widths(lines, name=NAME_GLYPHS):
    """Glyphs per line as drawn ({name} counted as `name` glyphs, numbers as NUMBER_GLYPHS)."""
    out = []
    for line in lines:
        line = line[:-1] if line.endswith('\\') else line
        w = 0
        for kind, v in segments(line):
            if kind == 'text':
                w += len(pairs(v))
            elif v & 0xff00 == 0x9B00:
                w += name
            elif v & 0xff00 == 0x9C00:
                w += NUMBER_GLYPHS
        out.append(w)
    return out


# Window records `X 00 Y 00 51 00 01 00 00 PTR 1A` place a string at pixel X, Y. Moved
# where English needs a different layout: {file offset of X: (original, new)}.
# 終 了 on the show schedule were two glyphs 20 pixels apart: "Qu" "it" now touch (12 pixels).
# (Joining them into one string left 了 empty - a zero-length transfer that wiped VRAM.)
RECORD_X = {0x43afc: (0xd8, 0xd0)}


# --- where strings are, and which may move --------------------------------------------------------

# Strings whose address is an immediate operand in code that ran (Mesen code/data log, 2026-10-20):
# they keep their start address even inside a pool.
PINNED = {0x40464, 0x56d14, 0x57000, 0x57420, 0x59ecf, 0x5a01b, 0x9ad60, 0xa428c, 0xa4e30, 0xa5004,
          0xa67c2}
# ... and strings named by window records (`.. 00 51 00 01 02 02 PTR`, 16-bit, same bank) besides
# their table: moved, they showed "ookies applied this month." (play-test, 2026-10-20).
PINNED |= {0x5fc74, 0x5fc6a, 0x5f4a2, 0x5f5f6, 0x5f4c0, 0x5f4fe, 0x5f4ae, 0x69922}


def find_strings(data):
    """[(start, end)] of text strings: glyph codes and $9x00 controls ending in $FFFF, both word
    alignments, at least two kana/kanji (the rest of the ROM yields chance matches)."""
    def textword(v):
        return is_glyph(v) or (v & 0xff) == 0 and 0x9000 <= v <= 0x9fff or v in CONTROL
    found = []
    for par in (0, 1):
        i = par
        while i + 1 < len(data):
            j, n, real = i, 0, 0
            while j + 1 < len(data):
                v = data[j] | data[j + 1] << 8
                if v == END or not textword(v):
                    break
                n += 1
                real += 97 <= v // 18 <= LAST_GLYPH and v % 18 == 0
                j += 2
            if j + 1 < len(data) and data[j] == 0xff and data[j + 1] == 0xff and n:
                # strings without kana/kanji (full-width ASCII, blanks) only join by adjacency
                found.append((i, j + 2, real >= 2 or n >= 3 and real > 0))
                i = j + 2
            else:
                i = j + 2 if j > i else i + 2
    # short strings (1人, 初級) are kept when they sit next to accepted ones: chance matches don't
    ends = {a: (a, b) for a, b, ok in found}
    starts_at = {b: (a, b) for a, b, ok in found}
    ok = {(a, b) for a, b, good in found if good}
    grew = True
    while grew:
        grew = False
        for a, b, good in found:
            if (a, b) in ok:
                continue
            if ends.get(b) in ok or starts_at.get(a) in ok:
                ok.add((a, b))
                grew = True
    return sorted(ok)


def find_tables(data, strings, minimum=3):
    """{string start: [table entry offsets]}: runs of `minimum`+ consecutive 16-bit words that are all
    starts of strings in one bank (pointer tables; shorter runs are often chance)."""
    starts = {}
    for a, b in strings:
        starts.setdefault(a >> 15, set()).add(0x8000 | (a & 0x7fff))
    refs = {}
    for bank, S in starts.items():
        for par in (0, 1):
            run = []
            for i in range(par, len(data) - 1, 2):
                v = data[i] | data[i + 1] << 8
                if v in S:
                    run.append(i)
                    continue
                if len(run) >= minimum:
                    for at in run:
                        p = data[at] | data[at + 1] << 8
                        refs.setdefault(bank << 15 | (p & 0x7fff), []).append(at)
                run = []
    return refs


def find_pools(strings, refs):
    """[[(start, end)...]]: runs of adjacent strings that are all reached through tables."""
    pools, cur = [], []
    for a, b in strings:
        if a in refs and cur and cur[-1][1] == a and a >> 15 == cur[0][0] >> 15:
            cur.append((a, b))
            continue
        if len(cur) >= 2:
            pools.append(cur)
        cur = [(a, b)] if a in refs else []
    if len(cur) >= 2:
        pools.append(cur)
    return pools


class Layout:
    """Strings, pointer tables and pools of the original ROM."""

    def __init__(self, data):
        self.data = data
        self.strings = find_strings(data)
        self.refs = find_tables(data, self.strings)
        self.pools = find_pools(self.strings, self.refs)
        self.pool_of = {a: k for k, p in enumerate(self.pools) for a, _ in p}
        # entries claimed by strings in two banks with the same low address (16-bit pointers):
        # rewriting one would break the other
        owners = {}
        for a, entries in self.refs.items():
            for e in entries:
                owners.setdefault(e, []).append(a)
        self.shared = set()
        for e, v in owners.items():
            if len(v) > 1:
                home = [a for a in v if a >> 15 == e >> 15]
                if len(home) == 1:       # the table's own bank wins
                    for a in v:
                        if a != home[0]:
                            self.refs[a] = [x for x in self.refs[a] if x != e]
                else:
                    self.shared.add(e)

    def place(self, pool, contents):
        """{start: (new start, words)}: the pool's strings packed in their original order from the
        pool's start; pinned strings keep their address (the string before them is padded with
        blanks). Raises ValueError with the overflow if they don't fit."""
        at, end = pool[0][0], pool[-1][1]
        out, prev = {}, None
        for a, _ in pool:
            ws = list(contents[a])
            if a in PINNED:
                if at > a:
                    raise ValueError(f'{at - a} bytes too many before pinned string {a:06x}')
                if prev is not None and at < a:      # the gap stays unused after the previous string's
                    p_at, p_ws = out[prev]            # terminator: blanks inside its text would make one
                    out[prev] = (p_at, p_ws, (a - at) // 2)   # very long line (the attract profiles broke)
                at = a
            out[a] = (at, ws)
            at += 2 * (len(ws) + 1)
            prev = a
        if at > end:
            raise ValueError(f'{(at - end) // 2} words too many')
        return out

    def slack(self, pool, contents):
        """Words left in a pool (negative = over)."""
        need = sum(len(contents[a]) + 1 for a, _ in pool)
        return (pool[-1][1] - pool[0][0]) // 2 - need


def jp_widths(ws):
    out, w = [], 0
    for v in ws:
        if v == BREAK:
            out.append(w)
            w = 0
        elif is_glyph(v):
            w += 1
        elif v & 0xff00 == 0x9B00:
            w += 5
    out.append(w)
    return out


class Block:
    def __init__(self, path, b, data):
        import re
        self.path, self.id = path, b.id
        self.offset = int(b.id, 16)
        m = re.search(r'words=(\d+)', b.meta)
        self.words = int(m.group(1))
        self.how = b.meta.split()[-1]
        self.en = b.english
        self.jp = words(data, self.offset)
        self.dialogue = 0x9200 in self.jp
        self.pooled = False
        self.pool_width = 0     # lists that move together: as wide as their widest original
        m = re.search(r'namewidth=(\d+)', ' '.join(t for k, t in b.lines if k == '#'))
        self.name_width = int(m.group(1)) if m else NAME_GLYPHS

    def limit(self):
        if any(v in self.jp for v in (0x9040, 0x9060, 0x9080)):
            return COMMENTARY_LINE
        return DIALOGUE_LINE if self.dialogue else (self.pool_width or max(jp_widths(self.jp)))

    def problems(self):
        if not self.en:
            return []
        out = []
        try:
            units = english_units(self.en)
            widths = line_widths(self.en, self.name_width)
        except ValueError as e:
            return [str(e)]
        if len(units) > self.words and not self.pooled:
            out.append(f'{len(units)} words, {self.words} available ({len(units) - self.words} over: '
                       f'about {2 * (len(units) - self.words)} letters too many)')
        limit = self.limit()
        for n, w in enumerate(widths):
            if w > limit:
                out.append(f'line {n + 1}: {w} glyphs, {limit} fit ({2 * (w - limit)} letters too many)')
        jp_codes = sorted(v for v in self.jp if v in CONTROL)
        en_codes = sorted(v for k, v in units if k == 'code' and v in CONTROL)
        if jp_codes != en_codes:
            out.append('control codes differ from the original: ' + ' '.join(CONTROL[v] for v in jp_codes)
                       + ' -> ' + ' '.join(CONTROL[v] for v in en_codes))
        return out


def load_blocks(data, files=None):
    import blocks
    files = files or sorted(paths.SCRIPT.glob('*.txt'))
    out = []
    for f in files:
        for b in blocks.BlockFile(f).blocks:
            out.append(Block(f, b, data))
    layout = _layout(data)
    widths = {}
    for k, pool in enumerate(layout.pools):
        widths[k] = max(max(jp_widths(words(data, a))) for a, _ in pool)
    for b in out:
        b.pooled = b.offset in layout.pool_of
        if b.pooled and not b.dialogue:
            b.pool_width = widths[layout.pool_of[b.offset]]
    return out


_LAYOUTS = {}


def _layout(data):
    key = hash(data)
    if key not in _LAYOUTS:
        _LAYOUTS[key] = Layout(data)
    return _LAYOUTS[key]


def pool_problems(data, blocks_):
    """[(pool, words over)] for pools whose translated strings don't fit together."""
    layout = _layout(data)
    by_off = {b.offset: b for b in blocks_}
    out = []
    for pool in layout.pools:
        contents = {}
        for a, _ in pool:
            b = by_off.get(a)
            contents[a] = english_units(b.en) if b and b.en else words(data, a)
        try:
            layout.place(pool, contents)
        except ValueError as e:
            out.append((pool, str(e)))
    return out


def padded(ws, size):
    """`ws` grown to `size` words with blank glyphs. The blanks go at the end of the text, before
    the trailing control codes: blanks after a final line break would be drawn on a line below the
    field (the attract-mode profile froze on one)."""
    def text(w):          # a word, or a ('pair'|'code', value) unit while checking
        return w[0] == 'pair' if isinstance(w, tuple) else is_glyph(w)
    blank = ('pair', '  ') if ws and isinstance(ws[0], tuple) else 0
    end = len(ws)
    while end and not text(ws[end - 1]):
        end -= 1
    return list(ws[:end]) + [blank] * (size - len(ws)) + list(ws[end:])


def build(rom, quiet=False, test=False):
    """Insert every translated block into `rom` (bytearray, headerless) and draw the letter pairs
    into free glyphs of the font. Returns (strings written, pairs used)."""
    data = bytes(rom)
    blocks_ = load_blocks(data)
    bad = [(b, p) for b in blocks_ for p in b.problems() if 'words' in p or 'code' in p]
    bad += [(type('P', (), {'path': paths.SCRIPT, 'id': f'{pool[0][0]:06x}'}), 'pool: ' + m)
            for pool, m in pool_problems(data, blocks_)]
    if bad:
        for b, p in bad[:20]:
            print(f'{paths.show(b.path)} @ {b.id}: {p}')
        raise SystemExit(f'{len(bad)} block(s) do not fit - tools/script.py check')
    # glyphs still needed: kana/ASCII, and every glyph of the strings left in Japanese
    keep = set(range(KEEP_GLYPHS))
    if not test:   # test builds may draw over glyphs that untranslated text still uses
        for b in blocks_:
            if not b.en:
                keep |= {v // 18 for v in b.jp if is_glyph(v)}
    free = [g for g in range(KEEP_GLYPHS, LAST_GLYPH + 1) if g not in keep]
    import halffont
    needed = []
    for b in blocks_:
        for kind, v in english_units(b.en) if b.en else []:
            if kind == 'pair' and v != '  ' and v not in needed:
                needed.append(v)
    saved = {p: g for p, g in read_pairs().items() if g in free}
    if len(set(saved) | set(needed)) > len(free):       # out of room: let go of pairs no longer used
        saved = {p: g for p, g in saved.items() if p in needed}
    spare = [g for g in free if g not in set(saved.values())]
    slot = {'  ': 0}
    for v in needed:
        if v not in saved:
            if not spare:
                raise SystemExit(f'out of glyphs: {len(slot)} letter pairs so far (tools/script.py check)')
            saved[v] = spare.pop(0)
        g = slot[v] = saved[v]
        rom[0x10000 + 18 * g:0x10000 + 18 * g + 18] = halffont.encode_glyph(halffont.bigram(v))
    free = spare
    if not test:
        write_pairs(saved)
    def encoded(b):
        if not b.en:
            return list(b.jp)
        return [slot[v] * 18 if kind == 'pair' else v for kind, v in english_units(b.en)]

    def put(at, ws):
        rom[at:at + 2 * len(ws)] = b''.join(w.to_bytes(2, 'little') for w in ws)

    by_off = {b.offset: b for b in blocks_}
    layout = Layout(data)
    pooled = set()
    for pool in layout.pools:
        placed = layout.place(pool, {a: encoded(by_off[a]) if a in by_off else words(data, a) for a, _ in pool})
        for a, (at, ws, *gap) in placed.items():
            put(at, ws + [END] + [0] * (gap[0] if gap else 0))
            if at != a:
                if layout.shared & set(layout.refs[a]):
                    raise SystemExit(f'text: {a:06x} moved, but its pointer entries are shared with a '
                                     f'string in another bank - add it to PINNED or shorten the pool')
                for entry in layout.refs[a]:
                    rom[entry:entry + 2] = (0x8000 | (at & 0x7fff)).to_bytes(2, 'little')
        pooled |= {a for a, _ in pool}
    n = 0
    for b in blocks_:
        if not b.en:
            continue
        n += 1
        if b.offset in pooled:
            continue
        ws = encoded(b)
        room = max(0, b.limit() - line_widths(b.en, b.name_width)[-1]) if b.en[-1].endswith('\\') else 0
        fill = min(room, b.words - len(ws))       # trailing blanks, only while the last line has room
        ws = padded(ws, len(ws) + fill)
        put(b.offset, ws + [END] + [0] * (b.words - len(ws)))   # the rest unused after the terminator
    for at, (old, new) in RECORD_X.items():
        if data[at] != old:
            raise SystemExit(f'text: window record x at {at:06x} is {data[at]:#x}, not {old:#x}')
        rom[at] = new
    if not quiet:
        print(f'text: {n} strings, {len(slot) - 1} letter pairs in glyphs ({len(free)} glyphs left)')
    return n, len(slot) - 1


def check(files):
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    blocks_ = load_blocks(data, files)
    allb = load_blocks(data) if files else blocks_
    bad = 0
    for b in blocks_:
        for p in b.problems():
            print(f'{paths.show(b.path)} @ {b.id}: {p}')
            bad += 1
    for pool, msg in pool_problems(data, allb):
        print(f'pool {pool[0][0]:06x}-{pool[-1][1]:06x} ({len(pool)} strings): {msg}')
        bad += 1
    pairs_used = {v for b in allb if b.en for k, v in english_units(b.en) if k == 'pair'}
    keep = set(range(KEEP_GLYPHS))
    for b in allb:
        if not b.en:
            keep |= {v // 18 for v in b.jp if is_glyph(v)}
    room = LAST_GLYPH + 1 - len(keep)
    done = sum(1 for b in blocks_ if b.en)
    print(f'{done}/{len(blocks_)} blocks translated, {bad} problem(s); letter pairs {len(pairs_used)} '
          f'of {room} glyphs free')
    return bad


def part_blocks(path):
    """{id: EN lines} of a part file (translators' output: @ id lines and EN lines)."""
    import blocks
    return {b.id: b.english for b in blocks.BlockFile(path).blocks if b.english}


def check_part(path):
    """Check a part file against the ROM without touching the script files."""
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    known = {b.id: b for b in load_blocks(data)}
    bad = 0
    part = part_blocks(path)
    for ident, en in part.items():
        b = known.get(ident)
        if b is None:
            print(f'{ident}: no such block')
            bad += 1
            continue
        b.en = en
        for p in b.problems():
            print(f'{ident} ({b.how.split("=")[0]}): {p}')
            bad += 1
    print(f'{paths.show(path)}: {len(part)} blocks, {bad} problem(s)')
    return bad


def merge(parts):
    """Write the EN lines of part files into translation/script/ (replacing EN lines there)."""
    import blocks
    want = {}
    for p in parts:
        want.update(part_blocks(p))
    n = 0
    for f in sorted(paths.SCRIPT.glob('*.txt')):
        bf = blocks.BlockFile(f)
        changed = False
        for b in bf.blocks:
            if b.id in want:
                b.english = want.pop(b.id)
                changed = True
                n += 1
        if changed:
            bf.save()
    print(f'merged {n} blocks' + (f'; not found: {", ".join(sorted(want))}' if want else ''))


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.exit(__doc__)
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    table = font_table()
    if argv[0] == 'show':
        for line in decode(words(data, int(argv[1], 0)), table):
            print(line)
        return
    if argv[0] == 'check-part':
        return 1 if sum(check_part(Path(f)) for f in argv[1:]) else 0
    if argv[0] == 'merge':
        return merge([Path(f) for f in argv[1:]])
    if argv[0] == 'check':
        return 1 if check([Path(f) for f in argv[1:]]) else 0
    if argv[0] != 'dump':
        sys.exit(__doc__)
    force = '--force' in argv
    found = find_strings(data)
    refs = find_tables(data, found)
    paths.SCRIPT.mkdir(parents=True, exist_ok=True)
    import blocks
    old = {}   # EN lines and comments survive a new dump (matched by id)
    for f in paths.SCRIPT.glob('*.txt'):
        for b in blocks.BlockFile(f).blocks:
            old[b.id] = b
    by_bank = {}
    for a, b in found:
        by_bank.setdefault(a >> 15, []).append((a, b))
    for bank, items in sorted(by_bank.items()):
        out = paths.SCRIPT / f'bank_{0x80 | bank:02X}.txt'
        if out.exists() and not force:
            print(f'kept {paths.show(out)}')
            continue
        lines = [f'# Bank ${0x80 | bank:02X} (file {bank * 0x8000:#07x}): {len(items)} strings.',
                 '# Codes: {wait} {box} {start} {name} {9E} - see tools/script.py. A line ending in \\ has no',
                 '# line break after it. Dialogue: 17 glyphs per line = 34 English letters (two per glyph).',
                 '']
        for a, b in items:
            ws = words(data, a)
            r = refs.get(a)
            how = 'table=' + ','.join(f'{x:#x}' for x in r) if r else 'inplace'
            lines.append(f'@ {a:06x} words={len(ws)} {how}')
            o = old.pop(f'{a:06x}', None)
            lines += [t for k, t in (o.lines if o else []) if k == '#']
            lines += ['JP ' + t for t in decode(ws, table)]
            lines += ['EN ' + t for t in (o.english if o else [])]
            lines.append('')
        out.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        print(f'{paths.show(out)}: {len(items)} strings')
    lost = [i for i, b in old.items() if b.english]
    if lost:
        print(f'note: translated blocks no longer found as strings: {", ".join(sorted(lost))}')


if __name__ == '__main__':
    sys.exit(main())
