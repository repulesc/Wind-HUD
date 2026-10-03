# Wind (v0.1 alpha)

A worn HUD for exploring Second Life regions in a magical way, without flying.
Tap it and the wind lifts you up and carries you: drifting above the land and
the rooftops (**Glide**), skimming the sea (**Surface**), or gliding through the
water under it (**Dive**). E and C take you up and down through those three
levels; each has its own movement, height, camera and animation.

This is a complete rewrite of the Gemini "Glide Suite" v1.4 prototype (kept in
`prototype/`). What was wrong with it, measured side by side with Wind, is in
[docs/Prototype_Review.md](docs/Prototype_Review.md). Where the project goes
next, what to decide and feature ideas are in [docs/ROADMAP.md](docs/ROADMAP.md).

## What is in this folder

| | |
|---|---|
| `Wind *.lsl` | **The six scripts to paste into the HUD.** Generated, never edit them. |
| `docs/Wind_Settings.txt` | Text of the **Wind Settings** notecard (speeds, heights, feel, camera, sound). |
| `docs/User_Manual.txt` | Text of the **Wind - User Manual** notecard, for customers. |
| `docs/ROADMAP.md` | The plan: next steps, decisions for you, feature ideas. |
| `docs/Prototype_Review.md` | The old prototype: what it did, why it was hard to steer. |
| `src/` | The source. Change this, then build. |
| `tools/build.py` | Builds the `Wind *.lsl` files from `src/` and checks them. |
| `tests/` | Runs the real scripts in a simulated Second Life (see Tests). |
| `prototype/` | The Gemini v1.4 script, for reference only. |

## Making the HUD

1. **Rez a box** and make it a button: Size 0.01 x 0.12 x 0.12, give it a texture,
   name the object **Wind HUD**. That is enough: a one-prim HUD works (tap to
   start and land, hold for the menu).
2. *Optional buttons:* link more flat prims to it and name each prim (Edit >
   General > Name) after what it does. Wind finds them by name, any case:

   | Prim name | Tap does |
   |---|---|
   | `power` (or any other name) | start / land (glows while Wind is on) |
   | `glide`, `surface`, `dive` | go to that level, starting Wind if needed (the current one glows) |
   | `up`, `down` | next glide height up / down |
   | `low`, `mid`, `high` | that glide height |
   | `speed` | next speed: Gentle, Cruise, Fast |
   | `menu` | the menu |
   | `help` | gives the user manual |

   Holding any button for a moment opens the menu.
3. **Scripts:** in the Content tab of the root prim, make six new scripts with
   exactly these names and paste the matching file into each. Each must be
   compiled as **Mono** (the default).

   | Script | Job |
   |---|---|
   | **Wind Engine** | Switching on and off, W/A/S/D, speed, and moving the avatar (an invisible guide point that `llMoveToTarget` pulls you after). |
   | **Wind Levels** | Where you should be: looks at the land, objects and water below and ahead, handles E/C, Glide/Surface/Dive, climbing over things, landing. |
   | **Wind Camera** | A camera for each level (stays under water while diving). |
   | **Wind Animator** | Plays your animations and sounds for each level. |
   | **Wind HUD** | Touches, the menu, the text above the HUD, `/8` commands. |
   | **Wind Config** | Reads the Wind Settings notecard; `/8 set`. |

4. **Notecards:** make a notecard named exactly **Wind Settings** with the text of
   `docs/Wind_Settings.txt`, and one named **Wind - User Manual** with
   `docs/User_Manual.txt`. Drop both into the HUD.
5. **Your animations** (see below) and, if you have them, sounds.
6. **Wear it** (e.g. HUD Bottom Right). You should see "Welcome to Wind 0.1.0".
   Then go through the first-flight checklist below.

## Your animations

Drop them into the HUD with these names. All are optional: with none of them,
the first animation in the HUD plays everywhere; with no animation at all,
Second Life's own "fly" and "hover".

