#!/usr/bin/env python3
"""Runs Wind's real scripts in a pretend Second Life and checks they behave.

    python3 tests/run_tests.py            all scenarios
    python3 tests/run_tests.py dive land  only scenarios whose name contains a word
    python3 tests/run_tests.py -v ...     also print what the scripts say

Build first (python3 tools/build.py): the tests run the generated "Wind *.lsl"
files, exactly what gets pasted into Second Life. They need LSL-PyOptimizer
(see tests/lslsim/lsl.py).

The world: four regions in a row and a column. Meadow (rolling land, a hill, a
tower, two trees), Bay to its east (land, a beach, then sea with a pier and an
underwater rock), Deep further east (open deep sea), Hills to the north of
Meadow. West of Meadow and north of Bay there is no region: the edge of the
world.

What these tests cannot tell: how Second Life's own physics feels. The pull of
llMoveToTarget is a guess here (tested at several strengths), and lag is
random late timers. They check Wind's logic, its safety margins and that the
scripts work together; the in-world checklist in the README checks the feel.
"""
import math
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from lslsim.world import World, Region, Box, C, AVATAR  # noqa: E402

FWD, BACK, LEFT, RIGHT = C["CONTROL_FWD"], C["CONTROL_BACK"], C["CONTROL_LEFT"], C["CONTROL_RIGHT"]
UP, DOWN = C["CONTROL_UP"], C["CONTROL_DOWN"]
VERBOSE = False


# ---- the world ----------------------------------------------------------------
def meadow(x, y):
    h = 24.0 + 3.0 * math.sin(x / 25.0) * math.cos(y / 31.0)
    return h + 30.0 * math.exp(-((x - 190.0) ** 2 + (y - 60.0) ** 2) / (2 * 18.0 ** 2))   # a steep hill


def bay(x, y):
    return max(2.0, 24.0 - max(0.0, x - 64.0) * 0.2)     # land, a beach at x = 84, then sea


def deep(x, y):
    return 2.0


def hills(x, y):
    return 40.0 + 15.0 * math.sin(x / 20.0) * math.sin(y / 23.0)


REGIONS = {
    (0, 0): Region(20.0, meadow, "Meadow"),
    (1, 0): Region(20.0, bay, "Bay"),
    (2, 0): Region(20.0, deep, "Deep"),
    (0, 1): Region(20.0, hills, "Hills"),
}
BOXES = [
    Box((100, 150, 20), (120, 170, 48), "tower"),
    Box((150, 100, 20), (153, 103, 34), "tree 1"),
    Box((156, 110, 20), (159, 113, 33), "tree 2"),
    Box((356, 120, 20.6), (360, 136, 21.6), "pier"),
    Box((456, 60, 1.0), (462, 66, 15.0), "rock"),
]
PRIMS = ["Wind HUD", "power", "glide", "surface", "dive", "menu", "speed", "up", "down", "help"]
SCRIPTS = ["Wind Engine", "Wind Levels", "Wind Camera", "Wind Animator", "Wind HUD", "Wind Config"]
SETTINGS_TEXT = open(os.path.join(ROOT, "docs", "Wind_Settings.txt"), encoding="utf-8").read()
EAST, NORTH, WEST, SOUTH = 0.0, math.pi / 2, math.pi, -math.pi / 2


def src(name):
    return open(os.path.join(ROOT, name + ".lsl"), encoding="utf-8").read()


def make(start=(128.0, 128.0), yaw=EAST, mtt_k=1.0, lag=0.0, anims=("Wind Glide",), sounds=(),
         prims=PRIMS, scripts=SCRIPTS, notecard=SETTINGS_TEXT, seed=1):
    w = World(REGIONS, start, seed=seed, mtt_k=mtt_k, lag=lag, boxes=BOXES, prims=prims, verbose=VERBOSE)
    w.yaw = yaw
    for n in scripts:
        w.add_script(n, src(n))
    if notecard is not None:
        w.add_item("Wind Settings", "notecard", notecard)
    w.add_item("Wind - User Manual", "notecard", "the manual")
    for a in anims:
        w.add_item(a, "animation")
    for s in sounds:
        w.add_item(s, "sound")
    w.start_all()
    w.wear()
    for _ in range(100):                       # until the settings notecard has been read
        if "st:card" in w.lsd:
            break
        w.run(0.1)
    w.run(0.5)
    return w


def said(w, text):
    return [m for (_, _, m) in w.said if text in m]


def level(w):
    return w.status()[1]


