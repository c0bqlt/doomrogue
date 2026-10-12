DoomRogue for macOS / Linux
===========================

macOS
  1. Double-click DoomRogue.command.
     If macOS says it "cannot be opened because it is from an unidentified
     developer": right-click DoomRogue.command > Open > Open (only needed once).
  2. If asked to install "command line developer tools", accept - that gives
     you python3. Then double-click DoomRogue.command again.
  3. The first launch downloads the GZDoom engine (~36 MB) and Freedoom
     (~24 MB) into the "data" folder. An existing GZDoom/UZDoom in
     /Applications is used if present.

Linux
  1. Install GZDoom or UZDoom (distro package, or the official .deb from
     https://zdoom.org/downloads).
  2. Run:  python3 doomrogue.py
     If the engine isn't on your PATH:  python3 doomrogue.py --engine /path/to/gzdoom

Options: --seed N, --skill 1-5, --floors N, --self-test
Found a bug? Open an issue on GitHub and attach data/last_run.log.
