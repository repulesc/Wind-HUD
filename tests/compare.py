#!/usr/bin/env python3
"""Flies the Gemini prototype (v1.4) and Wind through the same five short
experiments and prints a table. Both hover about 12 m up (the prototype's Low).

  1. lift-off      tap, then hover: overshoot and settling time
  2. cruise        W held over gentle land: speed and how steady the height is
  3. let go        release W at cruise: stopping time and distance
  4. tower         W held towards a 23 m tower: contact, closest pass, did it get over
  5. border        W held across a region border: still carried afterwards?

    python3 tests/compare.py

Same caveat as the tests: the physics is a model, so read the numbers as "how
the two designs behave", not as exact Second Life values.
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_tests as T  # noqa: E402
from lslsim.world import World  # noqa: E402

PROTO = open(os.path.join(T.ROOT, "prototype", "Glide_Suite_v1.4_gemini.lsl"), encoding="utf-8").read()


def prototype(start, yaw):
    w = World(T.REGIONS, start, boxes=T.BOXES, prims=["Glide HUD"])
    w.yaw = yaw
    w.add_script("Glide Suite 1.4", PROTO)
    w.start_all()
    w.wear()
    w.run(1.0)
    w.touch(1)                   # one click: on, at 12 m
    return w


def wind(start, yaw):
    w = T.make(start=start, yaw=yaw, notecard=T.SETTINGS_TEXT + "\nheight_low = 12\n")
    w.touch(w.link_named("power"))
    return w


def experiments(make):
    out = {}
    # 1. lift-off
    w = make((20.0, 10.0), T.NORTH)
    clear = []
    w.run(12.0, every=lambda w: clear.append(w.clearance()))
    rest = statistics.median(clear[-90:])
    out["hover height (feet above ground, m)"] = rest
    out["lift-off overshoot (m)"] = max(clear) - rest
    off = [abs(c - rest) for c in clear]
    settle = next(i for i in range(len(off)) if max(off[i:]) < 0.3)
    out["settles within 0.3 m after (s)"] = settle * w.STEP
    # 2. cruise (short enough to stay in the region even at the prototype's speed)
    w.press(T.FWD)
    w.run(2.0)
    heights, speeds = [], []
    w.run(2.5, every=lambda w: (heights.append(w.clearance()), speeds.append(w.speed())))
    out["cruise speed (m/s)"] = statistics.mean(speeds)
    out["height wobble while cruising (m)"] = statistics.pstdev(heights)
    # 3. let go
    x0, y0, t0 = w.gpos[0], w.gpos[1], w.t
    w.release(T.FWD)
    while w.speed() > 0.3 and w.t - t0 < 20:
        w.run(0.05)
    out["stopping time (s)"] = w.t - t0
    out["stopping distance (m)"] = ((w.gpos[0] - x0) ** 2 + (w.gpos[1] - y0) ** 2) ** 0.5
    # 4. tower
    w = make((40.0, 160.0), T.EAST)
    w.run(6.0)
    watch = T.Watch(w)
    w.press(T.FWD)
    w.run(20.0, every=watch)
    out["closest to a roof or the land (m)"] = watch.min_solid
    out["time touching the tower (s)"] = len(w.bumps) * w.STEP
    out["got over the tower"] = w.gpos[0] > 125
    # 5. border
    w = make((180.0, 128.0), T.EAST)
    w.run(6.0)
    w.press(T.FWD)
    while w.region().name == "Meadow" and w.t < 60:
        w.run(0.1)
    lowest = []
    w.run(4.0, every=lambda w: lowest.append(w.solid_clearance()))
    out["lowest in the 4 s after crossing a border (m)"] = min(lowest)
    out["still on after the border"] = abs(w.buoy - 1.0) < 1e-6
    return out


def main():
    a = experiments(prototype)
    b = experiments(wind)
    print("| | Gemini v1.4 | Wind 0.1 |")
    print("|---|---|---|")
    for k in a:
        cell = (lambda v: "yes" if v is True else "no" if v is False else "%.2f" % v)
        print("| %s | %s | %s |" % (k, cell(a[k]), cell(b[k])))


if __name__ == "__main__":
    main()