def active(w):
    return w.status() and w.status()[0] == 1


def lift(w, seconds=4.0):
    w.touch(w.link_named("power"))
    w.run(seconds)


class Watch:
    """Keeps the lowest clearances, the highest speed and so on while the world runs."""

    def __init__(self, w):
        self.w = w
        self.min_solid = 1e9      # feet above land / box tops (not water)
        self.min_clear = 1e9      # feet above whatever is below, water included
        self.max_clear = -1e9
        self.max_speed = 0.0
        self.min_x = 1e9

    def __call__(self, w):
        self.min_solid = min(self.min_solid, w.solid_clearance())
        self.min_clear = min(self.min_clear, w.clearance())
        self.max_clear = max(self.max_clear, w.clearance())
        self.max_speed = max(self.max_speed, w.speed())
        self.min_x = min(self.min_x, w.gpos[0] - w.corner[0])


def mean_speed(w, seconds):
    x0, y0 = w.gpos[0], w.gpos[1]
    w.run(seconds)
    return math.hypot(w.gpos[0] - x0, w.gpos[1] - y0) / seconds


def clean(w):
    """Nothing went wrong behind the scenes (and when Wind is off, it holds no keys)."""
    assert not w.errors, "script errors: %s" % w.errors[:5]
    crashed = [s.name + ": " + s.crashed for s in w.scripts if s.crashed]
    assert not crashed, crashed
    full = [n for n in w.notes if "queue full" in n[1]]
    assert not full, full[:3]
    assert w.far_targets == 0, "%d targets beyond 65 m" % w.far_targets
    if not active(w):
        w.run(0.5)
        assert not w.controls, "Wind is off but %s still holds keys" % [s.name for s in w.controls]
        assert w.mtt is None and w.buoy == 0.0, "Wind is off but still pulls the avatar"


# ---- scenarios ------------------------------------------------------------------
SCENARIOS = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


@scenario
def welcome_once():
    w = make()
    assert len(said(w, "Welcome to Wind")) == 1, w.said
    w.wear()                     # logging in again
    w.run(1.0)
    assert len(said(w, "Welcome to Wind")) == 1, "welcomed twice"
    assert w.text == "", "status text while off: %r" % w.text
    clean(w)


@scenario
def liftoff_is_smooth():
    for k in (0.5, 1.0, 3.0):
        w = make(mtt_k=k)
        watch = Watch(w)
        w.touch(w.link_named("power"))
        w.run(6.0, every=watch)
        assert active(w) and level(w) == 0, w.status()
        assert 3.5 < w.clearance() < 4.5, "k=%s: clearance %.2f, want about 4 (Low)" % (k, w.clearance())
        assert watch.max_clear < 4.7, "k=%s: overshot to %.2f" % (k, watch.max_clear)
        assert w.camera is not None and w.anims == {"Wind Glide"}, (w.camera, w.anims)
        assert w.text.startswith("GLIDE  4 m"), w.text
        assert w.glow.get(w.link_named("power")) and w.glow.get(w.link_named("glide")), w.glow
        clean(w)


@scenario
def cruise_speed_and_height():
    for k in (0.5, 1.0, 3.0):
        w = make(start=(20.0, 40.0), yaw=NORTH, mtt_k=k)
        lift(w)
        w.press(FWD)
        w.run(4.0)
        watch = Watch(w)
        sp = mean_speed(w, 3.0)
        w.run(0.0)
        assert 7.2 < sp < 8.8, "k=%s: cruise speed %.2f, want 8" % (k, sp)
        for _ in range(30):
            w.run(0.1, every=watch)
        assert watch.min_solid > 2.8, "k=%s: dipped to %.2f m" % (k, watch.min_solid)
        clean(w)


@scenario
def boost_and_gentle_stop():
    w = make(start=(20.0, 40.0), yaw=NORTH)
    lift(w)
    w.press(FWD)
    w.run(0.1)
    w.release(FWD)
    w.run(0.1)
    w.press(FWD)                 # double tap and hold: boost
    w.run(5.0)
    assert w.status()[6] == 1, "boost flag not shown"
    sp = mean_speed(w, 2.0)
    assert 13.0 < sp < 15.8, "boosted cruise %.2f, want 14.4" % sp
    w.release(FWD)
    vx, vy = w.vel[0], w.vel[1]
    backwards = []
    w.run(5.0, every=lambda w: backwards.append(w.vel[0] * vx + w.vel[1] * vy < -0.5))
    assert w.speed() < 0.5, "still drifting at %.2f after 5 s" % w.speed()
    assert not any(backwards), "bounced back while stopping"
    clean(w)