| Name | Plays |
|---|---|
| `Wind Glide` | gliding through the air (and the fallback for every level) |
| `Wind Glide Idle` | hovering still in the air (falls back to Wind Glide) |
| `Wind Surface` / `Wind Surface Idle` | on the water (over land the Glide ones play) |
| `Wind Dive` / `Wind Dive Idle` | under the water |

Make them **looped** and upload them at **priority 4** (the highest the
uploader allows for .bvh; .anim files can go to 5 or 6, which also beats most
animation overriders). If your surface animation swims *in* the water rather
than standing on it, set `surface_ride` in the settings to about -0.9.

Optional sounds: `Wind Glide Loop`, `Wind Surface Loop`, `Wind Dive Loop` (only
you hear them, louder the faster you go) and `Wind Splash` (when you dive in or
come out, heard nearby).

## Using it

Tap to rise, tap to land (twice to stop at once), hold for the menu.
W/S forward and back, A/D turn, Shift+A/D slide, double-tap W and hold to
boost, E/C up and down through the levels. All of it is in
[docs/User_Manual.txt](docs/User_Manual.txt).

## Settings and tuning

Every number that shapes the feel is in the **Wind Settings** notecard,
explained in plain words. Save the notecard and Wind uses the new values at
once. To try a value without editing: `/8 set name value`
(e.g. `/8 set coast 1.5`), `/8 settings` lists them all, `/8 reload` goes back
to the notecard, `/8 numbers` shows live height and speed above the HUD.

## How it moves (for whoever works on the code)

- The **Engine** turns your keys into a wanted velocity and eases towards it
  (separate time constants for speeding up, turning, coasting and braking).
  That velocity moves an invisible **guide point**, kept in global coordinates
  so region crossings do not disturb it, and `llMoveToTarget` pulls the avatar
  after it, aiming slightly ahead by the expected lag so turns and stops feel
  direct. Gravity is off (`llSetBuoyancy(1)`). If a script stalls, the avatar
  comes to rest at the guide: nothing can fling it.
- **Levels** decides the height 10 times a second and tells the Engine
  (`EVT_AIM`). It samples the land below and ahead (`llGround`), casts one ray
  down (near and far by turns) and one ahead (`llCastRay`, about 20 a second at
  most), remembers the highest thing for a moment so you do not dip between
  roofs, climbs at up to `climb_rate`, sinks at most `sink_rate`, and reports
  anything in the way so the Engine slows down in time.
- All link messages and the shared settings table are at the top of
  `src/common.lsl`. Settings live in the HUD's LinksetData (`cfg:*`); the
  height and speed you chose last in `st:*`. Both are wiped for a new owner.

## Source, build and tests

