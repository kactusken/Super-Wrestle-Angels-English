#!/usr/bin/env python3
"""BPS patches: make and apply. Standard library only.

  bps.py make ORIGINAL PATCHED OUT.bps
  bps.py apply ORIGINAL PATCH.bps OUT

BPS is the usual format for cartridge games (romhacking.net, Flips, Rom Patcher JS, MultiPatch,
Floating IPS). Unlike IPS it records the source and target CRC32s, so a patcher refuses the wrong
ROM, and it has no 16 MB limit. The encoder is linear: unchanged bytes are copied from the source,
changed ones stored, and runs of one byte (expanded ROM padding) repeated from the target. That
keeps translation patches small; it doesn't search for moved blocks.
"""
import sys
import zlib
from pathlib import Path

SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = range(4)
MIN_SAME = 4      # shorter unchanged stretches inside a changed region are stored with it
MIN_RUN = 16      # runs of one byte this long are repeated rather than stored


def _num(n, out):
    while True:
        x = n & 0x7f
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return
        out.append(x)
        n -= 1


def _signed(n, out):
    _num(abs(n) << 1 | (n < 0), out)


def make(source, target, metadata=b''):
    source, target = bytes(source), bytes(target)
    out = bytearray(b'BPS1')
    _num(len(source), out)
    _num(len(target), out)
    _num(len(metadata), out)
    out += metadata
    target_rel = 0   # the decoder's TargetCopy position

    def action(kind, length):
        _num((length - 1) << 2 | kind, out)

    i, n, ns = 0, len(target), len(source)
    while i < n:
        j = i
        while j < n and j < ns and target[j] == source[j]:
            j += 1
        if j > i:
            action(SOURCE_READ, j - i)
            i = j
            continue
        # a changed region: up to the next unchanged stretch of MIN_SAME bytes
        j = i
        while j < n:
            if j < ns and target[j:j + MIN_SAME] == source[j:j + MIN_SAME] and j + MIN_SAME <= n:
                break
            j += 1
        k = i
        while k < j:   # store the region, repeating long runs of one byte
            r = k
            while r < j and target[r] == target[k]:
                r += 1
            if r - k >= MIN_RUN:
                action(TARGET_READ, 1)
                out.append(target[k])
                action(TARGET_COPY, r - k - 1)
                _signed(k - target_rel, out)
                target_rel = k + (r - k - 1)
                k = r
                continue
            e = k
            while e < j:   # plain bytes up to the next long run
                r = e
                while r < j and target[r] == target[e]:
                    r += 1
                if r - e >= MIN_RUN:
                    break
                e = r
            action(TARGET_READ, e - k)
            out += target[k:e]
            k = e
        i = j
    for c in (zlib.crc32(source), zlib.crc32(target)):
        out += c.to_bytes(4, 'little')
    out += zlib.crc32(out).to_bytes(4, 'little')
    return bytes(out)


def apply(source, patch):
    source, patch = bytes(source), bytes(patch)
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS patch')
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], 'little'):
        raise ValueError('patch is damaged (CRC32)')
    pos = 4

    def num():
        nonlocal pos
        n, shift = 0, 1
        while True:
            x = patch[pos]
            pos += 1
            n += (x & 0x7f) * shift
            if x & 0x80:
                return n
            shift <<= 7
            n += shift

    ssize, tsize, msize = num(), num(), num()
    pos += msize
    if len(source) != ssize or zlib.crc32(source) != int.from_bytes(patch[-12:-8], 'little'):
        raise ValueError('wrong source file for this patch (size or CRC32)')
    target = bytearray()
    srel = trel = 0
    end = len(patch) - 12
    while pos < end:
        d = num()
        kind, length = d & 3, (d >> 2) + 1
        if kind == SOURCE_READ:
            target += source[len(target):len(target) + length]
        elif kind == TARGET_READ:
            target += patch[pos:pos + length]
            pos += length
        else:
            o = num()
            o = -(o >> 1) if o & 1 else o >> 1
            if kind == SOURCE_COPY:
                srel += o
                target += source[srel:srel + length]
                srel += length
            else:
                trel += o
                for _ in range(length):
                    target.append(target[trel])
                    trel += 1
    if len(target) != tsize or zlib.crc32(target) != int.from_bytes(patch[-8:-4], 'little'):
        raise ValueError('patch did not produce the expected target (size or CRC32)')
    return bytes(target)


def main(argv):
    if len(argv) == 4 and argv[0] == 'make':
        p = make(Path(argv[1]).read_bytes(), Path(argv[2]).read_bytes())
        Path(argv[3]).write_bytes(p)
        print(f'{argv[3]}: {len(p)} bytes')
    elif len(argv) == 4 and argv[0] == 'apply':
        Path(argv[3]).write_bytes(apply(Path(argv[1]).read_bytes(), Path(argv[2]).read_bytes()))
        print(f'{argv[3]}: written')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