@scenario
def turning_follows():
    w = make(start=(30.0, 40.0), yaw=NORTH)
    lift(w)
    w.press(FWD)
    w.run(4.0)
    for _ in range(45):          # turn right by 90 degrees in one second, like holding D
        w.yaw -= (math.pi / 2) / 45
        w.run(1.0 / 45)
    w.run(1.0)
    heading = math.degrees(math.atan2(w.vel[1], w.vel[0]))
    assert abs(heading) < 15, "after turning east the path heads %.0f degrees" % heading
    clean(w)


@scenario
def climbs_over_a_tower():
    for k in (0.5, 1.0, 3.0):
        w = make(start=(60.0, 160.0), yaw=EAST, mtt_k=k, notecard=SETTINGS_TEXT + "\nobjects = on\n")
        lift(w)
        watch = Watch(w)
        w.press(FWD)
        w.run(16.0, every=watch)
        assert w.gpos[0] > 125, "k=%s: did not get past the tower (x %.1f)" % (k, w.gpos[0])
        assert not w.bumps, "k=%s: bumped %s" % (k, w.bumps[:3])
        assert watch.min_solid > 1.0, "k=%s: only %.2f m above the roof/land" % (k, watch.min_solid)
        assert not said(w, "in the way"), w.said
        clean(w)


@scenario
def follows_a_steep_hill():
    w = make(start=(190.0, 10.0), yaw=NORTH)
    lift(w)
    w.touch(w.link_named("speed"))   # Fast
    w.run(0.5)
    watch = Watch(w)
    w.press(FWD)
    w.run(10.0, every=watch)
    assert w.gpos[1] > 100, "did not cross the hill (y %.1f)" % w.gpos[1]
    assert watch.min_solid > 1.0, "came within %.2f m of the hillside" % watch.min_solid
    clean(w)


@scenario
def crosses_regions_smoothly():
    w = make(start=(200.0, 128.0), yaw=EAST)
    lift(w)
    w.chat(8, "fast")
    w.press(FWD)
    w.run(5.0)
    speeds = []
    w.run(8.0, every=lambda w: speeds.append(w.speed()))
    assert w.region().name == "Bay", w.region().name
    assert min(speeds) > 0.7 * 16.0 * 0.8, "slowed to %.1f at the crossing" % min(speeds)
    assert not said(w, "in the way"), w.said
    clean(w)


@scenario
def stops_at_the_edge_of_the_world():
    w = make(start=(40.0, 128.0), yaw=WEST)
    lift(w)
    watch = Watch(w)
    w.press(FWD)
    w.run(12.0, every=watch)
    assert w.region().name == "Meadow"
    assert watch.min_x > 0.5, "pushed into the edge (x %.2f)" % watch.min_x
    assert w.speed() < 0.5
    w.release(FWD)
    w.yaw = EAST                 # and can leave again
    w.press(FWD)
    w.run(3.0)
    assert w.gpos[0] > 10, "stuck at the edge"
    clean(w)


@scenario
def hold_c_settles_on_the_water():
    w = make(start=(400.0, 128.0), anims=("Wind Glide", "Wind Surface"))   # standing on the sea bed
    lift(w)
    assert level(w) == 2, "standing in deep water should start in Dive, got %s" % w.status()
    w.press(UP)
    w.run(5.0)
    w.release(UP)
    w.run(1.0)
    assert level(w) == 1, "E at the top should surface: %s" % w.status()
    w.tap(UP)                    # lift off into Glide
    w.run(4.0)
    assert level(w) == 0
    assert 3.5 < w.clearance() < 4.6, "Low over water: %.2f" % w.clearance()
    w.press(DOWN)                # hold C: down to the lowest glide, then onto the water
    w.run(4.0)
    w.release(DOWN)
    w.run(2.0)
    assert level(w) == 1 and w.status()[3] == 1, "not on the water: %s" % w.status()
    feet_over_water = w.feet() - 20.0
    assert -0.1 < feet_over_water < 0.45, "feet %.2f over the water, want about 0.15" % feet_over_water
    assert w.anims == {"Wind Surface"}, w.anims
    assert abs(w.camera[C["CAMERA_DISTANCE"]] - 4.5) < 0.01, w.camera
    clean(w)


