# Promoter mode: how it works, what can happen, how it ends

A map of the promoter mode (団体経営), worked out from the code and checked in Mesen on 2026-10-21.
Each finding is marked: **(code)** read from the disassembly, **(Mesen)** seen in the emulator,
**(text)** inferred from the script only. Addresses are CPU addresses; WRAM details are in
[§10](#10-ram-reference-for-testing). Menu and message names are the English ones of this patch.

## 1. The short version

- A game lasts the chosen number of years (1-5; up to 10 with a secret code, §9). It starts in
  April and **ends in the April after the last year** (a 1-year game ends at the start of year 2).
- The winner, crowned **KING OF PRO-WRESTLING COMPANY**, is the promotion with the highest
  **TOTAL**. TOTAL is mostly **the roster** (20 points for every rating point each wrestler has
  above 400), then **fans** across the 47 prefectures; funds, titles and the dojo add a little.
  The RATING and SHOWS awards don't count at all (§7).
- **Every April's "Promotion Rankings" screen uses the same TOTAL**: it is a preview of who would
  win if the game ended then.
- There is **one ending**. When you win it names your promotion and your own wrestlers speak.
  The only variation: a game **shorter than 3 years won by a CPU promotion skips the credits**
  (and their music, Ending 2) (§8, Mesen). The only other way out is **GAME OVER**: every human promotion
  bankrupt, after funds below zero for 3 months in a row (§6).

## 2. Setting up a game (text, Mesen)

Players (1-4 humans), play length in years, funds level, emblem, promotion name (name entry), and
the CPU promotions to play against. The other promotions are picked from the game's list; which
ones are in the game matters: the **Ex Tag League** only exists if Shin Nihon Joshi is one of
them (§5).

Each human promotion starts without wrestlers: **6 are needed to hold a show** (counting booked
foreign guests and invaders, `$8A:A748`) (code).

## 3. A month, in order (code, Mesen trace of the game's tasks)

1. **Turns**, one promotion after another (task `$8A:A412`):
   1. the bankruptcy check (§6);
   2. the month's **events** for that promotion (§5): fan club, movie, TV, police chief, thief,
      injuries and hospital, heartbreak, rebels, alliances ending, belts vacated, random
      incidents;
   3. **December only**: the Ex Tag League invitation;
   4. the turn itself: the **main menu** for a human (unless Delegate is on), "...Thinking..."
      for a CPU (it signs rookies, scouts, raids, allies). **END** on the menu bar ends your turn.
2. **Booking** (task `$8A:A69F`): vacations start and end; a promotion that can hold a show
   books it. A human uses the show schedule (venue map) and the match card setup; a CPU, or a
   human with Delegate on, shows "Booking matches...".
3. **Shows**: CPU shows are simulated ("...In Progress..."); yours are played match by match,
   watched or skipped (Spectate setting, WATCH / SKIP). Invasions by raiding CPU wrestlers happen
   here. Then the **statement**: crowd, capacity and profit per show (up to 8), salaries, foreign
   fees, upkeep, other income and costs, funds before and now.
4. **The month advances** (`$8A:8172`). In **April**: yearly processing, then either the ending
   (if the last year is over) or the **Promotion Rankings** screen (§5).

## 4. Menus (Mesen, each opened from a save)

The number after AP in the header is **cash ÷ ¥50,000**: 1 AP = ¥50,000, and spending AP spends
money. It shows 0 while cash is negative.

| Menu | Item | What it does |
|---|---|---|
| STAFF | Tryouts | spend AP (20 by default; more = better odds) for a chance at a rookie; once a month ("Done for this month."). The rookie is drawn at random from the unsigned Japanese wrestlers (`$8C:CA8E`) |
| | Scout | pick a CPU promotion or Retired/Free, then a wrestler; costs AP; limited per month |
| | Overseas | send a wrestler to your foreign ally; needs an ally and your opening show held. **Foreign stars** only accept above a promotion Rating: Chris Morgan 4500, Super Chaos 4000, Remy Dadarne 2500, Nastassja Han and Chocho Caras 2000 (code) |
| | Vacation | 100 AP; she misses that month's shows; one at a time |
| | Mask | 30 AP; choose a mask type (MRL / FAN modifiers), then a name and short name; "Take off the mask?" for masked wrestlers |
| | Vacate | give up a belt she holds (her trust drops) |
| | Release | let a wrestler go |
| TRAIN | | per-wrestler training: dojo cap, manual or auto; tabs STATS, LEARN, SPECIAL, MOVE LV |
| ADMIN | Facility | Expand (invest AP; raises usable dojo AP) or Sell off |
| | Alliance | ally with a foreign body (IWWF, WWCA, EWA, AAC, GWA; IWWF costs 1200 AP); one at a time; can fail; allies can break it off |
| | Signing | autograph session in one of 10 regions: that region's draw rises |
| | TV Deal | a monthly fee; can be cancelled |
| COACH | Talk | 10 AP: Praise / Scold / Cheer, morale and trust up or down |
| | Training | 30 AP: more usable AP for her this month; risk she runs away or gets hurt |
| RAID | | send one of your wrestlers to invade a CPU promotion's show |
| INFO | Promo Data, Rankings, Belts | every promotion's Rating, Cash, Roster, Facility, Ally; top 10 wrestlers by any of 18 stats; title holders |
| END | | end your turn |
| SELECT | Save, Load | battery save slots |
| | Years | **change the play length mid-game**: not below the current year, up to 5 (10 with a code) (code `$8B:E0FD`; Mesen 1 -> 2 -> 4) |
| | Delegate | let the game run your promotion (after training, or including it) |
| | Split CG, Spectate, Quit | card-game CG, which matches to watch (None / Main Event / All), quit |

## 5. Calendar and conditions

### By date (code, Mesen where noted)

| When | What |
|---|---|
| Month 1 (April, year 1) | the secretary's reminder: 6 wrestlers are needed, and "If we haven't opened within six months, money will get very tight" |
| your first show | the opening show speech |
| **every December** | **Ex Tag League** invitation (Shin Nihon Joshi's year-end tag tournament): "Send 2 wrestlers?" Only if Shin Nihon Joshi is in the game and still running, and your promotion has debuted with a **Rating ≥ 1000 or the highest Rating** of all (`$8A:BB7C`, `$8A:BC08`). Shin Nihon Joshi skips its own December show while it runs |
| (Ex Tag League, Mesen) | invitation picture (a letter), "Send 2 wrestlers?", pick two (A marks, B confirms), "Also run the gym on auto?"; later in the month an announcer screen ("Seven top teams..."). The league itself runs off screen: no bracket or results are shown |
| **every April** | the 22 foreign wrestlers (IDs 39-60) are rebuilt at a stronger tier, one per year 1-6 (year 7+ keeps tier 6) (`$8A:8499`) |
| **every April** (not the last) | **Promotion Rankings** screen: TOTAL, RATING, ROSTER, FUNDS, DOJO, SHOWS, FAN nationwide and per region; A on a row shows the points (Mesen) |
| the April after the last year | the ending (§8) |

### Events any month (code; chances per promotion per month)

| Event | Condition | Effect |
|---|---|---|
| Fan club ("Approve?") | a wrestler with **FAN ≥ 50** and no fan club; 30% | fan club; promotion buzz +10 |
| Movie role ("Accept?") | none running; 10%; a wrestler with **MOR ≥ 60 and FAN ≥ 60** | she's away 6 months, FAN +25, buzz +50, ¥20M fee |
| TV appearance | **promotion Rating ≥ 2500**; 20% | FAN +5, 3-month wait |
| Police chief for a day | a wrestler with **MOR ≥ 60, FAN ≥ 80**; 20%; 3-month wait | buzz +30 |
| Thief | after the opening show, **funds ≥ about ¥100M**; 3% | lose ¥10-90M |
| Heartbreak | about 8% | her trust −30, her AP this month halved |
| Rebels / rejoin | a wrestler's **MOR below 21** / back to 21+ | she joins the rebels / returns |
| Injury, hospital, healed, retirement after a long stay | recovery dates per wrestler | |
| Invasion | a CPU promotion raided you | its wrestlers join your show card |
| In the red | funds < 0 at month end | warning after 1 and 2 months; bankruptcy at 3 (§6) |
| Belt vacated | a champion leaves, retires or won't defend | the belt changes hands |

**Random incidents** (only human promotions that have held their opening show; at most 2
promotions a month; the odds grow with the gap in funds to the leader): sponsor money (+¥10-80M),
tour-bus accident (insurance money, or a wrestler in hospital), a wrestler retires (at home or on
tour abroad), and the **festival donation**: pay and the region's draw may rise; refuse and it may
fall, and the man may be a con artist. A dojo fire exists in the code but is never chosen (code).

## 6. Losing: bankruptcy and GAME OVER (code; Mesen)

- At each turn, negative funds count up a counter; positive funds reset it. Warnings at 1 and 2;
  **at 3 months in a row the promotion folds**: wrestlers released, rankings cleared, the
  secretary's "launched at … / bankrupt at …" (or "never held an opening show").
- **GAME OVER** when every human promotion has folded (`$720A = $FF00`). In a 2-4 player game a
  bankrupt player drops out and the others play on. CPU promotions can fold too; they rank last.
  (Mesen: GAME OVER screen, then the attract mode.)
- Nothing else ends a game early: being far behind, or an empty roster, doesn't.
- (Fixed 2026-10-21: the English bankruptcy message was too wide and froze the game.)

## 7. What decides the winner: TOTAL (code; matches the game's figures to the point)

`$8A:D994`, for each promotion still running:

```
TOTAL = funds / ¥50,000                         (the header's AP number)
      + 20 × Σ roster (wrestler's rating − 400)  (her 評価, from the data screen)
      + 10 × Σ 47 prefectures (fans − 5)
      + 5 × prestige of each title held          (prestige 63-120 per belt)
      + 5 × buzz                                 (fan clubs +10, movie +50, police chief +30)
      + dojo / 10
```

Check, April of year 2 in the CHAOS test game (Mesen popup "Tot. POINT"): Pacific 45,856 (its 7
wrestlers alone give 41,800), Aoi 22,272, Japan Sea 21,853, CHAOS 20,147. Ties go to the earlier
promotion (the human player). The award banners rank RATING, ROSTER, FUNDS, DOJO, SHOWS and FANS
separately, but only OVERALL decides the ending.

**How to win, then:**
1. **Roster above all.** A wrestler at rating 900 is worth 10,000 points; one at 400 is worth
   none. Sign many good wrestlers (scouting, raids, tryouts, foreign stars once your Rating is
   high enough) and train them. The CPU leader had ~46,000 after one year, so expect to need
   about 7-8 wrestlers averaging 650+.
2. **Fans everywhere.** Each fan point above 5 in each prefecture is 10 points: +10 fans in every
   prefecture is 4,700. Shows across many regions, signings, fan clubs, TV and movies help.
3. **Don't go broke.** Funds count only 1 point per ¥50,000, but three months in the red ends the
   game.
4. Titles and buzz are a few hundred points each; the dojo hardly counts.
5. Watch each April's rankings screen, and the Years option: more years = more time to build.

## 8. The ending (Mesen, forced player win and CPU wins)

1. "It's time to decide the strongest promotion..." then **KING OF PRO-WRESTLING COMPANY** with
   the winner's emblem ("CHAOS!!").
2. **The winner's wrestlers speak**: special **pair dialogues** when both are on the winning
   roster, then one comment by each other wrestler (her own line, the same for any promotion):

   | Pair | Line |
   |---|---|
   | Mighty Yukiko + Bomber Kishima | "Yukiko: Number 1, huh? Not bad…" |
   | Beauty Ichigaya + Hikaru Ijuin | "Ichigaya: Ohhh ho ho ho! …" |
   | Hitomi Fujishima + Cutie Kanai | "Hitomi: We made 1st place all thanks to you, Kanai." |
   | Beauty Ichigaya + Mighty Yukiko | "Yukiko: Number 1, huh? Even I'm amazed…" |
   | Mimi Yoshihara + Akiko Saito | "Mimi: Number 1, huh. Sounds nice." |

   Two more pairs (Kyoko Kurenai + Saeko Endo, Riyu Kikuchi + Hikaru Ogawa) are in the script but
   **can never appear**: their table entries are written wrongly in the original game. A third
   (Nagahara, Rei, Cutie) is never referenced (code).
3. The **award screens**: OVERALL, RATING, FANS, then ROSTER, DOJO, SHOWS, FUNDS, each with the
   four promotions in order.
4. The **credits**, with the top wrestlers' rank, record and titles beside them.
5. The Imagineer logo and the title screen. Pressing A can skip the credits.

Music (Mesen, matched with the music test): **Ending 1** plays over the KING screen and the
awards, **Ending 2** over the credits.

**The variations** (code `$81:C289`, `$81:C2BA`; Mesen):

| Case | What changes |
|---|---|
| You win (any length) | nothing: same screens, your name and wrestlers (Mesen, forced win) |
| A CPU promotion wins, game of 3+ years | nothing: credits roll (Mesen, 3-year game) |
| **A CPU promotion wins, game under 3 years** | after the awards the music fades and the game goes to the Imagineer logo: **no credits, no Ending 2** (Mesen, 1-year game) |
| The winner has no wrestlers | the comments are skipped |

So to see everything (the credits with the wrestler ranking), win yourself, or play 3 years or
more.

## 9. Secret codes (a player's guide, matched with the code)

On the title screen, once "Press Start" shows (let the intro play out), **hold SELECT on
controller 2** and enter the code on controller 1; a chime confirms it. The game watches for them
at `$91:97C4` and sets a bit of `$7E:1A13`.

| Code | Effect | In the code |
|---|---|---|
| Up Down Up Down B B B B | **hold L** while choosing a COACH (指導) command to use it on the same wrestler more than once a turn | bit 0, `$8B:AA25`: with L held ($0020) the once-a-month flag isn't checked |
| Select Select Select Select | the game length can be set up to **10 years** instead of 5 | bit 2, `$8B:E13E` |
| Left Left Right Right B B B B | any match on your card can be skipped, **even title matches** | bit 1, `$83:84D9`: without it a title match is forced to be watched |

None of them changes the ending (code). Not yet tried in Mesen (tools/mesen.py drives controller 1
only).

## 10. RAM reference (for testing)

| Address | What |
|---|---|
| `$7E:71F0` | month counter, 16-bit: 1 = April of year 1 (shown month = counter + 3, wrapping) |
| `$7E:71F2` | play length in years |
| `$7E:720A` | end state: $FFFF time up, $FF00 all humans bankrupt, $F000 quit |
| `$7E:6116 + $401 × k` | promotion k (0 = first human, then the others); the one whose turn it is is copied to `$7E:5D15` and back: **poke both** |
| record +$02 | bit 7 = human; low bits = which promotion (5 = Shin Nihon Joshi) |
| +$1E / +$22 | month of the opening show (0 = none) / of bankruptcy (0 = running) |
| +$24 | Rating · +$28 funds in yen (32-bit) · +$2C funds/50,000 · +$2E months in the red |
| +$3E+p | fans in prefecture p = 1-47 (regions: table `$8A:8716`) |
| +$D4 buzz · +$D6 dojo · +$E4 shows held · +$E6 roster size · +$E8 wrestler ids | |
| `$7E:2800 + id × $BD` | wrestler: +$29 rating, +$3F morale, +$40 fans, +$A5 trust |
| `$7E:5CAC` | 9 title holders (promotion per belt) |

To reach the ending quickly: on a main-screen savestate, set the month counter to the last
March (e.g. 12 in a 1-year game) and end the month; poke a promotion's fans (+$3E+p, both copies)
to change who wins.

## 11. Not settled yet

- The button codes, tried in the game.
- Retirement odds, alliance timers, injury odds, the CPU's decisions, scouting success, the exact
  per-month limits on tryouts and scouting, the ROSTER award's formula.
- The setup strings "Newcomer / 3 Months / 6 Months / 8 Months" (a setup choice not identified).
