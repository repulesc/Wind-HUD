"""A pretend Second Life for testing: one avatar wearing a HUD whose scripts
run in the interpreter (lsl.py), on a grid of regions with land, water and
boxes (buildings, trees, piers).

Modelled, because Wind relies on it:
- time at the physics rate (45 steps a second); script timers, with optional
  lag (random late timers); event queues (64 at most, timers do not stack)
- link messages between the HUD's scripts, LinksetData, notecards, inventory
- permissions (granted at once, as for attachments), taking controls, keys
- the avatar: position, velocity, facing, size, gravity and buoyancy,
  llMoveToTarget as a critically damped pull, llApplyImpulse, standing on land
  and on boxes, bumping into boxes
- regions: water height, a land height function, boxes; crossing into the
  next region (CHANGED_REGION); the edge of the world
- llCastRay against land and boxes (counted, to watch the budget)
- camera parameters, animations, sounds, dialogs, listens, chat, HUD text

Not modelled: other avatars, flying physics, sim performance limits.

How strongly llMoveToTarget pulls is not documented by Linden Lab. Here it is
omega = mtt_k / tau; tests run with several mtt_k values so Wind cannot rely
on one guess.
"""
import hashlib
import heapq
import math
import random

from .lsl import B, Key, Vector, Quaternion, Script, CONSTANTS, f32

C = CONSTANTS
NULL_KEY = "00000000-0000-0000-0000-000000000000"
AVATAR = Key("a7a7a7a7-0000-4000-8000-000000000001")
AUTO_PERMS = (C["PERMISSION_TAKE_CONTROLS"] | C["PERMISSION_TRIGGER_ANIMATION"]
              | C["PERMISSION_TRACK_CAMERA"] | C["PERMISSION_CONTROL_CAMERA"]
              | C["PERMISSION_OVERRIDE_ANIMATIONS"] | C["PERMISSION_ATTACH"])
BUILTIN_ANIMS = {"fly", "hover", "hover_up", "hover_down", "fly_slow", "falling", "stand", "land"}
INV = {"animation": C["INVENTORY_ANIMATION"], "sound": C["INVENTORY_SOUND"],
       "notecard": C["INVENTORY_NOTECARD"], "script": C["INVENTORY_SCRIPT"]}


def V(*xs):
    return Vector(f32(x) for x in xs)


