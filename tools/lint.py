#!/usr/bin/env python3
"""Check the translation text: python3 tools/lint.py [--missing] [--warnings] [file...]

Errors (check.py and the build fail on these):
  source       source-language characters (kana, kanji) left in the English
  codes        control codes in the source missing from the English, or extra ones (CODE)
  lines        more lines than a block file's `# limit lines=N`
  chars        a line longer than `# limit chars=N` (characters; pixel widths need the game's
               own layout check)
  bytes        English longer than a fixed table string's max_bytes (refs == 0), as encoded by
               encoded_length() - adjust it to how the build stores English
Warnings (shown with --warnings; counted by status.py):
  glossary     the source contains a glossary term but the English doesn't use its translation
               (translation/glossary.csv: japanese, english, notes; several accepted English forms
               separated by ' | '; put [glossary-ok] in a block comment or row note to silence)
  spacing      trailing spaces or double spaces in the English (leading spaces are left alone:
               continuation lines are often indented)
--missing also lists untranslated entries (status.py counts them).
"""
import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import textdb  # noqa: E402

SOURCE_CHARS = re.compile(r'[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]')
CODE = re.compile(r'\{[^{}]*\}|<[^<>]*>|\\[nr]|%[-0-9.]*[sdx]')  # the game's control codes: adjust


def encoded_length(text):
    """Bytes the build will store for `text` - change to match the build (e.g. 2 per char for full-width)."""
    return len(text.encode('ascii', 'replace'))


def glossary():
    if not paths.GLOSSARY.exists():
        return []
    with open(paths.GLOSSARY, encoding='utf-8', newline='') as f:
        return [(r['japanese'].strip(), [e.strip() for e in r['english'].split(' | ') if e.strip()])
                for r in csv.DictReader(f) if (r.get('japanese') or '').strip() and (r.get('english') or '').strip()]


def check_entry(e, terms):
    """[(severity, kind, message)] for one entry."""
    out = []
    en = e.english
    if not en:
        return out
    m = SOURCE_CHARS.search(en)
    if m:
        out.append(('error', 'source', f'source-language text left in the English: {m.group()!r}'))
    a, b = Counter(CODE.findall(e.source)), Counter(CODE.findall(en))
    if a != b:
        miss, extra = list((a - b).elements()), list((b - a).elements())
        out.append(('error', 'codes', 'control codes ' + '; '.join(
            x for x in (f'missing {miss}' if miss else '', f'extra {extra}' if extra else '') if x)))
    lines = en.split('\n')
    if 'lines' in e.limits and len(lines) > e.limits['lines']:
        out.append(('error', 'lines', f'{len(lines)} lines, limit {e.limits["lines"]}'))
    if 'chars' in e.limits:
        for ln in lines:
            plain = CODE.sub('', ln)
            if len(plain) > e.limits['chars']:
                out.append(('error', 'chars', f'{len(plain)} characters, limit {e.limits["chars"]}: {ln!r}'))
    if 'max_bytes' in e.limits and e.limits.get('refs', 0) == 0 and encoded_length(en) > e.limits['max_bytes']:
        out.append(('error', 'bytes', f'{encoded_length(en)} bytes, room for {e.limits["max_bytes"]} (fixed string)'))
    if any(ln != ln.rstrip() or '  ' in ln.strip() for ln in lines):
        out.append(('warning', 'spacing', f'trailing or double spaces: {en!r}'))
    for jp, accepted in terms:
        if jp in e.source and not any(x.lower() in en.lower() for x in accepted):
            out.append(('warning', 'glossary', f'{jp} should be "{" | ".join(accepted)}"'))
    return out


def run(files=None, missing=False):
    """{'error': n, 'warning': n, 'missing': n, 'total': n} plus the printed lines."""
    terms = glossary()
    ents = []
    for p in files or textdb.text_files():
        ents += textdb.read_file(p)
    report, counts = [], Counter()
    for e in ents:
        counts['total'] += 1
        if not e.english:
            counts['missing'] += 1
            if missing:
                report.append(('missing', e, 'no English yet'))
            continue
        for sev, kind, msg in check_entry(e, [] if '[glossary-ok]' in e.notes else terms):
            counts[sev] += 1
            report.append((sev, e, f'{kind}: {msg}'))
    return counts, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=paths.FOLDER_HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', type=Path, help='only these text files (default: all)')
    ap.add_argument('--missing', action='store_true', help='also list untranslated entries')
    ap.add_argument('--warnings', action='store_true', help='also list warnings')
    args = ap.parse_args(paths.configure(sys.argv[1:] if argv is None else argv))
    counts, report = run(args.files or None, args.missing)
    for sev, e, msg in report:
        if sev == 'warning' and not args.warnings:
            continue
        print(f'{e.where}: {"! " if sev == "error" else ""}{msg}')
    print(f'{counts["total"]} entries, {counts["total"] - counts["missing"]} translated: '
          f'{counts["error"]} error(s), {counts["warning"]} warning(s)'
          + ('' if args.warnings or not counts['warning'] else ' (--warnings to list them)'))
    return 1 if counts['error'] else 0


if __name__ == '__main__':
    sys.exit(main())
