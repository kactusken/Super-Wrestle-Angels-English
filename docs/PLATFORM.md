# Platform notes: Super Famicom / SNES

Starting notes for cartridge games. Add to this file (and to the kit's copy) as you learn more.

## The ROM
- Dumps are verified against **No-Intro** (not Redump): headerless `.sfc`. A `.smc` may carry a
  512-byte copier header (size = n × 32 KB + 512); the tools drop it for reading and keep it on
  write, but the patch only applies to a ROM with the same header state, so say which one in the
  README (and prefer headerless).
- `tools/snes.py info ROM`: title, map mode, size, SRAM, checksum. LoROM: 32 KB banks at
  `$xx:8000-$FFFF`, file offset = `(bank & 0x7f) * 0x8000 + (addr & 0x7fff)`. HiROM: 64 KB banks
  at `$C0-$FF`. FastROM games (map byte bit 4) run from the `$80+` mirror, so pointers in the code
  usually carry `$80`-`$FF` bank bytes.
- There is no file system: `tools/disc.py` presents the whole ROM as one file, `/rom.sfc`, so
  build.py, extract.py and check.py work as for discs. A text step does
  `rom = files.get('/rom.sfc')`, changes it and `files.put('/rom.sfc', rom)`.
- **Checksum**: `disc.py` write_file() fixes the internal checksum (and complement) on every build.
  Emulators only warn about a bad one, but flash carts and some patchers check it.
- **Space**: a ROM can't grow files in place - every byte of text that grows must go into free
  space (`snes.py info` lists runs of `$00`/`$FF`; check in an emulator that nothing reads them) or
  into an **expanded** ROM (`snes.Rom.expand`, e.g. 12 → 16 or 32 Mbit; LoROM up to 4 MB). After
  expanding, check the game doesn't read past its original end expecting a mirror, and that SRAM
  (LoROM: `$70-$7D:0000-7FFF`) still maps.
- Pointers: text pointers are often 16-bit within a bank, with the bank byte loaded separately (or
  fixed in the code). Moving a block to another bank means changing that code too.
  `tools/dis65816.py refs ROM ADDR` finds pointers and code that refer to an address.
- `build.py` `to_offset()`: for a SNES project it is
  `snes.Rom(files.get('/rom.sfc')).to_file(addr)`; code patch tables use bytes, not 32-bit words.

## Code
- CPU: 65C816 (5A22). Instruction lengths depend on the **M** (accumulator) and **X** (index) flags
  set by `REP`/`SEP`: a listing that starts in the wrong state turns to nonsense
  (`tools/dis65816.py --m16/--x16`). Also mind the **data bank** (`PLB`) and **direct page** (`TCD`)
  registers: `LDA $1234` reads from the current data bank, `LDA $12` from the direct page.
- Hooks: `JSL` to free space and `RTL` back; preserve the registers and flags the original code
  relied on (`PHP`/`PLP`, `REP`/`SEP` back to the caller's sizes). Assemble with
  [asar](https://github.com/RPGHacker/asar) and paste the bytes into a code patch table, or record
  them in the project's tools; keep the source next to the bytes.
- Debugger: **Mesen** (2.x) has breakpoints on read/write/execute, a trace logger, an event viewer
  and VRAM/tilemap/palette viewers - the fastest way to find where text is read and drawn. Test
  final builds in more than one emulator (Mesen, bsnes/higan, Snes9x).
- Many games compress graphics (and sometimes text): LZ variants are common. Find the decompressor
  by breaking on writes to VRAM (`$2118/$2119`) or DMA from the buffer, then write a matching
  compressor (or store English data uncompressed if the code can be pointed past the decompressor).

## Text
- Japanese SNES games use their **own character codes**, not Shift-JIS: find them with a relative
  search (`tools/relsearch.py ROM みらくる`) on a word seen on screen, then grow a `.tbl` table
  (`tools/tbl.py`). Kanji usually follow the kana in an order of the game's own.
- **Dakuten**: many 8x8 games draw ゛/゜ as a separate tile on the row above the letter. The
  English line can then use both rows for 8x16 text or the top row is simply blank.
- Fonts: 8x8 (1bpp or 2bpp) or 16x16 (four 8x8 tiles, or 2 bytes per row). English options, from
  least to most work: fixed-width 8x8 English letters in the kana slots; 8x16; a variable-width font
  (VWF) drawn by a code hook into a tile buffer. Line and window widths limit the text: count tiles.
- Text is drawn into a BG tilemap: the number of free VRAM tiles limits what a VWF can draw.

## Images
- Tiles: 2bpp (4 colours), 4bpp (16), 8bpp (256), Mode 7 (8-bit linear). Palettes are BGR555
  words in CGRAM; colour 0 is transparent. `tools/snesgfx.py view/scan` draws tiles from the ROM to
  find fonts and title graphics; graphics that only look like noise there are compressed.
- Title screens and logos are tiles plus a tilemap: changing the picture often means changing both.

## Patches and screenshots
- Release patches are **BPS** (`tools/bps.py`, made by make_patches.py): they check the source CRC32,
  so players are warned about a wrong or headered ROM. Patchers: Rom Patcher JS (browser), Flips,
  MultiPatch (macOS).
- Native resolution is 256x224 (256x239 overscan; 512x448 hi-res/interlace). Take shots at 1x
  (Mesen: no filter, no aspect correction).