@scenario
def dives_and_comes_back_up():
    w = make(start=(400.0, 128.0), anims=("Wind Glide", "Wind Dive"), sounds=("Wind Splash", "Wind Dive Loop"))
    lift(w)
    w.press(UP)
    w.run(5.0)
    w.release(UP)
    w.run(1.0)
    assert level(w) == 1
    w.tap(DOWN)                  # dive
    w.run(4.0)
    assert level(w) == 2, w.status()
    assert w.gpos[2] < 20.0 - 2.0, "not under the water: centre %.2f" % w.gpos[2]
    assert "Wind Splash" in w.sounds_played
    assert w.sound and w.sound[0] == "Wind Dive Loop", w.sound
    assert w.anims == {"Wind Dive Idle"} or w.anims == {"Wind Dive"}, w.anims
    # the camera stays under water
    cam = w.camera
    pitch = math.radians(cam[C["CAMERA_PITCH"]])
    cam_z = w.gpos[2] + cam[C["CAMERA_FOCUS_OFFSET"]][2] + cam[C["CAMERA_DISTANCE"]] * math.sin(pitch)
    assert cam_z < 20.0, "camera above the water (%.2f)" % cam_z
    # swim forward and down
    w.press(FWD | DOWN)
    w.run(3.0)
    w.release(FWD | DOWN)
    assert w.gpos[2] < 20.0 - 4.0, "did not go deeper"
    assert w.solid_clearance() > 0.3, "touched the bottom"
    w.press(UP)
    w.run(8.0)
    w.release(UP)
    w.run(1.0)
    assert level(w) == 1, "did not surface: %s" % w.status()
    assert w.sounds_played.count("Wind Splash") >= 2
    clean(w)


@scenario
def too_shallow_to_dive():
    w = make(start=(256 + 75.0, 100.0))          # on the beach of Bay, away from the pier
    lift(w)
    w.chat(8, "surface")
    w.run(3.0)
    w.yaw = EAST
    w.press(FWD)
    while w.gpos[0] - 256.0 < 89.0:             # out over the shallows (1 to 2.5 m deep)
        w.run(0.1)
    w.release(FWD)
    w.run(4.0)
    assert 17.15 < w.land(w.gpos[0], w.gpos[1]) < 19.5, "not over shallow water (less than 2.9 m deep)"
    assert level(w) == 1 and w.status()[3] == 1, w.status()
    w.tap(DOWN)
    w.run(1.0)
    assert said(w, "Too shallow"), w.said
    assert level(w) == 1
    clean(w)


@scenario
def lands_gently_on_tap():
    w = make()
    lift(w)
    w.chat(8, "mid")
    w.run(6.0)
    assert 14.0 < w.clearance() < 16.0, "Mid: %.2f" % w.clearance()
    w.touch(w.link_named("power"))
    w.run(1.0)
    assert w.text == "landing...", w.text
    w.run(8.0)
    assert not active(w), "still on after landing: %s" % w.status()
    assert w.on_ground and w.mtt is None and w.buoy == 0.0, (w.on_ground, w.mtt, w.buoy)
    assert not w.controls and w.camera is None and not w.anims, (w.controls, w.camera, w.anims)
    assert w.text == "", w.text
    clean(w)


@scenario
def second_tap_stops_at_once():
    w = make()
    lift(w)
    w.chat(8, "high")
    w.run(10.0)
    w.touch(w.link_named("power"))
    w.run(0.3)
    w.touch(w.link_named("power"))
    w.run(0.5)
    assert not active(w) and w.mtt is None, w.status()
    clean(w)


@scenario
def hold_c_over_land_lands():
    w = make()
    lift(w)
    w.press(DOWN)
    w.run(8.0)
    w.release(DOWN)
    w.run(2.0)
    assert not active(w), "holding C over land should land: %s" % w.status()
    assert w.on_ground
    clean(w)


@scenario
def menu_heights_speeds_camera():
    w = make()
    w.touch(w.link_named("power"), hold=1.2)     # hold: the menu
    assert w.dialogs and "Start" in w.dialogs[-1][2], w.dialogs
    w.answer_dialog("High")
    w.run(10.0)
    assert active(w) and w.status()[4] == 40, w.status()
    assert 38.5 < w.clearance() < 41.5, "High: %.2f" % w.clearance()
    assert w.dialogs[-1][2][0] == "Land", "menu not shown again with Land"
    w.answer_dialog("Fast")
    w.run(0.5)
    assert w.status()[5] == 2
    w.answer_dialog("Options")
    w.answer_dialog("Camera: on")
    w.run(0.5)
    assert w.camera is None, "camera not given back"
    assert w.dialogs[-1][2][3] == "Camera: off", w.dialogs[-1][2]
    w.answer_dialog("Camera: off")
    w.run(0.5)
    assert w.camera is not None
    clean(w)


