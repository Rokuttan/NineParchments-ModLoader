#!/bin/sh
# NPModLoader launcher for Linux / Steam Deck:  ./modloader.sh <command> [options]
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
        exec "$py" modloader.py "$@"
    fi
done
echo "Python 3.8 or newer was not found. Install it with your package manager (e.g. python3)." >&2
exit 1
