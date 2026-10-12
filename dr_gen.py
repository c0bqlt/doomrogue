#!/usr/bin/env python3
"""
DoomRogue level generator.

Builds a PWAD with N procedurally generated UDMF floors (MAP01..MAPnn) plus a
MAPINFO lump. Pure Python 3 standard library, no dependencies.

    python3 dr_gen.py --seed 1234 --floors 12 --out run.wad
"""
import argparse
import random
import struct
from collections import deque

CELL = 64          # map units per grid cell
GRID_W = 52
GRID_H = 52

SOLID = -1

# --------------------------------------------------------------------------
# Themes (all names verified against freedoom2.wad)
# --------------------------------------------------------------------------
THEMES = {
    "tech": dict(
        walls=["STARTAN3", "STARG3", "COMPSPAN", "METAL2", "TEKGREN2", "PIPEWAL2"],
        corridor_wall="SUPPORT3",
        floors=["FLOOR4_8", "FLAT14", "FLOOR0_1", "FLAT5_4", "FLOOR7_1"],
        ceils=["CEIL5_1", "FLAT20", "CEIL3_5", "CEIL1_1", "TLITE6_4"],
        corridor_floor="FLAT19", corridor_ceil="CEIL5_2",
        light=(160, 224)),
    "base": dict(
        walls=["BROWN1", "BROWNGRN", "GRAY1", "METAL", "BRONZE1", "SILVER1"],
        corridor_wall="GRAY1",
        floors=["FLAT5_3", "FLOOR5_1", "FLAT1", "FLOOR1_6", "MFLR8_1"],
        ceils=["CEIL3_5", "FLAT23", "CEIL5_1"],
        corridor_floor="FLAT1", corridor_ceil="CEIL5_2",
        light=(160, 208)),
    "stone": dict(
        walls=["STONE2", "STONE3", "BIGBRIK1", "CEMENT9", "BRICK7", "BRICK10"],
        corridor_wall="STONE2",
        floors=["FLOOR5_1", "FLAT5_4", "RROCK19", "GRASS1"],
        ceils=["CEIL5_2", "FLAT20", "RROCK09"],
        corridor_floor="FLOOR5_1", corridor_ceil="CEIL5_2",
        light=(144, 200)),
    "hell": dict(
        walls=["SP_HOT1", "MARBLE1", "ROCK2", "ASHWALL2", "MARBGRAY", "TANROCK5", "ZIMMER2"],
        corridor_wall="MARBLE1",
        floors=["FLOOR6_1", "RROCK01", "DEM1_5", "RROCK09"],
        ceils=["RROCK01", "FLOOR6_1", "CEIL5_2"],
        corridor_floor="RROCK09", corridor_ceil="FLOOR6_1",
        light=(128, 192)),
}

MUSIC = ["D_RUNNIN", "D_STALKS", "D_COUNTD", "D_BETWEE", "D_DOOM", "D_THE_DA",
         "D_SHAWN", "D_DDTBLU", "D_IN_CIT", "D_DEAD", "D_STLKS2", "D_THEDA2",
         "D_DOOM2", "D_DDTBL2", "D_RUNNI2", "D_DEAD2", "D_ROMERO", "D_SHAWN2",
         "D_MESSAG", "D_COUNT2", "D_AMPIE", "D_ADRIAN", "D_TENSE", "D_EVIL"]

# --------------------------------------------------------------------------
# Thing tables (DoomEdNums)
# --------------------------------------------------------------------------
# (ednum, cost, min_floor, weight)
MONSTERS = [
    (3004, 1, 1, 10),   # zombieman
    (9,    2, 1, 8),    # shotgun guy
    (3001, 2, 1, 10),   # imp
    (3002, 3, 2, 7),    # demon
    (58,   3, 3, 4),    # spectre
    (65,   4, 3, 5),    # chaingunner
    (3006, 2, 3, 3),    # lost soul
    (3005, 6, 4, 6),    # cacodemon
    (69,   8, 5, 4),    # hell knight
    (66,   9, 6, 4),    # revenant
    (68,   9, 6, 3),    # arachnotron
    (71,  10, 7, 2),    # pain elemental
    (67,  12, 7, 3),    # mancubus
    (3003, 12, 8, 3),   # baron
    (64,  18, 9, 1),    # arch-vile
]
BOSS_FLOOR_GUARDS = [3003, 3003, 69, 69, 66, 67]
CYBERDEMON = 16