- Edit `src/`, then run `python3 tools/build.py --check`. It writes the
  `Wind *.lsl` files (each gets only the shared helpers it uses), prints each
  script's size, refuses unsupported string escapes and setting names that do
  not exist, keeps `docs/Wind_Settings.txt` in step with the settings table,
  and runs a strict LSL syntax and type check. The check needs a checkout of
  [LSL-PyOptimizer](https://github.com/Sei-Lisa/LSL-PyOptimizer) at `/tmp/lslopt`
  (or set `LSLOPT`).
- `python3 tests/run_tests.py` runs the generated scripts, all six together,
  in a simulated Second Life: an interpreter built on LSL-PyOptimizer, and a
  world with avatar physics, land, sea, buildings, trees, a pier, an underwater
  rock, region borders, the edge of the world, timer lag, ray casts, camera,
  animations, menus, notecards and LinksetData. 37 scenarios: lift-off,
  cruising, turning, stopping, climbing over a tower and a hill, crossing
  regions (also under water), the edge of the world, all the level changes,
  landing (on land, a roof, the water), menus, chat commands, settings
  notecards (including broken lines and a reset half way through reading),
  lag, teleports, sitting, a missing script, a one-prim HUD, animation and
  sound choices, invisible walls, the ray budget, and that Wind holds no keys
  and pulls nothing once it is off.
- `python3 tests/compare.py` flies the Gemini prototype and Wind through the
  same course (the table in the prototype review).

What the tests cannot tell: how it *feels* in Second Life. How hard
`llMoveToTarget` pulls an avatar is not documented, so the tests run at several
strengths and Wind does not depend on one; lag is modelled as late timers.
That is what the in-world checklist is for.

### Script sizes

Second Life gives each script 64 KB, code included. Sentinel taught us that in
practice 3,788 tokens started fine and 5,373 crashed, so Wind keeps every script
under about 3,800 tokens: Levels 3,386, HUD 2,801, Engine 2,652, Config 1,763,
Animator 1,148, Camera 1,087. `/8 memory` prints the real numbers in-world.

## First flight: in-world checklist (not run yet: I could only test in the simulator)

Do these in order, somewhere open with land and sea (a Linden coast is ideal).
Send me what differs, plus the numbers it asks for.

1. Wear the HUD: "Welcome to Wind 0.1.0" appears once. `/8 memory`: send me the
   six lines (anything under 10 KB free needs trimming).
2. Tap: you rise smoothly to about 4 m above the ground and hover, gently
   bobbing. Your animation plays (or Second Life's hover), the camera moves
   behind and a little above you, the text says `GLIDE 4 m · Cruise`.
3. `/8 numbers`, then hold W for 5 s on flat ground: the second line should show
   a speed close to 8 of 8 m/s. Send me the line. Release W: you drift to a stop
   in a few seconds, without bouncing back.
4. Turn with A/D while holding W: the path follows your turn within about half a
   second. Too floaty or too twitchy? Try `/8 set turn 0.2` or `0.5`.
5. Hold E, then C: the height changes smoothly; the camera pulls back and looks
   down more the higher you are. Menu > High: you rise to about 40 m.
6. Glide at Low towards a house or a tree: you rise over it without touching it,
   slowing down if it is tall. Over a forest or a town your height should stay
   steady, not dip between the trees and roofs.
7. Cross a region border at Cruise, then at Fast (`/8 fast`): you keep going.
   Tell me if there is any jump or stop at the border.
8. Over the sea: hold C until you settle on the water (`SURFACE`). Your feet
   should be just above the water, bobbing on the waves. Go towards a beach: you
   rise over the land and come back down on the water after it.
9. On the water, tap C: you dive about 2.5 m under. The camera stays under the
   surface. Swim around, hold C to go deeper (you stop above the bottom), try
   mouselook and look down while holding W. Hold E: you come back up.
10. Tap E on the water: back into the air. Tap the HUD: you land gently and
    everything is released (the camera is yours again, walking works).
11. Try a ban line or the edge of a region with no neighbour: you are stopped
    gently and told why.
12. Teleport while gliding, sit on something while gliding: Wind switches off and
    says so.
13. If you use an animation overrider, glide with it on: does your Wind
    animation stay on top? (If not: priority, see Your animations.)

## Assumptions to check in-world

- `llMoveToTarget` from a HUD moves the avatar smoothly at 10 updates a second,
  with `follow = 0.35`. The `/8 numbers` speed line tells whether the speeds
  match: if the avatar is slower than the guide, lower `follow`.
- `llGround` and `llWater` called from a HUD measure from the avatar (as
  `llGetPos` does in a HUD's root prim).
- An airborne avatar that is not flying shows the "Falling Down" animation
  state; a looped priority 4 animation covers it. The Animator restarts yours
  when the state changes, so an AO does not take over for long.
- Scripts that have taken controls keep running on no-script land (the usual
  Second Life rule), so the Engine and Levels keep working there.
- `llGetNotecardLineSync` is available (it is since 2024); if the region drops
  the notecard from memory, Wind falls back to reading line by line.
- Sounds looped from a HUD are heard only by the wearer.

## Known limits

- Water made of objects (pools, lakes on mountains or in skyboxes) is not water
  to Wind: Surface and Dive work on Second Life's own water.
- Wind is for the open air: indoors it climbs into ceilings.
- Turning uses Second Life's own turn speed (A/D). A smoother, banking turn
  needs `llSetAgentRot`, which today does not turn hovering avatars reliably.
- Ban lines and invisible walls cannot be seen by rays; Wind notices when it is
  blocked and stops pushing.
