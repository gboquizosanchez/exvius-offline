"""Make the client read the SPANISH text columns while it stays on its stock 'English' language.

`LocalizationManager::getTextCsvIndex(bool)` (v0.1.36 libgame.so, offset 0x1a3e5b0) returned a
per-language column. After the patch it returns 5 when the argument is true (map/event dialogue,
`key^EN^ZH^KO^FR^DE^ES^TH^ID`, so ES) and 1 otherwise (the two-column UI tables `[EN, ES]`).

It starts from the ORIGINAL library extracted from the release APK and refuses to patch anything
that does not match the expected instructions.

Example:
    patch_es_text.py --release-apk rel.apk --out mf/lib/arm64-v8a/libgame.so
"""
import argparse
import struct
import subprocess
from pathlib import Path

NATIVE_LIB = 'lib/arm64-v8a/libgame.so'
FUNCTION = 0x1a3e5b0
# Words the original function must contain (None = any value); little-endian 32-bit instructions.
EXPECTED = {
    FUNCTION: 0x7200003f,
    FUNCTION + 0x04: 0x52802188,
    FUNCTION + 0x08: 0x52802209,
    FUNCTION + 0x0c: None,
    FUNCTION + 0x10: None,
    FUNCTION + 0x14: 0xd65f03c0,
}
PATCH = {
    FUNCTION + 0x04: 0x528000a8,  # mov w8, #5
    FUNCTION + 0x08: 0x52800029,  # mov w9, #1
    FUNCTION + 0x0c: 0x1a891100,  # csel w0, w8, w9, ne
    FUNCTION + 0x10: 0xd503201f,  # nop
}


def extract_library(apk):
    result = subprocess.run(['unzip', '-p', str(apk), NATIVE_LIB], capture_output=True, check=True)
    return bytearray(result.stdout)


def check_original(library):
    """Raise if the instructions at the patch site are not the ones we know."""
    for address, expected in EXPECTED.items():
        current, = struct.unpack_from('<I', library, address)
        if expected is not None and expected != current:
            raise ValueError(f'unexpected instruction {current:08x} at {address:#x}; wrong libgame.so version?')


def apply_patch(library):
    for address, word in PATCH.items():
        struct.pack_into('<I', library, address, word)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--release-apk', type=Path, required=True, help='release APK with the original libgame.so')
    parser.add_argument('--out', type=Path, required=True, help='where to write the patched libgame.so')
    return parser.parse_args()


def main():
    args = parse_args()
    library = extract_library(args.release_apk)
    check_original(library)
    apply_patch(library)
    args.out.write_bytes(library)
    print(f'patched {args.out}')


if __name__ == '__main__':
    main()