def vadd(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def vsub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def vmul(a, k):
    return [a[0] * k, a[1] * k, a[2] * k]


def vlen(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


class Box:
    """An axis-aligned solid box in global coordinates (a building, tree, pier...)."""

    def __init__(self, lo, hi, name="box"):
        self.lo = [float(x) for x in lo]
        self.hi = [float(x) for x in hi]
        self.name = name
        self.key = Key(hashlib.md5(name.encode() + repr(lo).encode()).hexdigest()[:8] + "-0000-4000-8000-000000000000")

    def contains(self, p):
        return all(self.lo[i] < p[i] < self.hi[i] for i in range(3))

    def ray(self, a, b):
        """Fraction 0..1 along a->b where the ray enters the box, or None."""
        t0, t1 = 0.0, 1.0
        for i in range(3):
            d = b[i] - a[i]
            if abs(d) < 1e-12:
                if a[i] < self.lo[i] or a[i] > self.hi[i]:
                    return None
                continue
            ta = (self.lo[i] - a[i]) / d
            tb = (self.hi[i] - a[i]) / d
            if ta > tb:
                ta, tb = tb, ta
            t0 = max(t0, ta)
            t1 = min(t1, tb)
            if t0 > t1:
                return None
        if t0 <= 0.0:
            return None  # starts inside: Second Life does not report it either
        return t0


class Region:
    def __init__(self, water=20.0, ground=None, name="Region"):
        self.water = water
        self.ground = ground or (lambda x, y: 22.0)
        self.name = name


class World:
    STEP = 1.0 / 45.0

    def __init__(self, regions, start, seed=1, mtt_k=1.0, lag=0.0, boxes=(), prims=("Wind HUD",), verbose=False):
        """regions: {(ix, iy): Region}; start: global <x, y> (feet put on the ground)."""
        self.regions = regions
        self.boxes = list(boxes)
        self.rng = random.Random(seed)
        self.mtt_k = mtt_k
        self.lag = lag
        self.verbose = verbose
        self.t = 0.0
        self.seq = 0
        self.pending = []
        self.scripts = []
        self.sd = {}
        self.prims = list(prims)
        self.inventory = {}
        self.lsd = {}
        self.log = []
        self.notes = []
        self.errors = []
        self.said = []
        self.dialogs = []
        self.listens = {}
        self.next_listen = 1
        self.controls = {}
        self.keys = 0
        self.next_repeat = 0.0
        self.camera = None
        self.anims = set()
        self.sound = None
        self.sounds_played = []
        self.text = ""
        self.glow = {}
        self.given = []
        self.cached = {}           # notecard -> sync reads left before the region forgets it
        self.cache_lines = 1000
        self.rays = []
        self.far_targets = 0
        self.bumps = []            # (time, box name): sides or undersides of boxes hit
        # the avatar
        self.size = [0.45, 0.6, 1.9]
        self.half = self.size[2] / 2.0
        self.mass = 70.0
        x, y = start
        self.gpos = [float(x), float(y), self.solid_below(x, y, 4000.0) + self.half]
        self.vel = [0.0, 0.0, 0.0]
        self.yaw = 0.0
        self.pitch = 0.0
        self.buoy = 0.0
        self.mtt = None
        self.on_ground = True
        self.sitting = False
        self.flying = False
        self.mouselook = False
        self.corner = self.corner_of(self.gpos)
        self.attached = False

    # ---- geography ----------------------------------------------------
    @staticmethod
    def corner_of(p):
        return [math.floor(p[0] / 256.0) * 256.0, math.floor(p[1] / 256.0) * 256.0, 0.0]

    def region_at(self, x, y):
        return self.regions.get((int(math.floor(x / 256.0)), int(math.floor(y / 256.0))))

    def land(self, x, y):
        r = self.region_at(x, y)
        if r is None:
            return 0.0
        cx, cy = math.floor(x / 256.0) * 256.0, math.floor(y / 256.0) * 256.0
        return r.ground(x - cx, y - cy)

    def water_at(self, x, y):
        r = self.region_at(x, y)
        return r.water if r else 0.0

    def solid_below(self, x, y, z):
        """Top of the land or box under the point."""
        top = self.land(x, y)
        for b in self.boxes:
            if b.lo[0] <= x <= b.hi[0] and b.lo[1] <= y <= b.hi[1] and b.hi[2] <= z + 1e-6:
                top = max(top, b.hi[2])
        return top

    def region(self):
        return self.region_at(self.gpos[0], self.gpos[1])

    def local(self):
        return V(self.gpos[0] - self.corner[0], self.gpos[1] - self.corner[1], self.gpos[2])

    def rot(self):
        return B.llEuler2Rot(V(0.0, -self.pitch, self.yaw))

    # ---- what happened -------------------------------------------------
    def note(self, text):
        self.notes.append((round(self.t, 2), text))
        if self.verbose:
            print("  [%7.2f] %s" % (self.t, text))

    def error(self, script, text):
        self.errors.append((round(self.t, 2), script.name, text))
        self.note("ERROR %s: %s" % (script.name, text))

    # ---- scripts ---------------------------------------------------------
    def add_script(self, name, source, link=1):
        s = Script(self, name, source, link)
        self.scripts.append(s)
        self.inventory[name] = ("script", None)
        return s

    def script_reset(self, s):
        old = self.sd.get(s, {})
        for h in [h for h, l in self.listens.items() if l[0] is s]:
            del self.listens[h]
        self.controls.pop(s, None)
        self.sd[s] = {"t0": self.t, "timer": 0.0, "next": 0.0, "perms": 0}
        if old.get("perms", 0) & C["PERMISSION_TRIGGER_ANIMATION"]:
            pass  # animations keep playing after a reset, as in Second Life

    def at(self, delay, fn):
        self.seq += 1
        heapq.heappush(self.pending, (self.t + delay, self.seq, fn))

    def start_all(self, order=None):
        """Every script starts (state_entry), in the given or a random order."""
        scripts = list(self.scripts)
        if order is None:
            self.rng.shuffle(scripts)
        for s in scripts:
            s.post("state_entry")
        self.process()

    def wear(self):
        """Attaching the HUD: on_rez and attach for every script."""
        self.attached = True
        scripts = list(self.scripts)
        self.rng.shuffle(scripts)
        for s in scripts:
            s.post("on_rez", 0)
            s.post("attach", AVATAR)
        self.process()

    def process(self):
        for _ in range(200000):
            ran = False
            for s in self.scripts:
                if s.run_one():
                    ran = True
            if not ran:
                return
        raise RuntimeError("endless events")

    def broadcast(self, event, *args):
        for s in self.scripts:
            s.post(event, *args)

    # ---- time -------------------------------------------------------------
    def run(self, seconds, every=None):
        """Runs the world. `every(world)` is called after each physics step."""
        steps = int(round(seconds / self.STEP))
        for _ in range(steps):
            self.step()
            if every:
                every(self)

    def step(self):
        dt = self.STEP
        self.t += dt
        self.physics(dt)
        while self.pending and self.pending[0][0] <= self.t:
            _, _, fn = heapq.heappop(self.pending)
            fn()
        for s in self.scripts:
            d = self.sd[s]
            if d["timer"] > 0 and self.t >= d["next"]:
                s.post("timer")
                late = self.rng.uniform(0.0, self.lag) if self.lag else 0.0
                d["next"] = self.t + d["timer"] + late
        if self.keys and self.t >= self.next_repeat:
            self.next_repeat = self.t + 0.1
            for s, ctl in list(self.controls.items()):
                if self.keys & ctl:
                    s.post("control", AVATAR, self.keys & ctl, 0)
        self.process()

    # ---- physics --------------------------------------------------------
    def physics(self, dt):
        a = [0.0, 0.0, -9.81 * (1.0 - self.buoy)]
        if self.mtt is not None and not self.sitting:
            target, tau = self.mtt
            d = vsub(target, self.gpos)
            if vlen(d) < 65.0:
                w = self.mtt_k / max(tau, 2.0 / 45.0)
                a = vadd(a, vsub(vmul(d, w * w), vmul(self.vel, 2.0 * w)))
            else:
                self.far_targets += 1
        if self.sitting:
            self.vel = [0.0, 0.0, 0.0]
            return
        self.vel = vadd(self.vel, vmul(a, dt))
        if self.on_ground and self.mtt is None:
            self.vel[0] = self.vel[1] = 0.0   # standing still on the ground
        new = vadd(self.gpos, vmul(self.vel, dt))
        # the edge of the world
        if self.region_at(new[0], new[1]) is None:
            for i in (0, 1):
                probe = list(self.gpos)
                probe[i] = new[i]
                if self.region_at(probe[0], probe[1]) is None:
                    new[i] = self.gpos[i]
                    self.vel[i] = 0.0
        # boxes: bump against their sides, stand on their tops
        self.on_ground = False
        for b in self.boxes:
            lo = [new[0] - 0.3, new[1] - 0.3, new[2] - self.half]
            hi = [new[0] + 0.3, new[1] + 0.3, new[2] + self.half]
            if all(lo[i] < b.hi[i] and hi[i] > b.lo[i] for i in range(3)):
                pen = []
                for i in range(3):
                    pen.append((b.hi[i] - lo[i], i, +1))
                    pen.append((hi[i] - b.lo[i], i, -1))
                depth, i, sign = min(pen)
                new[i] += sign * depth
                if self.vel[i] * sign < 0:
                    self.vel[i] = 0.0
                if i == 2 and sign > 0:
                    self.on_ground = True
                elif self.mtt is not None or self.buoy > 0.0:   # while a script carries the avatar
                    self.bumps.append((round(self.t, 2), b.name))
        ground = self.land(new[0], new[1])
        if new[2] - self.half <= ground + 1e-4:
            new[2] = ground + self.half
            if self.vel[2] < 0:
                self.vel[2] = 0.0
            self.on_ground = True
        self.gpos = new
        corner = self.corner_of(self.gpos)
        if corner != self.corner:
            self.corner = corner
            self.note("region crossing into %s" % (self.region().name,))
            self.at(0.05, lambda: self.broadcast("changed", C["CHANGED_REGION"]))

    # ---- keys and touches (the person at the keyboard) --------------------
    def press(self, mask):
        changed = mask & ~self.keys
        self.keys |= mask
        self.control_event(changed)
        self.process()

    def release(self, mask=-1):
        changed = mask & self.keys
        self.keys &= ~mask
        self.control_event(changed)
        self.process()

    def tap(self, mask, seconds=0.1):
        self.press(mask)
        self.run(seconds)
        self.release(mask)

    def control_event(self, changed):
        for s, ctl in list(self.controls.items()):
            if changed & ctl:
                s.post("control", AVATAR, self.keys & ctl, changed & ctl)

    def touch(self, link=1, hold=0.1):
        det = [{"key": AVATAR, "link": link}]
        for s in self.scripts:
            s.post("touch_start", 1, detected=det)
        self.process()
        self.run(hold)
        for s in self.scripts:
            s.post("touch_end", 1, detected=det)
        self.process()

    def link_named(self, name):
        return self.prims.index(name) + 1

    def chat(self, channel, text):
        for h, (s, ch, name, key, msg) in list(self.listens.items()):
            if ch == channel and key in ("", NULL_KEY, AVATAR) and msg in ("", text):
                s.post("listen", channel, "Tester", AVATAR, text)
        self.process()

    def answer_dialog(self, button):
        ch, msg, buttons = self.dialogs[-1]
        assert button in buttons, "no button %r in %r" % (button, buttons)
        self.chat(ch, button)

    def teleport(self, gx, gy):
        self.mtt = None
        self.gpos = [gx, gy, self.solid_below(gx, gy, 4000.0) + self.half]
        self.vel = [0.0, 0.0, 0.0]
        self.corner = self.corner_of(self.gpos)
        self.broadcast("changed", C["CHANGED_TELEPORT"] | C["CHANGED_REGION"])
        self.process()

    # ---- helpers for tests ----------------------------------------------
    def feet(self):
        return self.gpos[2] - self.half

    def clearance(self):
        """Feet above the land/box tops/water directly below."""
        top = max(self.solid_below(self.gpos[0], self.gpos[1], self.feet()), self.water_at(self.gpos[0], self.gpos[1]))
        return self.feet() - top

    def solid_clearance(self):
        """Feet above the land / box tops directly below (ignores water)."""
        return self.feet() - self.solid_below(self.gpos[0], self.gpos[1], self.feet())

    def speed(self):
        return math.hypot(self.vel[0], self.vel[1])

    def status(self):
        for s in self.scripts:
            if "status" in s.globals and s.globals["status"]:
                return [int(x) for x in s.globals["status"]]
        return []

    # =====================================================================
    # ll* functions the library does not have. Each takes the script first.
    # =====================================================================
    def require(self, s, perm, fn):
        if not (self.sd[s]["perms"] & perm):
            self.error(s, "%s without permission" % fn)
            return False
        return True

    def llGetTime(self, s):
        return f32(self.t - self.sd[s]["t0"])

    def llResetTime(self, s):
        self.sd[s]["t0"] = self.t

    def llGetOwner(self, s):
        return AVATAR

    def llGetKey(self, s):
        return Key("b0b0b0b0-0000-4000-8000-000000000002")

    def llOwnerSay(self, s, msg):
        self.said.append((round(self.t, 2), s.name, msg))
        if self.verbose:
            print("  [%7.2f] %s says: %s" % (self.t, s.name, msg))

    def llSetTimerEvent(self, s, t):
        d = self.sd[s]
        d["timer"] = t
        d["next"] = self.t + t if t > 0 else 0.0

    def llMessageLinked(self, s, link, num, text, ident):
        if link not in (C["LINK_SET"], C["LINK_THIS"], C["LINK_ROOT"], 1):
            raise NotImplementedError("link target %d" % link)
        for t in self.scripts:
            t.post("link_message", s.link, num, text, Key(ident))

    # LinksetData
    def llLinksetDataRead(self, s, name):
        return self.lsd.get(name, "")

    def llLinksetDataWrite(self, s, name, value):
        if value == "":
            self.lsd.pop(name, None)
        else:
            self.lsd[name] = value
        return 0

    def llLinksetDataDelete(self, s, name):
        return 0 if self.lsd.pop(name, None) is not None else C["LINKSETDATA_NOTFOUND"]

    def llLinksetDataDeleteFound(self, s, pattern, password):
        import re
        hits = [k for k in self.lsd if re.search(pattern, k)]
        for k in hits:
            del self.lsd[k]
        return [len(hits), 0]

    def llLinksetDataReset(self, s):
        self.lsd.clear()

    # permissions and controls
    def llRequestPermissions(self, s, agent, perm):
        granted = perm & AUTO_PERMS if (agent == AVATAR and self.attached) else 0

        def grant():
            if not (granted & C["PERMISSION_TAKE_CONTROLS"]):
                self.controls.pop(s, None)
            self.sd[s]["perms"] = granted
            s.post("run_time_permissions", granted)
        self.at(0.02, grant)

    def llGetPermissions(self, s):
        return self.sd[s]["perms"]

    def llTakeControls(self, s, controls, accept, pass_on):
        if self.require(s, C["PERMISSION_TAKE_CONTROLS"], "llTakeControls"):
            self.controls[s] = controls

    def llReleaseControls(self, s):
        self.controls.pop(s, None)
        self.sd[s]["perms"] &= ~C["PERMISSION_TAKE_CONTROLS"]

    # the avatar
    def llGetPos(self, s):
        return self.local()

    def llGetRot(self, s):
        return self.rot()

    def llGetVel(self, s):
        return V(*self.vel)

    def llGetMass(self, s):
        return f32(self.mass)

    def llGetObjectMass(self, s, k):
        return f32(self.mass if k == AVATAR else 0.0)

    def llGetObjectDetails(self, s, k, params):
        if k != AVATAR:
            return []
        out = []
        for p in params:
            if p == C["OBJECT_POS"]:
                out.append(self.local())
            elif p == C["OBJECT_ROT"]:
                out.append(B.llEuler2Rot(V(0.0, 0.0, self.yaw)))
            elif p == C["OBJECT_VELOCITY"]:
                out.append(V(*self.vel))
            else:
                raise NotImplementedError("OBJECT_ %d" % p)
        return out

    def llGetAgentInfo(self, s, k):
        f = 0
        if self.sitting:
            f |= C["AGENT_SITTING"] | C["AGENT_ON_OBJECT"]
        if self.flying:
            f |= C["AGENT_FLYING"]
        if self.mouselook:
            f |= C["AGENT_MOUSELOOK"]
        if not self.on_ground:
            f |= C["AGENT_IN_AIR"]
        return f

    def llGetAgentSize(self, s, k):
        return V(*self.size) if k == AVATAR else V(0, 0, 0)

    def llGetAnimation(self, s, k):
        if self.sitting:
            return "Sitting"
        if self.flying:
            return "Hovering"
        if self.on_ground:
            return "Standing"
        return "Falling Down"

    def llGetCameraRot(self, s):
        if self.require(s, C["PERMISSION_TRACK_CAMERA"], "llGetCameraRot"):
            return self.rot()
        return Quaternion((0.0, 0.0, 0.0, 1.0))

    def llGetRegionCorner(self, s):
        return V(*self.corner)

    def llGround(self, s, off):
        p = vadd(self.gpos, off)
        lp = vsub(p, self.corner)
        if not (0.0 <= lp[0] < 256.0 and 0.0 <= lp[1] < 256.0):
            self.error(s, "llGround outside the region at %r" % (lp,))
        return f32(self.land(p[0], p[1]))

    def llWater(self, s, off):
        return f32(self.water_at(self.gpos[0], self.gpos[1]))

    def llEdgeOfWorld(self, s, pos, d):
        cx, cy = self.corner[0], self.corner[1]
        if abs(d[0]) >= abs(d[1]):
            nx, ny = cx + (256.0 if d[0] > 0 else -1.0), cy + 1.0
        else:
            nx, ny = cx + 1.0, cy + (256.0 if d[1] > 0 else -1.0)
        return int(self.region_at(nx, ny) is None)

    def llSetBuoyancy(self, s, b):
        self.buoy = b

    def llMoveToTarget(self, s, target, tau):
        if tau <= 0.0:
            return
        self.mtt = (vadd(list(target), self.corner), tau)

    def llStopMoveToTarget(self, s):
        self.mtt = None

    def llApplyImpulse(self, s, imp, local):
        self.vel = vadd(self.vel, vmul(list(imp), 1.0 / self.mass))

    def llCastRay(self, s, a, b, options):
        self.rays.append(self.t)
        ga = vadd(list(a), self.corner)
        gb = vadd(list(b), self.corner)
        reject = 0
        for i in range(0, len(options), 2):
            if options[i] == C["RC_REJECT_TYPES"]:
                reject = options[i + 1]
        best = None
        for box in self.boxes:
            t = box.ray(ga, gb)
            if t is not None and (best is None or t < best[0]):
                best = (t, box.key)
        if not reject & C["RC_REJECT_LAND"]:
            n = max(2, int(vlen(vsub(gb, ga)) / 0.25))
            prev = 0.0
            for i in range(1, n + 1):
                t = i / float(n)
                p = vadd(ga, vmul(vsub(gb, ga), t))
                if p[2] <= self.land(p[0], p[1]):
                    lo, hi = prev, t
                    for _ in range(20):
                        mid = (lo + hi) / 2
                        q = vadd(ga, vmul(vsub(gb, ga), mid))
                        if q[2] <= self.land(q[0], q[1]):
                            hi = mid
                        else:
                            lo = mid
                    if best is None or hi < best[0]:
                        best = (hi, Key(NULL_KEY))
                    break
                prev = t
        if best is None:
            return [0]
        hit = vsub(vadd(ga, vmul(vsub(gb, ga), best[0])), self.corner)
        return [best[1], V(*hit), 1]

    # camera, animations, sound
    def llSetCameraParams(self, s, rules):
        if not self.require(s, C["PERMISSION_CONTROL_CAMERA"], "llSetCameraParams"):
            return
        cam = dict(self.camera or {})
        for i in range(0, len(rules), 2):
            cam[rules[i]] = rules[i + 1]
        dist = cam.get(C["CAMERA_DISTANCE"], 3.0)
        pitch = cam.get(C["CAMERA_PITCH"], 0.0)
        if not (0.5 <= dist <= 10.0) or not (-45.0 <= pitch <= 80.0):
            self.error(s, "camera distance %s / pitch %s out of range" % (dist, pitch))
        self.camera = cam

    def llClearCameraParams(self, s):
        if self.require(s, C["PERMISSION_CONTROL_CAMERA"], "llClearCameraParams"):
            self.camera = None

    def llStartAnimation(self, s, name):
        if not self.require(s, C["PERMISSION_TRIGGER_ANIMATION"], "llStartAnimation"):
            return
        if name not in BUILTIN_ANIMS and self.inventory.get(name, ("",))[0] != "animation":
            self.error(s, "could not find animation " + name)
            return
        self.anims.add(name)

    def llStopAnimation(self, s, name):
        if self.require(s, C["PERMISSION_TRIGGER_ANIMATION"], "llStopAnimation"):
            self.anims.discard(name)

    def llLoopSound(self, s, name, vol):
        if self.inventory.get(name, ("",))[0] != "sound":
            self.error(s, "could not find sound " + name)
        self.sound = (name, round(vol, 3))

    def llStopSound(self, s):
        self.sound = None

    def llAdjustSoundVolume(self, s, vol):
        if self.sound:
            self.sound = (self.sound[0], round(vol, 3))

    def llTriggerSound(self, s, name, vol):
        self.sounds_played.append(name)

    def llPlaySound(self, s, name, vol):
        self.sounds_played.append(name)
        self.sound = None

    # inventory and notecards
    def add_item(self, name, kind, data=None):
        self.inventory[name] = (kind, data)

    def changed_inventory(self):
        self.broadcast("changed", C["CHANGED_INVENTORY"])
        self.process()

    def llGetInventoryType(self, s, name):
        item = self.inventory.get(name)
        return INV[item[0]] if item else C["INVENTORY_NONE"]

    def llGetInventoryNumber(self, s, kind):
        return sum(1 for k, v in self.inventory.items() if INV[v[0]] == kind)

    def llGetInventoryName(self, s, kind, n):
        names = sorted((k for k, v in self.inventory.items() if INV[v[0]] == kind), key=str.lower)
        return names[n] if 0 <= n < len(names) else ""

    def llGetInventoryKey(self, s, name):
        item = self.inventory.get(name)
        if not item:
            return Key(NULL_KEY)
        h = hashlib.md5((name + repr(item[1])).encode()).hexdigest()
        return Key("%s-%s-4%s-8%s-%s" % (h[:8], h[8:12], h[13:16], h[17:20], h[20:32]))

    def llGetNotecardLine(self, s, name, line):
        self.seq += 1
        q = Key("%08x-0000-4000-8000-%012x" % (self.seq, line))
        item = self.inventory.get(name)
        if not item or item[0] != "notecard":
            self.error(s, "no notecard " + name)
            return q
        lines = item[1].split("\n")
        data = lines[line] if line < len(lines) else C["EOF"]
        self.at(0.05, lambda: s.post("dataserver", q, data))
        return q

    def llGetNumberOfNotecardLines(self, s, name):
        self.seq += 1
        q = Key("%08x-0000-4000-8000-00000000ffff" % self.seq)
        item = self.inventory.get(name)
        if not item or item[0] != "notecard":
            self.error(s, "no notecard " + name)
            return q
        self.cached[name] = self.cache_lines      # now the region holds it for a while
        n = len(item[1].split("\n"))
        self.at(0.05, lambda: s.post("dataserver", q, str(n)))
        return q

    def llGetNotecardLineSync(self, s, name, line):
        item = self.inventory.get(name)
        if not item or self.cached.get(name, 0) <= 0:
            return C["NAK"]
        self.cached[name] -= 1
        lines = item[1].split("\n")
        return lines[line] if line < len(lines) else C["EOF"]

    def llGiveInventory(self, s, dest, name):
        self.given.append(name)

    # HUD
    def llSetText(self, s, text, color, alpha):
        self.text = text

    def llSetLinkPrimitiveParamsFast(self, s, link, rules):
        i = 0
        while i < len(rules):
            if rules[i] == C["PRIM_GLOW"]:
                self.glow[link] = round(rules[i + 2], 3)
                i += 3
            else:
                raise NotImplementedError("PRIM rule %d" % rules[i])

    def llGetLinkName(self, s, link):
        if len(self.prims) == 1:
            return self.prims[0] if link in (0, 1) else ""
        return self.prims[link - 1] if 1 <= link <= len(self.prims) else ""

    def llGetNumberOfPrims(self, s):
        return len(self.prims)

    def llDetectedKey(self, s, i):
        return s.detected[i]["key"] if i < len(s.detected) else Key(NULL_KEY)

    def llDetectedLinkNumber(self, s, i):
        if i >= len(s.detected):
            return 0
        return 0 if len(self.prims) == 1 else s.detected[i]["link"]

    def llGetAttached(self, s):
        return 32 if self.attached else 0

    def llListen(self, s, ch, name, k, msg):
        h = self.next_listen
        self.next_listen += 1
        self.listens[h] = (s, ch, name, k, msg)
        return h

    def llListenRemove(self, s, h):
        self.listens.pop(h, None)

    def llDialog(self, s, av, msg, buttons, ch):
        if not 1 <= len(buttons) <= 12:
            self.error(s, "dialog with %d buttons" % len(buttons))
        for b in buttons:
            if not b or len(b.encode()) > 24:
                self.error(s, "bad dialog button %r" % b)
        if not msg or len(msg.encode()) > 511:
            self.error(s, "dialog text of %d bytes" % len(msg.encode()))
        self.dialogs.append((ch, msg, list(buttons)))

    def llFrand(self, s, mx):
        return f32(self.rng.uniform(0.0, mx))

    def llGetUsedMemory(self, s):
        return 20000

    def llGetFreeMemory(self, s):
        return 40000