@scenario
def chat_settings():
    w = make(start=(20.0, 40.0), yaw=NORTH)
    w.chat(8, "set speed_cruise 6")
    assert said(w, "speed_cruise = 6"), w.said[-1:]
    w.chat(8, "set nonsense 3")
    assert said(w, 'no setting called "nonsense"')
    w.chat(8, "set speed_cruise banana")
    assert said(w, "is not a number")
    w.chat(8, "set speed_cruise 99")
    assert said(w, "must be from 0.5 to 40")
    w.chat(8, "set camera off")
    assert said(w, "camera = 0")
    w.chat(8, "settings")
    assert said(w, "speed_cruise 6") and said(w, "(* = default)")
    lift(w)
    w.press(FWD)
    w.run(5.0)
    sp = mean_speed(w, 2.0)
    assert 5.4 < sp < 6.6, "set speed not used: %.2f" % sp
    assert w.camera is None, "camera = off not used"
    w.chat(8, "defaults")
    w.run(4.0)
    assert 7.2 < mean_speed(w, 2.0) < 8.8
    clean(w)


@scenario
def settings_notecard_lines():
    card = "\n".join([
        "# a comment",
        "",
        "speed_cruise = 7   # with a note",
        "BOB=off",
        "  height_low = 6",
        "just words",
        "nonsense = 3",
        "height_mid =",
        "volume = 2",
        "=5",
    ])
    w = make(notecard=card)
    w.run(2.0)
    lsd = w.lsd
    assert float(lsd["cfg:speed_cruise"]) == 7.0 and float(lsd["cfg:bob"]) == 0.0, lsd
    assert float(lsd["cfg:height_low"]) == 6.0
    assert "cfg:height_mid" not in lsd and "cfg:volume" not in lsd
    skipped = said(w, "(skipped)")
    assert len(skipped) == 5, skipped
    lift(w)
    assert 5.5 < w.clearance() < 6.5, "height_low = 6 not used: %.2f" % w.clearance()
    clean(w)


@scenario
def notecard_edit_reloads_but_animations_do_not():
    w = make()
    w.chat(8, "set speed_fast 20")
    w.add_item("Wind Dive", "animation")          # dropping in an animation
    w.changed_inventory()
    w.run(1.0)
    assert float(w.lsd["cfg:speed_fast"]) == 20.0, "an animation drop wiped the /8 set value"
    w.add_item("Wind Settings", "notecard", "speed_fast = 12\n")   # editing the notecard
    w.changed_inventory()
    w.run(1.0)
    assert float(w.lsd["cfg:speed_fast"]) == 12.0 and "cfg:speed_cruise" not in w.lsd, w.lsd
    clean(w)


@scenario
def slow_notecard_still_reads():
    card = "\n".join("# note %d" % i for i in range(20)) + "\nspeed_cruise = 7\nheight_low = 5\n"
    w = World(REGIONS, (128.0, 128.0), boxes=BOXES, prims=PRIMS)
    w.cache_lines = 3                            # the region forgets the notecard quickly
    for n in SCRIPTS:
        w.add_script(n, src(n))
    w.add_item("Wind Settings", "notecard", card)
    w.start_all()
    w.wear()
    w.run(5.0)
    assert float(w.lsd.get("cfg:speed_cruise", 0)) == 7.0 and float(w.lsd.get("cfg:height_low", 0)) == 5.0, w.lsd
    clean(w)


@scenario
def reset_while_reading_the_notecard():
    w = make(notecard="speed_cruise = 7\n" * 30)
    w.cache_lines = 2                             # slow reading, one line at a time
    w.chat(8, "reload")
    w.run(0.3)                                    # half way through the notecard...
    for s in w.scripts:                           # ...the HUD is taken off and worn again
        s.post("on_rez", 0)
    w.process()
    w.run(4.0)
    assert float(w.lsd.get("cfg:speed_cruise", 0)) == 7.0, "settings lost: %s" % w.lsd
    clean(w)


@scenario
def survives_lag():
    for seed in (1, 2, 3):
        w = make(start=(60.0, 160.0), yaw=EAST, lag=0.5, seed=seed, notecard=SETTINGS_TEXT + "\nobjects = on\n")
        lift(w, 6.0)
        watch = Watch(w)
        w.chat(8, "fast")
        w.press(FWD)
        w.run(14.0, every=watch)
        assert watch.min_solid > 0.6, "seed %d: down to %.2f m above the roof/land" % (seed, watch.min_solid)
        assert watch.max_speed < 16.0 * 1.35, "seed %d: ran away at %.1f m/s" % (seed, watch.max_speed)
        assert not w.bumps, "seed %d: bumped %s" % (seed, w.bumps[:3])
        clean(w)


