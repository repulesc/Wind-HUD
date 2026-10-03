# Changelog

## 0.1.0 - complete rewrite (alpha, not yet tested in-world)

Replaces the Gemini "Glide Suite" v1.4 prototype (kept in `prototype/`; see
`docs/Prototype_Review.md` for what was wrong with it).

**Moving**
- Smooth, lag-safe motion: an invisible guide point moves at the speed you ask
  for and `llMoveToTarget` pulls the avatar after it. Speeding up, turning,
  coasting and braking all ease in and out; if a script stalls you come to rest.
- Three speeds: Gentle 3.5, Cruise 8, Fast 16 m/s, plus boost (double-tap W and
  hold). The prototype always ended at 34 m/s.
- Crossing into the next region keeps you flying (the prototype switched off and
  dropped you). Stops gently at the edge of the world.
- Notices when something invisible (a ban line) blocks you and stops pushing.

**Three levels**
- Glide: a chosen height (Low 4, Mid 15, High 40 m, or anything with E/C) above
  the highest thing below and ahead: land, roofs, trees, water. Climbs over
  buildings and hills in time, slowing down if needed.
- Surface: skims the sea and rides its waves; just above the land elsewhere.
- Dive: under the water, between the bottom and the surface; in mouselook you
  swim where you look.
- E/C move through the levels; landing is gentle (on land, a roof or the water).

**Look and feel**
- Your own animations per level (moving and idle), with sensible fallbacks.
- A camera per level: further back and higher the higher you glide, low over
  the water, under the surface when diving.
- Optional sounds per level and a splash.

**Using it**
- Tap to start and land, hold for the menu; buttons found by prim name; `/8`
  chat commands; status text above the HUD; welcome and user manual.
- Every feel and height number in the Wind Settings notecard; `/8 set` to try
  values live; settings and your choices reset for a new owner.

**Under the hood**
- Six scripts sharing `src/common.lsl`; `tools/build.py` builds and strictly
  checks them; each stays under the size that crashed Sentinel.
- `tests/`: the real scripts run in a simulated Second Life, 37 scenarios, and
  a side-by-side comparison with the prototype.
