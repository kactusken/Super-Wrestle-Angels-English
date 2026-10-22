#!/usr/bin/env python3
"""The name entry's KANJI page as a page of letter pairs: 576 glyphs (9 columns, 64 rows) at
$8B:A259 (bank_8B.txt @ 05a259), refilled with two-letter glyphs so names can be typed in the
same narrow letters as the rest of the English.

  namepage.py show       the page as it would be written, row by row, and how many new glyphs
  namepage.py write      write it as the block's EN line in translation/script/bank_8B.txt

What goes on the page: every capital + vowel (Ka Mi ...), lowercase letter + vowel (ka mi ...,
and the long vowels aa ii ou ...; no Q or X), letter + space and space + capital (to end a word or start one off the pair grid); then the most
common pairs of a corpus of Japanese and English names (both alignments of every word), pairs
that already have a glyph first, until NEW_MAX new glyphs. Grouped by first letter (capitals,
then lowercase, then the space pairs), each group on a new row.
"""
import csv
import string
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

BLOCK = '05a259'
COLS, ROWS = 9, 64
NEW_MAX = 160            # new letter-pair glyphs this page may take (the rest stay free for text)
UP, LO, VOWELS = string.ascii_uppercase, string.ascii_lowercase, 'aeiou'

JAPANESE = '''Ai Aiko Akane Akemi Aki Akiko Ami Asami Asuka Aya Ayaka Ayako Ayame Ayano Ayumi Chiaki
Chie Chieko Chihiro Chika Chikako Chinatsu Chiyo Emi Emiko Eri Erika Etsuko Fumiko Fuyumi Hana
Hanako Haruka Haruko Haruna Hikari Hiromi Hisako Hitomi Honoka Hotaru Izumi Junko Kaede Kana
Kanako Kaori Kasumi Kayo Kazue Kazumi Keiko Kimiko Kiyomi Kotone Kumiko Kyoko Mai Maki Makoto
Mami Mana Manami Mari Mariko Masako Mayu Mayumi Megumi Mei Michiko Midori Mie Miho Mika Miki
Miku Minako Minami Mio Misaki Mitsuko Miwa Miyuki Mizuki Momoko Nana Nanami Naomi Natsuki
Natsumi Nobuko Noriko Rei Reiko Rie Rika Rin Rina Risa Ryoko Sachiko Saki Sakura Sanae Sato Sayaka
Sayuri Setsuko Shiho Shiori Shizuka Sumire Tamaki Tomoko Tomomi Towa Yoko Yoshiko Yui Yuka
Yukari Yuki Yukiko Yumi Yumiko Yuna Yuri Yuriko Kong Bomber Jaguar Lioness Devil Dump Bull
Abe Aoki Arai Endo Fujii Fujita Fukuda Goto Hara Hasegawa Hashimoto Hayashi Hirano Ikeda Inoue
Ishida Ishii Ishikawa Ito Kato Kikuchi Kimura Kobayashi Kondo Kudo Matsuda Matsumoto Miura
Mori Murakami Murata Nakajima Nakamura Nakano Nishimura Ogawa Okada Ono Saito Sakai Sakamoto
Sasaki Shimizu Suzuki Takahashi Takeda Tanaka Ueda Uehara Wada Watanabe Yamada Yamaguchi
Yamamoto Yamashita Yoshida Yokoyama Hokuto Nagayo Asari Toyota Ozaki Kansai Kandori Inoue
Shinobu Akira Aja Chigusa Manami Takako Etsuko Mima Kyoko Shirai'''
ENGLISH = '''Alice Amanda Amy Angela Anna Barbara Betty Beth Brenda Candy Carol Cindy Claire Dana Diana
Donna Elena Emily Emma Eva Grace Helen Holly Iris Jane Jenny Jessica Julia Karen Kate Kelly
Laura Linda Lisa Lucy Madusa Maria Mary Megan Melissa Monica Nancy Nina Olivia Paula Rachel Rita
Rose Ruby Sally Sandra Sarah Sophia Stella Susan Tina Tracy Victoria Wendy Zoe Alex Bob Chris
Dan David Eddie Frank George Jack James Joe John Kevin Mark Mike Nick Paul Peter Ray Rick Sam
Steve Tom Tony Bull Blizzard Thunder Storm Cyclone Venus Luna Star Black Queen Rose Cobra Viper
Smith Johnson Brown Miller Davis Wilson Taylor Moore White Martin Garcia Clark Lewis Walker
Hall Allen Young King Wright Scott Green Baker Adams Nelson Hill Carter Mitchell Turner'''


