#!/usr/bin/env python3
"""Unpack the original image into extracted/ and export the original images for review.

  extract.py [--all] [--no-images] [--force]

Writes:
  extracted/<path>          every file on the disc (empty padding files are skipped unless --all)
  extracted/...             GAME-SPECIFIC: unpacked archives, decompressed overlays (unpack() below)
  review/images-original/   every image, via gfx.export_all() (unless --no-images)

build.py reads the original image directly; extract.py is for the research, checking and
translating tools. Files already extracted are kept unless --force.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disc  # noqa: E402
import gfx  # noqa: E402
import paths  # noqa: E402


def unpack(extracted):
    """GAME-SPECIFIC: unpack archives / decompress files under `extracted` for the other tools."""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--all', action='store_true', help='also extract empty padding files')
    ap.add_argument('--no-images', action='store_true', help="don't export the original images")
    ap.add_argument('--force', action='store_true', help='extract again even if files exist')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    if not paths.ROM.exists():
        sys.exit(f'put the original image in {paths.show(paths.ROM_DIR)} (or pass --rom): {paths.ORIGINAL_NAME}')
    d = disc.Disc(paths.ROM)
    for e in d.files():
        out = paths.EXTRACTED / e.path.lstrip('/')
        if out.exists() and out.stat().st_size == e.size and not args.force:
            continue
        if not args.all and d.is_empty(e):
            print(f'  skipped {e.path} ({e.size} bytes of padding)')
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        d.extract_file(e, out)
        print(f'{e.path} ({e.size} bytes)')
    unpack(paths.EXTRACTED)
    if not args.no_images:
        n = gfx.export_all(paths.EXTRACTED, paths.ORIGINAL_IMAGES)
        if n:
            print(f'{n} images -> {paths.show(paths.ORIGINAL_IMAGES)}')


if __name__ == '__main__':
    main()
