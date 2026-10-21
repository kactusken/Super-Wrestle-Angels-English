#!/usr/bin/env python3
"""Build the release variants and make a verified patch for each (xdelta for discs, BPS for cartridges).

  python3 make_patches.py [--version v1.0] [--allow-handmade] [--any-rom]
      -> release/<GAME_FILE> English Patch <version>/ (patches, README.txt) + .zip

For each variant in VARIANTS this runs build.py, makes a patch (FORMAT) from the clean original to
the result, applies it again and checks that it reproduces the build exactly. Patches never stack:
each applies to the clean original on its own (say so in the README).

Refuses to run while translation/images-handmade/ holds unapproved images (--allow-handmade) or
automatic renders are out of date (run tools/render.py), when rom/ isn't the expected original
(--any-rom), and for a versioned release without tools/paths.py AI_DISCLOSURE. Every variant is built into the same staging image (build/release/staging.<ext>), so
after the first one each build only restores what the previous one changed (tools/image.py).
Disc images need the xdelta3 program (Debian/Ubuntu: apt install xdelta3), or give its path with
--xdelta; cartridge BPS patches are made by tools/bps.py.
"""
import argparse
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
import catalog  # noqa: E402
import image  # noqa: E402
import paths  # noqa: E402

# (output name, build.py options, description for the README)
VARIANTS = [
    (f'{paths.GAME_FILE} (English)', ['--unlocks', 'none'], 'The English translation.'),
    # (f'{paths.GAME_FILE} (English) (All Unlocked)', ['--unlocks', 'all'], 'The English translation with every unlock.'),
    # (f'{paths.GAME_FILE} (Japan) (All Unlocked)', ['--no-translation', '--unlocks', 'all'], 'The original game with every unlock.'),
]

# Cartridge ROMs get BPS patches (tools/bps.py, standard library; patchers check the source CRC32),
# disc images xdelta3 (fast on multi-gigabyte images).
FORMAT = 'bps' if paths.PLATFORM.upper() in ('SNES',) else 'xdelta'
MEDIUM = 'cartridge ROM' if FORMAT == 'bps' else 'disc image'

# -S none: no secondary compression, which some patchers (Rom Patcher JS) can't read.
# -A=: no application header (it would record local file paths).
# Add '-B', str(1 << 30) for DVD images if a patch comes out large because data moved far.
XDELTA_ENCODE = ['-e', '-9', '-S', 'none', '-A=', '-f']

APPLY_HELP = {'xdelta': '''\
How to apply
------------
You need your own copy of the original disc image:
  {name}
  {size} bytes, CRC32 {crc32}, MD5 {md5}
  SHA-1 {sha1}

1. {pick}
2. Apply it to the original image with an xdelta tool:
     - Delta Patcher (Windows, macOS, Linux)
     - Rom Patcher JS in a web browser (fine for CD images; DVD images may be too big for it)
     - command line: xdelta3 -d -s "original{ext}" "patch.xdelta" "patched{ext}"
3. Load the patched image in your emulator.

Patches
-------
''', 'bps': '''\
How to apply
------------
You need your own copy of the original cartridge ROM:
  {name}
  {size} bytes, CRC32 {crc32}, MD5 {md5}
  SHA-1 {sha1}

1. {pick}
2. Apply it to the original ROM with a BPS patcher:
     - Rom Patcher JS in a web browser
     - Floating IPS (Flips) on Windows or Linux, MultiPatch on macOS
   The patcher checks the ROM first: if it refuses, the ROM is a different dump or has a
   512-byte copier header the original above doesn't have (or the other way round).
3. Load the patched ROM in your emulator.

Patches
-------
'''}

