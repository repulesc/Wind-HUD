// ---------------------------------------------------------------------
// WIND - ENGINE
// Moves the avatar.
//
// How: an invisible guide point travels at the speed you ask for, at the
// height the Levels script asks for (EVT_AIM), and llMoveToTarget pulls
// the avatar smoothly after it. The region's physics does the pulling
// between our updates, so the ride stays smooth when scripts are slow,
// and if this script ever stalls you simply come to rest at the guide:
// nothing can fling you away. Gravity is off while Wind is on.
//
// Turning is left to the viewer (A/D or the arrow keys, the mouse in
// mouselook), so the avatar always faces where you steer.
//
// The Engine owns: switching on and off, W/A/S/D, speed and boost, the
// guide point, and noticing when something invisible blocks the way.
// ---------------------------------------------------------------------
// @include common

float TICK = 0.1;          // seconds between updates

// settings (EVT_SETTINGS reads them again)
list  speeds;              // Gentle, Cruise, Fast in m/s
float s_boost;
float s_surf;
float s_dive;
float s_accel;
float s_turn;
float s_coast;
float s_brake;
float s_follow;

key     owner;
integer active;
integer gear = 1;
integer boost;
integer debug;

// from the Levels script (EVT_AIM)
integer aimed;             // an aim has come since starting
float   aim_t;             // when the last one came
float   aim_z;             // height to hold
float   allow = -1.0;      // most speed allowed (-1 = any)
integer level;
integer wet;
float   height = 4.0;
integer landing;

// the guide point
vector  guide;             // x, y in global metres (region corner + local),
                           // so crossing into the next region does not move it
vector  vh;                // its velocity, m/s
vector  corner;            // corner of the region we are in
vector  last_g;            // last global position, to notice jumps
float   t_last;
float   start_t;
float   cross_t;           // last region crossing

// keys and status
integer held;
float   tap_t;             // last W press: two quick ones = boost
integer moving;
integer blocked;
float   slow_t;
string  sent;
float   sent_t;
float   dbg_t;
integer fly_told;

LoadSettings() {
    speeds = [Cfg("speed_gentle"), Cfg("speed_cruise"), Cfg("speed_fast")];
    s_boost = Cfg("boost");
    s_surf = Cfg("surface_speed");
    s_dive = Cfg("dive_speed");
    s_accel = Cfg("accel");
    s_turn = Cfg("turn");
    s_coast = Cfg("coast");
    s_brake = Cfg("brake");
    s_follow = Cfg("follow");
}

float Speed() {
    float sp = llList2Float(speeds, gear);
    if (level == L_SURFACE) sp = sp * s_surf;
    else if (level == L_DIVE) sp = sp * s_dive;
    if (boost) sp = sp * s_boost;
    return sp;
}

// At the edge of the world (no region beyond) do not push outwards.
Edges(vector pos) {
    vector p = guide - corner;
    if (p.x < 2.0 || p.x > 254.0) if (llEdgeOfWorld(pos, llVecNorm(<p.x - 128.0, 0.0, 0.0>))) {
        if (vh.x * (p.x - 128.0) > 0.0) vh.x = 0.0;
        p.x = 2.0 + 252.0 * (p.x > 128.0);
    }
    if (p.y < 2.0 || p.y > 254.0) if (llEdgeOfWorld(pos, llVecNorm(<0.0, p.y - 128.0, 0.0>))) {
        if (vh.y * (p.y - 128.0) > 0.0) vh.y = 0.0;
        p.y = 2.0 + 252.0 * (p.y > 128.0);
    }
    guide = p + corner;
}

// Tells the other scripts what is going on (only when something changed).
Report(integer at_once) {
    integer sp = llRound(llVecMag(vh) * 5.0 / llList2Float(speeds, 2));
    if (sp > 5) sp = 5;
    string s = llDumpList2String([active, level, moving, wet, llRound(height), gear, boost, landing, sp], ",");
    if (s == sent) return;
    float now = llGetTime();
    if (!at_once && now - sent_t < 0.25) return;
    sent = s;
    sent_t = now;
    Send(EVT_STATE, s);
}

Start() {
    if (active) return;
    owner = llGetOwner();
    if (llGetAgentInfo(owner) & AGENT_SITTING) {
        Say("Stand up first, then tap Wind again.");
        return;
    }
    llRequestPermissions(owner, PERMISSION_TAKE_CONTROLS);
}

