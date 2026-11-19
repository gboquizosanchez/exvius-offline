#!/bin/bash
# Put the app's saved language back to English (use it if the app got stuck in another language).
# Keeps a copy of gamedata.xml first.
# usage: reset_lang.sh <adb-serial> [backup-dir]   (default backup dir: current directory)
set -euo pipefail
DEVICE=${1:?usage: reset_lang.sh <adb-serial> [backup-dir]}
BACKUP_DIR=${2:-.}
PACKAGE=com.exvius.offline.test
PREFS=shared_prefs/gamedata.xml
SETTING='keylocalization_language\">'

adb -s "$DEVICE" shell "am force-stop $PACKAGE"
adb -s "$DEVICE" exec-out "run-as $PACKAGE cat $PREFS" > "$BACKUP_DIR/gamedata.xml.$(date +%H%M%S).bak"
adb -s "$DEVICE" shell "run-as $PACKAGE sed -i 's/${SETTING}LANGUAGE_[A-Z]*</${SETTING}LANGUAGE_ENGLISH</' $PREFS; \
  run-as $PACKAGE grep -o '${SETTING}[^<]*' $PREFS"
