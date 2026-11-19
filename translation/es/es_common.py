"""Helpers shared by the Spanish translation scripts.

Localized text tables are files named `Ver<N>_<token>.dat`: base64 lines of AES-ECB
with a key that `libgame.so` keeps next to the table name. The author's decoder lives
in this repository under `source/`, so no path depends on the machine.
"""
import base64
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'source' / 'exvius'), str(REPO / 'source' / 'server')]

import decode_client_data as decoder  # noqa: E402
import ffbe_crypto  # noqa: E402
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402

NATIVE_LIB = 'lib/arm64-v8a/libgame.so'
TABLE_FILE = re.compile(r'Ver(\d+)_(.+)\.dat')
# Tokens the decoder cannot find in the library; keys found by hand.
EXTRA_KEYS = {'0ThfQQWd': 's9E34w78', '8e6PGb3p': '7nyO4pC9'}


def read_native(apk):
    """libgame.so bytes from an APK (the config split holds the arm64 library)."""
    return zipfile.ZipFile(apk).read(NATIVE_LIB)


def table_keys(native):
    """token -> {'table': name, 'key': AES key} for every localized table."""
    found = {m.group(2).decode(): {'table': m.group(1).decode(), 'key': m.group(3).decode()}
             for m in decoder.TRIPLET.finditer(native)}
    found.update(decoder.getter_manifest(native))
    return found


def latest_files(folder, recursive=False):
    """token -> (version, path) keeping the highest version of each table."""
    best = {}
    finder = Path(folder).rglob if recursive else Path(folder).glob
    for file in finder('Ver*.dat'):
        version, token = TABLE_FILE.match(file.name).groups()
        if token not in best or int(version) > best[token][0]:
            best[token] = (int(version), file)
    return best


def decode_rows(file, key):
    """Rows of one table: [{'key': ..., 'v': [column, ...]}, ...]."""
    return decoder.decode(Path(file).read_bytes(), key, localized=True)[1]


def row_values(file, key):
    """key -> [column, ...] for one table."""
    return {row['key']: row['v'] for row in decode_rows(file, key) if 'v' in row}


def encode_table(key, plain):
    """Inverse of decode: PKCS7 pad, AES-ECB, base64."""
    padding = 16 - len(plain) % 16
    encryptor = Cipher(algorithms.AES(ffbe_crypto.key16(key)), modes.ECB()).encryptor()
    return base64.b64encode(encryptor.update(plain + bytes([padding]) * padding) + encryptor.finalize())


def load_tables(folder, by_token, recursive=False):
    """table name -> {row key: columns} from the newest file of every token we know the key of."""
    tables = {}
    for token, (_, file) in latest_files(folder, recursive).items():
        entry = by_token.get(token)
        if entry:
            tables[entry['table']] = row_values(file, entry['key'])
    return tables
