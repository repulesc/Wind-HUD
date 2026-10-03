// ---------------------------------------------------------------------
// Shared definitions. tools/build.py copies into each Wind script only
// the parts that script uses (Second Life counts code against each
// script's memory). Edit here, then rebuild. Never edit a built script.
//
// Rules for this file, so the build tool can read it:
//   - a global variable is ONE line:  type NAME = value;
//     except a list, which may start with "list NAME = [" on its own
//     line and end with a line ending in "];"
//   - a function starts at column 0 and ends with a lone "}" at column 0.
// ---------------------------------------------------------------------

string VERSION = "0.1.0";
string MANUAL_NOTECARD = "Wind - User Manual";
string SETTINGS_NOTECARD = "Wind Settings";

// ---- Levels -------------------------------------------------------------
integer L_GLIDE   = 0;   // above the ground
integer L_SURFACE = 1;   // on the water (just above the land where there is none)
integer L_DIVE    = 2;   // under the water
list LEVEL_NAMES = ["Glide", "Surface", "Dive"];
list GEAR_NAMES  = ["Gentle", "Cruise", "Fast"];

// ---- Link messages ------------------------------------------------------
// HUD -> Engine and Levels
integer CMD_START    = 7001;  // str = level number, "" = automatic
integer CMD_STOP     = 7002;  // land gently, then switch off (twice = at once)
integer CMD_HALT     = 7003;  // switch off right now (Levels sends it when landed)
integer CMD_LEVEL    = 7004;  // str = level number (starts Wind if it is off)
integer CMD_HEIGHT   = 7005;  // str = "low" "mid" "high" "up" "down" (starts Wind in Glide if off)
integer CMD_GEAR     = 7006;  // str = gear number, or "next"
integer CMD_DEBUG    = 7007;  // str = "1" live numbers on, "0" off
// Engine -> everyone
integer EVT_STATE    = 7100;  // str = the S_* fields joined with ","
// EVT_DEBUG: the Engine's live numbers, comma separated:
// speed, guide speed, guide distance, blocked (1/0)
integer EVT_DEBUG    = 7101;
// EVT_DEBUG_LEVELS: the Levels script's live numbers, comma separated:
// level, feet above what is below, water below (1/0), depth,
// feet above the bottom, wall distance (0 = none)
integer EVT_DEBUG_LEVELS = 7102;
// Levels -> everyone
integer EVT_SPLASH   = 7103;  // str = "in" or "out" of the water
// EVT_AIM: Levels -> Engine, ten times a second while on, comma separated:
// height to hold (region z of the avatar centre), how far ahead something
// is in the way (0 = nothing), level, water below (1/0), glide height,
// landing (1/0)
integer EVT_AIM      = 7104;
// Config <-> everyone
integer EVT_SETTINGS = 7200;  // settings changed: read them again
integer SET_COMMAND  = 7201;  // HUD -> Config: str = "set name value", "get name", "settings", "reload", "defaults"
integer MSG_MEMORY   = 7300;  // everyone: say how much memory you use

// ---- EVT_STATE fields ---------------------------------------------------
integer S_ACTIVE  = 0;  // 1 while Wind is on
integer S_LEVEL   = 1;  // L_*
integer S_MOVING  = 2;  // 1 while travelling
integer S_WATER   = 3;  // Glide/Surface: water is what is below you. Dive: always 1
integer S_HEIGHT  = 4;  // Glide height setting, whole metres
integer S_GEAR    = 5;  // 0 Gentle, 1 Cruise, 2 Fast
integer S_BOOST   = 6;  // 1 while boosting (double-tap W and hold)
integer S_LANDING = 7;  // 1 while landing
integer S_SPEED   = 8;  // 0..5, how fast compared with the Fast gear

// The last EVT_STATE, for the scripts that listen to it.
list status = [];

// ---- Settings -----------------------------------------------------------
// name, default, lowest, highest. The "Wind Settings" notecard and
// "/8 set name value" override the default; docs/Wind_Settings.txt
// explains each one. Keep all numbers written as floats (1.0, not 1).
list CFG = [
    "speed_gentle",  3.5,  0.5,  40.0,
    "speed_cruise",  8.0,  0.5,  40.0,
    "speed_fast",   16.0,  0.5,  40.0,
    "boost",         1.8,  1.0,   3.0,
    "surface_speed", 0.8,  0.1,   2.0,
    "dive_speed",    0.5,  0.1,   2.0,
    "accel",         0.6,  0.05,  5.0,
    "turn",          0.3,  0.05,  5.0,
    "coast",         1.0,  0.05, 10.0,
    "brake",         0.35, 0.05,  5.0,
    "follow",        0.35, 0.05,  2.0,
    "height_low",    4.0,  1.0, 100.0,
    "height_mid",   15.0,  1.0, 100.0,
    "height_high",  40.0,  1.0, 100.0,
    "height_min",    2.0,  0.5,  20.0,
    "height_max",   80.0, 10.0, 300.0,
    "rise_speed",    4.0,  0.5,  20.0,
    "climb_rate",    6.0,  1.0,  30.0,
    "sink_rate",     2.5,  0.5,  20.0,
    "surface_ride",  0.15, -2.0,  2.0,
    "land_skim",     1.0,  0.3,   5.0,
    "dive_depth",    2.5,  1.0,  30.0,
    "bob",           1.0,  0.0,   3.0,
    "camera",        1.0,  0.0,   1.0,
    "cam_zoom",      1.0,  0.5,   2.0,
    "sound",         1.0,  0.0,   1.0,
    "volume",        0.6,  0.0,   1.0,
    "hud_text",      1.0,  0.0,   1.0,
    "channel",       8.0,  1.0, 99999.0
];

// ---- Helpers ------------------------------------------------------------
// A setting: the stored value if there is one, else the default.
float Cfg(string name) {
    string v = llLinksetDataRead("cfg:" + name);
    if (v != "") return (float)v;
    return llList2Float(CFG, llListFindList(CFG, [name]) + 1);
}

Send(integer num, string str) {
    llMessageLinked(LINK_SET, num, str, "");
}

Say(string msg) {
    llOwnerSay("Wind: " + msg);
}

// One field of the last EVT_STATE.
integer Field(integer i) {
    return llList2Integer(status, i);
}

// A number with up to two decimals: 8, 0.5, 0.15, -1.25
string Fmt(float x) {
    integer i = llRound(x * 100.0);
    string s = "";
    if (i < 0) {
        s = "-";
        i = -i;
    }
    s += (string)(i / 100);
    integer d = i % 100;
    if (d) {
        s += "." + (string)(d / 10);
        if (d % 10) s += (string)(d % 10);
    }
    return s;
}

Memory(string who) {
    Say(who + ": " + (string)(llGetUsedMemory() / 1024) + " KB used, " + (string)(llGetFreeMemory() / 1024) + " KB free");
}
