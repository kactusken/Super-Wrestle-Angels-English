# Technical notes - Super Wrestle Angels

**Conventions:** numbers in hex with `0x`; addresses are RAM addresses unless marked as file
offsets; `u16`/`u32` little-endian unless marked BE. Findings are marked *verified in game* or
*from the code*.

## Contents
- [Image](#image) · [ROM layout](#rom-layout) · [Executable and memory](#executable-and-memory)
- [Archives and compression](#archives-and-compression) · [Text](#text) · [Images](#images)
- [Open questions](#open-questions)

## Image
`Super Wrestle Angels (J).smc`, 1572864 bytes, SHA-1 `1897062b952636ce0d2f9b714c7cd0b08cdc340b`.

## ROM layout
| | |
|---|---|
| Title | `SUPER WRESTLE ANGELS` |
| Map | LoROM FastROM (`$30`), header at `0x7fc0` |
| Size | 0x180000 bytes (12 Mbit), 48 banks of 32 KB |
| ROM | $80:8000 - $AF:FFFF |
| Cart | type `$02`, SRAM 8 KB |
| Reset | $00:8075 |
| Checksum | `0x0098` (fixed by tools/disc.py on every build) |

Runs of `$00`/`$FF` of 1 KB or more (free space candidates - verify nothing reads them):

| Offset | CPU | Bytes | Fill |
|---|---|---|---|
| `0x006539` | $80:E539 | 0x1a77 | `$ff` |

Only ~6.7 KB of `$FF` free space in the original (bank $80): growing text will almost certainly
need an expanded ROM (12 → 16 or 32 Mbit; `snes.Rom.expand`). *(from the ROM)*

## Executable and memory
- Reset at `$00:8075`: native mode, stack `$1FFF`, DP 0, data bank `$80`, `JSR $810D`, then three
  `JSL`s to `$81:EE16`/`$81:EDFB`/`$81:EDDC`. `$81:EE16` uploads data to the sound CPU through
  `$2140` (the `$A8:81EC` pointer is sound data). Main loop: `JML $80:926D`. *(from the code)*
- Bank $80 holds a library with its own error strings: `grp:` (0x2128), `pal:`, `scroll:`, `bgput:`,
  `kprint:` (0x4c3d), `kwindow:`, `mojigrp:` (0x59f5); each follows a `BRA *` halt. *(from the ROM)*
- "NINTENDO SHVC MULTI5 BIOS Ver2.10" at 0x627: the multitap driver.
- Text buffer for windows: WRAM `$7E:18A0` (16-bit glyph codes), filled by the script reader at
  `$89:BC1D` (`LDA ($23),Y`) and printed by `$80:CD86` (`LDA ($10)`). Wrestler records in WRAM from
  `$7E:28BE` hold their names as 10 glyph codes, copied from the name table at new game.
  *(verified with Mesen traces)*
- Screen: mode 1. BG1 tiles at VRAM 0, map `$E000`; BG2 tiles `$4000`, map `$F000`; BG3 (2bpp) tiles
  `$8000`, map `$B000`. Window text is drawn into BG3 tiles from `$101` on. *(Mesen, setup screens)*

## Archives and compression
- Graphics compression, decompressor `$80:BDD7` (tools/pack8.py): groups of 8 output bytes, a
  control byte per group (MSB first; 1 = new byte, 0 = repeat the byte two back). Source DB:X,
  groups in Y, output through the WRAM port. **Blocks are contiguous and callers continue from the
  previous block's end** (`$8E:8002` -> `$8E:8CF2` -> `$8E:98F2` -> `$8E:A4C6`), so a changed block
  must keep its packed length (pack8.pack_exact pads with redundant literals). *(verified in game)*
- `$8E:8002` (4 KB, 4bpp): YES/NO, 能力値 所属選手 戻る, the main menu bar 人事 練習 運営 指導 殴込
  評価 終了, 技難易度. `$8E:8CF2`: 投 極 打 飛 他 技習得, 形式 反転, small プロレス, 前頁 次頁, 終了,
  年月, 必殺技. `$8E:98F2`: ○△×, 回復 速さ 筋力 耐久, attack/defence stat labels, 評価 信頼 人気, HP.
  `$8E:A4C6`: circled numbers, icons. `$84:EE4C`: the 8x8 2bpp UI font (ASCII, kana). *(decompressed)*

## Text
- **Font**: 12x12, 1bpp, 18 bytes per glyph at `$82:8000` (file 0x10000); glyphs 0-1446 (the rest of
  bank $82 is other data). Each 3 bytes = 2 rows: a 24-bit little-endian value, first row in the
  upper 12 bits, bit 11 leftmost. Order: 0 space, 1 ▼, 2-95 ASCII `!`-`~` (glyph = code - 0x1F), 96
  ±, 97-142 hiragana in gojuon order, 143-167 voiced, 168-176 small kana, 177 ・ 178 。, 179-259
  katakana (same order, then ヴ), 260-269 、「」『』ー゛…‥‼, 270-1446 kanji and symbols in order of
  first use. The full table: `translation/tables/font.tsv` (read from the glyphs, unsure ones checked
  against the script). *(verified)*
- **Encoding**: every word of text is a glyph code = glyph number × 18 (the glyph's byte offset in
  the font), little-endian, `$FFFF` ends a string, `$0000` is a blank. Control words: `$9F00` line
  break, `$9100` wait for a button, `$9200` clear the window, `$9D00` start of a conversation,
  `$9E00` (unknown), `$9B00`-`$9B07` string variables (names, prefectures, promotions), `$9400`
  `$9600` `$9900` `$9A00` match variables. No compression. *(verified)*
- **Where**: ~1280 strings in banks $83-$94 (tools/script.py dump). Most are reached through tables
  of 16-bit pointers within the string's bank (some tables sit in another bank, e.g. bank $93's
  scouting talks from a 91-entry table at file 0x4c259). Others are walked or fixed-length fields.
  Some messages are built from several strings that overwrite each other on screen (the funds /
  emblem header) or follow game-printed numbers.
- **The English**: two 6-pixel letters per 12x12 glyph (tools/halffont.py); every letter pair used
  gets one of the glyphs freed from kanji (270-1446, ~950 needed). Strings reached only through
  tables (n >= 3 entries, checked against Mesen's data-read log) are repacked within their original
  span and the tables rewritten ("pools", tools/script.py Layout); the rest keep their place and
  length. 11 strings that executed code loads by address stay put (PINNED).
- Some text is drawn with the 8x8 UI font (`$84:EE4C`) or is part of graphics (menu bar, labels,
  title menu, name entry buttons): see Images.

## Images
- Boxed labels: tools/labels.py reletters them in the original colours (menu bar done, verified in
  game). Still Japanese: the title menu (エキシビション 団体経営 ミニ・リーグ戦 トーナメント システム), the
  name entry buttons (ひらがな カタカナ アルファベット 漢字 スペース 終了, P1団体名), 年月, the small
  プロレス after promotion names, the stat labels in `$8E:8CF2`/`$8E:98F2`, the title logo.

## Late game, 2026-10-21
- Date: `$7E:71F0` month counter (16-bit, 1 = April of year 1; shown as month = value + 3, starting in
  April); `$7E:71F2` the play length in years. `$8A:8172` advances the month; in April
  (`$8A:FA13` returns 4) it ends the game when year - 1 >= the length (`$8A:81E9`), or at
  `$7E:720A` = `$FF00` (another way out). Funds: 32-bit yen at `$7E:5D3D` (the statement's NOW).
- Show screen banners are compressed 8x2 templates in the run at file 0x1edb5.. (header
  `W H 01 01 00`, then a pack8 stream of tilemap words): SOLD OUT 0x1ef8c, 超満員 0x1efa6,
  満員 0x1efc1 (its 員 was 超満員's $74 $75), 最終戦 0x1f03b.
- Ending awards: BG1 tiles $A6:CBA9 (0-$7F) + $A6:D791 ($80-$E5, continues from it), maps
  $A6:E547 / $A6:E6CB; the KING screen map $A6:E016.
- Year-end ranks: tiles $8A:9191 + $8A:9DE7 (continues), 18 button maps of 5x2 at $8A:A0C5 +
  0x15 k (3 groups each). にんき is 8x8 text at file 0x508dc.
- Letter-pair glyphs are kept from build to build (translation/work/glyph_pairs.tsv): names sit in
  WRAM and the battery save as glyph codes, and a savestate from a build that assigned the pairs
  differently shows garbled names (seen in an old state's ending: "Beb!ty Ichigaya").

## Open questions
- Is the ROM the No-Intro dump? CRC32 `b697f8a0`, headerless, internal checksum valid - not yet
  compared with the No-Intro DAT.
- `$9E00`: shown before some scouting pages - picture or music cue?
- Pointer tables with fewer than 3 entries are not rewritten; strings they reach stay in place.

## Button tiles $8F:C166 (exhibition, tournament, league), 2026-10-20

- BG1 tiles 0-$7F, 4bpp. START button $3A-$41 / $43-$49; tournament WATCH $1A-$21 / $2A-$31,
  SKIP $22-$29 / $32-$39; the bracket's player boxes オート $4B $4C / $56 $57, 1P $4D $50 / $58 $5B
  (2 and 3: $4E, $4F / $59, $5A); circles $51-$55; a 超満員札止 banner $60-$7F.
- The START button's tilemap is a compressed template at file 0x1ee3b.. (inside a run of
  templates with 2-word trailers, copied to WRAM $7F:04AC and then to the screen). Edited in place
  with the same packed length (labels.py START_MAP).
- Wrestler data (X on a wrestler in exhibition, league, tournament): the move type buttons
  投 極 打 飛 他 are BG3 tiles $15B-$164 over $16B-$174 = $5B-$64 / $6B-$74 of $8F:D6D9, placed by
  code (no tilemap in the ROM); BG1 draws the button frames. *(verified in game: exhibition, league,
  tournament, 2026-10-22)*
- League setup's 参加チーム数 is BG3 (2bpp) text: tiles $65-$6A, $48-$4A / $75-$7A, $58-$5A of
  $8F:D6D9 (the strips block), map $83:E3C8 (9x2).
- Decompressor calls per screen (trace exec $80:BDD7): League loads $83:E28C, E278, E418, EE9C,
  E1FB, E3C8, EDBA, E249, EEBE, EED1 and $8F:C166, CD50, BBDA, D6D9, CAC8.

## Promoter mode graphics, 2026-10-20

- `tools/gfxfind.py VRAM.bin OFFSET`: the ROM offset whose decompression gives those VRAM bytes
  (any group start; the two bytes before give the state). Found the blocks below in seconds.
- Name entry: $85:A9A0 (BG1 tiles 0-$7F): buttons 5x2 tiles each, P1団体名 label $3F-$4D.
  選手名 (mask names) is $5C-$5E + $4D of the same block; 略称名 (the short name, second screen) is
  VRAM tiles $9F-$A6 = $1F-$26 of $85:B45D (tilemap $85:B9D1).
- Main screen / training tabs: BG1 tiles 0-$7F = $8E:8002, $80-$FF = $8E:8CF2. 必殺技 and 技難易度 are
  assembled from tiles of both (labels.py TABS). The training screen scrolls BG1/BG3 by 256: the
  visible maps are the second pages ($7400, $5C00).
- Training AP labels: two $FF-terminated 8x8 strings at 0x45434 (top row) and 0x4544b (bottom).
- Window records `.. 00 51 00 01 02 02 PTR` (bank $8B and others) name strings by 16-bit address.
- Window records `X 00 Y 00 51 00 01 00 00 PTR 1A` (show schedule buttons at file 0x43ac8..) place
  a string at pixel X, Y; an empty string ($FFFF only) in one of them corrupts VRAM.
- Foreign promotions (alliance menu): records of 0x22 bytes from $8A:DAE6 (file 0x55ae6), each
  the name (4 glyphs + $FFFF) then data. A new game copies them to WRAM from $7E:711E (0x2A bytes
  apart, name at +4; $8A:C7B9), and the menu reads that copy: a game started on an older build
  keeps the old names. In tools/script.py EXTRA (no kana, so not found as text). *(verified in game)*
- CPU promotion cards (new promoter game): names from the pointer table at file 0x88356 (bank $91,
  strings in $8B), right-aligned against the small PRO by pixel offsets at 0x88326 (one word each,
  12 * (6 - glyphs)). The English names are unpadded and the offsets recomputed from them
  (tools/script.py NAME_X). *(verified in game)*
- Name entry keeps its tile block in WRAM at $7F:3518 as well as VRAM.
- Name entry's kanji page: 576 glyph codes at file 0x5a259, 9 per row (64 rows, 8 visible). Any
  glyph codes work there (letter pairs, tools/namepage.py). *(verified in game)*
- Match card setup: BG1 tiles 0-$7F = $8F:9209 (0x200 groups, 24-bit pointer at $82:C3F1).
- Window bytecode: interpreter at $80:97BA, opcode table $80:97D7 (one byte opcode, X = 2*op).
  $0D = load a compressed tilemap (24-bit pointer to a 5-byte header: w, h, ?, flag, ?), $0E =
  print an 8x8-font string (16-bit pointer in the script's bank; $80:9AB8 -> $80:A574).
- Show match screen: BG1 tiles 0-$7F = $8F:C166, $80+ = $8F:CAC8 (0x98 groups, unpacked with A=7).