WEAPON_BY_FLOOR = {
    1: [2001],                 # shotgun
    2: [2002, 82],             # chaingun, SSG
    3: [82, 2001, 2002],
    4: [2003, 82],             # rocket launcher
    5: [2004, 2002],           # plasma
    6: [2003, 2004, 82],
    7: [2004, 2003, 2005],
    8: [2006, 2004],           # BFG
}
AMMO_SMALL = [2007, 2008, 2010, 2047]           # clip, shells, rocket, cell
AMMO_BIG = [2048, 2049, 2046, 17]               # boxes
HEALTH = [(2011, 6), (2012, 3), (2014, 4)]      # stim, medikit, bonus
ARMOR = [(2015, 5), (2018, 2), (2019, 1)]       # bonus, green, blue
KEYS = {"blue": (5, 130), "yellow": (6, 131), "red": (13, 129)}


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
class Room:
    def __init__(self, idx, x, y, w, h):
        self.idx, self.x, self.y, self.w, self.h = idx, x, y, w, h

    @property
    def cx(self):
        return self.x + self.w // 2

    @property
    def cy(self):
        return self.y + self.h // 2

    def cells(self):
        for yy in range(self.y, self.y + self.h):
            for xx in range(self.x, self.x + self.w):
                yield xx, yy

    def intersects(self, o, pad):
        return not (self.x + self.w + pad <= o.x or o.x + o.w + pad <= self.x or
                    self.y + self.h + pad <= o.y or o.y + o.h + pad <= self.y)


class Region:
    """A future sector."""
    def __init__(self, kind, floor_h, ceil_h, ftex, ctex, wall, light, special=0, tag=0):
        self.kind = kind
        self.floor_h, self.ceil_h = floor_h, ceil_h
        self.ftex, self.ctex = ftex, ctex
        self.wall = wall
        self.light = light
        self.special = special
        self.tag = tag
        self.lock = 0          # for locked doors
        self.door_tex = "BIGDOOR2"


