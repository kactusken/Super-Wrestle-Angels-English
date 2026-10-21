# Building

## Requirements

- Python 3.9+ - `build.py` and `make_patches.py` use only the standard library
- For the image and research tools: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`

## Setup (once)

1. Put `Super Wrestle Angels (J).smc` in `rom/` (or pass `--rom`). Expected SHA-1 `1897062b952636ce0d2f9b714c7cd0b08cdc340b`.
2. `python3 tools/extract.py` - copies the ROM to `extracted/rom.sfc`.
3. `python3 build.py` - first build (copies the image; later builds only restore what changed).

## I want to...

| I want to... | Do this |
|---|---|
| Build the translation | `python3 build.py` → `build/Super Wrestle Angels (English).smc` |
| See how far along it is | `python3 tools/status.py` |
| Check everything | `python3 tools/check.py` (`--control`: prove the build is lossless) |
| Check text only | `python3 tools/lint.py --warnings` |
| Edit the script (dialogue, menus, commentary) | the `EN` lines in `translation/script/*.txt`, then `python3 tools/script.py check` (does every line fit?) |
| Edit the 8x8 menu text (moves, labels) | `translation/text/*.csv`, then `python3 tools/text8.py check` |
| Change a relettered graphic (buttons, banners, labels) | the word lists in `tools/labels.py` and `tools/strips.py` |
| Make release patches | `python3 make_patches.py --version v0.1` |
| Run checks before every commit | `python3 tools/check.py --install-hook` |

## Build options

| Option | |
|---|---|
| `--name NAME` | output name (default `Super Wrestle Angels (English)`) |
| `--clean` | copy the original instead of restoring the last build |
| `--unlocks all\|none\|GROUP,...` | gameplay patches (`CODE_PATCHES` in build.py) |
| `--no-translation` | skip text and images; alone the result is identical to the original |
| `--boot PART` | test build that starts in PART (`BOOT_PATCHES`) |
| `--no-text FILE` | developer: leave one text file untranslated |
| `--skip-verify` | don't hash the original |

## Folder options

Every tool takes `--root`, `--rom`, `--translation`, `--extracted`, `--build`, `--review` (see
`--help`); the defaults are the folders in [tools/paths.py](../tools/paths.py).
