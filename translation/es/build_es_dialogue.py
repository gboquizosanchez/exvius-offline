"""Put the official Spanish dialogue into the author's dialogue packs.

The author's `<id>_event_text_sg.txt`, `<id>_event_teller_sg.txt` and `map_*_sg.txt` entries repeat
the English text in every language column. The official packs hold the real columns. Rows are
`id^EN^ZH^KO^FR^DE^ES^TH^ID`; for every author row the Spanish column is replaced by the official
one when all of this holds, and the row is left as the author wrote it otherwise:
 - the official pack has the same entry and the same id, with a non-empty Spanish column;
 - the English texts match once `<br>`, spacing and the number of `<name=N>` are ignored (the
   author re-wraps lines and renumbers speakers, so a strict comparison drops a third of the rows);
 - both texts have the same number of `<name=N>` tags. The tags of the Spanish text are then
   replaced, in order, by the author's, so the speaker stays the one the author's script expects.

The CPK structure and the line endings (LF) of the author's files are kept; only changed packs are
written, under `<out>/common_lang/<same relative path>`.

Example (needs `cricodecs`):
    build_es_dialogue.py --author samples/dlg_author --official samples/dlg_official \
        --out out/es_dialogue
"""
import argparse
import re
from collections import Counter
from pathlib import Path

from cricodecs import cpk

PACK_NAME = re.compile(r'Ver\d+_(.+)\.cpk')
TABLE_SUFFIX = '_sg.txt'
COLUMNS = 9
ENGLISH, SPANISH = 1, 6
LAYOUT = re.compile(rb'<br>|\s+')
SPEAKER = re.compile(rb'<name=\d+>')
SPEAKER_ANY = b'<name=N>'
# Ordered: the first one that holds names why the row keeps the author's text.
SKIP_REASONS = (
    ('no_official_row', lambda author, official: official is None),
    ('no_spanish', lambda author, official: not official[SPANISH].strip()),
    ('english_differs', lambda author, official: comparable(author[ENGLISH]) != comparable(official[ENGLISH])),
    ('speakers_differ', lambda author, official: speakers(author[ENGLISH]) != speakers(official[SPANISH])),
)


def comparable(english):
    """The English text without what the author's edition changes (line breaks, speaker ids)."""
    return SPEAKER.sub(SPEAKER_ANY, LAYOUT.sub(b' ', english)).strip()


def speakers(text):
    return len(SPEAKER.findall(text))


def skip_reason(author, official):
    """Why this author row keeps its text; None when the official Spanish goes in."""
    return next((reason for reason, holds in SKIP_REASONS if holds(author, official)), None)


def with_speakers(spanish, english):
    """The Spanish text with the speaker tags of the author's English text, in order."""
    tags = iter(SPEAKER.findall(english))
    return SPEAKER.sub(lambda _: next(tags), spanish)


def pack_key(root, file):
    """(tree, token): `sd`/`hd` and the id in the pack name, which does not change between editions."""
    return file.relative_to(root).parts[0], PACK_NAME.match(file.name).group(1)


def index_packs(root):
    packs = {}
    for file in sorted(root.rglob('*.cpk')):
        packs.setdefault(pack_key(root, file), []).append(file)
    return packs


def official_rows(data):
    """id -> columns for the well-formed rows of an official table (CRLF removed)."""
    rows = {}
    for line in data.split(b'\n'):
        columns = line.rstrip(b'\r').split(b'^')
        if len(columns) == COLUMNS:
            rows[columns[0]] = columns
    return rows


def official_tables(files):
    """entry name -> {id: columns} over the official packs that share a token."""
    tables = {}
    for file in files:
        pack = cpk.load(str(file))
        for index, entry in enumerate(pack.files):
            if entry.filename.endswith(TABLE_SUFFIX):
                tables.setdefault(entry.filename, {}).update(official_rows(pack.file_bytes(index)))
    return tables


def merge_row(columns, official, stats):
    reason = skip_reason(columns, official)
    stats[reason or 'replaced'] += 1
    if reason is None:
        columns[SPANISH] = with_speakers(official[SPANISH], columns[ENGLISH])
    return columns


def merge_table(data, official, stats):
    """The author's table with the official Spanish where the rules allow it."""
    lines = []
    for line in data.split(b'\n'):
        columns = line.split(b'^')
        if len(columns) == COLUMNS:
            columns = merge_row(columns, official.get(columns[0]), stats)
        lines.append(b'^'.join(columns))
    return b'\n'.join(lines)


def merge_pack(author_file, official_files, stats):
    """The author's pack with Spanish dialogue; None if no row changed."""
    pack = cpk.load(str(author_file))
    tables = official_tables(official_files)
    changed = 0
    for index, entry in enumerate(pack.files):
        if not entry.filename.endswith(TABLE_SUFFIX):
            continue
        data = pack.file_bytes(index)
        merged = merge_table(data, tables.get(entry.filename, {}), stats)
        if merged != data:
            pack.replace_bytes(index, merged, False)
            changed += 1
    return pack.save_bytes() if changed else None


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--author', type=Path, required=True, help="folder with the author's sd/ and hd/")
    parser.add_argument('--official', type=Path, required=True, help='folder with the official sd/ and hd/')
    parser.add_argument('--out', type=Path, required=True, help='gets common_lang/<sd|hd>/...')
    parser.add_argument('--only', default='*.cpk', help='glob on the author side, to try a few packs')
    return parser.parse_args()


def main():
    args = parse_args()
    official = index_packs(args.official)
    stats = Counter()
    for file in sorted(args.author.rglob(args.only)):
        merged = merge_pack(file, official.get(pack_key(args.author, file), []), stats)
        if merged is None:
            continue
        destination = args.out / 'common_lang' / file.relative_to(args.author)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(merged)
        stats['packs_written'] += 1
        stats['bytes_written'] += len(merged)
    print(dict(sorted(stats.items())))


if __name__ == '__main__':
    main()
