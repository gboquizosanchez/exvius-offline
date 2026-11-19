"""Build the Spanish data pack zip and the manifest that lists it.

The game app downloads every pack in `data/latest.json`, checks its sha256 and
unzips it under `files/`. `DataPack.destination()` only accepts entry names of
the form `native/<allowed folder>/...`, so every file is stored with that prefix.

Each run builds ONE pack from the folders given with `--root` (each holds `localized_texts/`, `en/`,
`common_lang/`...) and adds it last to the manifest, so run it once per pack, feeding the manifest
of the previous run as `--base-manifest`. A pack must stay under 2 GiB.

Example:
    package_es.py --root out/es_over_en --root out/es_img_over_en \
        --base-manifest upstream/data/latest.json --out-dir out/pack --tag es-r1
    package_es.py --pack-id spanish-es-dialogue --root out/es_dialogue \
        --base-manifest out/pack/latest.json --out-dir out/pack_dialogue --tag es-r1 \
        --zip-name exvius-es-dialogue.zip
"""
import argparse
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

ENTRY_PREFIX = 'native/'
RELEASES_URL = 'https://github.com/gboquizosanchez/exvius-offline/releases/download'
# Tables are base64 text and compress well; images are already compressed CPK packs.
COMPRESSED_SUFFIXES = ('.dat',)


@dataclass(frozen=True)
class Pack:
    id: str
    path: Path
    size: int
    unpacked_size: int
    sha256: str
    file_count: int


def list_files(roots):
    """(root, file) pairs for every file under the given folders, in a stable order."""
    return [(root, file) for root in roots for file in sorted(root.rglob('*')) if file.is_file()]


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_zip(files, destination):
    """Zip the files under `native/` and return the total unpacked size."""
    unpacked = 0
    with zipfile.ZipFile(destination, 'w') as archive:
        for root, file in files:
            entry = ENTRY_PREFIX + file.relative_to(root).as_posix()
            method = zipfile.ZIP_DEFLATED if entry.endswith(COMPRESSED_SUFFIXES) else zipfile.ZIP_STORED
            archive.write(file, entry, compress_type=method)
            unpacked += file.stat().st_size
    return unpacked


def build_pack(pack_id, roots, destination):
    files = list_files(roots)
    unpacked = write_zip(files, destination)
    return Pack(pack_id, destination, destination.stat().st_size, unpacked, sha256_of(destination), len(files))


def pack_entry(pack, tag):
    return {
        'id': pack.id,
        'url': f'{RELEASES_URL}/{tag}/{pack.path.name}',
        'size': pack.size,
        'unpackedSize': pack.unpacked_size,
        'sha256': pack.sha256,
    }


def build_manifest(base, pack, tag):
    """The base manifest plus our pack, last so it overwrites the English files."""
    manifest = dict(base)
    # The original APK is signed with another key, so never offer it as an update.
    manifest.pop('app', None)
    others = [entry for entry in base['packs'] if entry['id'] != pack.id]
    manifest['packs'] = others + [pack_entry(pack, tag)]
    manifest['revision'] = base['revision'] + 1
    manifest['version'] = f"{base['version'].rsplit('.', 1)[0]}.{manifest['revision']}"
    manifest['downloadBytes'] = base['downloadBytes'] + pack.size
    manifest['installedBytes'] = base['installedBytes'] + pack.unpacked_size
    manifest['files'] = base['files'] + pack.file_count
    return manifest


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, action='append', required=True,
                        help='folder whose content goes into the pack (repeatable)')
    parser.add_argument('--pack-id', default='spanish-es')
    parser.add_argument('--base-manifest', type=Path, required=True, help="the author's data/latest.json")
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--tag', required=True, help='GitHub release tag that will hold the zip')
    parser.add_argument('--zip-name', default='exvius-es-r1.zip')
    return parser.parse_args()


def main():
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    pack = build_pack(args.pack_id, args.root, args.out_dir / args.zip_name)
    base = json.loads(args.base_manifest.read_text())
    manifest = build_manifest(base, pack, args.tag)
    (args.out_dir / 'latest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'files={pack.file_count} zip={pack.size} unpacked={pack.unpacked_size} sha256={pack.sha256}')


if __name__ == '__main__':
    main()