@scenario
def teleport_and_sitting_switch_off():
    w = make()
    lift(w)
    w.teleport(256 + 30.0, 128.0)
    w.run(0.5)
    assert not active(w) and said(w, "Paused for the teleport")
    lift(w)
    w.sitting = True
    w.run(0.5)
    assert not active(w) and said(w, "You sat down")
    w.sitting = False
    clean(w)


@scenario
def missing_levels_script_is_reported():
    w = make(scripts=[s for s in SCRIPTS if s != "Wind Levels"])
    lift(w, 5.0)
    assert not active(w), w.status()
    assert said(w, '"Wind Levels" script is not answering')
    assert w.mtt is None and w.buoy == 0.0


@scenario
def dive_needs_deep_water():
    w = make()
    w.chat(8, "dive")
    w.run(2.0)
    assert said(w, "Dive needs deep water")
    assert not active(w)
    assert w.on_ground and w.buoy == 0.0
    assert not w.controls, "keys still taken by %s" % [s.name for s in w.controls]
    clean(w)


@scenario
def one_prim_hud():
    w = make(prims=["Wind HUD"])
    w.touch(0)
    w.run(4.0)
    assert active(w)
    w.touch(0, hold=1.2)
    assert w.dialogs and w.dialogs[-1][2][0] == "Land"
    w.touch(0)
    w.run(6.0)
    assert not active(w)
    clean(w)


@scenario
def animation_choices():
    w = make(anims=())
    lift(w)
    assert w.anims == {"hover"}, w.anims        # nothing in the HUD: Second Life's own
    w.press(FWD)
    w.run(2.0)
    assert w.anims == {"hover"}, w.anims          # never the forward-leaning "fly"
    w.release(FWD)
    w.run(4.0)

    w = make(anims=("My Own Glide",))
    lift(w)
    assert w.anims == {"My Own Glide"}, w.anims   # any one animation plays everywhere

    w = make(anims=("Wind Glide", "Wind Glide Idle", "Wind Surface", "Wind Dive", "Wind Dive Idle"))
    lift(w)
    assert w.anims == {"Wind Glide Idle"}, w.anims
    w.press(FWD)
    w.run(2.0)
    assert w.anims == {"Wind Glide"}, w.anims
    w.release(FWD)
    w.run(5.0)
    assert w.anims == {"Wind Glide Idle"}, w.anims
    w.add_item("Wind Glide Idle", "animation")    # (inventory change re-picks)
    w.changed_inventory()
    assert w.anims == {"Wind Glide Idle"}, w.anims
    w.touch(w.link_named("power"))
    w.run(8.0)
    assert not w.anims, "animation left playing after landing: %s" % w.anims
    clean(w)


@scenario
def sounds_follow_speed():
    w = make(start=(20.0, 40.0), yaw=NORTH, sounds=("Wind Glide Loop",))
    lift(w)
    assert w.sound and w.sound[0] == "Wind Glide Loop"
    quiet = w.sound[1]
    w.chat(8, "fast")
    w.press(FWD)
    w.run(6.0)
    assert w.sound[1] > quiet + 0.1, "louder when fast: %s -> %s" % (quiet, w.sound)
    w.chat(8, "set sound off")
    w.run(0.5)
    assert w.sound is None
    clean(w)


@scenario
def hud_buttons_and_chat_words():
    w = make()
    w.touch(w.link_named("glide"))
    w.run(4.0)
    assert active(w) and level(w) == 0
    w.touch(w.link_named("up"))
    w.run(6.0)
    assert w.status()[4] == 15, w.status()
    w.touch(w.link_named("down"))
    w.run(6.0)
    assert w.status()[4] == 4, w.status()
    w.touch(w.link_named("speed"))
    assert w.status()[5] == 2
    w.touch(w.link_named("help"))
    assert "Wind - User Manual" in w.given and said(w, "Tap the HUD to rise")
    w.chat(8, "numbers")
    w.run(1.0)
    assert "feet" in w.text and "speed" in w.text, w.text
    w.chat(8, "numbers")
    w.run(0.5)
    assert w.text.startswith("GLIDE"), w.text
    w.chat(8, "memory")
    assert len(said(w, "KB used")) == 6, said(w, "KB used")
    w.chat(8, "fly me to the moon")
    assert said(w, 'I do not know "fly me to the moon"')
    clean(w)


