# Wind: the road from alpha to a finished product

This is the plan for you, the inventor: the steps in order, what each one is
for and when it is done, the decisions that are yours to make, and ideas for
features. Wind's promise, in one line: **a very simple, very immersive way to
discover a region: the wind lifts you and carries you over the land, on the
sea and under it.** Every step and every feature is judged against that line.

## Where we are: v0.1 alpha

- The Gemini prototype is replaced by a complete rewrite: six scripts, three
  levels (Glide, Surface, Dive), smooth motion, your own animations, a camera
  per level, settings you can tune without touching code.
- It has passed 37 scenarios in a simulated Second Life, and it beats the
  prototype on every measure we compared (see `Prototype_Review.md`).
- **It has not flown in Second Life yet.** The simulator checks logic and
  safety; only you can judge the feel. That is step 1.

## The steps

### Step 1: First flight (you, one evening)

1. Build the HUD and install everything (README, "Making the HUD"). A single
   flat prim is enough for now; design comes later.
2. Go through the **first-flight checklist** in the README, somewhere with land,
   a town and the sea.
3. Send me: what differed from the checklist, the six `/8 memory` lines, two or
   three `/8 numbers` lines (gliding at Cruise, on the water, under it), and in
   your own words how each level *felt* (too fast, too floaty, jerky, too
   high...).

**Done when** every checklist item works, or we know why it does not.

### Step 2: Tune the feel (you and me, two or three short sessions)

The feel *is* the product, so this step matters most. Everything is in the
Wind Settings notecard, so no code changes are needed while tuning.

- Use the same short route every time: a region with open land, a town or
  forest, a coast and deep water.
- Change one thing at a time with `/8 set ...`, fly the route, keep it or put it
  back. Go in this order:
  1. speeds (`speed_gentle`, `speed_cruise`, `speed_fast`, `boost`)
  2. how it responds (`accel`, `turn`, `coast`, `brake`), then `follow`
  3. glide heights (`height_low/mid/high`), `climb_rate`, `sink_rate`
  4. the camera (`cam_zoom`), then the water (`surface_ride`, `dive_depth`, `bob`)
- Write down the values you like and send them to me: they become the new
  defaults. If a camera angle is wrong (not just its distance), describe it:
  the camera angles are in code.

**Done when** a friend who has never seen Wind can glide around a town, land
on the sea and dive, within two minutes and without help.

### Step 3: Your look and sound (you; me for any code)

- **Animations:** the six names in the README. At least `Wind Glide` (gliding),
  ideally an idle hover, a surface pose (skimming, or swimming at the surface)
  and a swim for Dive. Looped, priority 4, with soft ease-in/ease-out so the
  switches blend.
- **HUD design:** a small, clean button set (power, the three levels, speed,
  menu); the glow already shows which level you are in.
- **Sounds:** a soft wind loop, gentle waves, a muffled underwater hum, a splash.

**Done when** it looks and sounds like something you would buy.

### Step 4: Immersion features

Pick two or three from the feature ideas below. My suggestion for the first
round: the **trail effects**, the **scenic camera / photo mode** and the
**Wind Tour**. They are what makes people say "how do I get that?".

### Step 5: Beta test (5 to 10 people, one or two weeks)

Give copies to people with different setups:

- Firestorm and the official viewer; slow and fast computers
- tiny, normal and very tall avatars; mesh bodies; with and without an AO
- busy and laggy regions; mainland (ban lines!) and private islands;
  no-script and no-fly land
- people who never read manuals

Give them a short form: what you did, what happened, what you expected, and
the `/8 numbers` line. Fix, send a new version, repeat.

**Done when** a week passes with no "it broke" reports.

### Step 6: Launch

- **Permissions:** scripts no-modify (copy; transfer is your call). The Wind
  Settings notecard full-permission, so owners can tune and Wind can notice the
  edits. The manual no-modify.
- **The box:** the HUD, the manual notecard, a landmark to your store or a demo
  area.
- **Marketplace listing:** a short video (lift off over a town, skim to a beach,
  dive under a reef), three or four pictures, the feature list in plain words.
- **A demo:** a copy that switches off after a few minutes per wear (a small
  change I can make: a "demo" flag).
- **Updates:** keep version numbers (they are in the welcome message), and use
  Marketplace redelivery or a vendor system with updates.
- **Support:** a short FAQ notecard from what the beta testers asked.

