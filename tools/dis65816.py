#!/usr/bin/env python3
"""A 65816 disassembler with M/X flag tracking, and reference search. Standard library only.

  dis65816.py ROM ADDR [COUNT] [--m8|--m16] [--x8|--x16]
      disassemble COUNT instructions (default 40) from CPU address ADDR ($C08000, 80:8000, ...)
  dis65816.py refs ROM ADDR
      code that calls, jumps to or loads from ADDR (JSL/JML/long loads anywhere; JSR/JMP and
      absolute loads only from the same bank), and 16/24-bit pointers to it - for text pointer tables

Immediate operands are 8 or 16 bits depending on the M flag (accumulator, memory) and X flag
(index registers). The disassembler starts in the state you give (default 8-bit, the state after
reset is 8-bit too) and follows REP/SEP; after a branch target or a subroutine entry the real state
can differ - if the listing turns to nonsense, restart there with the other flag. Mesen's debugger
shows the real state at any breakpoint.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snes  # noqa: E402

# mode: operand bytes ('M'/'X' = 1 or 2 by flag), format
MODES = {
    'imp': (0, ''), 'acc': (0, 'A'), 'imm': (1, '#${:02X}'), 'immM': ('M', '#${}'), 'immX': ('X', '#${}'),
    'dp': (1, '${:02X}'), 'dpx': (1, '${:02X},X'), 'dpy': (1, '${:02X},Y'),
    'idp': (1, '(${:02X})'), 'idpx': (1, '(${:02X},X)'), 'idpy': (1, '(${:02X}),Y'),
    'ildp': (1, '[${:02X}]'), 'ildpy': (1, '[${:02X}],Y'),
    'abs': (2, '${:04X}'), 'absx': (2, '${:04X},X'), 'absy': (2, '${:04X},Y'),
    'long': (3, '${:06X}'), 'longx': (3, '${:06X},X'),
    'sr': (1, '${:02X},S'), 'isry': (1, '(${:02X},S),Y'),
    'rel': (1, None), 'rell': (2, None),
    'iabs': (2, '(${:04X})'), 'iabsx': (2, '(${:04X},X)'), 'ilabs': (2, '[${:04X}]'),
    'bm': (2, None),
}

_ALU = ['idpx', 'sr', 'dp', 'ildp', 'immM', 'abs', 'long', 'idpy', 'idp', 'isry', 'dpx', 'ildpy', 'absy', 'absx', 'longx']
_ALU_COLS = [0x01, 0x03, 0x05, 0x07, 0x09, 0x0d, 0x0f, 0x11, 0x12, 0x13, 0x15, 0x17, 0x19, 0x1d, 0x1f]
OPS = {}
for _row, _m in zip(range(0, 0x100, 0x20), ['ORA', 'AND', 'EOR', 'ADC', 'STA', 'LDA', 'CMP', 'SBC']):
    for _c, _mode in zip(_ALU_COLS, _ALU):
        OPS[_row + _c] = (_m, _mode)
del OPS[0x89]   # STA # doesn't exist: $89 is BIT #
OPS.update({
    0x00: ('BRK', 'imm'), 0x02: ('COP', 'imm'), 0x04: ('TSB', 'dp'), 0x06: ('ASL', 'dp'), 0x08: ('PHP', 'imp'),
    0x0a: ('ASL', 'acc'), 0x0b: ('PHD', 'imp'), 0x0c: ('TSB', 'abs'), 0x0e: ('ASL', 'abs'),
    0x10: ('BPL', 'rel'), 0x14: ('TRB', 'dp'), 0x16: ('ASL', 'dpx'), 0x18: ('CLC', 'imp'), 0x1a: ('INC', 'acc'),
    0x1b: ('TCS', 'imp'), 0x1c: ('TRB', 'abs'), 0x1e: ('ASL', 'absx'),
    0x20: ('JSR', 'abs'), 0x22: ('JSL', 'long'), 0x24: ('BIT', 'dp'), 0x26: ('ROL', 'dp'), 0x28: ('PLP', 'imp'),
    0x2a: ('ROL', 'acc'), 0x2b: ('PLD', 'imp'), 0x2c: ('BIT', 'abs'), 0x2e: ('ROL', 'abs'),
    0x30: ('BMI', 'rel'), 0x34: ('BIT', 'dpx'), 0x36: ('ROL', 'dpx'), 0x38: ('SEC', 'imp'), 0x3a: ('DEC', 'acc'),
    0x3b: ('TSC', 'imp'), 0x3c: ('BIT', 'absx'), 0x3e: ('ROL', 'absx'),
    0x40: ('RTI', 'imp'), 0x42: ('WDM', 'imm'), 0x44: ('MVP', 'bm'), 0x46: ('LSR', 'dp'), 0x48: ('PHA', 'imp'),
    0x4a: ('LSR', 'acc'), 0x4b: ('PHK', 'imp'), 0x4c: ('JMP', 'abs'), 0x4e: ('LSR', 'abs'),
    0x50: ('BVC', 'rel'), 0x54: ('MVN', 'bm'), 0x56: ('LSR', 'dpx'), 0x58: ('CLI', 'imp'), 0x5a: ('PHY', 'imp'),
    0x5b: ('TCD', 'imp'), 0x5c: ('JML', 'long'), 0x5e: ('LSR', 'absx'),
    0x60: ('RTS', 'imp'), 0x62: ('PER', 'rell'), 0x64: ('STZ', 'dp'), 0x66: ('ROR', 'dp'), 0x68: ('PLA', 'imp'),
    0x6a: ('ROR', 'acc'), 0x6b: ('RTL', 'imp'), 0x6c: ('JMP', 'iabs'), 0x6e: ('ROR', 'abs'),
    0x70: ('BVS', 'rel'), 0x74: ('STZ', 'dpx'), 0x76: ('ROR', 'dpx'), 0x78: ('SEI', 'imp'), 0x7a: ('PLY', 'imp'),
    0x7b: ('TDC', 'imp'), 0x7c: ('JMP', 'iabsx'), 0x7e: ('ROR', 'absx'),
    0x80: ('BRA', 'rel'), 0x82: ('BRL', 'rell'), 0x84: ('STY', 'dp'), 0x86: ('STX', 'dp'), 0x88: ('DEY', 'imp'),
    0x89: ('BIT', 'immM'), 0x8a: ('TXA', 'imp'), 0x8b: ('PHB', 'imp'), 0x8c: ('STY', 'abs'), 0x8e: ('STX', 'abs'),
    0x90: ('BCC', 'rel'), 0x94: ('STY', 'dpx'), 0x96: ('STX', 'dpy'), 0x98: ('TYA', 'imp'), 0x9a: ('TXS', 'imp'),
    0x9b: ('TXY', 'imp'), 0x9c: ('STZ', 'abs'), 0x9e: ('STZ', 'absx'),
    0xa0: ('LDY', 'immX'), 0xa2: ('LDX', 'immX'), 0xa4: ('LDY', 'dp'), 0xa6: ('LDX', 'dp'), 0xa8: ('TAY', 'imp'),
    0xaa: ('TAX', 'imp'), 0xab: ('PLB', 'imp'), 0xac: ('LDY', 'abs'), 0xae: ('LDX', 'abs'),
    0xb0: ('BCS', 'rel'), 0xb4: ('LDY', 'dpx'), 0xb6: ('LDX', 'dpy'), 0xb8: ('CLV', 'imp'), 0xba: ('TSX', 'imp'),
    0xbb: ('TYX', 'imp'), 0xbc: ('LDY', 'absx'), 0xbe: ('LDX', 'absy'),
    0xc0: ('CPY', 'immX'), 0xc2: ('REP', 'imm'), 0xc4: ('CPY', 'dp'), 0xc6: ('DEC', 'dp'), 0xc8: ('INY', 'imp'),
    0xca: ('DEX', 'imp'), 0xcb: ('WAI', 'imp'), 0xcc: ('CPY', 'abs'), 0xce: ('DEC', 'abs'),
    0xd0: ('BNE', 'rel'), 0xd4: ('PEI', 'idp'), 0xd6: ('DEC', 'dpx'), 0xd8: ('CLD', 'imp'), 0xda: ('PHX', 'imp'),
    0xdb: ('STP', 'imp'), 0xdc: ('JML', 'ilabs'), 0xde: ('DEC', 'absx'),
    0xe0: ('CPX', 'immX'), 0xe2: ('SEP', 'imm'), 0xe4: ('CPX', 'dp'), 0xe6: ('INC', 'dp'), 0xe8: ('INX', 'imp'),
    0xea: ('NOP', 'imp'), 0xeb: ('XBA', 'imp'), 0xec: ('CPX', 'abs'), 0xee: ('INC', 'abs'),
    0xf0: ('BEQ', 'rel'), 0xf4: ('PEA', 'abs'), 0xf6: ('INC', 'dpx'), 0xf8: ('SED', 'imp'), 0xfa: ('PLX', 'imp'),
    0xfb: ('XCE', 'imp'), 0xfc: ('JSR', 'iabsx'), 0xfe: ('INC', 'absx'),
})
assert len(OPS) == 256


class State:
    def __init__(self, m8=True, x8=True):
        self.m8, self.x8 = m8, x8


def length(op, st):
    n = MODES[OPS[op][1]][0]
    if n == 'M':
        n = 1 if st.m8 else 2
    elif n == 'X':
        n = 1 if st.x8 else 2
    return 1 + n


def decode(code, pc, st):
    """(length, text, target or None) of the instruction at CPU address pc; updates st for REP/SEP."""
    op = code[0]
    mnem, mode = OPS[op]
    n = length(op, st)
    b = code[1:n]
    v = int.from_bytes(b, 'little') if b else 0
    target = None
    if mode == 'rel':
        target = (pc & 0xff0000) | ((pc + 2 + (v - 256 if v & 0x80 else v)) & 0xffff)
        arg = f'${target & 0xffff:04X}'
    elif mode == 'rell':
        target = (pc & 0xff0000) | ((pc + 3 + (v - 65536 if v & 0x8000 else v)) & 0xffff)
        arg = f'${target & 0xffff:04X}'
    elif mode == 'bm':
        arg = f'${b[1]:02X},${b[0]:02X}'   # source bank, destination bank (stored dest first)
    elif mode in ('immM', 'immX'):
        arg = '#$' + (f'{v:02X}' if n == 2 else f'{v:04X}')
    else:
        arg = MODES[mode][1].format(v) if MODES[mode][1] else ''
    if mnem in ('JSR', 'JMP') and mode == 'abs':
        target = (pc & 0xff0000) | v
    elif mnem in ('JSL', 'JML') and mode == 'long':
        target = v
    if mnem == 'REP':
        st.m8 = st.m8 and not v & 0x20
        st.x8 = st.x8 and not v & 0x10
    elif mnem == 'SEP':
        st.m8 = st.m8 or bool(v & 0x20)
        st.x8 = st.x8 or bool(v & 0x10)
    return n, f'{mnem} {arg}'.rstrip(), target


def disassemble(rom, addr, count, st):
    lines = []
    for _ in range(count):
        off = rom.to_file(addr)
        code = bytes(rom.data[off:off + 4])
        n, text, _ = decode(code, addr, st)
        lines.append(f'{snes.fmt(addr)}  {code[:n].hex(" ").upper():<12} {text}')
        addr = (addr & 0xff0000) | ((addr + n) & 0xffff)
    return lines


def refs(rom, target):
    """[(offset, what)] of references to CPU address `target`."""
    d, out = rom.data, []
    t16, t24 = (target & 0xffff).to_bytes(2, 'little'), target.to_bytes(3, 'little')
    alt = (target ^ 0x800000).to_bytes(3, 'little')   # the other mirror (slow/fast ROM)
    long_ops = {0x22: 'JSL', 0x5c: 'JML', 0xaf: 'LDA long', 0xbf: 'LDA long,X', 0x8f: 'STA long', 0x9f: 'STA long,X'}
    abs_ops = {0x20: 'JSR', 0x4c: 'JMP', 0xad: 'LDA abs', 0xbd: 'LDA abs,X', 0xb9: 'LDA abs,Y', 0xae: 'LDX abs',
               0xac: 'LDY abs', 0xa9: 'LDA #', 0xa2: 'LDX #', 0xa0: 'LDY #', 0xf4: 'PEA'}
    for i in range(len(d) - 3):
        w3 = bytes(d[i + 1:i + 4])
        if d[i] in long_ops and w3 in (t24, alt):
            out.append((i, long_ops[d[i]]))
        elif w3 in (t24, alt):
            out.append((i + 1, '24-bit pointer'))
        elif d[i] in abs_ops and w3[:2] == t16 and rom.to_cpu(i) >> 16 & 0x7f == target >> 16 & 0x7f:
            out.append((i, abs_ops[d[i]] + ' (same bank)'))
    for i in range(len(d) - 1):
        if bytes(d[i:i + 2]) == t16 and not any(o in (i, i - 1) for o, _ in out[-4:]):
            out.append((i, '16-bit pointer'))
    return sorted(set(out))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'refs':
        if len(argv) != 3:
            sys.exit(__doc__)
        rom = snes.Rom.open(argv[1])
        t = snes.parse_addr(argv[2])
        hits = refs(rom, t)
        for off, what in hits:
            print(f'{off:#08x} {snes.fmt(rom.to_cpu(off))}  {what}')
        print(f'{len(hits)} reference(s) to {snes.fmt(t)} (16-bit pointers include chance matches)')
        return
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    ap.add_argument('rom')
    ap.add_argument('addr', type=snes.parse_addr)
    ap.add_argument('count', type=int, nargs='?', default=40)
    ap.add_argument('--m16', action='store_true')
    ap.add_argument('--x16', action='store_true')
    ap.add_argument('--m8', action='store_true', help='(default)')
    ap.add_argument('--x8', action='store_true', help='(default)')
    args = ap.parse_args(argv)
    rom = snes.Rom.open(args.rom)
    print('\n'.join(disassemble(rom, args.addr, args.count, State(not args.m16, not args.x16))))


if __name__ == '__main__':
    main()
