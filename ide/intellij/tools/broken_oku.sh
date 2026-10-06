#!/bin/bash
# An oku that fails the way one without `preview` fails while
# build/oku-broken exists, and is the installed oku once it is gone.
# For tools/retry_ide.py:
#   touch build/oku-broken
#   ./gradlew runIde -PokuExecutable=$PWD/tools/broken_oku.sh -PopenPaths=…
flag="$(dirname "$0")/../build/oku-broken"
if [ -e "$flag" ]; then
  echo "oku: error: argument cmd: invalid choice: 'preview' (choose from build, check, serve)" >&2
  exit 2
fi
exec "$(command -v oku || echo "$HOME/.local/bin/oku")" "$@"
