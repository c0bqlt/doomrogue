#!/usr/bin/env python3
"""Generate many dungeons and check basic invariants. Run: python3 tests/test_generator.py"""
import os
import random
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import dr_gen  # noqa: E402

SEEDS = int(os.environ.get("DR_TEST_SEEDS", "25"))


def lumps(path):
    d = open(path, "rb").read()
    assert d[:4] == b"PWAD"
    n, off = struct.unpack("<ii", d[4:12])
    out = []
    for i in range(n):
        p, s, nm = struct.unpack("<ii8s", d[off + i * 16: off + i * 16 + 16])
        out.append((nm.rstrip(b"\0").decode(), d[p:p + s]))
    return out


def main():
    rng = random.Random(1)
    failures = 0
    with tempfile.TemporaryDirectory() as td:
        for _ in range(SEEDS):
            seed = rng.randrange(1, 10 ** 9)
            path = os.path.join(td, "t.wad")
            try:
                dr_gen.generate(seed, 12, path)
                ls = lumps(path)
                names = [n for n, _ in ls]
                assert names[0] == "MAPINFO" and names[1] == "DRINFO", names[:2]
                maps = [n for n in names if n.startswith("MAP") and n != "MAPINFO"]
                assert maps == ["MAP%02d" % i for i in range(1, 13)], maps
                for i, (n, data) in enumerate(ls):
                    if n != "TEXTMAP":
                        continue
                    t = data.decode()
                    assert t.count("type = 1;") == 1, "exactly one player start"
                    assert "GATE3" in t, "exit pad present"
                    final = ls[i - 1][0] == "MAP12"
                    if final:
                        assert "type = 16;" in t, "cyberdemon on final floor"
                        assert "id = 999;" in t, "victory sector tagged"
                    else:
                        assert "special = 243;" in t, "exit special"
                        assert "special = 13;" in t, "locked vault door"
                        assert any(("type = %d;" % k) in t for k in (5, 6, 13)), "keycard"
            except Exception as e:
                failures += 1
                print("seed %d FAILED: %s" % (seed, e))
    print("%d/%d seeds ok" % (SEEDS - failures, SEEDS))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