### Step 7: After launch

Collect what people ask for, and release 1.1 and 1.2 with the most wanted
features. Keep the same habits: one change at a time, test, changelog.

## Decisions that are yours

1. **No-fly land.** Wind is not flying, so Second Life does not stop it where
   flying is switched off. Land owners chose that for a reason (role-play, privacy),
   and gliding in at 40 m can upset them; on the other hand, exploring no-fly
   regions is a big part of Wind's appeal. Options: ignore it (as now), warn
   only, or stay low there (Surface height) unless the owner switches that off.
   *My recommendation:* stay low and say so by default, with a setting to turn
   it off. Wind stays welcome everywhere, and it still works.
2. **Who hears Wind:** only you (now: looping sounds from a HUD reach only the
   wearer), or everyone nearby (needs the small body attachment from the
   trail-effects idea).
3. **The words:** "Glide / Surface / Dive", "Gentle / Cruise / Fast", chat
   channel 8. Change anything you like now, before people learn them.
4. **The defaults**, after tuning (step 2).
5. **Price, demo, and whether copies may be given away** (transfer permission).
6. **Name and branding:** "Wind" everywhere (the old "Glide Suite" name is gone
   from the code).

## Feature ideas

★ = the most magic for the effort. Effort: S small (an evening), M medium, L large.

### The magic: how it looks and sounds

- ★ **Trail effects others can see** (M). HUD particles only show on your own
  screen, so this is a tiny invisible body attachment the HUD talks to: soft
  wind streaks and sparkles behind you in the air, a wake and spray on the
  water, bubbles under it. It makes Wind visible and makes people ask.
- ★ **Sounds for each level** (S; the code is ready, it needs the sound files).
- **Banking into turns** (S): "Wind Glide Left/Right" animations, picked from
  your turn direction.
- **Take-off and touch-down animations** (S): a short lift and a soft landing.
- **Splash particles** when you dive in and come out (S, with the attachment).
- **An underwater light** (S, with the attachment) for dark depths.

### Exploring

- ★ **Scenic camera / photo mode** (M): when you stop, the camera slowly circles
  you or holds a postcard view; one button hides the HUD text for snapshots.
- ★ **Wind Tour** (M): "carry me around this region": a slow automatic loop
  along the coast or around the island, while you sit back and look. Later:
  "take me to the spot I am looking at".
- **Save a spot** (S): remember beautiful places (region and position), list
  them later, and open the map on one.
- **Follow a friend** (M): glide beside another avatar, or a whole group behind
  a leader.
- **Compass and readout** (S): heading, region name, height or depth on the HUD.
- **Thermals** (M): rising air near slopes and cliffs, so gliding feels alive.
- **Currents** under water (S): a gentle drift in the deep.

### Comfort and control

- ★ **Gamepad support** (M): Second Life can now pass a game controller to
  scripts. An analog stick for speed and direction and triggers for up and down
  would make Wind feel like a game, and would be the biggest single improvement
  to steering.
- **Gesture pack** (S): ready-made gestures binding F-keys to the levels,
  heights and speeds.
- **Pause the AO while gliding** (S): many animation overriders take a chat
  command to switch off and on.
- **Smoother turning** (S, later): when Linden Lab fixes `llSetAgentRot` for
  hovering avatars, Wind can turn you itself, smoothly.

### More water

- **Water made of objects** (M): lakes in skyboxes and on mountains, e.g. an
  owner-placed marker or a list of known water objects.

### Business

- **Demo mode** (S), **update notices** (S).
- **Wind Gates** (L, a second product): rings and markers region owners can
  place: a scenic route, a race through hoops. Owners get visitors; you sell
  more Wind HUDs.

## How we work together

- **One change at a time.** Try it in-world, then tell me what happened.
- **A good report:** what you did, what happened, what you expected, the
  `/8 numbers` line, and the version from the welcome message.
- **Never edit the `Wind *.lsl` files** in Second Life or here: they are made
  from `src/`. Tell me (or whoever works on it) what to change; we change
  `src/`, run `python3 tools/build.py --check` and `python3 tests/run_tests.py`,
  and give you new files to paste.
- **Every change gets a version and a line in `CHANGELOG.md`**, so you always
  know what is in the HUD you are wearing.
- **This repository is the one true copy.** If something only exists in
  Second Life, it does not exist.
