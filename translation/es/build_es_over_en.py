"""Build Spanish text tables under the ENGLISH file names.

The patched client reads column 1 of the two-column tables, so it shows Spanish
without any language switch. For each of the author's tables on the phone:
    rows = union(keys of the author's table, keys of the official Spanish table)
    v0   = English text (the author's, else the official one)
    v1   = official Spanish if not empty, else the English text (to translate later)
The output is one big ECB line like the official tables.

Example:
    build_es_over_en.py --author phone_en --official es --apk config.arm64_v8a.apk --out out/es_over_en
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import es_common as common


def build_rows(author, official, stats):
    """'key^English^Spanish' lines; official rows first, then the ones only the author has."""
    order = list(official) + [key for key in author if key not in official]
    return [table_line(key, author.get(key), official.get(key), stats) for key in order]


def table_line(key, author_row, official_row, stats):
    english = author_row[0] if author_row else official_row[0]
    spanish = official_spanish(official_row)
    stats['es_official' if spanish else 'fallback_en'] += 1
    stats['author_only_rows'] += official_row is None
    return f'{key}^{english}^{spanish or english}'


def official_spanish(row):
    """The Spanish column of an official row, or None when it is missing or blank."""
    if row and len(row) > 1 and row[1].strip():
        return row[1]
    return None


def table_key(token, by_token):
    return common.EXTRA_KEYS.get(token) or by_token[token]['key']


def build_table(file, official_files, by_token, stats):
    token = common.TABLE_FILE.match(file.name).group(2)
    key = table_key(token, by_token)
    author = common.row_values(file, key)
    official_file = official_files.get(token)
    official = common.row_values(official_file[1], key) if official_file else {}
    lines = build_rows(author, official, stats)
    stats['rows'] += len(lines)
    plain = ('\n'.join(lines) + '\n').encode('utf-8')
    return common.encode_table(key, plain) + b'\n'


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--author', type=Path, required=True, help="the author's English tables (Ver*.dat)")
    parser.add_argument('--official', type=Path, required=True, help='the official Spanish tables')
    parser.add_argument('--apk', required=True, help='APK holding libgame.so (for the keys)')
    parser.add_argument('--out', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    by_token = common.table_keys(common.read_native(args.apk))
    official_files = common.latest_files(args.official)
    args.out.mkdir(parents=True, exist_ok=True)
    stats = Counter(files=0)
    for file in sorted(args.author.glob('Ver*.dat')):
        (args.out / file.name).write_bytes(build_table(file, official_files, by_token, stats))
        stats['files'] += 1
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
