"""Overlay the official Spanish images onto the author's English image tree.

English file names and versions are kept, so the client finds them where it expects.
 - CPK packs `en/sd/<dir>/Ver<N>_<name>.cpk`: every entry whose file name also exists in the
   Spanish pack with the same base name gets the Spanish bytes.
 - Loose files `en/sd/<path>`: replaced by `es/sd/<path>` when both exist.
Only files that change are written.

An atlas (`name.plist` + `name.png`) is replaced only when the Spanish plist has every frame of the
author's one. The official images come from an older interface: a missing frame makes the client
crash, so such an atlas keeps the author's version (both files, so they stay consistent).

Example (needs `cricodecs`):
    build_es_images.py --author phone_en_img --official es_img --out out/es_img_over_en
"""
import argparse
import json
import plistlib
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from cricodecs import cpk

VERSION_PREFIX = re.compile(r'^Ver\d+_')


def list_files(root):
    """relative posix path -> file, for every file under root."""
    return {file.relative_to(root).as_posix(): file for file in root.rglob('*') if file.is_file()}


def pack_base(relative):
    """The pack path without its version, so English and Spanish versions can be paired."""
    folder, _, name = relative.rpartition('/')
    return f'{folder}/{VERSION_PREFIX.sub("", name)}'


def frame_names(data):
    """The sprite frame names listed in a plist atlas, or None when it cannot be read."""
    try:
        return set(plistlib.loads(data).get('frames', {}))
    except Exception:  # an atlas we cannot read is never replaced
        return None


def stale_atlases(author, official, official_index):
    """Stems of the atlases whose Spanish plist lacks frames the author's plist has."""
    stale = set()
    for index, entry in enumerate(author.files):
        other = official_index.get(entry.filename)
        if other is None or not entry.filename.endswith('.plist'):
            continue
        wanted = frame_names(author.file_bytes(index))
        offered = frame_names(official.file_bytes(other))
        if wanted is None or offered is None or not wanted <= offered:
            stale.add(PurePosixPath(entry.filename).stem)
    return stale


def is_stale(filename, stale):
    path = PurePosixPath(filename)
    return path.suffix in ('.plist', '.png') and path.stem in stale


def merge_pack(author_file, official_file):
    """The author's pack with Spanish bytes where they differ; None if nothing changed."""
    author, official = cpk.load(str(author_file)), cpk.load(str(official_file))
    official_index = {entry.filename: index for index, entry in enumerate(official.files)}
    stale = stale_atlases(author, official, official_index)
    replaced = 0
    for index, entry in enumerate(author.files):
        other = official_index.get(entry.filename)
        if other is None or is_stale(entry.filename, stale):
            continue
        data = official.file_bytes(other)
        if data != author.file_bytes(index):
            author.replace_bytes(index, data, False)
            replaced += 1
    return (author.save_bytes(), replaced) if replaced else None


def write(destination, data):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def overlay_pack(relative, files, destination):
    """Statistics for one pack; writes the merged pack when it differs."""
    merged = merge_pack(files['author'][relative], files['official_packs'][pack_base(relative)])
    if not merged:
        return {}
    data, replaced = merged
    write(destination, data)
    return {'packs': 1, 'entries_replaced': replaced, 'bytes': len(data)}


def overlay_loose(relative, files, destination):
    data = files['official'][relative].read_bytes()
    if data == files['author'][relative].read_bytes():
        return {}
    write(destination, data)
    return {'loose_replaced': 1, 'bytes': len(data)}


def is_replaceable_pack(relative, files):
    return relative.endswith('.cpk') and pack_base(relative) in files['official_packs']


def is_replaceable_loose(relative, files):
    return not relative.endswith('.cpk') and relative in files['official'] and not relative.endswith('.tmp')


def build(author_root, official_root, out):
    files = {'author': list_files(author_root / 'sd'), 'official': list_files(official_root / 'sd')}
    files['official_packs'] = {pack_base(rel): file for rel, file in files['official'].items() if rel.endswith('.cpk')}
    stats = Counter()
    for relative in sorted(files['author']):
        destination = out / 'en' / 'sd' / relative
        if is_replaceable_pack(relative, files):
            stats.update(overlay_pack(relative, files, destination))
        elif is_replaceable_loose(relative, files):
            stats.update(overlay_loose(relative, files, destination))
    return stats


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--author', type=Path, required=True, help="the author's folder that contains sd/")
    parser.add_argument('--official', type=Path, required=True, help='the official Spanish folder that contains sd/')
    parser.add_argument('--out', type=Path, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    print(json.dumps(build(args.author, args.official, args.out)))


if __name__ == '__main__':
    main()
