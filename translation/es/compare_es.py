"""Report how much of the author's English text has an official Spanish translation.

For every row of every table: `missing` (no Spanish or blank), `same` (Spanish equals
English, usually proper nouns) or `translated`. Prints totals and the tables with most gaps.

Example:
    compare_es.py --author phone_en/localized_texts/en --official es --apk config.arm64_v8a.apk
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

import es_common as common


@dataclass(frozen=True)
class Coverage:
    table: str
    rows: int
    missing: int
    same: int
    translated: int

    @property
    def gaps(self):
        return self.missing + self.same


def classify(english, spanish_row):
    if spanish_row is None or len(spanish_row) < 2 or not spanish_row[1].strip():
        return 'missing'
    return 'same' if spanish_row[1] == english else 'translated'


def table_coverage(table, author_rows, official_rows):
    counts = {'missing': 0, 'same': 0, 'translated': 0}
    for key, values in author_rows.items():
        counts[classify(values[0], official_rows.get(key))] += 1
    return Coverage(table, len(author_rows), **counts)


def coverage_report(author, official):
    return [table_coverage(table, rows, official.get(table, {})) for table, rows in author.items()]


def print_report(report, top):
    total = sum(item.rows for item in report)
    print(f'rows {total} | missing {sum(i.missing for i in report)}'
          f' | same as English {sum(i.same for i in report)} | translated {sum(i.translated for i in report)}')
    print(f"{'table':40} {'rows':>7} {'missing':>8} {'same':>7} {'translated':>10}")
    for item in sorted(report, key=lambda i: -i.gaps)[:top]:
        print(f'{item.table:40} {item.rows:7} {item.missing:8} {item.same:7} {item.translated:10}')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--author', type=Path, required=True, help="the author's English tables")
    parser.add_argument('--official', type=Path, required=True, help='the official Spanish tables')
    parser.add_argument('--apk', required=True, help='APK holding libgame.so (for the keys)')
    parser.add_argument('--top', type=int, default=25, help='how many tables to list')
    return parser.parse_args()


def main():
    args = parse_args()
    by_token = common.table_keys(common.read_native(args.apk))
    author = common.load_tables(args.author, by_token)
    official = common.load_tables(args.official, by_token)
    print_report(coverage_report(author, official), args.top)


if __name__ == '__main__':
    main()
