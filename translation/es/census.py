"""Census of the language columns across localized tables: how many cells each column has and
how many are filled, plus the biggest tables and a sample of three well-known ones.

Example:
    census.py --apk config.arm64_v8a.apk --folder samples/en
"""
import argparse
from collections import Counter
from pathlib import Path

import es_common as common

SAMPLE_TABLES = ('F_TEXT_ABILITY_NAME', 'F_TEXT_MONSTER_NAME', 'F_TEXT_GACHA')
SAMPLE_ROWS = slice(100, 104)


def decode_file(file, entry):
    localized = entry['table'].startswith('F_TEXT')
    return common.decoder.decode(file.read_bytes(), entry['key'], localized=localized)[1]


def decode_all(folder, by_token):
    """(decoded tables, failures); a table is (name, records)."""
    tables, failures = [], []
    for file in sorted(folder.glob('Ver*.dat')):
        entry = by_token.get(file.stem.split('_', 1)[1])
        if not entry:
            failures.append((file.name, 'nomanifest'))
            continue
        try:
            tables.append((entry['table'], decode_file(file, entry)))
        except Exception as error:  # a table we cannot decode is reported, not fatal
            failures.append((file.name, str(error)[:50]))
    return tables, failures


def column_counts(tables):
    cells, filled = Counter(), Counter()
    for _, records in tables:
        for record in records:
            for index, cell in enumerate(record.get('v', [])):
                cells[index] += 1
                filled[index] += bool(cell.strip())
    return cells, filled


def width(records):
    return max((len(record['v']) for record in records if 'v' in record), default=0)


def print_census(tables, failures):
    print('ok', len(tables), 'fail', len(failures), failures[:5])
    cells, filled = column_counts(tables)
    for index in sorted(cells):
        print('col', index, 'cells', cells[index], 'filled', filled[index])
    for name, records in sorted(tables, key=lambda table: -len(table[1]))[:8]:
        print((name, len(records), width(records)))
    for name, records in tables:
        if name in SAMPLE_TABLES:
            print(name, records[SAMPLE_ROWS] if len(records) > 104 else records[:3])


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apk', required=True, help='APK holding libgame.so (for the keys)')
    parser.add_argument('--folder', type=Path, required=True, help='folder with Ver*.dat tables')
    return parser.parse_args()


def main():
    args = parse_args()
    by_token = common.table_keys(common.read_native(args.apk))
    print_census(*decode_all(args.folder, by_token))


if __name__ == '__main__':
    main()
