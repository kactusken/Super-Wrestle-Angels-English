# Images with text

Every image with text has a row in `translation/graphics.csv` (columns: see `tools/catalog.py`).
The build uses, in this order: a hand edit in `translation/images-handmade/`, an approved image in
`translation/images-approved/`, an automatic render in `translation/images-rendered/`, else the
original. All three hold indexed PNGs in the game's palette.

## Automatic renders

Plain labels (one background + one text colour, optionally an outline) are drawn by
`.venv/bin/python tools/render.py` from the row's `english` (`' / '` forces a line break; `font`,
`align`, `boxes` hints). It only redraws rows that changed since they were drawn. Look at the
result with `tools/compare.py`, then `tools/edit.py approve <image>` freezes it.

## Hand edits

1. Find the image: `.venv/bin/python tools/edit.py list <words>`, or `review/compare/`, or
   `review/contact-sheets/`.
2. `.venv/bin/python tools/edit.py start <image>` → edit `translation/images-handmade/<image>.png`
   (same size; the original palette is best, RGB works too and is snapped on approve; transparent
   stays transparent). `<image>_original.png` next to it is for reference.
   - Aseprite: opens indexed; save as PNG.
   - GIMP: keep Image › Mode › Indexed; File › Export As › PNG over the same file.
   - Photoshop: Image › Mode › Indexed Color with the existing palette.
3. `.venv/bin/python tools/edit.py check <image>` → `OK`, or `!` lines saying what to fix;
   `<image>_check.png` shows the original above yours.
4. `python3 build.py` and look at it in the emulator.
5. `.venv/bin/python tools/edit.py approve <image>` → moved to `images-approved/`, marked done.

Undo: `edit.py reset <image>`. Several images: names, commas, ranges (`0013_020-0013_052`) or
patterns (`0013_*`).

## Many similar images as one sheet

`edit.py sheet start <name> <images>` writes `translation/images-handmade/sheets/<name>.png`:
original | English pairs at real size. Edit the right-hand images (magenta = transparent), then
`sheet check`, `sheet split` or `sheet approve`.
