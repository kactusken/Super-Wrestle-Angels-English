# Matches: cards, moves, who wins an exchange, damage and finishes

How a match plays out under the hood, worked out from the code and checked in Mesen on 2026-10-21.
Each finding is marked: **(code)** read from the disassembly, **(Mesen)** seen in the emulator.
Addresses are CPU addresses; RAM and data layouts are in [§12](#12-reference). Move names are the
English ones of this patch (the game's 8-letter names: GUILLOTINE is the guillotine leg drop).

## In plain words

Think of a match as a card game played over and over, one round ("exchange") at a time.

- **You have 5 cards.** Each one says what *kind* of move to try (a throw, a hold, a strike, a
  flying move, or something sneaky) and has a number from 1 to 10. Every round, you and your
  opponent each put one card down.
- **The bigger "push" wins the round.** Each card gets a score: how good you are at that kind of
  move, minus how good the opponent is at stopping it, plus the card's number. Only the winner's
  move happens. A **finisher card** is the trump card: it always wins.
- **You pick the card; the game picks the move.** At the start your wrestler only uses her small
  moves. As the opponent gets tired, her bigger moves unlock. Wearing the opponent down is what
  lets you hit hard.
- **Damage is simple:** each move does a set amount, plus a bit more for every level your
  wrestler has in that move. Some holds hurt an arm or a leg instead of the main health bar.
- **Sometimes the loser turns it around.** A few big moves can be countered (a moonsault can
  miss, a backdrop can be rolled into a pin).
- **If you keep losing, the game helps a little.** After a losing streak your cards get a small
  push. In tag matches, asking to tag out gets a push too when your partner is fresher than you.
- **To win, pin or make her give up.** A normal pin only gets the 3-count once her health bar
  is completely empty. The small cradles (SMALL PKG., INV. CRADLE, ROLL. CRADLE) are sneaky: they
  can win while she still has a little left. There's no time limit and no count-out.
- **The famous bug:** the leg drop (GUILLOTINE) and the MOONSAULT were meant to be *worse*
  against a standing opponent. A mistake in the game made them hugely *better* instead, so they
  win almost every round while the opponent is on her feet. That's why the leg drop "always
  connects."

The rest of this page has the exact numbers.

## 1. The short version

- A match is a series of **exchanges**. Each side plays one of five cards; the cards are types
  **T L S F O** (throw, lock, strike, fly, other), plus the rarer **finisher** and **double-team**
  cards. Each card has a number from 1 to 10.
- **You choose the card, the game chooses the move.** From the card's type it takes the
  biggest move in your list that the opponent is worn down enough for (§3).
- Both cards get a **priority score**, mostly your attack stat for that type minus the opponent's
  defence stat, plus the card's number. **The higher score wins the exchange** and only the winner's
  move happens (§4). A finisher card wins outright.
- The loser may **counter** the winning move (some moves only, §5).
- **Damage** = the move's base value + its per-level value × the move's level, plus small bonuses
  (§6). It comes off HP, or off the arm or leg meter for some holds.
- Matches end by **pinfall** or **submission** (§9). An ordinary pin only gets the 3-count when the
  opponent's HP is at **exactly 0**; the cradles (SMALL PKG., INV. CRADLE, ROLL. CRADLE) can win
  earlier. There is no time limit and no count-out.
- **Two bugs** stand out (§10): **GUILLOTINE and MOONSAULT get +255 priority against a standing
  opponent**, so they win almost every exchange; and a CPU's double-team card gets about +255
  whenever the CPU is behind on HP.

## 2. The hand (code)

Each side holds 5 cards (on screen under the A B X Y R buttons). A card is a type and a number.
After an exchange the played card is replaced (`$83:F697`, refill `$84:8A0C`/`$84:8A35`).

| Card | How often | Number |
|---|---|---|
| T, L, S, F | about 23% each | 1-10, even odds |
| O (other) | about 9% (an O roll is kept only 40% of the time, `$84:8BBC`) | 1-10 |
| **Finisher** | (stat `+$39`[5] + 2 − your HP tenths) % per new card, only once you've lost some HP, never two in hand, at most 2 per match (wrestler byte `+$AE` counts them). The second also needs a singles match and your HP at least 5 tenths above the opponent's (`$84:8A95`) | always 10 |
| **Double-team** | tag and trios only, never two in hand, the other side's HP tenths ≥ 7; then 1 in 6 per new card (`$84:8B70`) | 1-10 |

"HP tenths" throughout means `floor(current HP × 10 / max HP)` (`$8A:F8FC`): 10 at full health,
0 when nearly empty.

## 3. From card to move (code; Mesen)

The player picks only the card. The move is chosen by the same routine for humans and the CPU
(`$89:A154`), before the exchange is resolved:

1. Every wrestler has, for each of T L S F O, up to **6 moves, each with a level** (1-9), plus a
   finisher and RECOVER (§12). A move's level is fixed per wrestler; the same move can appear twice
   at two levels (Beauty Ichigaya: LARIAT 3 and LARIAT 7).
2. The game works out a **threshold T** (`$89:9D22`): **10 − the opponent's HP tenths**, plus half the
   partner's HP lead in tag matches, plus up to +4 from an advantage score that looks at the
   opponent's card, plus a 5% chance of +3 (otherwise +1).
3. It scans the card type's moves from the last slot down and takes the **first move whose level is
   below T** and that fits the ring position (move byte +36: GUILLOTINE can't be done from position
   1, PLANCHA only from there). Ties are picked at random; if nothing fits it takes the lowest
   slot.

So the **number on your card doesn't pick the move**: the opponent's condition does. Against a fresh
opponent T is about 2-4 and only level 1-3 moves come out; the big moves appear as the opponent
tires. In the trace, Yuki's strike cards numbered 2 and 7 both gave her slot-0 move (Mesen).

A **finisher card** plays the wrestler's finisher, or RECOVER instead when you have less HP than the
opponent (or the finisher doesn't fit the ring position) (`$89:9BB6`).

## 4. Who wins the exchange (code; Mesen)

`$88:914A` compares the two cards:

- **A finisher card wins outright**. Two finishers: the side that lost the previous exchange wins.
- Otherwise each card gets a **priority score** (`$88:91CB`), and the higher one wins. A tie goes to
  the side that lost the previous exchange.

The score, for your card against the opponent's:

| Term | Value | Where |
|---|---|---|
| Attack − defence | your attack stat for the card's type − the opponent's defence stat for it (the T L S F O numbers on the match screen) | `$88:91D2` |
| Card number | + the card's number (1-10) | `$88:9216` |
| Level penalty | − the move's level, if (10 − the opponent's HP tenths) is less than the level. Human wrestlers add the difficulty (0 Easy, 1 Normal, 2 Hard) to the 10 | `$88:9223` |
| Double-team card only | your winning streak: +1, +3, +5, +7, +9 after 1-5+ wins in a row; the opponent's streak: −3, −5, −7 after 1-3+ | `$88:9278` |
| **TAG requested** (tag/trios) | + (partner's HP tenths − yours), doubled when the gap is 5 or more, never negative. This is the "bonus for trying to tag out" | `$88:92DF` |
| Move vs position | + the move's bonus against a standing or a downed opponent: 0 standing for every move except **GUILLOTINE and MOONSAULT ($FF = +255, §10)**; 0-5 against a downed opponent | `$88:9346` |
| Comeback | if the opponent has won 3, 4, 5, 6, 7+ exchanges in a row: +1, +3, +5, +7, +9 (any card) | `$88:9372` |
| Difficulty (humans only) | Easy +4, Normal +1, Hard 0 | `$88:93A2` |

Typical scores are 0-20. A wrestler is **down** after losing an exchange to a big hit: the loser is
knocked down when the damage is more than 40 + a random 0-79 (`$88:AC59`); the winner always ends
up standing.

### Worked examples (Mesen)

Real exchanges from one traced match, with every term logged. It's a trios match from a savestate:
**Chigusa Yuki** (human player, difficulty Easy, so +4 to every card) against **Mighty Yukiko**
(CPU). Their attack / defence stats:

| | Throw | Lock | Strike | Fly | Other |
|---|---|---|---|---|---|
| Yuki | 9 / 5 | 3 / 5 | 6 / 8 | 5 / 3 | 4 / 4 |
| Yukiko | 7 / 6 | 4 / 6 | 6 / 4 | 9 / 7 | 7 / 7 |

**1. A plain exchange, first round of the match.** Yuki plays Strike 2, Yukiko plays Other 3.

| | Yuki: Strike 2 → ELBOW BUTT (level 2) | Yukiko: Other 3 → BACK OFF (level 1) |
|---|---|---|
| Attack − defence | 6 − 4 = 2 | 7 − 4 = 3 |
| Card number | +2 → 4 | +3 → 6 |
| Level penalty (opponent at full HP) | −2 → 2 | −1 → 5 |
| Difficulty (human, Easy) | +4 → **6** | — → **5** |

Yuki wins, 6 to 5. Without the Easy bonus she'd have lost.

**2. The comeback bonus.** Yukiko has won the last 4 exchanges. Yuki plays Throw 7, Yukiko plays
Fly 4.

| | Yuki: Throw 7 → BODY SLAM | Yukiko: Fly 4 → FLYING KNEE |
|---|---|---|
| Attack − defence | 9 − 6 = 3 | 9 − 3 = 6 |
| Card number | +7 → 10 | +4 → 10 |
| Level penalty | none: Yukiko is worn down | none: Yuki is worn down |
| Comeback (opponent won 4 in a row) | +3 → 13 | — |
| Difficulty | +4 → **17** | **10** |

Yuki wins, 17 to 10.

**3. A tie.** Both score 5 (Yuki's CRAB HOLD from Lock 4, Yukiko's COBRA TWIST from Lock 6). Yuki
won the exchange before, so **Yukiko gets the tie**.

**4. Asking to tag.** Yukiko's side has TAG requested, and her partner is fresher than her by 5
tenths of HP, so the gap is doubled.

| | Yuki: Strike 7 → PILEDRIVER | Yukiko: Lock 9 → COBRA TWIST |
|---|---|---|
| Attack − defence | 6 − 4 = 2 | 4 − 5 = −1 |
| Card number | +7 → 9 | +9 → 8 |
| Tag bonus (partner 5 tenths fresher, doubled) | — | +10 → **18** |
| Difficulty | +4 → **13** | |

Yukiko wins, 18 to 13.

**5. The leg drop, used the way it was meant.** Yukiko is down. Yuki plays Fly 1 → GUILLOTINE;
Yukiko's side plays Lock 2 → CRAB HOLD with TAG requested. (Its attack − defence came to −2
rather than the −1 the table gives, so a stat had changed or a partner was in; only the logged
value is shown.)

| | Yuki: GUILLOTINE vs a downed opponent | Yukiko: CRAB HOLD |
|---|---|---|
| Attack − defence | 5 − 7 = −2 | −2 (logged) |
| Card number | +1 → −1 | +2 → 0 |
| Move vs position (opponent down) | +5 → 4 | (Yuki is standing: +0) |
| Tag bonus | — | +12 → **12** |
| Difficulty | +4 → **8** | |

Yukiko wins, 12 to 8. Against a downed opponent the leg drop gets a normal +5.

**6. The bug: MOONSAULT against a standing opponent.** Yuki plays Strike 5 → DDT, Yukiko plays
Fly 7 → MOONSAULT.

| | Yuki: DDT | Yukiko: MOONSAULT vs a standing opponent |
|---|---|---|
| Attack − defence | 6 − 4 = 2 | 9 − 3 = 6 |
| Card number | +5 → 7 | +7 → 13 |
| Move vs position (opponent standing) | +0 | **+255** → **268** |
| Difficulty | +4 → **11** | |

Yukiko wins, 268 to 11. Yuki would have needed a finisher card. The same thing happens with a
CPU double-team card while the CPU is behind: in this match Yukiko's DBL DROPKICK (Double 6)
scored **257** against Yuki's DROPKICK at 3 (§10).

## 5. Counters (code)

After the winner is known, the loser may turn the move around (`$88:953A`). Only these moves can
be countered:

| Winning move | Countered into |
|---|---|
| BRAINBUSTER | BRAINBUSTER |
| BACKDROP | BODY PRESS |
| LARIAT | LARIAT, or ARMBAR if lock is the loser's best attack stat |
| PILEDRIVER | REV. SUPLEX |
| POWER SLAM | ROLL. CRADLE |
| POWERBOMB | REV. SUPLEX, or HURACANRANA if fly is the loser's best attack stat |
| FLYING KNEE, MISSILE KICK, MOONSAULT, PLANCHA | MISSED (the attacker crashes) |
| FRANKENSTEIN | POWERBOMB |
| WEAPON SHOT | WEAPON SHOT |

Never from a finisher card. The chance, in %: **the winning move's level + 3 − (10 − the loser's
HP tenths) + (10 − the loser's card number)** (+ a bugged term, §10). So big moves are easier to
counter, a hurt wrestler counters less, and a low card number helps the loser. On a counter the
loser becomes the attacker and the counter move is played instead.

## 6. Damage (code)

`$88:971D`. A wrestler has three meters: **HP** and two body meters, which these notes call
**arm** and **leg** (ARMBAR and CHICKENWING hit the first, ACHILLES LCK, CRAB HOLD and SCORPION
the second; the meters themselves have no name in the game). Max HP comes from two of the
wrestler's stats and shrinks in tag (×0.8) and trios (×0.75); the arm and leg meters are half of
max HP.

For each meter a move hits:

> **damage = base + per-level × level + strength + bonuses**

- **base, per-level:** from the move (table in §11). "Level" is the move's level in the wrestler's
  list, not the card number.
- **strength:** the attacker's stat `+$3A`, added to every hit.
- **bonuses:** a bleeding attacker adds (10 − her own HP tenths); outside the ring the strength stat
  counts twice; a **finisher card** adds **+40 to HP damage** (+15 per meter for a hold).
- The meter can't go below 0.

So for **the moves where level doesn't matter** (per-level 0): ARM DRAG 15, **J.O. CYCLONE 90**,
**N.LIGHT BOMB 80**, SMALL PKG. 10, INV. CRADLE 10, ROLL. CRADLE 20, POST SHOT 45, and the five
double-team moves (40, 52, 78, 90, 96). J.O. CYCLONE and N.LIGHT BOMB come at two levels, but a
higher level only makes them come out later (§3) and costs more priority (§4). CHICKENWING,
ACHILLES LCK, FACE LOCK and S.T.F. are the opposite: all their damage is per level.

**Bleeding.** Some moves can open a cut: WEAPON SHOT and POST SHOT 20%, CHAIR SHOT and PLANCHA
15%, PALM STRIKE, FLYING KNEE and FRANKENSTEIN 10%, ELBOW BUTT 5% ("…is bleeding! Whoa! The ring
is running red!"). A bleeding wrestler hits harder as her HP drops and recovers half as fast. No
HP drain was found.

**Recovery between exchanges** (`$88:9CD5`): each exchange gives back some HP (from a recovery stat;
more in singles, double when nearly out, half when bleeding), less after 20:00 on the clock and none
after 30:00. Partners on the apron recover too. The clock advances 30 or 60 seconds an exchange
(`$89:B47C`).

## 7. The O cards and RECOVER (code)

| Move | Effect |
|---|---|
| RECOVER (finisher card, when behind) | HP + 40 + 5 × recovery stat; arm and leg + 10 + 5 × recovery stat |
| PSYCH UP | your ten attack/defence stats +1 for the next exchange |
| TAUNT | the opponent's ten attack/defence stats −1 for the next exchange |
| BACK OFF | moves two steps back toward your own side; no damage |
| WEAPON SHOT, CHAIR SHOT, POST SHOT | damage and a chance of bleeding (§6) |
| SMALL PKG., INV. CRADLE, ROLL. CRADLE | small damage, then a pin with their own odds (§9) |

## 8. Ring position (code)

The ring is positions 0-6: 1 and 5 are the ropes (each side's own corner side), 0 and 6 are
outside (`$7E:5AFE`). Each move moves the fight (table §11): one step, two steps, or "mirror"
(swap ends); holds drift it. At the ropes, pins and holds can be broken. When both fall outside
they fight there until the winner of an exchange calls RETURN (the CPU does after a while, stat
`+$3D`); there is no count-out.

## 9. Winning: pins and submissions (code; Mesen for the pin)

**Pinfall.** After a winning move, a pin follows when:

- the move is a **pinning move** (Pin "pins" in §11) and the opponent's HP is under 6 tenths, or it
  came from an O card; or
- the winner asked for it (the **PIN** command under the portrait; Down cycles PIN / TAG / PIN&TAG
  / RETURN / RET&TAG) and the move allows it ("on PIN"). The CPU asks with 100/80/60/40% when the
  loser's HP tenths are 0/1/2/3, and never above that.

The count (`$88:9F86`), with h = the loser's HP tenths:

1. **One:** kicked out with chance (h − 1)/10.
2. **Two:** kicked out with chance h/10. In tag and trios the partner may run in and break it up
   when the loser is in danger; at the ropes the loser may get a foot on the rope (chance h + two of
   her stats, in %).
3. **Three:**
   - **SMALL PKG., INV. CRADLE, ROLL. CRADLE:** win with chance (9 − h)/10 when h is 3 or less;
     at 4 or more, always kicked out.
   - **Every other move: the 3-count only comes when her HP is exactly 0** (`$88:A1AE`, `$88:A848`),
     and then almost always (a small stat-based escape). With any HP left it's a kick-out at 2.5, 2.8
     or 2.9.

**Submission** (`$89:A62E`, holds). Each round of a hold: a hold that only hits HP makes her give up
at 0 HP tenths; a limb hold makes her give up at once when that limb's meter is at 0 tenths,
otherwise with a small chance that grows below 3 HP tenths and with the attacker's lock attack and
the hold's level. The hold also has to beat her lock defence (half of it must be under the hold's
level). She escapes at the ropes, by breaking free (her HP tenths against the attacker's lock attack),
or when the hold runs out of rounds (6-7), and in tag matches a partner can cut in.

**Tags.** You tag when you win an exchange with TAG requested and you aren't outside (`$88:9B36`).

## 10. Bugs and oddities (code; Mesen where noted)

- **GUILLOTINE and MOONSAULT: +255 priority against a standing opponent.** Each move has a priority
  byte for "opponent standing" and one for "opponent down" (move bytes +37/+38). These two have
  **$FF** in the standing byte, almost certainly meant as −1 (a penalty for diving onto someone
  standing), but `$88:9366` reads it unsigned (`AND #$00FF`) and adds **255**. Normal scores are
  0-20, so they win nearly every exchange while the opponent is up, which is most of the match. Only
  a finisher card or the other side's own GUILLOTINE/MOONSAULT beats them. GUILLOTINE can't be
  countered, so once it wins it always lands; MOONSAULT can still turn into MISSED. (Mesen:
  MOONSAULT 268 vs DDT 11.)
  - Base rosters with GUILLOTINE (level 2-4): Chigusa Yuki, Beauty Ichigaya, Hikaru Ogawa, Cutie
    Kanai, Inferno Hiromi, Phantom Juri, Hikaru Ijuin, Thunder Ryuko, H. Fujishima, Kyoko Kurenai,
    Mami Sawanobori, and the foreign wrestlers Super Chaos, The Spike, Pink Flower, Remy Dadarne,
    Annie Blair, The Sekitori, Lady Cody, Despina Libre.
  - MOONSAULT, as a card and as the finisher: Mighty Yukiko (9), Chocho Caras (8), Luna Alpana (7).
- **The counter roll reads the wrong byte.** `$88:95B7` means to add the loser's move bonus for the
  winner's position, but drops the `TAX` and always reads the "standing" byte. It's 0 for every move
  but those two, so if you lose an exchange holding GUILLOTINE or MOONSAULT, a counterable move
  against you is always countered. (Not tried in game.)
- **CPU double-team cards: about +255 when behind.** The double-team card's attack/defence pair is
  written by the CPU's card logic as (its HP tenths − the opponent's) and 0 (`$89:8A0C`). When the
  CPU is behind this wraps to $FE/$FF and is read unsigned, so a CPU double-team card played while
  trailing wins almost every exchange. (Mesen: DBL DROPKICK scored 257.)
- **TAUNT can wrap a stat.** It takes 1 from stats without a floor; a 0 becomes 255 until the next
  move.
- **The automatic pin check reads side 0's card** (`$1664` instead of `$1664,X`): an O card in the
  first side's slot blocks the CPU's automatic pin for both sides.
- **A tag cut-in cooldown only counts down for side 0** (`$89:B47C`).
- **The finisher's hold bonus** checks the move's category for HP and two unrelated bytes for the arm
  and leg meters, so it rarely applies there.
- **Dead code:** after a counter, a branch meant to let an L9 MOONSAULT be dodged (DODGE, chance from
  the attacker's leg meter) can never run (`$88:9682`: counter moves are read as a byte, so the level
  check never matches).

## 11. Every move

Card: the card type that plays it ("counter" = only as a counter). Damage: base + per-level × L.
vs down: priority bonus against a downed opponent (§4). Bleed: chance to cause bleeding. Pin:
"pins" = a pinning move, "on PIN" = pins when asked, "no" = never. Knockback: how it moves the
fight (§8). From the move records at `$88:851B` (41 bytes each).

| ID | Move | Card | Levels | Damage (L = level) | vs down | Countered into | Bleed | Pin | Knockback |
|---|---|---|---|---|---|---|---|---|---|
| $01 | ARM DRAG | Throw | 1 | HP 15 | 4 | — | — | on PIN | 1 step |
| $02 | BODY SLAM | Throw | 1–3 | HP 15 + 4L | 4 | — | — | on PIN | 1 step |
| $03 | FRONT SUPLEX | Throw | 3–5 | HP 5 + 7L | 4 | — | — | on PIN | 1 step |
| $04 | BRAINBUSTER | Throw | 2–5 | HP 15 + 5L | 4 | BRAINBUSTER | — | on PIN | 1 step |
| $05 | BACKDROP | Throw | 4–8 | HP 10 + 9L | 4 | BODY PRESS | — | on PIN | 1 step |
| $06 | THROW | Throw | 4–7 | HP 20 + 7L | 4 | — | — | on PIN | 1 step |
| $07 | N.L. SUPLEX | Throw | 5–7 | HP 18 + 8L | 4 | — | — | pins | 1 step |
| $08 | CAPTURE | Throw | 6–8 | HP 6 + 10L | 4 | — | — | on PIN | 1 step |
| $09 | GERMAN S.P. | Throw | 7–9 | HP 15 + 9L | 4 | — | — | pins | 1 step |
| $0A | J.O. CYCLONE | Throw | 8–9 | HP 90 | 4 | — | — | pins | 1 step |
| $0B | SLEEPER HOLD | Lock | 1–4 | HP 12 + 4L | 4 | — | — | no | — |
| $0C | ARMBAR | Lock | 2–5 | arm 5 + 5L | 3 | — | — | no | — |
| $0D | CRAB HOLD | Lock | 2–4 | HP 10 + 4L, leg 5 + 3L | 5 | — | — | no | — |
| $0E | COBRA TWIST | Lock | 3–5 | HP 8 + 4L, arm 5 + 3L | 3 | — | — | no | — |
| $0F | CHICKENWING | Lock | 3–6 | arm 0 + 6L | 3 | — | — | no | — |
| $10 | ACHILLES LCK | Lock | 4–7 | leg 0 + 6L | 5 | — | — | no | — |
| $11 | STRETCH PLUM | Lock | 5–7 | HP 12 + 4L, arm 5 + 3L | 3 | — | — | no | — |
| $12 | SCORPION | Lock | 5–7 | HP 10 + 4L, leg 0 + 4L | 5 | — | — | no | — |
| $13 | FACE LOCK | Lock | 4–7 | HP 0 + 7L | 4 | — | — | no | — |
| $14 | S.T.F. | Lock | 6–8 | HP 0 + 5L, leg 0 + 4L | 5 | — | — | no | — |
| $15 | ELBOW BUTT | Strike | 1–4 | HP 10 + 6L | 3 | — | 5% | on PIN | mirror |
| $16 | PALM STRIKE | Strike | 2–5 | HP 5 + 10L | 3 | — | 10% | on PIN | — |
| $17 | LARIAT | Strike | 3–8 | HP 12 + 8L | 4 | LARIAT / ARMBAR | — | on PIN | mirror |
| $18 | DDT | Strike | 3–6 | HP 25 + 6L | 4 | — | — | on PIN | 1 step |
| $19 | COMBO KICK | Strike | 5–8 | HP 10 + 7L, leg 0 + 3L | 4 | — | — | on PIN | — |
| $1A | PILEDRIVER | Strike | 5–7 | HP 30 + 6L | 4 | REV. SUPLEX | — | on PIN | 1 step |
| $1B | BACKBREAKER | Strike | 3–6 | HP 20 + 7L | 4 | — | — | on PIN | — |
| $1C | N.LIGHT BOMB | Strike | 7–8 | HP 80 | 3 | — | — | on PIN | 1 step |
| $1D | POWER SLAM | Strike | 5–8 | HP 25 + 7L | 3 | ROLL. CRADLE | — | pins | 1 step |
| $1E | POWERBOMB | Strike | 5–8 | HP 30 + 7L | 3 | REV. SUPLEX / HURACANRANA | — | pins | — |
| $1F | DROPKICK | Fly | 1–3 | HP 15 + 5L | 3 | — | — | on PIN | mirror |
| $20 | ROLL. SOBAT | Fly | 1–3 | HP 10 + 9L | 4 | — | — | on PIN | mirror |
| $21 | GUILLOTINE | Fly | 2–4 | HP 18 + 5L | 5 (**+255 standing**) | — | — | on PIN | — |
| $22 | JUMPING KNEE | Fly | 2–4 | HP 20 + 5L | 3 | — | — | on PIN | mirror |
| $23 | FLY SHOULDER | Fly | 3–5 | HP 17 + 6L | 4 | — | — | on PIN | mirror |
| $24 | ENZUGIRI | Fly | 4–6 | HP 20 + 7L | 4 | — | — | on PIN | — |
| $25 | FLYING KNEE | Fly | 5–7 | HP 18 + 8L | 4 | MISSED | 10% | on PIN | mirror |
| $26 | MISSILE KICK | Fly | 5–7 | HP 20 + 8L | 3 | MISSED | — | on PIN | — |
| $27 | FRANKENSTEIN | Fly | 7–9 | HP 12 + 9L | 3 | POWERBOMB | 10% | pins | mirror |
| $28 | MOONSAULT | Fly | 7–8 | HP 25 + 8L | 2 (**+255 standing**) | MISSED | — | pins | — |
| $29 | PLANCHA | Fly | 4–7 | HP 20 + 7L | 0 | MISSED | 15% | no | — |
| $2A | BACK OFF | Other | 1–5 | — | 5 | — | — | no | 2 steps |
| $2B | TAUNT | Other | 1–5 | — | 5 | — | — | no | — |
| $2C | WEAPON SHOT | Other | 3–6 | HP 20 + 6L | 4 | WEAPON SHOT | 20% | on PIN | 1 step |
| $2D | SMALL PKG. | Other | 4 | HP 10 | 3 | — | — | pins | 1 step |
| $2E | INV. CRADLE | Other | 5 | HP 10 | 3 | — | — | pins | — |
| $2F | ROLL. CRADLE | Other | 6 | HP 20 | 3 | — | — | pins | mirror |
| $30 | CHAIR SHOT | Other | 2–5 | HP 30 + 5L | 0 | — | 15% | no | — |
| $31 | POST SHOT | Other | 3 | HP 45 | 0 | — | 20% | no | — |
| $32 | PSYCH UP | Other | 1–5 | — | 4 | — | — | no | — |
| $33 | DBL DROPKICK | Double | 3 | HP 40 | 4 | — | — | on PIN | mirror |
| $34 | DBL BUSTER | Double | 4 | HP 52 | 4 | — | — | on PIN | 1 step |
| $35 | DBL PILEDRVR | Double | 6 | HP 78 | 3 | — | — | on PIN | 1 step |
| $36 | DBL P.BOMB | Double | 7 | HP 90 | 3 | — | — | pins | 1 step |
| $37 | DBL IMPACT | Double | 8 | HP 96 | 3 | — | — | on PIN | 1 step |
| $38 | BODY PRESS | counter | — | HP 20 | — | — | — | pins | — |
| $39 | REV. SUPLEX | counter | — | HP 25 | — | — | — | pins | 1 step |
| $3A | MISSED | counter | — | HP 25, leg 10 | — | — | — | no | — |
| $3B | BRAINBUSTER | counter | — | HP 25 | — | — | — | no | 1 step |
| $3C | LARIAT | counter | — | HP 32 | — | — | — | on PIN | mirror |
| $3D | ROLL. CRADLE | counter | — | HP 10 | — | — | — | pins | 1 step |
| $3E | POWERBOMB | counter | — | HP 60 | — | — | — | pins | 1 step |
| $3F | WEAPON SHOT | counter | — | HP 40 | — | — | — | no | — |
| $40 | RECOVER | finisher card | — | heals (§7) | — | — | — | no | — |
| $41 | ARMBAR | counter | — | arm 20 | — | — | — | no | — |
| $42 | HURACANRANA | counter | — | HP 25 | — | — | — | pins | — |
| $43 | PIN | — | — | — | — | — | — | — | — |
| $44 | DODGE | — | — | — | — | — | — | — | — |
| $45 | WIN POSE | — | — | — | — | — | — | — | — |

$46-$48 are three more MISSED records (the same move with the crash animation of MISSILE KICK,
MOONSAULT and PLANCHA).

## 12. Reference

**Move record** (`$88:851B` + 41 × (ID − 1); code reads it as `$88:84F2 + 41 × ID`, `$88:8000`
multiplies): +0 name (12 bytes), +12 ID, +13 category (1-5 T L S F O, 6 RECOVER, 7 double-team,
8 counter), +14 animation move, +15..+18 animation frames, +19..+21 base damage (HP, arm, leg),
+22..+24 per-level damage, +25/+26 lowest/highest level, +27/+28 counter moves, +29 the stat type
that picks the second counter, +30 pin (0 no, 1 on PIN, 2 pins), +31 finishing-hold name (match
results), +33 bleeding %, +34 knockback (1 step, 2 mirror, 3 two steps), +35 hold rounds, +36 ring
positions allowed (bits), **+37/+38 priority vs standing / vs down**, +39 pointer.

**Wrestler data in the ROM** (`$92:9EF1` + 84 × (ID − 1), file 0x91ef1): 22 bytes of stats, then
5 × 6 move words (move ID, level), then the finisher word.

**In a match** (`$7E`):

| Address | What |
|---|---|
| `$5977`, `$5A34` | the two active wrestlers, 189 bytes each (`$92:9E10` table, `$92:9C13` index): +$1D/+$1F max/current HP, +$21/+$23 arm, +$25/+$27 leg (words); +$2B.. seven (attack, defence) pairs for T L S F O, finisher, double-team; +$39.. stats (+$3A strength, +$3C recovery); +$42 move list; +$A7 controller (0 = CPU); +$AC bleeding; +$AE finishers dealt |
| `$5509` | tag and trios team members (same layout) |
| `$5B05`, `$5B0F` | the hands, 5 × (type, number) |
| `$5B2D`/`$5B2E` | the card each side played; `$5B2F`/`$5B30` the move slot chosen |
| `$1660`/`$1662` | each side's move word (ID, level); `$1664`/`$1666` their cards |
| `$1668` | the exchange winner; `$166A` the move being done |
| `$5B01`/`$5B02` | the last exchange's winner and their streak |
| `$5B39`/`$5B3A` | each side down (1) or standing (0) |
| `$5AFD` | 0 singles, 1 tag, 2 trios; `$5AFE` ring position 0-6 |
| `$5B31`, `$5B35`, `$5B37` | TAG, PIN and RETURN requests |
| `$5B03` | the match clock; `$16A0` match over (1 submission, 2 pinfall) |
| `$7220` | difficulty: 0 Easy, 1 Normal (default), 2 Hard |

## 13. Not settled yet

- The double-team card's own move choice (`$89:9D26`), and whether its stat pair is ever set for a
  human.
- The submission odds and the breaking-free roll are from the code only; one term (`$0536`) may be
  a stale value.
- The CPU's card choice (`$89:8994` evaluates the card types) is only partly read.
- What BACK OFF's RETURN flag does beyond the ring position; the stat array's other entries
  (`+$39`[0], [4], [5], [6]).
- Who takes MISSED's damage, and DODGE / WIN POSE.