@scenario
def blocked_by_something_invisible():
    w = make(start=(20.0, 40.0), yaw=NORTH)
    lift(w)
    w.press(FWD)
    w.run(3.0)
    w.boxes.append(Box((0, w.gpos[1] + 8, 0), (256, w.gpos[1] + 9, 200), "ban line"))
    w.boxes[-1].ray = lambda a, b: None            # rays do not see it, like a ban line
    w.run(6.0)
    assert said(w, "Something you cannot see is in the way"), w.said[-2:]
    pushes = len(w.bumps)
    w.run(3.0)
    assert len(w.bumps) - pushes < 10, "keeps pushing against it"
    w.release(FWD)
    w.yaw = EAST
    w.press(FWD)
    w.run(3.0)
    assert w.speed() > 5.0, "cannot leave after being blocked"


@scenario
def rays_and_messages_stay_cheap():
    w = make(start=(60.0, 160.0), yaw=EAST)
    lift(w)
    w.press(FWD)
    t0, n0 = w.t, len(w.rays)
    w.run(10.0)
    per_second = (len(w.rays) - n0) / (w.t - t0)
    assert per_second <= 25.0, "%.1f rays a second" % per_second
    clean(w)


@scenario
def mouselook_dives_where_you_look():
    w = make(start=(600.0, 128.0))               # on the floor of the Deep (18 m of water)
    lift(w)
    assert level(w) == 2
    w.press(UP)
    w.run(4.0)
    w.release(UP)
    w.run(1.0)
    start_z = w.gpos[2]
    w.mouselook = True
    w.pitch = -0.6               # looking down
    w.press(FWD)
    w.run(3.0)
    assert w.gpos[2] < start_z - 1.5, "did not follow the look down (%.2f -> %.2f)" % (start_z, w.gpos[2])
    w.pitch = 0.6                # looking up
    w.run(4.0)
    assert w.gpos[2] > start_z - 1.0
    w.release(FWD)
    clean(w)


@scenario
def objects_off_stops_before_a_tower_and_e_goes_over():
    w = make(start=(60.0, 160.0), yaw=EAST)
    lift(w)
    watch = Watch(w)
    w.press(FWD)
    w.run(14.0, every=watch)
    assert 90 < w.gpos[0] < 99.5, "should wait in front of the tower (x %.1f)" % w.gpos[0]
    assert abs(w.clearance() - 4.0) < 1.0, "must not rise by itself (%.2f)" % w.clearance()
    assert not w.bumps, w.bumps[:3]
    w.press(UP)
    w.run(7.0)                                   # hold E: up past the 23 m roof
    w.release(UP)
    w.run(8.0)
    assert w.gpos[0] > 125, "E did not get over the tower (x %.1f)" % w.gpos[0]
    clean(w)


@scenario
def city_is_calm_with_objects_off():
    import random
    rnd = random.Random(7)
    boxes = []
    for i in range(6):
        for j in range(6):
            x0, y0 = 40 + i * 36, 40 + j * 36
            h = rnd.choice([12, 16, 20, 28, 36, 48, 60])
            boxes.append(Box((x0, y0, 20), (x0 + 26, y0 + 26, 20 + h), "b%d_%d" % (i, j)))
    global BOXES
    saved, BOXES = BOXES, boxes
    try:
        w = make(start=(22.0, 128.0), yaw=EAST)
        lift(w)
        w.chat(8, "high")                        # 40 m: above most of the skyline, chosen by you
        w.run(8.0)
        zs = []
        w.press(FWD)
        while w.gpos[0] - w.corner[0] < 200 and w.t < 90:
            w.run(0.1, every=lambda w: zs.append(w.gpos[2]))
        assert max(zs) - min(zs) < 8.0, "height ranged %.1f m across the city" % (max(zs) - min(zs))
    finally:
        BOXES = saved
    clean(w)