// The keys are ours: lift off (as soon as the Levels script says how high).
Begin() {
    vector pos = llList2Vector(llGetObjectDetails(owner, [OBJECT_POS]), 0);
    corner = llGetRegionCorner();
    guide = pos + corner;
    last_g = guide;
    vh = ZERO_VECTOR;
    held = 0;
    boost = FALSE;
    blocked = FALSE;
    slow_t = 0.0;
    aimed = FALSE;
    allow = -1.0;
    landing = FALSE;
    t_last = llGetTime();
    start_t = t_last;
    cross_t = t_last;
    active = TRUE;
    llSetBuoyancy(1.0);
    llSetTimerEvent(TICK);
    Report(TRUE);
}

Halt() {
    llSetTimerEvent(0.0);
    llStopMoveToTarget();
    llSetBuoyancy(0.0);
    if (llGetPermissions() & PERMISSION_TAKE_CONTROLS) llReleaseControls();
    active = FALSE;
    aimed = FALSE;
    landing = FALSE;
    boost = FALSE;
    blocked = FALSE;
    moving = FALSE;
    held = 0;
    vh = ZERO_VECTOR;
    Report(TRUE);
}

SetGear(string how) {
    if (how == "next") gear = (gear + 1) % 3;
    else gear = (integer)how;
    if (gear < 0 || gear > 2) gear = 1;
    llLinksetDataWrite("st:gear", (string)gear);
    Report(TRUE);
}

Tick() {
    float now = llGetTime();
    float dt = now - t_last;
    t_last = now;
    if (dt > 0.3) dt = 0.3;      // after a stall, do not leap ahead
    list d = llGetObjectDetails(owner, [OBJECT_POS, OBJECT_ROT, OBJECT_VELOCITY]);
    if (d == []) return;
    vector pos = llList2Vector(d, 0);
    vector vel = llList2Vector(d, 2);
    integer info = llGetAgentInfo(owner);
    if (info & AGENT_SITTING) {
        Halt();
        Say("You sat down, so Wind switched off.");
        return;
    }
    if (info & AGENT_FLYING) {
        if (!fly_told) Say("Tip: switch Fly off. Wind carries you by itself, and glides more smoothly without it.");
        fly_told = TRUE;
    }
    // no word from the Levels script: it is missing, or has stopped
    if (now - aim_t > 3.0) if (now - start_t > 3.0) {
        Halt();
        Say("The \"Wind Levels\" script is not answering, so Wind switched off. Is it in the HUD and running?");
        return;
    }

    // a region crossing, or a jump we did not make (a sim hiccup)
    vector c = llGetRegionCorner();
    if (c != corner) {
        corner = c;
        cross_t = now;
    }
    vector g = pos + corner;
    if (llVecDist(g, last_g) > 20.0 + llVecMag(vel) * dt * 3.0) guide = g;
    last_g = g;
    if (!aimed) return;

    // ---- the keys -> the velocity you want
    vector fwd = llRot2Fwd(llList2Rot(d, 1));
    fwd.z = 0.0;
    fwd = llVecNorm(fwd);
    float f;
    float s;
    if (held & CONTROL_FWD) f += 1.0;
    if (held & CONTROL_BACK) f -= 0.5;         // backwards is slower
    if (held & CONTROL_LEFT) s += 0.7;         // sliding sideways too
    if (held & CONTROL_RIGHT) s -= 0.7;
    if (landing || blocked) {
        f = 0.0;
        s = 0.0;
    }
    vector want = fwd * f + <-fwd.y, fwd.x, 0.0> * s;
    if (llVecMag(want) > 1.0) want = llVecNorm(want);
    want = want * Speed();

    // ---- ease towards it: speeding up, turning and stopping all blend in
    float wm = llVecMag(want);
    float vm = llVecMag(vh);
    float tau = s_turn;
    if (wm < 0.01) tau = s_coast;
    else if (want * vh < 0.0) tau = s_brake;
    else if (wm > vm + 0.5) tau = s_accel;
    vh += (want - vh) * (dt / (tau + dt));
    vh.z = 0.0;
    vm = llVecMag(vh);
    // something in the way ahead: slower, so the Levels script can lift us over it
    if (allow >= 0.0) if (vm > allow) {
        vh = vh * (allow / vm);
        vm = allow;
    }

    // ---- move the guide; keep it near the avatar
    guide += vh * dt;
    Edges(pos);
    vector off = guide - g;
    off.z = 0.0;
    float leash = 3.0 + vm * 1.5;
    if (leash > 30.0) leash = 30.0;
    if (llVecMag(off) > leash) guide = g + llVecNorm(off) * leash;
    vector t = guide - corner;
    t.z = aim_z;
    // llMoveToTarget ignores a target more than 65 m away
    if (t.z > pos.z + 25.0) t.z = pos.z + 25.0;
    else if (t.z < pos.z - 25.0) t.z = pos.z - 25.0;
    llMoveToTarget(t, s_follow);

    // ---- stuck? (a ban line, an invisible wall, a region we may not enter)
    float got = llVecMag(<vel.x, vel.y, 0.0>);
    if (vm > 2.0 && got < vm * 0.25 && now - cross_t > 3.0) {
        if (slow_t == 0.0) slow_t = now;
        else if (now - slow_t > 1.5) {
            blocked = TRUE;
            slow_t = 0.0;
            vh = ZERO_VECTOR;
            guide = g;
            Say("Something you cannot see is in the way (a ban line or an invisible wall). Turn and try another way.");
        }
    } else slow_t = 0.0;

    // ---- tell the others
    if (vm > 0.8) moving = TRUE;
    else if (vm < 0.4) moving = FALSE;
    Report(FALSE);
    if (debug) if (now - dbg_t > 0.5) {
        dbg_t = now;
        Send(EVT_DEBUG, llList2CSV([got, vm, llVecMag(<t.x - pos.x, t.y - pos.y, 0.0>), blocked]));
    }
}

