"""Overlay the official Spanish images onto the author's English image tree.

English file names and versions are kept, so the client finds them where it expects.
 - CPK packs `en/sd/<dir>/Ver<N>_<name>.cpk`: every entry whose file name also exists in the
   Spanish pack with the same base name gets the Spanish bytes.
 - Loose files `en/sd/<path>`: replaced by `es/sd/<path>` when both exist.
Only files that change are written.

An atlas (`name.plist` + `name.png`) is replaced as a whole only when the Spanish plist has every
frame of the author's one. The official images come from an older interface: a missing frame makes
the client crash, so otherwise the author's atlas keeps its plist and its layout and receives the
Spanish pixels frame by frame, wherever the same frame has the same size in both atlases.

Example (needs `cricodecs`):
    build_es_images.py --author phone_en_img --official es_img --out out/es_img_over_en
"""
import argparse
import ast
import io
import json
import plistlib
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from cricodecs import cpk
from PIL import Image

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


def frame_box(frame):
    """(box in the sheet, size, rotated) of a plist frame, or None for a format we do not know.

    Formats 2 and 3 name the keys differently; a rotated frame is stored turned 90 degrees.
    """
    rect = frame.get('textureRect') or frame.get('frame')
    if rect is None:
        return None
    (x, y), (width, height) = ast.literal_eval(rect.replace('{', '[').replace('}', ']'))
    rotated = bool(frame.get('textureRotated', frame.get('rotated')))
    stored = (height, width) if rotated else (width, height)
    return (x, y, x + stored[0], y + stored[1]), (width, height), rotated


def paste_spanish_frames(author_sheet, author_frames, official):
    """Copy the official pixels of every frame that has the same size and rotation in both atlases."""
    official_sheet, official_frames = official
    for name, frame in author_frames.items():
        mine = frame_box(frame)
        theirs = frame_box(official_frames[name]) if name in official_frames else None
        if mine and theirs and mine[1:] == theirs[1:]:
            author_sheet.paste(official_sheet.crop(theirs[0]), mine[0][:2])


def merge_atlas(author_entries, official_entries):
    """PNG bytes of the author's sheet with the Spanish frames pasted in; plist untouched."""
    author_sheet = Image.open(io.BytesIO(author_entries['png'])).convert('RGBA')
    official_sheet = Image.open(io.BytesIO(official_entries['png'])).convert('RGBA')
    author_frames = plistlib.loads(author_entries['plist'])['frames']
    official_frames = plistlib.loads(official_entries['plist'])['frames']
    paste_spanish_frames(author_sheet, author_frames, (official_sheet, official_frames))
    output = io.BytesIO()
    author_sheet.save(output, format='PNG')
    return output.getvalue()


def entry_bytes(pack, stem):
    """{'png': bytes, 'plist': bytes} of one atlas in a pack, or None if it is not complete."""
    found = {PurePosixPath(e.filename).suffix[1:]: pack.file_bytes(i) for i, e in enumerate(pack.files)
             if PurePosixPath(e.filename).stem == stem and e.filename.endswith(('.png', '.plist'))}
    return found if {'png', 'plist'} <= set(found) else None


def merged_atlas_pngs(author, official, stale):
    """filename of the sheet -> merged PNG bytes, for every stale atlas both packs hold completely."""
    merged = {}
    for stem in stale:
        mine, theirs = entry_bytes(author, stem), entry_bytes(official, stem)
        if mine and theirs:
            merged[f'{stem}.png'] = merge_atlas(mine, theirs)
    return merged


def is_stale(filename, stale):
    path = PurePosixPath(filename)
    return path.suffix in ('.plist', '.png') and path.stem in stale


def merge_pack(author_file, official_file):
    """The author's pack with Spanish bytes where they differ; None if nothing changed."""
    author, official = cpk.load(str(author_file)), cpk.load(str(official_file))
    official_index = {entry.filename: index for index, entry in enumerate(official.files)}
    stale = stale_atlases(author, official, official_index)
    atlas_pngs = merged_atlas_pngs(author, official, stale)
    replaced = 0
    for index, entry in enumerate(author.files):
        data = atlas_pngs.get(entry.filename)
        other = official_index.get(entry.filename)
        if data is None and other is not None and not is_stale(entry.filename, stale):
            data = official.file_bytes(other)
        if data is not None and data != author.file_bytes(index):
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