@scenario
def snappy_response():
    for k in (0.5, 1.0, 3.0):
        w = make(start=(20.0, 10.0), yaw=NORTH, mtt_k=k)
        lift(w, 5.0)
        t0 = w.t
        w.press(FWD)
        while w.speed() < 7.2 and w.t - t0 < 6.0:
            w.run(0.02)
        limit = 2.0 if k < 1.0 else 1.5          # the soft-pull guess is the slowest case
        assert w.t - t0 < limit, "k=%s: %.2f s to reach speed (want under %.1f)" % (k, w.t - t0, limit)
        w.run(2.0)
        t1 = w.t
        w.release(FWD)
        while w.speed() > 0.3 and w.t - t1 < 10:
            w.run(0.02)
        limit = 3.5 if k < 1.0 else 3.0
        assert w.t - t1 < limit, "k=%s: %.2f s to stop (want under %.1f)" % (k, w.t - t1, limit)
        clean(w)


@scenario
def camera_follows_closely():
    w = make()
    lift(w)
    assert abs(w.camera[C["CAMERA_POSITION_LAG"]] - 0.12) < 0.001, w.camera
    w.chat(8, "set cam_lag 0.4")
    w.run(0.5)
    assert abs(w.camera[C["CAMERA_POSITION_LAG"]] - 0.4) < 0.001, w.camera
    clean(w)


@scenario
def lands_on_the_water_then_sinks():
    w = make(start=(600.0, 128.0))               # the Deep: under water
    lift(w)
    w.press(UP)
    w.run(7.0)
    w.release(UP)
    w.run(1.0)
    assert level(w) == 1, w.status()
    w.touch(w.link_named("power"))
    w.run(6.0)
    assert not active(w), w.status()
    w.run(6.0)
    assert w.on_ground and w.feet() < 3.0, "did not sink to the sea bed: feet at %.2f" % w.feet()
    clean(w)


@scenario
def lands_on_a_roof():
    w = make(start=(60.0, 160.0), yaw=EAST, notecard=SETTINGS_TEXT + "\nobjects = on\n")
    lift(w)
    w.press(FWD)
    while w.gpos[0] < 108.0 and w.t < 60:
        w.run(0.1)
    w.release(FWD)
    w.run(4.0)
    assert 100 < w.gpos[0] < 120, "not over the tower (x %.1f)" % w.gpos[0]
    w.touch(w.link_named("power"))
    w.run(8.0)
    assert not active(w)
    assert w.on_ground and abs(w.feet() - 48.0) < 0.2, "not on the roof: feet at %.2f" % w.feet()
    clean(w)


@scenario
def crosses_a_border_under_water():
    w = make(start=(256 + 230.0, 128.0), yaw=EAST)   # Bay sea floor, 12 m deep, going east into the Deep
    lift(w)
    assert level(w) == 2
    w.press(FWD)
    while w.region().name == "Bay" and w.t < 60:
        w.run(0.1)
    w.run(3.0)
    assert w.region().name == "Deep" and level(w) == 2, (w.region().name, w.status())
    assert w.gpos[2] < 19.0 and w.speed() > 2.5, "lost the dive at the border (z %.2f, speed %.2f)" % (w.gpos[2], w.speed())
    clean(w)


@scenario
def remembers_height_and_speed():
    w = make()
    lift(w)
    w.chat(8, "high")
    w.chat(8, "fast")
    w.run(8.0)
    w.touch(w.link_named("power"))
    w.run(10.0)
    assert not active(w)
    w.wear()                                     # log out and in again
    w.run(2.0)
    lift(w, 10.0)
    assert w.status()[4] == 40 and w.status()[5] == 2, w.status()
    assert 38.5 < w.clearance() < 41.5, "not back at High: %.2f" % w.clearance()
    clean(w)


@scenario
def new_owner_starts_fresh():
    w = make()
    w.chat(8, "set speed_cruise 5")
    w.chat(8, "high")
    w.lsd["st:owner"] = "someone else"           # as if the HUD was sold or given
    w.wear()
    w.run(2.0)
    assert float(w.lsd["cfg:speed_cruise"]) == 8.0, "old settings kept: %s" % w.lsd.get("cfg:speed_cruise")
    assert "st:height" not in w.lsd, "old height kept"
    assert len(said(w, "Welcome to Wind")) == 2, "the new owner was not welcomed"
    clean(w)


def main(argv):
    global VERBOSE
    if "-v" in argv:
        VERBOSE = True
        argv = [a for a in argv if a != "-v"]
    chosen = [s for s in SCENARIOS if not argv or any(a in s.__name__ for a in argv)]
    failed = 0
    for fn in chosen:
        try:
            fn()
            print("PASS  " + fn.__name__)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("FAIL  " + fn.__name__ + ": " + (str(e) or type(e).__name__))
            if VERBOSE or not isinstance(e, AssertionError):
                traceback.print_exc()
    print("%d passed, %d failed" % (len(chosen) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