def existing():
    path = paths.TRANSLATION / 'work' / 'glyph_pairs.tsv'
    with open(path, encoding='utf8') as f:
        return {row['pair'].strip('|') for row in csv.DictReader(f, delimiter='\t')}


def corpus():
    words = (JAPANESE + ' ' + ENGLISH).split()
    with open(paths.TRANSLATION / 'glossary.csv', encoding='utf8') as f:
        for row in csv.DictReader(f):
            words += [w for w in row['english'].split() if w.isalpha()]
    count = Counter()
    for w in words:
        for text in (w + ' ', ' ' + w + ' '):          # starting on the pair grid, or one letter off
            for i in range(0, len(text) - 1, 2):
                if text[i:i + 2].strip():
                    count[text[i:i + 2]] += 1
    return count


def page():
    have = existing()
    must = [c + v for c in UP if c not in 'QX' for v in VOWELS]
    must += [c + v for c in LO if c not in 'qx' for v in VOWELS]      # with the long vowels aa ii ou ...
    must += [c + ' ' for c in LO if c != 'q'] + [' ' + c for c in UP]
    chosen = set(must)
    new = sum(p not in have for p in chosen)
    ranked = sorted(corpus().items(), key=lambda kv: (kv[0] not in have, -kv[1], kv[0]))

    def layout(pairs):
        rows = []
        for group in [c for c in UP] + [c for c in LO] + [' ']:
            members = sorted(p for p in pairs if p[0] == group)
            for i in range(0, len(members), COLS):
                rows.append(members[i:i + COLS])
        return rows

    for pair, _ in ranked:
        if pair in chosen or not (pair[0] in UP + LO and pair[1] in LO + ' ' or pair[0] == ' ' and pair[1] in UP):
            continue
        if pair not in have and new >= NEW_MAX:
            continue
        if len(layout(chosen | {pair})) > ROWS:
            continue
        chosen.add(pair)
        new += pair not in have
    rows = layout(chosen)
    if len(rows) > ROWS:
        raise SystemExit(f'namepage: {len(rows)} rows, {ROWS} fit')
    return rows, sum(p not in have for p in chosen)


def line(rows):
    rows = rows + [[]] * (ROWS - len(rows))
    return ''.join(''.join(r + ['  '] * (COLS - len(r))) for r in rows)


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if argv not in (['show'], ['write']):
        sys.exit(__doc__)
    rows, new = page()
    if argv == ['show']:
        for r in rows:
            print(' '.join(f'{p:2}' for p in r).replace(' ', '·'))
        print(f'{len(rows)} of {ROWS} rows, {sum(map(len, rows))} pairs, {new} pairs not yet in glyph_pairs.tsv')
        return
    path = paths.TRANSLATION / 'script' / 'bank_8B.txt'
    text = path.read_text(encoding='utf8')
    head = f'@ {BLOCK} '
    at = text.index(head)
    end = text.find('\n\n', at)
    block = text[at:end].split('\n')
    block = [b for b in block if not b.startswith('EN ')] + ['EN ' + line(rows) + '\\']
    path.write_text(text[:at] + '\n'.join(block) + text[end:], encoding='utf8')
    print(f'namepage: {path.name} @ {BLOCK}: {sum(map(len, rows))} pairs, {new} pairs not yet in glyph_pairs.tsv')


if __name__ == '__main__':
    main()
