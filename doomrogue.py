#!/usr/bin/env python3
"""
DoomRogue launcher.

Each run: roll a seed -> generate a fresh 12-floor dungeon -> start GZDoom/UZDoom
with the DoomRogue mod. When the run ends (death or victory) you get a fresh
dungeon next time. Python 3 standard library only; also ships as a Windows .exe.

    python3 doomrogue.py                 # play
    python3 doomrogue.py --seed 1234     # replay a specific dungeon
    python3 doomrogue.py --skill 4       # 1..5 (default 3)
    python3 doomrogue.py --self-test     # check everything without playing
"""
import argparse
import glob
import hashlib
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

VERSION = "0.1.0"

# When frozen by PyInstaller, bundled files (mod/, dr_gen) live in sys._MEIPASS,
# while user data (downloads, runs, saves) belongs next to the .exe.
FROZEN = getattr(sys, "frozen", False)
RES_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
DATA = os.path.join(APP_DIR, "data")
MOD_DIR = os.path.join(RES_DIR, "mod")
PK3 = os.path.join(DATA, "doomrogue.pk3")
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Pinned downloads (verified checksums).
FREEDOOM = dict(
    url="https://github.com/freedoom/freedoom/releases/download/v0.13.0/freedoom-0.13.0.zip",
    sha256="3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59",
    size="24 MB")
GZDOOM_WIN = dict(
    url="https://github.com/ZDoom/gzdoom/releases/download/g4.14.2/gzdoom-4-14-2-windows.zip",
    sha256="6d01c5bb48610cebfa9dfd0b7705a1e20bfd56032a74484ac256d8c4e3c51bee",
    size="22 MB")
GZDOOM_MAC = dict(
    url="https://github.com/ZDoom/gzdoom/releases/download/g4.14.2/gzdoom-4-14-2-macos.zip",
    sha256="0f2e638574ce2a2b5adec3613cf3fc1c66f63468019d412bb8dc8787ee78fb05",
    size="36 MB")

sys.path.insert(0, RES_DIR)
import dr_gen  # noqa: E402


# --------------------------------------------------------------------------
# downloads
# --------------------------------------------------------------------------
def download(spec, what, attempts=5):
    """Download with a few retries (flaky networks happen)."""
    for i in range(attempts):
        try:
            return _download_once(spec, what)
        except Exception as e:
            if i == attempts - 1:
                raise
            print("  download failed (%s), retrying..." % e)
            time.sleep(2 + 3 * i)