default {
    state_entry() {
        owner = llGetOwner();
        llStopMoveToTarget();
        llSetBuoyancy(0.0);
        LoadSettings();
        // the speed and height you chose last time
        string v = llLinksetDataRead("st:gear");
        if (v != "") gear = (integer)v;
        v = llLinksetDataRead("st:height");
        if (v != "") height = (float)v;
        Report(TRUE);
    }

    on_rez(integer p) {
        llResetScript();
    }

    attach(key id) {
        if (id == NULL_KEY) {
            llStopMoveToTarget();
            llSetBuoyancy(0.0);
        }
    }

    changed(integer c) {
        if (c & CHANGED_OWNER) llResetScript();
        if (c & CHANGED_TELEPORT) {
            if (active) {
                Halt();
                Say("Paused for the teleport. Tap the HUD to glide again.");
            }
        }
        else if (c & CHANGED_REGION) {
            corner = llGetRegionCorner();
            cross_t = llGetTime();
        }
    }

    run_time_permissions(integer perm) {
        if (active || !(perm & PERMISSION_TAKE_CONTROLS)) return;
        llTakeControls(CONTROL_FWD | CONTROL_BACK | CONTROL_LEFT | CONTROL_RIGHT, TRUE, FALSE);
        Begin();
    }

    control(key id, integer keys, integer edge) {
        integer now_down = keys & edge;
        if (now_down & CONTROL_FWD) {
            float now = llGetTime();
            if (now - tap_t < 0.35) boost = TRUE;
            tap_t = now;
        }
        if (!(keys & CONTROL_FWD)) boost = FALSE;
        if (now_down & (CONTROL_FWD | CONTROL_BACK | CONTROL_LEFT | CONTROL_RIGHT)) blocked = FALSE;
        held = keys;
    }

    timer() {
        if (active) Tick();
        else llSetTimerEvent(0.0);
    }

    link_message(integer from, integer num, string str, key id) {
        if (num == EVT_AIM) {
            if (!active) return;
            list a = llCSV2List(str);
            aim_z = llList2Float(a, 0);
            allow = llList2Float(a, 1);
            level = llList2Integer(a, 2);
            wet = llList2Integer(a, 3);
            height = llList2Float(a, 4);
            landing = llList2Integer(a, 5);
            aimed = TRUE;
            aim_t = llGetTime();
        }
        else if (num == CMD_START || num == CMD_LEVEL || num == CMD_HEIGHT) Start();
        else if (num == CMD_STOP) {
            if (active) if (landing) Halt();    // asked again while landing: now
        }
        else if (num == CMD_HALT) {
            if (active) Halt();
        }
        else if (num == CMD_GEAR) SetGear(str);
        else if (num == CMD_DEBUG) debug = (integer)str;
        else if (num == EVT_SETTINGS) LoadSettings();
        else if (num == MSG_MEMORY) Memory("Engine");
    }
}
