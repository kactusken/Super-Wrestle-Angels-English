#!/usr/bin/env python3
"""Survey every compressed graphics block the game loads, to find Japanese drawn as graphics
before a player does.

  gfxsurvey.py collect [STATE...]   replay savestates (default: all in build/work/mesen/states)
                                    with wandering input, logging each call of the decompressor
                                    ($80:BDD7: source DB:X, Y groups) -> translation/work/gfx_blocks.csv
  gfxsurvey.py screens              the runs' screenshots, near-duplicates dropped, as contact pages
                                    in build/work/survey/ - the quickest review
  gfxsurvey.py sheets               render every logged block (2bpp and 4bpp, grey) into
                                    build/work/survey/, marking the blocks the build reletters

The CSV accumulates (one row per block: address, groups, first state seen, done). Review the sheets
for kana/kanji and add what's found to tools/labels.py or tools/strips.py; then set done=yes.
The runs use a copy of the ROM named survey.smc, so its battery save never touches the player's.
"""
import csv
import random
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATES = ROOT / 'build/work/mesen/states'
WORK = ROOT / 'build/work/survey'
CSV = ROOT / 'translation/work/gfx_blocks.csv'
FRAMES = 6000


def steps(seed):
    rnd = random.Random(seed)
    out = ['trace exec 0x80bdd7 0x80bdd7 20000']
    n, shot = 0, 0
    while n < FRAMES:
        b = rnd.choice(['a', 'a', 'a', 'b', 'up', 'down', 'left', 'right', 'down', 'right'])
        w = rnd.randint(15, 45)
        out += [f'press {b}', f'wait {w}']
        n += w + 6
        if n // 150 > shot:
            shot = n // 150
            out.append(f'shot s{shot:03d}')
    return out


def run(state, rom):
    out = WORK / f'run_{state}'
    shutil.rmtree(out, ignore_errors=True)
    (out / 'states').mkdir(parents=True, exist_ok=True)
    shutil.copy(STATES / f'{state}.mss', out / 'states' / f'{state}.mss')
    script = out / 'steps.txt'
    script.write_text('\n'.join([f'load {state}', 'wait 3'] + steps(state)) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/mesen.py'), '--rom', str(rom), '--out', str(out),
                    '--file', str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200)
    found = set()
    trace = out / 'trace.txt'
    if trace.exists():
        for m in re.finditer(r'X=([0-9A-F]{4}) Y=([0-9A-F]{4}) DB=([0-9A-F]{2})', trace.read_text()):
            addr = int(m.group(3) + m.group(1), 16)
            if addr & 0xffff >= 0x8000 and (addr >> 16) & 0x7f < 0x40:     # ROM, not RAM
                found.add((addr, int(m.group(2), 16)))
    shots = WORK / 'shots'
    shots.mkdir(exist_ok=True)
    for f in out.glob('s[0-9][0-9][0-9].png'):
        shutil.move(str(f), shots / f'{state}_{f.name}')
    shutil.rmtree(out, ignore_errors=True)
    return state, found


def load():
    if not CSV.exists():
        return {}
    with open(CSV, encoding='utf-8', newline='') as f:
        return {(int(r['address'], 16), int(r['groups'], 16)): r for r in csv.DictReader(f)}


def save(rows):
    CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['address', 'groups', 'seen', 'done', 'notes'], lineterminator='\n')
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def handled():
    """Block addresses the build already changes (labels.py, strips.py)."""
    import labels
    import strips
    out = set(labels.BLOCKS) | {labels.SMALL[0], labels.STAT_BLOCK[0], labels.FONT8_BLOCK[0],
                                labels.CARD_BLOCK[0], labels.HUD_BLOCK[0], labels.START_BLOCK[0],
                                labels.TITLE_BLOCK[0], labels.NAME_BLOCK[0], labels.SHORT_BLOCK[0], labels.CARD_SETUP[0],
                                labels.MENU_A, labels.MENU_B} | {a for a, _ in labels.AWARD_BLOCKS + labels.RANK_BLOCKS} | {labels.LEAGUE_BLOCK[0], labels.WINNER_BLOCK[0]}
    for s in strips.STRIPS:
        out.add(s['tiles'][0])
        out |= {m[0] for m in s['maps']}
    return out


