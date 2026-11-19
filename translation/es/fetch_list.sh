#!/bin/bash
# Download a list of files, skipping those already complete.
# usage: fetch_list.sh <list.tsv> <dest-dir>      (list lines: url<TAB>relative path<TAB>size in bytes)
set -uo pipefail
LIST=${1:?usage: fetch_list.sh <list.tsv> <dest-dir>}
DEST=${2:?usage: fetch_list.sh <list.tsv> <dest-dir>}

while IFS=$'\t' read -r url relative size; do
  file="$DEST/$relative"
  mkdir -p "$(dirname "$file")"
  if [ -f "$file" ] && [ "$(stat -c %s "$file")" = "$size" ]; then continue; fi
  curl -sL --fail --retry 3 -o "$file" "$url" || echo "FAIL $relative"
done < "$LIST"
