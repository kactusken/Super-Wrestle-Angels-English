# Translation

## Where the text is

| File | Holds | Checked by |
|---|---|---|
| `translation/script/bank_XX.txt` | every string of the game, one file per ROM bank (dumped by `tools/script.py dump`) | `tools/script.py check`, `tools/lint.py` |
| `translation/tables/font.tsv` | the 12x12 font: glyph number, code, character | read from the glyphs |
| `translation/glossary.csv` | names and terms | `tools/lint.py` |
| `translation/work/` | `glyph_pairs.tsv` (which glyph holds each letter pair, kept between builds) and `gfx_blocks.csv` (graphics blocks the game was seen loading) | |

Rough content per bank: $83 prefectures, belts, match labels; $84/$85 move lists; $88/$89 system
messages, match commentary, generic conversations, victory quotes; $8A venues; $8B setup and
management menus; $8D show booking; $91 misc; $92 wrestler names; $93/$94 scouting talks,
tryout calls, profiles, move commands, events.

## File format

Message blocks (`tools/blocks.py`): `@ id words=N how`, `JP` lines (reference), `EN` lines.
Each line is one line on screen; a line ending in `\` has no line break after it. Codes:
`{box}` new window, `{wait}` wait for a button, `{start}` conversation start, `{name}` and
`{name1}`-`{name7}` strings the game fills in, `{9E}` and `{9400}` `{9600}` `{9900}` `{9A00}`.
`words=N`: the space the string had (glyphs + codes + line breaks); English uses one glyph per two
letters. `inplace` strings must fit N; `table` strings are repacked with their neighbours and only
the group must fit (`tools/script.py check` reports both). `# namewidth=N` in a block tells the
checker how wide its `{name}` is.

## Style guide

- Speaker labels: `President:` for 社長, the wrestler's short name for 選手 (`Megumi:`, `Kong:`),
  `Wrestler:` when the speaker isn't known. No quote marks after a label; no indent.
- Names: Western order, glossary spellings (shared with the Wrestle Angels Survivor 2 project).
  Honorifics dropped except `senpai`.
- `・・・` -> `...`. Money stays `AP`. Wrestling terms in plain English (glossary).
- Dialogue windows: 3 lines of 34 letters. Menu fields: the Japanese width, 2 letters per glyph,
  padded with spaces.

## Glossary

`translation/glossary.csv` (`japanese, english, notes`).

## Decisions

| Decision | Why |
|---|---|
| English drawn as two 6-pixel letters per glyph (letter pairs replace the kanji glyphs) | no code changes; 34 letters per line |
| Kanji page of the name entry left blank | its 576 glyphs are needed for letter pairs |
| Wrestler names shortened where the name table is full (C. Nagahara, short names Beauty, Rei, Kong ...) | the table must fit its bytes |
| Title menu: EXHIBITION / PROMOTER (団体経営) / LEAGUE / TOURNAMENT / SYSTEM | |
| Menu bar: STAFF TRAIN ADMIN COACH RAID INFO END; panels STATS ROSTER BACK | the menu bar's 32-pixel buttons |
| Promotion names after a name: small "PRO" (was プロレス) | |
| Dates: 年 / 月 after the numbers -> YR / MO ("1 YR 4 MO") | |
| Event pictures with drawn Japanese stay as they are (heartbreak, Ex Tag League letter, police chief, retirement) | the text box says what happens; the drawn words are scenery |

## What stays untranslated

- The title logo (art).
- The hiragana/katakana pages of name entry (players may still enter Japanese names).
- ◎○△× marks (symbols).
- Event pictures with drawn text (e.g. the heartbreak picture).
