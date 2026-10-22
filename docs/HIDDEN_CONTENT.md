# Hidden content

Unlockables, debug features, button codes and unused content, each marked *verified in game* or
*from the code*. Check The Cutting Room Floor and existing guides first.

## Button codes (promoter mode; from a player's guide, matched with the code 2026-10-21) *(verified in game)*

On the title screen with "Press Start" showing, hold SELECT on controller 2 and enter the code on
controller 1 (a chime plays). Checked at `$91:97C4`, flags in `$7E:1A13`:
- **Up Down Up Down B B B B**: hold L when choosing a COACH command to use it more than once a turn
  (`$8B:AA25` skips the once-a-month flag while L is held).
- **Select Select Select Select**: game length up to 10 years instead of 5 (`$8B:E13E`).
- **Left Left Right Right B B B B**: any match on your card can be skipped, even title matches
  (`$83:84D9`: without it a title match is forced to be watched).
All three tried in game and working (play-test, 2026-10-22).

## Unused ending dialogues (from the code)

The promoter ending has special lines for pairs of wrestlers on the winning roster (table
`$81:C437`). Two pairs, Kyoko Kurenai + Saeko Endo and Riyu Kikuchi + Hikaru Ogawa, can never
match: their entries are written as 16-bit values where the table reads bytes, so each reads as
(wrestler, 0). One more line (Nagahara, Rei and Cutie) has no reference at all. All three are
translated anyway. See docs/PROMOTER.md section 8.

## Unused random incident (from the code)

A dojo fire ("A fire broke out at the dojo. Usable dojo AP dropped by {n}.", handler `$91:A6E7`)
is in the incident jump table but in neither list the game picks incidents from.

## Search summary (2026-10-21)

Public sources first: The Cutting Room Floor has no page for this game, GameFAQs has no guides or
codes, and Japanese code sites list only the three button codes above. Then the ROM (code read
with tools/dis65816.py, checked in Mesen where marked):

- **No other codes.** The title screen's checker (`$91:97C4`) knows exactly three sequences; every
  read of the code flags (`$7E:1A13`) tests bits 0-2. The joypads are read only by the pad /
  multitap driver; no held-button combos at boot, reset or name entry.
- **No hidden mode or debug menu.** The mode table (`$81:E8D0`) holds exhibition, promoter,
  league, tournament, an empty slot and quit. The only ASCII text is the multitap BIOS banner,
  a graphics library's error strings, the credits, "PAUSE" and two code labels ("Sin1Sin2").
- **No hidden music.** The sound driver has 26 songs ($A8:8000); the music test plays all 26.
- **No hidden wrestlers.** There are exactly 60 (38 Japanese, 22 foreign; names at file
  0x9739c) and all can appear (Mesen).
- **Harumi Minagawa** (皆川晴美, ID 36; Japanese Wikipedia notes she's missing from the demo)
  is complete and playable: record, portrait, profile, scouting talk, tryout dialogue, ending
  comment; in the exhibition, league and tournament lists, and in promoter mode via tryouts or
  scouting (Mesen). Only the **attract demo** never shows her: its 64-byte list of wrestler ids at
  file 0xe76f is shifted by one from the sixth column on, so 36 is skipped (and its last row
  repeats five others). Changing file 0xe787 from 17 to 36 would put her in; the patch leaves the
  demo as the original has it.
- **Unreachable text** (code):
  - Mami Sawanobori's tryout dialogue: tryouts draw from ids 1-37 and she is 38.
  - The three ending pair dialogues and the dojo fire above.
  - A "1111" placeholder among the match commentary (message $93).
- **A latent bug** (code): the ending's comments have no check for foreign wrestlers. A foreign
  wrestler on the winning roster would get an unrelated line; they only come as booked guests, so
  it shouldn't happen.
- **One unused picture** (code; shown in Mesen with a patched copy): event picture 11,
  `$A3:B99C` (entry 24 of the picture table at `$8D:F9DE`). A banquet hall with round tables of
  guests in suits, a man in a suit and a woman in pink on a stage, and a blank white banner; no
  drawn text. Every other event picture has a caller (`$8C:F6FD` with the picture number, 27
  places); nothing ever asks for 11. Probably a cut reception or party event.
- **The rest of the graphics are used** (code): everything a random-play run never displayed is
  either named by a pointer table (move pictures, event pictures, the 64 portraits at
  `$81:F6F4`), a later slice of a move picture streamed in pieces by `$80:A03A`, sound data
  (banks $A8-$AF: 26 songs), script text, code, or leftover filler at bank ends.
- **A public claim that doesn't hold here:** a Japanese wiki says the ending only comes if your
  promotion is first. In this game the ending always comes when time is up, with whoever is
  first (Mesen, docs/PROMOTER.md section 8).

