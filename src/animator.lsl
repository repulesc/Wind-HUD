// ---------------------------------------------------------------------
// WIND - ANIMATOR
// Plays your own animations and sounds from the HUD's contents.
//
// Animations (all optional; use any you have, Wind falls back sensibly):
//   Wind Glide     Wind Glide Idle      moving / hovering in the air
//   Wind Surface   Wind Surface Idle    on the water
//   Wind Dive      Wind Dive Idle       under the water
// A missing Idle uses the moving one; a missing level uses Glide; with
// none of these names, the first animation in the HUD plays everywhere;
// with no animation at all, Second Life's upright "hover" pose.
//
// Sounds (optional, only you hear the loops):
//   Wind Glide Loop, Wind Surface Loop, Wind Dive Loop, Wind Splash
// ---------------------------------------------------------------------
// @include common

string  playing;           // our animation running now
string  avatar_state;      // the avatar's own animation state when we last looked
string  loop;              // our looping sound now
float   loop_vol;
integer sound_on = TRUE;
float   volume = 0.6;

Load() {
    sound_on = (integer)Cfg("sound");
    volume = Cfg("volume");
}

// The level whose animations and sounds fit: on the Surface level over
// land you hover like gliding.
integer Look() {
    integer lv = Field(S_LEVEL);
    if (lv == L_SURFACE && !Field(S_WATER)) lv = L_GLIDE;
    return lv;
}

string Pick() {
    string base = "Wind " + llList2String(LEVEL_NAMES, Look());
    list names = [base, "Wind Glide"];
    if (!Field(S_MOVING)) names = [base + " Idle", base, "Wind Glide Idle", "Wind Glide"];
    integer i;
    for (i = 0; i < llGetListLength(names); ++i) {
        string n = llList2String(names, i);
        if (llGetInventoryType(n) == INVENTORY_ANIMATION) return n;
    }
    if (llGetInventoryNumber(INVENTORY_ANIMATION) > 0) return llGetInventoryName(INVENTORY_ANIMATION, 0);
    return "hover";     // upright; Second Life's "fly" leans forward
}

Animate() {
    string want = "";
    if (Field(S_ACTIVE)) want = Pick();
    if (want == playing) return;
    if (!(llGetPermissions() & PERMISSION_TRIGGER_ANIMATION)) {
        if (want != "") llRequestPermissions(llGetOwner(), PERMISSION_TRIGGER_ANIMATION);
        return;
    }
    // start the new one before stopping the old, so there is no gap
    if (want != "") llStartAnimation(want);
    if (playing != "") llStopAnimation(playing);
    playing = want;
}

Sound() {
    string want = "";
    if (Field(S_ACTIVE) && sound_on) {
        string n = "Wind " + llList2String(LEVEL_NAMES, Look()) + " Loop";
        if (llGetInventoryType(n) == INVENTORY_SOUND) want = n;
    }
    // louder the faster you go
    float v = volume * (0.4 + 0.12 * Field(S_SPEED));
    if (want != loop) {
        if (want == "") llStopSound();
        else llLoopSound(want, v);
        loop = want;
        loop_vol = v;
    } else if (want != "") if (llFabs(v - loop_vol) > 0.05) {
        llAdjustSoundVolume(v);
        loop_vol = v;
    }
}

default {
    state_entry() {
        Load();
        llStopSound();
    }

    on_rez(integer p) {
        llResetScript();
    }

    attach(key id) {
        // taken off while on: a looped animation would keep playing without us
        if (id == NULL_KEY) if (playing != "") if (llGetPermissions() & PERMISSION_TRIGGER_ANIMATION) llStopAnimation(playing);
    }

    changed(integer c) {
        if (c & CHANGED_OWNER) llResetScript();
        if (c & CHANGED_INVENTORY) {
            // animations or sounds were added or removed: choose again
            if (playing != "") if (llGetPermissions() & PERMISSION_TRIGGER_ANIMATION) llStopAnimation(playing);
            playing = "";
            loop = "";
            Animate();
            Sound();
        }
    }

    run_time_permissions(integer perm) {
        if (perm & PERMISSION_TRIGGER_ANIMATION) Animate();
    }

    link_message(integer from, integer num, string str, key id) {
        if (num == EVT_STATE) {
            status = llCSV2List(str);
            Animate();
            Sound();
            // while on, look now and then whether the avatar's own animation
            // (or an AO) took over, and if so play ours again on top
            if (Field(S_ACTIVE)) llSetTimerEvent(1.0);
            else llSetTimerEvent(0.0);
        }
        else if (num == EVT_SPLASH) {
            if (sound_on) if (llGetInventoryType("Wind Splash") == INVENTORY_SOUND) llTriggerSound("Wind Splash", volume);
        }
        else if (num == EVT_SETTINGS) {
            Load();
            Sound();
        }
        else if (num == MSG_MEMORY) Memory("Animator");
    }

    timer() {
        string s = llGetAnimation(llGetOwner());
        if (s == avatar_state) return;
        avatar_state = s;
        if (playing != "") if (llGetPermissions() & PERMISSION_TRIGGER_ANIMATION) {
            llStopAnimation(playing);
            llStartAnimation(playing);
        }
    }
}