LEGAL = ('A non-commercial fan project, not affiliated with or endorsed by the makers or publishers of '
         '{game}. {game} and its contents belong to their respective owners. '
         'These patches contain no game data and no playable image; you need your own copy of the '
         'original {medium}. The tools and documentation are released under the MIT License.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--version', default='dev')
    ap.add_argument('--xdelta', default='xdelta3', metavar='PROGRAM')
    ap.add_argument('--any-rom', action='store_true', help="skip the check that rom/ is the expected original")
    ap.add_argument('--allow-handmade', action='store_true', help='build even with unapproved hand edits')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))

    if args.version != 'dev' and not paths.AI_DISCLOSURE.strip():
        sys.exit('tools/paths.py AI_DISCLOSURE is empty: say how AI helped and what a person did '
                 '')
    wip = catalog.handmade_in_progress()
    if wip and not args.allow_handmade:
        sys.exit(f'{paths.show(paths.HANDMADE)} has unapproved images, which the build would include:\n  '
                 + ', '.join(wip) + '\napprove or reset them (docs/EDITING.md), or pass --allow-handmade')
    missing, changed, _ = catalog.stale()
    if missing or changed:
        sys.exit(f'{len(missing) + len(changed)} automatic renders are out of date - run tools/render.py first')
    if FORMAT == 'xdelta' and not shutil.which(args.xdelta):
        sys.exit(f'{args.xdelta} not found; install xdelta3 or pass --xdelta PATH')

    rom = paths.ROM
    print(f'checking {paths.show(rom)}')
    source = image.checksums(rom)
    if source != paths.ORIGINAL and not args.any_rom:
        sys.exit(f'{rom} is not the expected original:\n  got      {source}\n  expected {paths.ORIGINAL}\n'
                 '(--any-rom makes patches for it anyway)')

    changelog = ROOT / 'CHANGELOG.md'
    if args.version != 'dev' and changelog.exists() and f'## {args.version}' not in changelog.read_text(encoding='utf-8'):
        print(f'note: CHANGELOG.md has no "## {args.version}" section yet')
    title = f'{paths.GAME} English Patch {args.version}'
    base = f'{paths.GAME_FILE} English Patch {args.version}'   # folder and zip
    out = paths.RELEASE / base
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stage = paths.BUILD / 'release'
    pick = (f'Pick one of the .{FORMAT} patches below (each applies to the original on its own).'
            if len(VARIANTS) > 1 else f'Take the .{FORMAT} patch below.')
    notes = APPLY_HELP[FORMAT].format(name=paths.ORIGINAL_NAME, ext=rom.suffix, pick=pick, **source)
    for name, options, description in VARIANTS:
        print(f'\n=== {name}')
        subprocess.run([sys.executable, str(ROOT / 'build.py'), '--rom', str(rom), '--build', str(stage),
                        '--name', 'staging', '--skip-verify', *options], check=True)
        built = stage / ('staging' + rom.suffix)
        patch = out / f'{name}.{FORMAT}'
        check = stage / 'staging.check'
        if FORMAT == 'bps':
            import bps
            patch.write_bytes(bps.make(rom.read_bytes(), built.read_bytes()))
            check.write_bytes(bps.apply(rom.read_bytes(), patch.read_bytes()))
        else:
            subprocess.run([args.xdelta, *XDELTA_ENCODE, '-s', str(rom), str(built), str(patch)], check=True)
            subprocess.run([args.xdelta, '-d', '-f', '-s', str(rom), str(patch), str(check)], check=True)
        target = image.checksums(built)
        if image.checksums(check) != target:
            sys.exit(f'{patch} does not reproduce {built}')
        check.unlink()
        cue = stage / 'staging.cue'
        if cue.exists():  # CD images: a .cue naming the patched image
            (out / f'{name}.cue').write_text(cue.read_text().replace(built.name, name + rom.suffix))
        print(f'{paths.show(patch)}: {patch.stat().st_size} bytes, verified')
        notes += (f'\n{patch.name}\n{textwrap.fill(description, 78, initial_indent="  ", subsequent_indent="  ")}\n'
                  f'  Result: {target["size"]} bytes, CRC32 {target["crc32"]}, SHA-1 {target["sha1"]}\n')

    if paths.AI_DISCLOSURE.strip():
        notes += '\nAI disclosure\n-------------\n' + textwrap.fill(paths.AI_DISCLOSURE.strip(), 78) + '\n'
    notes += '\nLegal\n-----\n' + textwrap.fill(LEGAL.format(game=paths.GAME, medium=MEDIUM), 78) + '\n'
    (out / 'README.txt').write_text(f'{title}\n\n{notes}', encoding='utf-8', newline='\r\n')
    zip_path = paths.RELEASE / f'{base}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f.name)
    print(f'\n{paths.show(zip_path)}: {zip_path.stat().st_size} bytes')


if __name__ == '__main__':
    main()