def _download_once(spec, what):
    """Download spec['url'] to a temp file, verify sha256, return the path."""
    print("Downloading %s (%s, one time only)..." % (what, spec["size"]))
    fd, tmp = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    h = hashlib.sha256()
    req = urllib.request.Request(spec["url"], headers={"User-Agent": "DoomRogue/" + VERSION})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if total and time.time() - last > 0.5:
                last = time.time()
                print("  %3d%%" % (got * 100 // total), end="\r", flush=True)
    print("  100%")
    if h.hexdigest() != spec["sha256"]:
        os.remove(tmp)
        raise RuntimeError("Checksum mismatch for %s - download was corrupted or changed." % what)
    return tmp


# --------------------------------------------------------------------------
# engine / IWAD discovery
# --------------------------------------------------------------------------
def local_engine():
    """Engine that the launcher downloaded itself into data/engine."""
    if IS_WIN:
        p = os.path.join(DATA, "engine", "gzdoom.exe")
    elif IS_MAC:
        p = os.path.join(DATA, "engine", "GZDoom.app", "Contents", "MacOS", "gzdoom")
    else:
        return None
    return p if os.path.exists(p) else None


def installed_engine():
    cands = []
    if IS_MAC:
        for base in ["/Applications", os.path.expanduser("~/Applications")]:
            for app in ("UZDoom", "GZDoom"):
                for exe in glob.glob(os.path.join(base, app + ".app", "Contents", "MacOS", "*")):
                    if os.path.basename(exe).lower() in ("uzdoom", "gzdoom"):
                        cands.append(exe)
    for name in ("uzdoom", "gzdoom"):
        p = shutil.which(name)
        if p:
            cands.append(p)
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")]
    for base in pf:
        if not base:
            continue
        for sub, exe in (("UZDoom", "uzdoom.exe"), ("GZDoom", "gzdoom.exe")):
            cands.append(os.path.join(base, sub, exe))
    cands += ["/opt/uzdoom/uzdoom", "/opt/gzdoom/gzdoom"]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def get_engine(explicit=None, allow_download=True):
    for p in (explicit, os.environ.get("DR_ENGINE"), local_engine(), installed_engine()):
        if p and os.path.exists(p):
            return p
    if not allow_download:
        return None
    if IS_WIN or IS_MAC:
        spec = GZDOOM_WIN if IS_WIN else GZDOOM_MAC
        z = download(spec, "the GZDoom engine")
        dest = os.path.join(DATA, "engine")
        os.makedirs(dest, exist_ok=True)
        if IS_MAC:
            # ditto keeps the app's permissions and code signature intact
            subprocess.run(["ditto", "-x", "-k", z, dest], check=True)
        else:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
        os.remove(z)
        p = local_engine()
        if p:
            print("GZDoom installed into data/engine")
            return p
    print("\nCould not find GZDoom or UZDoom.\n"
          "Install one from https://zdoom.org/downloads (or your package manager),\n"
          "or point to it with:  --engine /path/to/gzdoom")
    return None


def get_iwad(explicit=None):
    if explicit:
        return explicit
    for p in [os.path.join(DATA, "freedoom2.wad"), os.path.join(APP_DIR, "freedoom2.wad")]:
        if os.path.exists(p):
            return p
    os.makedirs(DATA, exist_ok=True)
    z = download(FREEDOOM, "Freedoom (free, BSD-licensed Doom assets)")
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith("freedoom2.wad"):
                with open(os.path.join(DATA, "freedoom2.wad"), "wb") as f:
                    f.write(zf.read(n))
                break
    os.remove(z)
    return os.path.join(DATA, "freedoom2.wad")


# --------------------------------------------------------------------------
# mod packaging
# --------------------------------------------------------------------------
def build_pk3():
    """Zip the mod folder so edits to the ZScript are always picked up."""
    os.makedirs(DATA, exist_ok=True)
    with zipfile.ZipFile(PK3, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(MOD_DIR):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                if fn.startswith("."):          # skip .DS_Store and friends
                    continue
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, MOD_DIR).replace(os.sep, "/"))
        names = set(z.namelist())
    if "ZSCRIPT" not in names:
        raise SystemExit("The mod folder is incomplete (mod/ZSCRIPT is missing). "
                         "Re-download DoomRogue and unzip it again.")


# --------------------------------------------------------------------------
# UI helpers
# --------------------------------------------------------------------------
def ask(prompt, options, default):
    """Small cross-platform chooser: macOS dialog when not in a terminal."""
    if IS_MAC and not sys.stdin.isatty():
        btns = ", ".join('"%s"' % o for o in options)
        script = 'button returned of (display dialog "%s" with title "DoomRogue" buttons {%s} default button "%s")' % (
            prompt.replace('"', "'"), btns, default)
        try:
            out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()
            return out or default
        except Exception:
            return default
    keys = "/".join(o if o != default else o.upper() for o in options)
    try:
        ans = input("%s [%s] " % (prompt, keys)).strip().lower()
    except EOFError:
        return default
    for o in options:
        if ans and o.lower().startswith(ans):
            return o
    return default


def prune_runs(keep=6):
    runs = sorted(glob.glob(os.path.join(DATA, "runs", "run_*.wad")), key=os.path.getmtime)
    for old in runs[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass


# --------------------------------------------------------------------------
# play
# --------------------------------------------------------------------------
def read_log(path):
    try:
        with open(path, errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def play(engine, iwad, seed, floors, skill, resume=False):
    runs = os.path.join(DATA, "runs")
    saves = os.path.join(DATA, "saves", str(seed))
    os.makedirs(runs, exist_ok=True)
    os.makedirs(saves, exist_ok=True)
    wad = os.path.join(runs, "run_%d.wad" % seed)
    if not os.path.exists(wad):
        dr_gen.generate(seed, floors, wad)
    log = os.path.join(DATA, "last_run.log")
    if os.path.exists(log):
        os.remove(log)
    cmd = [engine, "-iwad", iwad, "-file", PK3, wad, "-savedir", saves, "+logfile", log]
    if not resume:
        cmd += ["-skill", str(skill), "+map", "MAP01"]
    print("\n=== DoomRogue %s  seed %d  (%d floors) ===" % (VERSION, seed, floors))
    print("Starting:", engine)
    subprocess.run(cmd)
    text = read_log(log)
    if "DR_RUN_OVER victory" in text:
        return "victory"
    if "DR_RUN_OVER death" in text:
        return "death"
    return "quit"


def self_test(a):
    """Everything short of playing: downloads, mod build, map generation, engine compile check."""
    print("DoomRogue %s self-test (%s, frozen=%s)" % (VERSION, sys.platform, FROZEN))
    build_pk3()
    print("[ok] mod packed:", PK3)
    tmpwad = os.path.join(DATA, "selftest.wad")
    dr_gen.generate(12345, a.floors, tmpwad)
    print("[ok] generated %d floors" % a.floors)
    iwad = get_iwad(a.iwad)
    print("[ok] IWAD:", iwad)
    engine = get_engine(a.engine)
    if not engine:
        return 1
    print("[ok] engine:", engine)
    log = os.path.join(DATA, "selftest.log")
    if os.path.exists(log):
        os.remove(log)
    try:
        subprocess.run([engine, "-iwad", iwad, "-file", PK3, tmpwad, "-norun", "-nosound",
                        "+logfile", log], timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("[!!] engine did not exit (it may be showing an error window)")
    text = read_log(log)
    if "Script error" in text or "Fatal" in text or "unknown event handler" in text:
        print("[FAIL] engine reported errors:\n" + "\n".join(
            l for l in text.splitlines() if "rror" in l or "Fatal" in l or "unknown" in l))
        return 1
    if "script parsing took" not in text:
        print("[FAIL] engine log incomplete:\n" + text[-2000:])
        return 1
    print("[ok] engine loaded the mod without script errors")
    print("SELF-TEST PASSED")
    return 0


def main():
    ap = argparse.ArgumentParser(description="DoomRogue launcher")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--floors", type=int, default=12)
    ap.add_argument("--skill", type=int, default=3, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--engine", help="path to gzdoom/uzdoom executable")
    ap.add_argument("--iwad", help="path to freedoom2.wad or doom2.wad")
    ap.add_argument("--self-test", action="store_true", help="check setup without playing")
    ap.add_argument("--version", action="version", version="DoomRogue " + VERSION)
    a = ap.parse_args()

    if a.self_test:
        return self_test(a)

    print("DoomRogue %s" % VERSION)
    build_pk3()
    iwad = get_iwad(a.iwad)
    engine = get_engine(a.engine)
    if not engine:
        return 1

    seed = a.seed if a.seed is not None else random.randrange(1, 10 ** 9)
    resume = False
    while True:
        prune_runs()
        result = play(engine, iwad, seed, a.floors, a.skill, resume)
        if result in ("victory", "death"):
            shutil.rmtree(os.path.join(DATA, "saves", str(seed)), ignore_errors=True)   # permadeath
        if result == "victory":
            print("You beat the dungeon! (seed %d)" % seed)
            choice = ask("Victory! Start a new dungeon?", ["New run", "Quit"], "New run")
        elif result == "death":
            print("You died. Seed %d is gone." % seed)
            choice = ask("You died. Start a new dungeon?", ["New run", "Quit"], "New run")
        else:
            choice = ask("Run still alive (seed %d). What now?" % seed,
                         ["Resume", "New run", "Quit"], "Quit")
        if choice == "Quit":
            return 0
        resume = (choice == "Resume")
        if not resume:
            seed = random.randrange(1, 10 ** 9)


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code)
        code = 1 if e.code not in (None, 0) else 0
    except Exception as e:   # keep the window open on Windows so people can read the error
        import traceback
        traceback.print_exc()
        print("\nSomething went wrong: %s" % e)
        code = 1
    if FROZEN and code != 0 and "--self-test" not in sys.argv:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    sys.exit(code)
