# The Gemini prototype (Glide Suite v1.4): what it did, and why Wind replaces it

The original script is kept in `prototype/Glide_Suite_v1.4_gemini.lsl` for reference.
Do not put it in the HUD.

## What it did

- **One script, one button.** Click once: on, about 12 m up ("Low"). Double-click:
  on at 50 m ("High"), or switch between Low and High while on. Click once while
  on: off. A single click waited 0.3 s to make sure it was not a double click.
- **While on** it took W/S, Shift+A/D (slide), E and C, switched gravity off, and
  ten times a second gave the avatar a push (`llApplyImpulse`):
  - up/down: a spring pulling the avatar's middle to 12 m or 50 m above the land
    or water directly below it;
  - forward: started at 18 m/s and grew by 0.45 m/s every tenth of a second
    while W was held, up to 34 m/s. Double-tapping W jumped straight to 34.
  - C (down) was an air brake (2.5 m/s), so there was no way to go lower.
  - one ray straight ahead at body height: if it hit something, the height aim
    jumped to 1.6 m above the hit point plus the 12/50 m.
- No camera control (despite "Camera" in its title), no animation, messages in
  Hungarian. It sent link messages (1000 "SET_STATE"/"SET_ALT_MODE") for a
  display script that is not part of it.

## Why it was hard to steer (measured)

`python3 tests/compare.py` flies both through the same five experiments in the
test world. Both hover about 12 m up. The physics is a model of Second Life, so
read these as "how the two designs behave", not as exact in-world values.

| | Gemini v1.4 | Wind 0.1 |
|---|---|---|
| hover height (feet above ground, m) | 11.07 | 12.08 |
| lift-off overshoot (m) | 3.01 | 0.02 |
| settles within 0.3 m after (s) | 5.71 | 4.00 |
| cruise speed (m/s) | 30.25 | 8.00 |
| height wobble while cruising (m) | 0.72 | 0.12 |
| stopping time (s) | 1.69 | 3.47 |
| stopping distance (m) | 13.36 | 8.99 |
| closest to a roof or the land (m) | 0.00 | 4.59 |
| time touching the tower (s) | 0.09 | 0.00 |
| got over the tower | yes | yes |
| lowest in the 4 s after crossing a border (m) | 0.00 | 12.06 |
| still on after the border | no | yes |

The problems behind those numbers:

1. **Far too fast to explore.** Holding W always ends at 34 m/s within about
   3.5 s ("turbo" made no real difference). Textures do not even load at that
   speed, and every stop overshoots what you wanted to look at. Wind cruises at
   8 m/s, with Gentle (3.5) and Fast (16) gears and an optional boost.
2. **Bouncy height.** The height spring was under-damped (it overshoots by about
   a quarter every time): 3 m overshoot after lift-off, and it bobs over every
   bump. Wind eases into every change of height and never overshoots.
3. **Pushes in bursts.** An impulse ten times a second assumes the script runs
   exactly every 0.1 s. In a busy region it does not, so the push came out
   uneven: sagging, then surging. Wind moves a guide point and lets the region's
   physics pull the avatar after it continuously (`llMoveToTarget`), so lag only
   slows it down. If a script stalls, you come to rest instead of drifting off.
4. **Only looked straight down and straight ahead.** Hills and buildings were
   noticed when you were already at them, and roofs and trees below did not count
   as "the ground", so 12 m could mean scraping a roof. It touched the tower and
   came down to 0 m above it. Wind looks below and ahead (land, objects and
   water), climbs early, slows down when something is in the way, and keeps the
   height above whatever is highest: land, roofs, trees or water.
5. **Crossing into the next region switched it off in mid-air.** The script reset
   itself on every region change: gravity came back and you fell. For a tool made
   to explore regions this was the worst bug. Wind keeps going across borders,
   and stops gently at the edge of the world.
6. **Switching off dropped you.** Gravity simply came back, from up to 50 m.
   Wind lands you gently (tap again while landing to stop at once).
7. **No way down, no water.** C was a brake. Wind uses E/C to move through three
   levels: Glide (air), Surface (on the water) and Dive (under it).
8. **No camera, no animation.** You saw Second Life's "falling" pose. Wind plays
   your own animations per level and gives each level its own camera.
9. **Hidden controls.** Double-click for High and the 0.3 s click delay were hard
   to discover. Wind: tap to start or land, hold for a menu, buttons by name,
   `/8` chat commands, and a status line above the HUD.
10. **Smaller issues:** asked for camera tracking it never used; its "safe camera
    clear" could never run (it never asked for camera control); one timer did
    both click timing and physics.
