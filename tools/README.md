# Tools

Everything is Python 3 and runs from the project folder or anywhere else; every tool has `--help`
(or prints its usage). Folder locations come from [paths.py](paths.py) and can be moved with the
folder options. `build.py`, `make_patches.py` and everything they import use only the standard
library; the tools marked *Pillow* or *capstone* need `.venv` (`pip install -r requirements.txt`).

Tools marked *game* are specific to Super Wrestle Angels.

## Used by the build

| Tool | What it does |
|---|---|
| [../build.py](../build.py) | builds the translated image (text steps, code patches, images, write-back) |
| [paths.py](paths.py) | every folder location and the folder options |
| [image.py](image.py) | the output image: fresh copy or fast restore from a journal; checksums |
| [codepatch.py](codepatch.py) | applies code patch tables, checking the original bytes first |
| [catalog.py](catalog.py) | the image catalogue: which file the build uses, fingerprints, stale renders |
| [gfx.py](gfx.py) | *game*: exports the original images, imports the English ones |
| [pngio.py](pngio.py) | PNG reading and indexed PNG writing without dependencies |
| [blocks.py](blocks.py), [textdb.py](textdb.py) | message block files; every translatable string as one list |
| [disc.py](disc.py) | the cartridge as one file (`/rom.sfc`): copier header kept, checksum fixed on write |
| [snes.py](snes.py) | header, LoROM/HiROM/ExHiROM map (CPU address ↔ file offset), checksum, expansion, free space |
| [bps.py](bps.py) | BPS patches: make and apply (release patches) |
| [snesgfx.py](snesgfx.py) | planar 1/2/4/8bpp and Mode 7 tiles, BGR555 palettes, PNG sheets |
| [tbl.py](tbl.py) | `.tbl` character tables: decode, dump, encode |
| [script.py](script.py) | *game*: the text - dump to `translation/script/`, check, letter pairs into the font, repack pools, insert (build step) |
| [halffont.py](halffont.py) | *game*: the 5x10 English letters and the two-letters-per-glyph builder |
| [pack8.py](pack8.py) | *game*: the graphics compression ($80:BDD7), unpack/pack/pack_exact |
| [gfxfind.py](gfxfind.py) | *game*: finds the ROM offset whose decompression gives bytes seen in a VRAM dump |
| [gfxsurvey.py](gfxsurvey.py) | *game*: replays savestates, logs every decompressed block and screenshots the screens, for review |
| [labels.py](labels.py) | *game*: reletters boxed UI labels, the title menu and the small PRO (build step) |
| [text8.py](text8.py) | *game*: text in the 8x8 UI font (move records, label lists): dump/check, build step |
| [strips.py](strips.py) | *game*: reletters pre-rendered text strips and their tilemaps (exhibition header/tabs) |

## Checking

| Tool | What it does |
|---|---|
| [check.py](check.py) | runs every check (`--quick` for the pre-commit hook, `--control` for a lossless-build proof) |
| [lint.py](lint.py) | text: leftover source text, control codes, line/char/byte limits, glossary |
| [status.py](status.py) | how far along the text and images are |
| [stepcheck.py](stepcheck.py) | run one build text step against `extracted/` (no image, nothing written) and list what it changed |
| [records.py](records.py) | fixed-record text tables (names, items, menus of records): `dump` the CSV, `verify` the layout, `measure` unknown data, build step - configure `TABLES` |

## Images (the kit's image workflow; this game's graphics are relettered by labels.py and strips.py)

| Tool | What it does |
|---|---|
| [fill_text.py](fill_text.py) | fills repeated strings from a source → English table |
| [render.py](render.py) | *Pillow*: automatic English renders, only redrawing what changed |
| [edit.py](edit.py) | *Pillow*: hand-edit workflow - start, check, approve, reset, sheets |
| [compare.py](compare.py) | *Pillow*: original \| English sheets |
| [contact.py](contact.py) | *Pillow*: every original image on labelled sheets |

## Releasing

| Tool | What it does |
|---|---|
| [../make_patches.py](../make_patches.py) | builds every variant, makes and re-verifies the BPS patches, README.txt and the zip |

## Research

| Tool | What it does |
|---|---|
| [extract.py](extract.py) | copies the ROM to `extracted/rom.sfc` and exports the images (*game*: `unpack()`) |
| [sjisscan.py](sjisscan.py) | finds Shift-JIS text in binary files |
| [relsearch.py](relsearch.py) | relative search for text in an unknown encoding (kana orders, ASCII, 8/16-bit) |
| [dis65816.py](dis65816.py) | 65816 disassembler (M/X flags followed through REP/SEP) and reference/pointer search |
| [mesen.py](mesen.py) | drives Mesen 2 headless: input, screenshots, savestates, memory dumps, access traces, code/data log |