def collect(states):
    WORK.mkdir(parents=True, exist_ok=True)
    rom = WORK / 'survey.smc'
    shutil.copy(ROOT / 'build' / f'{paths.GAME_FILE} (English).smc', rom)
    rows = load()
    with ThreadPoolExecutor(4) as ex:
        for state, found in ex.map(lambda st: run(st, rom), states):
            new = [k for k in found if k not in rows]
            for addr, groups in new:
                rows[addr, groups] = {'address': f'{addr:06X}', 'groups': f'{groups:04X}', 'seen': state,
                                      'done': '', 'notes': ''}
            print(f'{state}: {len(found)} blocks, {len(new)} new')
            save(rows)
    done = handled()
    for (addr, _), r in rows.items():
        if addr in done and not r['done']:
            r['done'] = 'yes'
    save(rows)
    print(f'{paths.show(CSV)}: {len(rows)} blocks')


def sheets():
    from PIL import Image, ImageDraw
    import pack8
    import snes
    import snesgfx
    data = (paths.EXTRACTED / 'rom.sfc').read_bytes()
    r = snes.Rom(data)
    WORK.mkdir(parents=True, exist_ok=True)
    biggest = {}
    for (addr, groups), row in load().items():        # one sheet per address, the longest load
        if groups > biggest.get(addr, (0, None))[0]:
            biggest[addr] = (groups, row)
    for addr, (groups, row) in sorted(biggest.items()):
        try:
            raw, _ = pack8.unpack(data, r.to_file(addr), groups)
        except (ValueError, IndexError):
            continue
        if len(raw) < 256:
            continue                      # tilemaps and small tables
        imgs = []
        for bpp in (2, 4):
            size = 8 * bpp
            n = len(raw) // size
            img = Image.new('L', (16 * 9, ((n + 15) // 16) * 9), 40)
            for t in range(n):
                tl = snesgfx.decode_tile(raw[size * t:size * t + size], bpp)
                for y in range(8):
                    for x in range(8):
                        img.putpixel((9 * (t % 16) + x, 9 * (t // 16) + y), tl[y][x] * (255 // ((1 << bpp) - 1)))
            imgs.append(img)
        w = sum(i.width for i in imgs) + 8
        h = max(i.height for i in imgs) + 12
        out = Image.new('L', (w, h), 0)
        x = 0
        for i in imgs:
            out.paste(i, (x, 12))
            x += i.width + 8
        ImageDraw.Draw(out).text((2, 0), f'{addr:06X} {groups:04X} {"done" if row["done"] else ""}', fill=255)
        out.resize((out.width * 3, out.height * 3), Image.NEAREST).save(WORK / f'{addr:06X}.png')
    print(f'sheets in {paths.show(WORK)}')


def screens():
    """Unique screenshots of the collect runs (near-duplicates dropped) as pages of 4x4."""
    from PIL import Image, ImageDraw
    seen, keep = [], []
    for f in sorted((WORK / 'shots').glob('*.png')):
        if int(f.stem[-3:]) <= 3:
            continue                              # still the savestate's old graphics
        im = Image.open(f).convert('L')
        small = list(im.resize((32, 28)).tobytes())
        if sum(small) < 32 * 28 * 8:
            continue                              # black (fades)
        if any(sum(abs(a - b) for a, b in zip(small, o)) < 32 * 28 * 18 for o in seen):
            continue
        seen.append(small)
        keep.append(f)
    for k in range(0, len(keep), 16):
        page = Image.new('RGB', (4 * 260, 4 * 238), (90, 90, 90))
        for i, f in enumerate(keep[k:k + 16]):
            x, y = 260 * (i % 4), 238 * (i // 4)
            page.paste(Image.open(f).convert('RGB').crop((0, 0, 256, 224)), (x, y + 12))
            ImageDraw.Draw(page).text((x + 2, y), f.stem, fill=(255, 255, 0))
        page.save(WORK / f'screens{k // 16:02d}.png')
    print(f'{len(keep)} unique screens, {(len(keep) + 15) // 16} pages in {paths.show(WORK)}')


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['collect']:
        collect(argv[1:] or sorted(p.stem for p in STATES.glob('*.mss')))
    elif argv == ['screens']:
        screens()
    elif argv == ['sheets']:
        sheets()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
