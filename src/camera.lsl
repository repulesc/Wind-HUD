// ---------------------------------------------------------------------
// WIND - CAMERA
// A follow camera for each level: further back and higher the higher you
// glide, low over the water on the surface, and close behind you under
// the water. When diving it keeps the camera below the surface, so you
// see the underwater world instead of the surface from above.
// Setting "camera = 0" leaves the camera to you.
// ---------------------------------------------------------------------
// @include common

integer on = TRUE;         // setting "camera"
float   zoom = 1.0;        // setting "cam_zoom"
float   lag_s = 0.12;      // setting "cam_lag"
integer mine;              // our camera is in use
string  applied;           // the camera we set last

Load() {
    on = (integer)Cfg("camera");
    zoom = Cfg("cam_zoom");
    lag_s = Cfg("cam_lag");
}

Release() {
    applied = "";
    if (mine) if (llGetPermissions() & PERMISSION_CONTROL_CAMERA) llClearCameraParams();
    mine = FALSE;
}

// How far the camera may tilt down behind you and stay under the water.
float DivePitch(float dist) {
    vector p = llList2Vector(llGetObjectDetails(llGetOwner(), [OBJECT_POS]), 0);
    float room = (llWater(ZERO_VECTOR) - 0.5) - (p.z + 0.3);
    float s = room / dist;
    if (s > 0.14) s = 0.14;            // about 8 degrees
    else if (s < -0.42) s = -0.42;     // about -25 degrees
    return (float)llRound(llAsin(s) * RAD_TO_DEG);
}

Apply() {
    if (!Field(S_ACTIVE) || !on) {
        Release();
        return;
    }
    if (!(llGetPermissions() & PERMISSION_CONTROL_CAMERA)) {
        llRequestPermissions(llGetOwner(), PERMISSION_CONTROL_CAMERA);
        return;
    }
    integer lv = Field(S_LEVEL);
    float dist = 5.0;
    float pitch = 10.0;
    vector focus = <2.0, 0.0, 0.5>;
    if (lv == L_DIVE) {
        dist = 3.2;
        focus = <1.0, 0.0, 0.3>;
    } else if (lv == L_SURFACE && Field(S_WATER)) {
        dist = 4.5;
        pitch = 7.0;
        focus = <1.5, 0.0, 0.4>;
    } else if (lv == L_GLIDE) {
        // 2 m up: close behind; 42 m and more: far back and looking down
        float n = (Field(S_HEIGHT) - 2.0) / 40.0;
        if (n < 0.0) n = 0.0;
        if (n > 1.0) n = 1.0;
        dist = 5.0 + 4.0 * n;
        pitch = 10.0 + 22.0 * n;
    }
    if (Field(S_BOOST)) dist += 1.5;
    dist = dist * zoom;
    if (dist > 10.0) dist = 10.0;
    if (lv == L_DIVE) pitch = DivePitch(dist);
    string now = llDumpList2String([lv, dist, pitch, focus, lag_s], "|");
    if (now == applied) return;
    applied = now;
    mine = TRUE;
    llSetCameraParams([
        CAMERA_ACTIVE, 1,
        CAMERA_DISTANCE, dist,
        CAMERA_PITCH, pitch,
        CAMERA_FOCUS_OFFSET, focus,
        CAMERA_POSITION_LAG, lag_s,
        CAMERA_FOCUS_LAG, lag_s * 0.5,
        CAMERA_BEHINDNESS_ANGLE, 20.0,
        CAMERA_BEHINDNESS_LAG, 0.25,
        CAMERA_POSITION_THRESHOLD, 0.0,
        CAMERA_FOCUS_THRESHOLD, 0.0
    ]);
}

default {
    state_entry() {
        Load();
        // a reset may have left our camera on: take it back and clear it
        if (llGetAttached()) llRequestPermissions(llGetOwner(), PERMISSION_CONTROL_CAMERA);
    }

    on_rez(integer p) {
        llResetScript();
    }

    changed(integer c) {
        if (c & CHANGED_OWNER) llResetScript();
    }

    run_time_permissions(integer perm) {
        if (!(perm & PERMISSION_CONTROL_CAMERA)) return;
        if (Field(S_ACTIVE)) Apply();
        else llClearCameraParams();
    }

    link_message(integer from, integer num, string str, key id) {
        if (num == EVT_STATE) {
            status = llCSV2List(str);
            Apply();
            // under the water, keep checking the depth so the camera stays under too
            if (mine && Field(S_LEVEL) == L_DIVE) llSetTimerEvent(0.5);
            else llSetTimerEvent(0.0);
        }
        else if (num == EVT_SETTINGS) {
            Load();
            applied = "";
            Apply();
        }
        else if (num == MSG_MEMORY) Memory("Camera");
    }

    timer() {
        Apply();
    }
}
