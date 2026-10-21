#!/usr/bin/env python3
"""Text tables (.tbl): the game's own character encoding, for decoding, dumping and inserting text.

  tbl.py dump TABLE ROM START END [--end HEX]
      decode file offsets START..END, one string per terminator (--end, default the table's /XX)
  tbl.py decode TABLE HEXBYTES
  tbl.py encode TABLE TEXT

Table lines (Thingy format, the one romhacking tools share):
  20=あ          one byte
  8140=漢        two (or more) bytes
  FE=[name]      a control code: decoded as the bracketed text, encoded from it
  /FF=[end]      the string terminator
  # comment
Decoding takes the longest byte sequence that matches; bytes with no entry show as [$xx]. Encoding
takes the longest text that matches, and [$xx] always means the raw byte.
"""
import re
import sys
from pathlib import Path

RAW = re.compile(r'\[\$([0-9a-fA-F]{2})\]')


class Table:
    def __init__(self, path=None, lines=None):
        self.dec, self.enc, self.end = {}, {}, None
        if path is not None:
            lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
        for line in lines or []:
            self.add_line(line)

    def add_line(self, line):
        line = line.rstrip('\r\n')
        if not line.strip() or line.startswith('#'):
            return
        end = line.startswith('/')
        if end:
            line = line[1:]
        code, _, text = line.partition('=')
        code = bytes.fromhex(code.strip())
        if end:
            self.end = code
            text = text or '[end]'
        self.dec[code] = text
        self.enc.setdefault(text, code)

    def add(self, code, text):
        self.dec[bytes(code)] = text
        self.enc.setdefault(text, bytes(code))

    @property
    def longest(self):
        return max((len(k) for k in self.dec), default=1)

    def decode(self, data, stop_at_end=False):
        """(text, bytes used)."""
        out, i, n, longest = [], 0, len(data), self.longest
        while i < n:
            for k in range(min(longest, n - i), 0, -1):
                t = self.dec.get(bytes(data[i:i + k]))
                if t is not None:
                    out.append(t)
                    i += k
                    break
            else:
                out.append(f'[${data[i]:02x}]')
                i += 1
                continue
            if stop_at_end and self.end is not None and bytes(data[i - len(self.end):i]) == self.end:
                break
        return ''.join(out), i

    def encode(self, text):
        out, i, longest = bytearray(), 0, max((len(t) for t in self.enc), default=1)
        while i < len(text):
            m = RAW.match(text, i)
            if m:
                out.append(int(m.group(1), 16))
                i = m.end()
                continue
            for k in range(min(longest, len(text) - i), 0, -1):
                code = self.enc.get(text[i:i + k])
                if code is not None:
                    out += code
                    i += k
                    break
            else:
                raise ValueError(f'no table entry for {text[i]!r} in {text!r}')
        return bytes(out)

    def strings(self, data, start, end):
        """[(offset, text)] for terminator-separated strings in data[start:end]."""
        out, i = [], start
        while i < end:
            text, used = self.decode(data[i:end], stop_at_end=True)
            out.append((i, text))
            i += max(used, 1)
        return out


def main(argv):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import snes
    if len(argv) >= 5 and argv[0] == 'dump':
        t = Table(argv[1])
        if '--end' in argv:
            t.end = bytes.fromhex(argv[argv.index('--end') + 1])
        data = snes.read_rom(argv[2])[0]
        for off, text in t.strings(data, int(argv[3], 0), int(argv[4], 0)):
            print(f'{off:06x}  {text}')
    elif len(argv) == 3 and argv[0] == 'decode':
        print(Table(argv[1]).decode(bytes.fromhex(argv[2]))[0])
    elif len(argv) == 3 and argv[0] == 'encode':
        print(Table(argv[1]).encode(argv[2]).hex(' '))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
