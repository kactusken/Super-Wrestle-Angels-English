#!/usr/bin/env python3
"""Game images: export every original and import the English ones (GAME-SPECIFIC - fill in).

The generic image tools (render, edit, compare, contact, build) only need two things from here:

export_all(extracted, out) -> count
    Write every image in the game to out/<id>.png: an indexed PNG in the game's own palette
    (exactly the colours the game uses, transparent colours as tRNS alpha 0), plus out/<id>.json
    with whatever import_images needs to put it back (source file, offset, format, palette
    location, ...). Ids must be stable: they're used in graphics.csv, file names and contact sheets.
    Use tools/pngio.py (no dependencies) and the platform's format module (tim.py, tim2.py, ...).

import_images(images, files) -> count
    images: {id: path to an indexed PNG in the original's palette} - the final English set the
    build picked (hand-made > approved > rendered). files: build.py's Files (get(name) ->
    bytearray, put(name, data)). Convert each PNG back to the game's format and write it into
    its file. Check that sizes and palettes match and stop with a clear message otherwise.

No dependencies here: build.py must run on a plain python3.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngio  # noqa: E402,F401


def export_all(extracted, out):
    return 0


def import_images(images, files):
    if images:
        raise SystemExit(f'{len(images)} English images to import, but tools/gfx.py import_images() '
                         'is not written yet')
    return 0