class Floor:
    def __init__(self, rng, depth, total):
        self.rng = rng
        self.depth = depth
        self.total = total
        self.final = depth == total
        if self.final:
            self.theme_name = "hell"
        else:
            order = ["tech", "base", "stone", "hell"]
            band = min(3, (depth - 1) * 4 // max(1, total - 1))
            self.theme_name = rng.choice([order[band], order[band], rng.choice(order)])
        self.theme = THEMES[self.theme_name]
        self.grid = [[SOLID] * GRID_W for _ in range(GRID_H)]
        self.regions = []
        self.rooms = []
        self.room_region = {}
        self.things = []
        self.edges = []

    # ---------------------------------------------------------------- regions
    def new_region(self, *a, **kw):
        self.regions.append(Region(*a, **kw))
        return len(self.regions) - 1

    def at(self, x, y):
        if 0 <= x < GRID_W and 0 <= y < GRID_H:
            return self.grid[y][x]
        return SOLID

    # ---------------------------------------------------------------- layout
    def place_rooms(self):
        rng = self.rng
        target = rng.randint(9, 13)
        if self.final:
            # big arena in the middle first
            w, h = 16, 16
            self.rooms.append(Room(0, (GRID_W - w) // 2, (GRID_H - h) // 2, w, h))
            target = 7
        tries = 0
        while len(self.rooms) < target and tries < 3000:
            tries += 1
            w, h = rng.randint(5, 10), rng.randint(5, 10)
            x, y = rng.randint(2, GRID_W - w - 2), rng.randint(2, GRID_H - h - 2)
            r = Room(len(self.rooms), x, y, w, h)
            if any(r.intersects(o, 3) for o in self.rooms):
                continue
            self.rooms.append(r)
        return len(self.rooms) >= 6

    def connect_rooms(self):
        rooms = self.rooms
        n = len(rooms)
        dist = lambda a, b: abs(a.cx - b.cx) + abs(a.cy - b.cy)
        in_tree = {0}
        edges = []
        while len(in_tree) < n:
            best = None
            for i in in_tree:
                for j in range(n):
                    if j in in_tree:
                        continue
                    d = dist(rooms[i], rooms[j])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            _, i, j = best
            edges.append((i, j))
            in_tree.add(j)
        self.mst = list(edges)
        return edges

    def add_loops(self, edges, forbidden):
        rng = self.rng
        n = len(self.rooms)
        dist = lambda a, b: abs(a.cx - b.cx) + abs(a.cy - b.cy)
        extra = []
        for i in range(n):
            for j in range(i + 1, n):
                if i in forbidden or j in forbidden:
                    continue
                if (i, j) in edges or (j, i) in edges:
                    continue
                if dist(self.rooms[i], self.rooms[j]) < 22:
                    extra.append((i, j))
        rng.shuffle(extra)
        return edges + extra[: max(1, n // 4)]

    def carve_rooms(self):
        th = self.theme
        rng = self.rng
        lo, hi = th["light"]
        for r in self.rooms:
            sky = (not self.final and rng.random() < 0.18) or (self.final and r.idx == 0)
            ceil_h = rng.choice([160, 192, 224, 256])
            if sky:
                ceil_h = 320
            light = rng.randint(lo, hi) // 16 * 16
            special = 0
            if rng.random() < 0.12:
                special = 65 if rng.random() < 0.5 else 72   # light blink / glow
            reg = self.new_region("room", 0, ceil_h, rng.choice(th["floors"]),
                                  "F_SKY1" if sky else rng.choice(th["ceils"]),
                                  rng.choice(th["walls"]), light, special)
            self.room_region[r.idx] = reg
            for x, y in r.cells():
                self.grid[y][x] = reg

    def carve_corridor(self, a, b):
        """2-wide L-shaped corridor between room centers."""
        ra, rb = self.rooms[a], self.rooms[b]
        th = self.theme
        x0, y0, x1, y1 = ra.cx, ra.cy, rb.cx, rb.cy

        def path(horizontal_first):
            pts = []
            if horizontal_first:
                for x in range(min(x0, x1), max(x0, x1) + 2):
                    pts += [(x, y0), (x, y0 + 1)]
                for y in range(min(y0, y1), max(y0, y1) + 2):
                    pts += [(x1, y), (x1 + 1, y)]
            else:
                for y in range(min(y0, y1), max(y0, y1) + 2):
                    pts += [(x0, y), (x0 + 1, y)]
                for x in range(min(x0, x1), max(x0, x1) + 2):
                    pts += [(x, y1), (x, y1 + 1)]
            return pts

        def cost(pts):
            c = 0
            for x, y in pts:
                v = self.at(x, y)
                if v != SOLID and self.regions[v].kind == "room" and v not in (
                        self.room_region[a], self.room_region[b]):
                    c += 10
            return c

        opts = [path(True), path(False)]
        opts.sort(key=cost)
        pts = opts[0]
        reg = self.new_region("corridor", 0, 128, th["corridor_floor"], th["corridor_ceil"],
                              th["corridor_wall"], max(128, th["light"][0] - 16))
        for x, y in pts:
            if 1 <= x < GRID_W - 1 and 1 <= y < GRID_H - 1 and self.grid[y][x] == SOLID:
                self.grid[y][x] = reg

    def room_features(self, protect):
        """Pillars, raised platforms, nukage pools inside rooms."""
        rng = self.rng
        for r in self.rooms:
            if r.idx in protect or r.w < 7 or r.h < 7:
                continue
            roll = rng.random()
            base = self.regions[self.room_region[r.idx]]
            inner = [(x, y) for x in range(r.x + 2, r.x + r.w - 2)
                     for y in range(r.y + 2, r.y + r.h - 2)]
            if roll < 0.30:
                # pillars on a checker pattern
                for x in range(r.x + 2, r.x + r.w - 2, 3):
                    for y in range(r.y + 2, r.y + r.h - 2, 3):
                        self.grid[y][x] = SOLID
            elif roll < 0.55:
                reg = self.new_region("platform", 24, base.ceil_h, rng.choice(self.theme["floors"]),
                                      base.ctex, base.wall, min(255, base.light + 32))
                for x, y in inner:
                    self.grid[y][x] = reg
            elif roll < 0.75:
                liquid = "NUKAGE1" if self.theme_name != "hell" else "LAVA1"
                special = 71 if liquid == "NUKAGE1" else 80   # 5% / 20% damage
                reg = self.new_region("pool", -8, base.ceil_h, liquid, base.ctex, base.wall,
                                      min(255, base.light + 16), special)
                for x, y in inner:
                    self.grid[y][x] = reg

    # ---------------------------------------------------------------- doors
    def make_doors(self, locked_room, lock_num, lock_tex):
        """Turn corridor cells adjacent to rooms into door sectors."""
        rng = self.rng
        cand = {}
        for y in range(GRID_H):
            for x in range(GRID_W):
                v = self.grid[y][x]
                if v == SOLID or self.regions[v].kind != "corridor":
                    continue
                touching = set()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = self.at(x + dx, y + dy)
                    if n != SOLID and self.regions[n].kind == "room":
                        touching.add(n)
                if len(touching) == 1:
                    cand[(x, y)] = touching.pop()
        # group into doorways (connected door cells touching the same room)
        seen = set()
        locked_reg = self.room_region[locked_room] if locked_room is not None else None
        for start, room in cand.items():
            if start in seen:
                continue
            group = []
            q = deque([start])
            seen.add(start)
            while q:
                c = q.popleft()
                group.append(c)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in cand and nb not in seen and cand[nb] == room:
                        seen.add(nb)
                        q.append(nb)
            must_lock = room == locked_reg
            if not must_lock and (len(group) > 3 or rng.random() > 0.45):
                continue
            th = self.theme
            reg = self.new_region("door", 0, 0, th["corridor_floor"], th["corridor_ceil"],
                                  "DOORTRAK", self.regions[room].light)
            if must_lock:
                self.regions[reg].lock = lock_num
                self.regions[reg].door_tex = lock_tex
            else:
                self.regions[reg].door_tex = rng.choice(["BIGDOOR2", "BIGDOOR2", "BIGDOOR4"])
            for x, y in group:
                self.grid[y][x] = reg

    # ---------------------------------------------------------------- graph
    def reachable(self, start, blocked_regions):
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                v = self.at(nx, ny)
                if v == SOLID or v in blocked_regions or (nx, ny) in seen:
                    continue
                seen.add((nx, ny))
                q.append((nx, ny))
        return seen

    def room_graph_dist(self, start):
        adj = {i: set() for i in range(len(self.rooms))}
        for a, b in self.edges:
            adj[a].add(b)
            adj[b].add(a)
        d = {start: 0}
        q = deque([start])
        while q:
            c = q.popleft()
            for n in adj[c]:
                if n not in d:
                    d[n] = d[c] + 1
                    q.append(n)
        return d, adj

    # ---------------------------------------------------------------- things
    def add_thing(self, ednum, x, y, angle=None, ambush=False):
        if angle is None:
            angle = self.rng.choice([0, 90, 180, 270])
        self.things.append((ednum, x * CELL + CELL // 2, y * CELL + CELL // 2, angle, ambush))

    def free_cells(self, room, used, kinds=("room", "platform")):
        out = []
        for x, y in room.cells():
            v = self.grid[y][x]
            if v == SOLID or (x, y) in used:
                continue
            if self.regions[v].kind not in kinds:
                continue
            # keep a margin from walls so big monsters fit
            ok = True
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if self.at(x + dx, y + dy) == SOLID:
                    ok = False
            if ok:
                out.append((x, y))
        return out

    def populate(self, start_room, key_room, exit_room, key_ednum):
        rng = self.rng
        used = set()
        depth = self.depth
        # player start
        sr = self.rooms[start_room]
        self.add_thing(1, sr.cx, sr.cy, angle=90)
        used.add((sr.cx, sr.cy))

        # key
        if key_ednum:
            kr = self.rooms[key_room]
            cells = self.free_cells(kr, used)
            c = rng.choice(cells) if cells else (kr.cx, kr.cy)
            self.add_thing(key_ednum, *c)
            used.add(c)

        # monsters
        pool = [m for m in MONSTERS if m[2] <= depth]
        budget_per_room = 2 + depth * 1.6
        for r in self.rooms:
            if r.idx == start_room:
                continue
            area = r.w * r.h
            budget = budget_per_room * (area / 50.0) * rng.uniform(0.7, 1.3)
            if self.final and r.idx == 0:
                continue
            cells = self.free_cells(r, used)
            rng.shuffle(cells)
            while budget > 0 and cells:
                ed, cost, _, _ = rng.choices(pool, weights=[m[3] for m in pool])[0]
                if cost > budget + 2:
                    budget -= 1
                    continue
                c = cells.pop()
                self.add_thing(ed, *c, ambush=rng.random() < 0.25)
                used.add(c)
                budget -= cost

        if self.final:
            arena = self.rooms[0]
            self.add_thing(CYBERDEMON, arena.cx, arena.cy - 3, angle=270)
            used.add((arena.cx, arena.cy - 3))
            for ed in BOSS_FLOOR_GUARDS:
                cells = self.free_cells(arena, used)
                if cells:
                    c = rng.choice(cells)
                    self.add_thing(ed, *c)
                    used.add(c)

        # weapons
        weps = WEAPON_BY_FLOOR.get(min(depth, 8), [])
        if depth > 8:
            weps = WEAPON_BY_FLOOR[8] + [2003, 82]
        n_weps = 1 + (rng.random() < 0.5)
        non_start = [r for r in self.rooms if r.idx not in (start_room,)]
        for _ in range(n_weps):
            if not weps:
                break
            r = rng.choice(non_start)
            cells = self.free_cells(r, used)
            if cells:
                c = rng.choice(cells)
                self.add_thing(rng.choice(weps), *c)
                used.add(c)
        # starting room always gets a little something
        cells = self.free_cells(sr, used)
        rng.shuffle(cells)
        for ed in [2008, 2007, 2011]:
            if cells:
                self.add_thing(ed, *cells.pop())

        # health / ammo / armor scattered
        for r in self.rooms:
            cells = self.free_cells(r, used)
            rng.shuffle(cells)
            n = max(1, (r.w * r.h) // 25)
            for _ in range(n):
                if not cells:
                    break
                roll = rng.random()
                if roll < 0.40:
                    ed = rng.choice(AMMO_SMALL if rng.random() < 0.7 else AMMO_BIG)
                elif roll < 0.75:
                    ed = rng.choices([h[0] for h in HEALTH], [h[1] for h in HEALTH])[0]
                else:
                    ed = rng.choices([a[0] for a in ARMOR], [a[1] for a in ARMOR])[0]
                c = cells.pop()
                self.add_thing(ed, *c)
                used.add(c)
        # rare powerups
        if rng.random() < 0.35 + depth * 0.03:
            r = rng.choice(non_start)
            cells = self.free_cells(r, used)
            if cells:
                self.add_thing(rng.choice([2013, 2013, 2023, 2022, 2024]), *rng.choice(cells))

    # ---------------------------------------------------------------- build
    def build(self):
        rng = self.rng
        if not self.place_rooms():
            return False
        edges = self.connect_rooms()
        # start = room farthest from map centre-ish random, exit = farthest leaf
        self.edges = edges
        start = 0 if not self.final else rng.randrange(1, len(self.rooms))
        if not self.final:
            start = rng.randrange(len(self.rooms))
        d, adj = self.room_graph_dist(start)
        if self.final:
            exit_room = 0
        else:
            def exit_score(i):
                r = self.rooms[i]
                big = 2 if min(r.w, r.h) >= 7 else (1 if min(r.w, r.h) >= 6 else 0)
                return (big, d.get(i, 0))
            exit_room = max((i for i in d if i != start), key=exit_score)
        self.edges = self.add_loops(edges, set())
        d, adj = self.room_graph_dist(start)
        # key room: far from start, not the exit
        cands = sorted((i for i in d if i not in (start, exit_room)), key=lambda i: -d[i])
        key_room = cands[0] if cands else start
        key_color = rng.choice(list(KEYS)) if not self.final else None

        self.carve_rooms()
        for a, b in self.edges:
            self.carve_corridor(a, b)
        self.room_features({start, exit_room} if not self.final else {start, 0})
        self.make_doors(None, 0, "")

        # exit pad (2x2). Normal floors: inside a locked vault in the exit room.
        er = self.rooms[exit_room]
        base = self.regions[self.room_region[exit_room]]
        pad = self.new_region("exit", 0, base.ceil_h, "GATE3", base.ctex, base.wall, 255,
                              tag=999 if self.final else 0)
        if self.final:
            # victory gate sits at the far edge of the arena, behind the boss
            px, py = er.cx - 1, er.y + er.h - 3
        else:
            px, py = er.cx - 1, er.cy - 1
        if key_color:
            vault_wall = rng.choice(self.theme["walls"])
            for x in range(px - 1, px + 3):
                for y in range(py - 1, py + 3):
                    self.grid[y][x] = SOLID
            side = rng.randrange(4)
            off = rng.randrange(2)
            dx, dy = [(px + off, py - 1), (px + off, py + 2), (px - 1, py + off), (px + 2, py + off)][side]
            lock_tex = {"blue": "DOORBLU2", "yellow": "DOORYEL2", "red": "DOORRED2"}
            th = self.theme
            dreg = self.new_region("door", 0, 0, th["corridor_floor"], base.ctex, "DOORTRAK", base.light)
            self.regions[dreg].lock = KEYS[key_color][1]
            self.regions[dreg].door_tex = lock_tex[key_color]
            self.grid[dy][dx] = dreg
            self.regions[pad].wall = vault_wall
        for x in range(px, px + 2):
            for y in range(py, py + 2):
                self.grid[y][x] = pad

        # validation: start can reach key without locked doors, and exit with them
        sr = self.rooms[start]
        locked = {i for i, r in enumerate(self.regions) if r.kind == "door" and r.lock}
        reach_nokey = self.reachable((sr.cx, sr.cy), locked)
        kr = self.rooms[key_room]
        if key_color and not any((x, y) in reach_nokey for x, y in kr.cells()):
            return False
        if key_color and any(self.grid[y][x] == pad for x, y in reach_nokey):
            return False   # exit reachable without the key
        reach_all = self.reachable((sr.cx, sr.cy), set())
        if not any(self.grid[y][x] == pad for x, y in reach_all):
            return False
        # every room reachable
        for r in self.rooms:
            if not any((x, y) in reach_all for x, y in r.cells()):
                return False

        self.start_room, self.key_room, self.exit_room = start, key_room, exit_room
        self.populate(start, key_room, exit_room, KEYS[key_color][0] if key_color else 0)
        return True

    # ---------------------------------------------------------------- UDMF
    def to_udmf(self):
        verts = {}
        vlist = []

        def vid(x, y):
            k = (x, y)
            if k not in verts:
                verts[k] = len(vlist)
                vlist.append(k)
            return verts[k]

        sectors = self.regions
        lines = []   # (v1, v2, front_region, back_region)

        def orient(a, b, a_is_first):
            """Return (front, back) for a boundary between regions a and b.
            a is the cell on the 'right' side of the canonical direction."""
            if a == SOLID:
                return (b, None, False)
            if b == SOLID:
                return (a, None, True)
            ka, kb = sectors[a].kind, sectors[b].kind
            # exit pad, then doors, go on the back side (specials act on the back)
            rank = {"exit": 2, "door": 1}
            if rank.get(ka, 0) > rank.get(kb, 0):
                return (b, a, False)
            return (a, b, True)

        # horizontal boundaries: between row y-1 (south, smaller y) and row y
        for y in range(GRID_H + 1):
            x = 0
            while x < GRID_W:
                s, n = self.at(x, y - 1), self.at(x, y)
                if s == n:
                    x += 1
                    continue
                x0 = x
                while x < GRID_W and self.at(x, y - 1) == s and self.at(x, y) == n:
                    x += 1
                # canonical direction west->east: right side is south (s)
                front, back, keep = orient(s, n, True)
                p0, p1 = (x0 * CELL, y * CELL), (x * CELL, y * CELL)
                if keep:
                    lines.append((vid(*p0), vid(*p1), front, back))
                else:
                    lines.append((vid(*p1), vid(*p0), front, back))
        # vertical boundaries: between column x-1 (west) and column x (east)
        for x in range(GRID_W + 1):
            y = 0
            while y < GRID_H:
                w, e = self.at(x - 1, y), self.at(x, y)
                if w == e:
                    y += 1
                    continue
                y0 = y
                while y < GRID_H and self.at(x - 1, y) == w and self.at(x, y) == e:
                    y += 1
                # canonical direction south->north: right side is east (e)
                front, back, keep = orient(e, w, True)
                p0, p1 = (x * CELL, y0 * CELL), (x * CELL, y * CELL)
                if keep:
                    lines.append((vid(*p0), vid(*p1), front, back))
                else:
                    lines.append((vid(*p1), vid(*p0), front, back))

        out = ['namespace = "zdoom";']
        for ed, x, y, ang, amb in self.things:
            out.append("thing { x = %d.0; y = %d.0; angle = %d; type = %d; "
                       "skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; "
                       "single = true; coop = true; dm = true;%s }"
                       % (x, y, ang, ed, " ambush = true;" if amb else ""))
        for x, y in vlist:
            out.append("vertex { x = %d.0; y = %d.0; }" % (x, y))
        sides = []
        for v1, v2, f, b in lines:
            fr = sectors[f]
            props = ["v1 = %d;" % v1, "v2 = %d;" % v2]
            fs = len(sides)
            if b is None:
                props.append("blocking = true;")
                tex = fr.wall
                extra = ""
                if fr.kind == "door":
                    extra = " "
                    props.append("dontpegbottom = true;")
                sides.append((f, "-", "-", tex))
                props.append("sidefront = %d;" % fs)
            else:
                bk = sectors[b]
                props.append("twosided = true;")
                # upper/lower textures: use the wall of the sector that is "taller"
                f_up = bk.door_tex if bk.kind == "door" else (bk.wall if bk.kind == "room" else fr.wall)
                f_lo = fr.wall if fr.kind != "pool" else bk.wall
                b_up = fr.wall
                b_lo = bk.wall if bk.kind != "pool" else fr.wall
                if bk.kind in ("platform",):
                    f_lo = "STEP1" if self.theme_name != "hell" else "STEP4"
                if fr.kind in ("platform",):
                    b_lo = "STEP1" if self.theme_name != "hell" else "STEP4"
                sides.append((f, f_up, f_lo, "-"))
                sides.append((b, b_up, b_lo, "-"))
                props.append("sidefront = %d;" % fs)
                props.append("sideback = %d;" % (fs + 1))
                if bk.kind == "door":
                    if bk.lock:
                        props.append("special = 13; arg0 = 0; arg1 = 32; arg2 = 150; arg3 = %d;" % bk.lock)
                    else:
                        props.append("special = 12; arg0 = 0; arg1 = 32; arg2 = 150;")
                        props.append("monsteruse = true;")
                    props.append("playeruse = true; repeatspecial = true;")
                elif bk.kind == "exit" and not self.final:
                    props.append("special = 243; playercross = true;")
            out.append("linedef { %s }" % " ".join(props))
        for sec, up, lo, mid in sides:
            out.append('sidedef { sector = %d; texturetop = "%s"; texturebottom = "%s"; '
                       'texturemiddle = "%s"; }' % (sec, up, lo, mid))
        for s in sectors:
            out.append('sector { heightfloor = %d; heightceiling = %d; texturefloor = "%s"; '
                       'textureceiling = "%s"; lightlevel = %d;%s%s }'
                       % (s.floor_h, s.ceil_h, s.ftex, s.ctex, s.light,
                          " special = %d;" % s.special if s.special else "",
                          " id = %d;" % s.tag if s.tag else ""))
        return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# WAD writing
# --------------------------------------------------------------------------
def write_wad(path, lumps):
    data = b""
    directory = []
    offset = 12
    for name, content in lumps:
        directory.append((offset, len(content), name))
        data += content
        offset += len(content)
    header = struct.pack("<4sii", b"PWAD", len(lumps), offset)
    dirbytes = b"".join(struct.pack("<ii8s", o, s, n.encode("ascii")) for o, s, n in directory)
    with open(path, "wb") as f:
        f.write(header + data + dirbytes)


FLOOR_NAMES = ["Entryway", "Barracks", "Pump Station", "Waste Tunnels", "Cold Storage",
               "Reactor Spine", "The Foundry", "Sunken Vaults", "Bone Quarry", "The Ash Gate",
               "Furnace Choir", "Throne of Teeth", "Gutter Abyss", "The Last Kiln"]


def generate(seed, floors, out):
    master = random.Random(seed)
    lumps = []
    mapinfo = ["clearepisodes",
               'episode MAP01 { name = "Descend (seed %d)" key = "d" }' % seed, ""]
    music = MUSIC[:]
    master.shuffle(music)
    for depth in range(1, floors + 1):
        for attempt in range(200):
            fl = Floor(random.Random(master.getrandbits(64)), depth, floors)
            if fl.build():
                break
        else:
            raise RuntimeError("could not build floor %d" % depth)
        name = "MAP%02d" % depth
        lumps += [(name, b""), ("TEXTMAP", fl.to_udmf().encode("ascii")), ("ENDMAP", b"")]
        title = FLOOR_NAMES[(depth - 1) % len(FLOOR_NAMES)] if depth < floors else "The Last Kiln"
        nxt = "MAP%02d" % (depth + 1) if depth < floors else "EndTitle"
        mapinfo.append('map %s "Floor %d: %s"\n{\n  levelnum = %d\n  next = "%s"\n  sky1 = "%s"\n'
                       '  music = "%s"\n  nointermission\n  par = 0\n}\n'
                       % (name, depth, title, depth, nxt,
                          "SKY3" if fl.theme_name == "hell" else ("SKY2" if depth > floors // 2 else "SKY1"),
                          music[(depth - 1) % len(music)]))
    lumps.insert(0, ("MAPINFO", "\n".join(mapinfo).encode("ascii")))
    lumps.insert(1, ("DRINFO", ("floors=%d\nseed=%d\n" % (floors, seed)).encode("ascii")))
    write_wad(out, lumps)


def main():
    ap = argparse.ArgumentParser(description="DoomRogue level generator")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--floors", type=int, default=12)
    ap.add_argument("--out", default="dr_run.wad")
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else random.randrange(1, 10**9)
    generate(seed, a.floors, a.out)
    print("seed=%d floors=%d -> %s" % (seed, a.floors, a.out))


if __name__ == "__main__":
    main()
