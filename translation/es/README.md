# Spanish translation tooling

Scripts that add Spanish (es-ES) to Exvius Offline. They run from any folder: the author's decoder is
taken from `source/` in this repository, and every input/output is a command-line argument
(`--help` on each script). Python needs `cryptography`; `build_es_images.py` also needs `cricodecs`.

| Script | What it does |
| --- | --- |
| `build_es_over_en.py` | Merges the official Spanish tables over the author's English ones, under the English names. |
| `build_es_images.py` | Overlays Spanish images on the author's `en/sd` CPK packs. |
| `build_es_dialogue.py` | Puts the official Spanish dialogue into the author's `event*`/`map*` CPK packs. |
| `patch_es_text.py` | Patches `libgame.so` so the client reads the Spanish text columns. |
| `package_es.py` | Builds one data pack zip (`--pack-id`, `--root` folders) and adds it to the manifest (`data/latest.json`). |
| `compare_es.py` | Reports how many rows still have no Spanish, per table. |
| `census.py` | Counts filled cells per language column. |
| `reset_lang.sh` | Puts the app's saved language back to English on a device (adb). |
| `fetch_list.sh` | Downloads a `url<TAB>path<TAB>size` list, resuming what is complete. |

`es_common.py` holds what they share: reading the table keys from `libgame.so`, picking the newest
version of each table, and decoding/encoding the AES-ECB table format.

Each Python script was checked to produce byte-for-byte the same output as the version it replaces.
The two shell scripts were only syntax-checked.
