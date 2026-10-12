#!/bin/bash
# Double-click to play DoomRogue on macOS.
cd "$(dirname "$0")"
python3 doomrogue.py "$@"
