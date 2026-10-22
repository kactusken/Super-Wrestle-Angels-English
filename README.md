# Super Wrestle Angels — English Translation

An English translation patch for **Super Wrestle Angels** (Imagineer, 1994, Super Famicom),
a women's pro wrestling game that was released only in Japan.

Everything a player reads is in English: all four modes (Exhibition, Promoter, League,
Tournament) and the system menu, about 1,340 messages - match commentary, the promoter mode's
events, scouting talks and the ending - the 60 wrestlers' names and profiles, the 8x8 menu text
and the labels, buttons and banners drawn as graphics. The game's 12x12 font holds two English
letters in each Japanese glyph, and the relettered graphics are recompressed to their original
size.

**[See screenshots](docs/SCREENSHOTS.md)** of the patched game.

> **Status: v0.1, the first public release.** The whole game is translated and every mode has
> been played through, but by few people so far: please report problems
> ([how to report](#reporting-problems)). Not yet tried: 3-4 player promoter games (multitap).
> [CHANGELOG.md](CHANGELOG.md) lists what's in each release.

## Downloads

Get the latest zip from the [Releases](../../releases) page. It contains one patch:

| Patch | What you get |
|---|---|
| **Super Wrestle Angels (English)** | The translation, with the game otherwise unchanged. |

## How to patch

You need your own copy of the original Japanese cartridge, as a ROM file. ROMs are not provided here.

- Game: *Super Wrestle Angels* (Japan), SHVC-AWAJ-JPN.
- The image must match: `Super Wrestle Angels (J).smc`, 1572864 bytes, CRC32 `b697f8a0`,
  SHA-1 `1897062b952636ce0d2f9b714c7cd0b08cdc340b`.

Then:

1. Apply the `.bps` patch with a BPS patcher:
   - [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) runs in your web browser.
   - Floating IPS (Flips) on Windows or Linux, MultiPatch on macOS.
   The patcher checks the ROM first. If it refuses, your ROM is a different dump, or it has a
   512-byte copier header (this one has none).
2. Open it in your emulator. Tested in Mesen 2.

## Notes for players

- **Names.** Long names are shortened where the game has little room ("C. Nagahara").
  Wrestlers keep their Japanese names, in the usual order (given name first).
- **What's still in Japanese.** The title logo, and words drawn into a few event pictures
  (the scenes explain themselves).
- **Naming wrestlers and promotions.** The PAIRS page (where the kanji were) has two-letter
  pieces in the same narrow letters as the rest of the English ("Ka", "mi", "a "), so a name
  can be up to 20 letters. The ABC page still has the original wide letters.
- **Saves.** Start a new game: in battery saves from the Japanese version the names show as
  random letters.
- **A small quirk.** Names are drawn two letters at a time, so a name with an odd number of
  letters ends in a space: "Pacific 's".
- **How promoter mode works** - the month, every menu, the events and what decides the ending:
  [docs/PROMOTER.md](docs/PROMOTER.md).
- **How matches work** - the cards, what wins an exchange, damage, pins and submissions, and the
  leg drop bug: [docs/MATCHES.md](docs/MATCHES.md).
- **Hidden content.** See [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md).

## Reporting problems

Open an [issue](../../issues) with:

- a screenshot,
- which patch you used,
- where you were: the mode and menu, or roughly what had just happened.

Text that is cut off, overlaps, or still shows Japanese is especially helpful.

## For ROM hackers and contributors

Everything needed to rebuild the patches from the original ROM is in this repository: the
translated text, the patching code (Python 3, no dependencies for the build) and documentation of
the game's formats.

| Document | What's in it |
|---|---|
| [docs/BUILDING.md](docs/BUILDING.md) | Setting up, building, making patches, and the checking tools |
| [docs/TRANSLATION.md](docs/TRANSLATION.md) | Text file formats, scope, style guide, glossary, and naming decisions |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | The ROM layout, compression, data formats, and memory map |
| [docs/PLATFORM.md](docs/PLATFORM.md) | SNES pitfalls for this kind of work |
| [docs/PROMOTER.md](docs/PROMOTER.md) | How promoter mode works: the month, menus, events, what decides the ending |
| [docs/MATCHES.md](docs/MATCHES.md) | How matches work: cards, move choice, who wins an exchange, damage, pins, every move |
| [docs/HIDDEN_CONTENT.md](docs/HIDDEN_CONTENT.md) | Unlockables, debug features, and unused and cut content |
| [tools/README.md](tools/README.md) | Every tool, what it's for and how to run it |

Quick start:

```sh
python3 tools/extract.py                 # copy the ROM in rom/ to extracted/
python3 build.py                         # -> build/Super Wrestle Angels (English).smc
python3 make_patches.py --version v0.1   # -> release/*.bps and a zip
```

## AI disclosure

This translation was made with AI assistance (Claude).

## Legal

This is a non-commercial fan translation, not affiliated with or endorsed by the game's developers
or publishers. It contains no copyrighted game data that would let
anyone play without owning the game. The patches only work on your own copy of the game.
Super Wrestle Angels and its contents belong to their respective owners. The Japanese text in this
repository is included for translation and reference.

The code in this repository is released under the [MIT License](LICENSE).
