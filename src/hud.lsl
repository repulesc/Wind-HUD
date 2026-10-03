// ---------------------------------------------------------------------
// WIND - HUD
// Touching the HUD, the menu, the status text above the HUD and the chat
// commands (/8 unless the settings say otherwise). It only asks; the
// Engine decides and tells everyone what happened (EVT_STATE), and that
// is what the text and the button glow show.
//
// Buttons are found by prim name (upper or lower case):
//   glide, surface, dive        go to that level (starts Wind if it is off)
//   up, down, low, mid, high    glide height
//   speed                       next speed: Gentle, Cruise, Fast
//   menu                        the menu
//   help                        the user manual
//   power, or any other name    start / land
// Holding any button for a moment opens the menu. A HUD of one single
// prim works too: tap to start and land, hold for the menu.
// ---------------------------------------------------------------------
// @include common

integer chan;              // chat command channel
integer chat_h;
integer menu_chan;
integer menu_h;
float   menu_t;            // when the menu was opened (its listener expires)
integer reopen;            // after a choice, show again: 1 the menu, 2 the options
float   touch_t;
integer touch_link;
integer text_on = TRUE;
integer cam_on = TRUE;
integer snd_on = TRUE;
integer debug;
string  dbg_levels;        // the latest live numbers (see Numbers)
string  dbg_engine;
string  shown;             // the text above the HUD now
string  lit;               // which buttons glow now
integer greeted;           // welcome checked since the last reset
list    glows;             // stride 2: link number, what it lights up for

Load() {
    text_on = (integer)Cfg("hud_text");
    cam_on = (integer)Cfg("camera");
    snd_on = (integer)Cfg("sound");
    integer c = (integer)Cfg("channel");
    if (c != chan || !chat_h) {
        chan = c;
        llListenRemove(chat_h);
        chat_h = llListen(chan, "", llGetOwner(), "");
    }
}

FindButtons() {
    glows = [];
    lit = "";
    integer n = llGetNumberOfPrims();
    if (n < 2) return;
    integer i;
    for (i = 1; i <= n; ++i) {
        string name = llToLower(llStringTrim(llGetLinkName(i), STRING_TRIM));
        if (llListFindList(["power", "glide", "surface", "dive"], [name]) != -1) glows += [i, name];
    }
}

// The power button glows while Wind is on, and the level you are in.
Highlight() {
    string now = (string)Field(S_ACTIVE) + (string)Field(S_LEVEL);
    if (now == lit) return;
    lit = now;
    integer i;
    for (i = 0; i < llGetListLength(glows); i += 2) {
        string what = llList2String(glows, i + 1);
        float g;
        if (Field(S_ACTIVE)) {
            if (what == "power") g = 0.1;
            else if (what == llToLower(llList2String(LEVEL_NAMES, Field(S_LEVEL)))) g = 0.2;
        }
        llSetLinkPrimitiveParamsFast(llList2Integer(glows, i), [PRIM_GLOW, ALL_SIDES, g]);
    }
}

ShowText() {
    string t = "";
    vector col = <0.8, 0.95, 1.0>;
    if (debug && Field(S_ACTIVE) && dbg_levels != "") {
        t = Numbers();
        col = <1.0, 0.9, 0.5>;
    } else if (text_on && Field(S_ACTIVE)) {
        integer lv = Field(S_LEVEL);
        t = llToUpper(llList2String(LEVEL_NAMES, lv));
        if (lv == L_GLIDE) t += "  " + (string)Field(S_HEIGHT) + " m";
        t += "  ·  " + llList2String(GEAR_NAMES, Field(S_GEAR));
        if (Field(S_BOOST)) t += "  ·  BOOST";
        if (Field(S_LANDING)) t = "landing...";
    }
    if (t == shown) return;
    shown = t;
    llSetText(t, col, 1.0);
}

// The live numbers from the Levels script (EVT_DEBUG_LEVELS) and the
// Engine (EVT_DEBUG), in words.
string Numbers() {
    list d = llCSV2List(dbg_levels);
    list e = llCSV2List(dbg_engine);
    integer lv = llList2Integer(d, 0);
    string t = llList2String(LEVEL_NAMES, lv) + ": feet " + Fmt(llList2Float(d, 1)) + " m above the ";
    if (llList2Integer(d, 2)) t += "water";
    else t += "ground";
    if (lv == L_DIVE) t = "Dive: " + Fmt(llList2Float(d, 3)) + " m deep, " + Fmt(llList2Float(d, 4)) + " m above the bottom";
    if (llList2Float(d, 5) > 0.0) t += ", wall " + Fmt(llList2Float(d, 5)) + " m";
    t += "\nspeed " + Fmt(llList2Float(e, 0)) + " of " + Fmt(llList2Float(e, 1)) + " m/s, guide " + Fmt(llList2Float(e, 2)) + " m ahead";
    if (llList2Integer(e, 3)) t += ", BLOCKED";
    return t;
}

string Line() {
    string gear = llList2String(GEAR_NAMES, Field(S_GEAR));
    if (!Field(S_ACTIVE)) return "Off.  Speed: " + gear + ".";
    string t = llList2String(LEVEL_NAMES, Field(S_LEVEL));
    if (Field(S_LEVEL) == L_GLIDE) t += " at " + (string)Field(S_HEIGHT) + " m";
    return "Now: " + t + ",  " + gear + ".";
}

string OnOff(string name, integer on) {
    if (on) return name + ": on";
    return name + ": off";
}

Dialog(string text, list buttons) {
    llListenRemove(menu_h);
    menu_chan = -1 - (integer)llFrand(2000000000.0);
    menu_h = llListen(menu_chan, "", llGetOwner(), "");
    llDialog(llGetOwner(), text, buttons, menu_chan);
    menu_t = llGetTime();
    llSetTimerEvent(5.0);
}

Menu() {
    string go = "Start";
    if (Field(S_ACTIVE)) go = "Land";
    Dialog("Wind " + VERSION + "\n" + Line() + "\n\nGlide: through the air.  Surface: on the water.  Dive: under it.\nLow / Mid / High: how high you glide.\nGentle / Cruise / Fast: how fast you go.",
        [go, "Options", "Close", "Gentle", "Cruise", "Fast", "Low", "Mid", "High", "Glide", "Surface", "Dive"]);
}

Options() {
    Dialog("Wind options\n\nCamera: Wind moves your camera (off: your own camera).\nSound: Wind's sounds, if the HUD has any.\nText: the line above the HUD.\nNumbers: live height and speed, for testing.\nReload: read the settings notecard again.",
        ["Back", "Close", "Help", OnOff("Camera", cam_on), OnOff("Sound", snd_on), OnOff("Text", text_on), OnOff("Numbers", debug), "Memory", "Reload"]);
}

Help() {
    if (llGetInventoryType(MANUAL_NOTECARD) == INVENTORY_NOTECARD) llGiveInventory(llGetOwner(), MANUAL_NOTECARD);
    string c = "/" + (string)chan + " ";
    Say("Tap the HUD to rise, tap again to land. Hold the HUD for the menu.\n"
        + "W / S: forward and back.  A / D: turn.  Double-tap W and hold it: boost.\n"
        + "E / C: up and down. Keep holding C at the lowest glide to settle on the water (over land: to land). On the water, tap C to dive and E to rise again.\n"
        + "Chat: " + c + "glide, surface, dive, low, mid, high, gentle, cruise, fast, land, menu, numbers. Settings: " + c + "set name value, " + c + "settings, " + c + "reload.");
}

SetDebug(integer on) {
    debug = on;
    dbg_levels = "";
    dbg_engine = "";
    Send(CMD_DEBUG, (string)on);
    ShowText();
}

// A chat command, or a menu button (same words).
Command(string m) {
    list w = llParseString2List(llToLower(llStringTrim(m, STRING_TRIM)), [" "], []);
    string c = llList2String(w, 0);
    integer i = llListFindList(["glide", "surface", "dive"], [c]);
    if (i != -1) Send(CMD_LEVEL, (string)i);
    else if ((i = llListFindList(["gentle", "cruise", "fast"], [c])) != -1) Send(CMD_GEAR, (string)i);
    else if (llListFindList(["low", "mid", "high", "up", "down"], [c]) != -1) Send(CMD_HEIGHT, c);
    else if (c == "speed") Send(CMD_GEAR, "next");
    else if (c == "on" || c == "start") Send(CMD_START, "");
    else if (c == "off" || c == "land" || c == "stop") Send(CMD_STOP, "");
    else if (c == "halt") Send(CMD_HALT, "");
    else if (c == "menu") Menu();
    else if (c == "numbers" || c == "debug") SetDebug(!debug);
    else if (c == "memory") Send(MSG_MEMORY, "");
    else if (c == "help") Help();
    else if (llListFindList(["set", "get", "settings", "reload", "defaults"], [c]) != -1) Send(SET_COMMAND, llDumpList2String(w, " "));
    else Say("I do not know \"" + m + "\". Type /" + (string)chan + " help");
}

Choice(string m) {
    llListenRemove(menu_h);
    menu_h = 0;
    string w = llToLower(llStringTrim(llList2String(llParseString2List(m, [":"], []), 0), STRING_TRIM));
    if (w == "close") return;
    if (w == "options") Options();
    else if (w == "back") Menu();
    else if (w == "help" || w == "memory") Command(w);
    else if (w == "start" || w == "land") Command(w);
    else if (w == "camera" || w == "sound" || w == "text") {
        if (w == "text") w = "hud_text";
        Send(SET_COMMAND, "set " + w + " " + (string)(!(integer)Cfg(w)));
        reopen = 2;
    } else if (w == "numbers") {
        SetDebug(!debug);
        reopen = 2;
    } else if (w == "reload") Send(SET_COMMAND, "reload");
    else {
        Command(w);
        reopen = 1;
    }
    // show the menu again once the change has gone round
    if (reopen) llSetTimerEvent(0.4);
}

default {
    state_entry() {
        FindButtons();
        Load();
        ShowText();
    }

    on_rez(integer p) {
        llResetScript();
    }

    changed(integer c) {
        if (c & CHANGED_OWNER) llResetScript();
        if (c & CHANGED_LINK) FindButtons();
    }

    touch_start(integer n) {
        if (llDetectedKey(0) != llGetOwner()) return;
        touch_t = llGetTime();
        touch_link = llDetectedLinkNumber(0);
    }

    touch_end(integer n) {
        if (llDetectedKey(0) != llGetOwner()) return;
        if (llGetTime() - touch_t > 0.8) {
            Menu();
            return;
        }
        string name = llToLower(llStringTrim(llGetLinkName(touch_link), STRING_TRIM));
        integer i = llListFindList(["glide", "surface", "dive"], [name]);
        if (i != -1) Send(CMD_LEVEL, (string)i);
        else if (llListFindList(["up", "down", "low", "mid", "high"], [name]) != -1) Send(CMD_HEIGHT, name);
        else if (name == "speed") Send(CMD_GEAR, "next");
        else if (name == "menu") Menu();
        else if (name == "help") Help();
        else if (Field(S_ACTIVE)) Send(CMD_STOP, "");
        else Send(CMD_START, "");
    }

    listen(integer ch, string name, key id, string msg) {
        if (ch == menu_chan) Choice(msg);
        else Command(msg);
    }

    link_message(integer from, integer num, string str, key id) {
        if (num == EVT_STATE) {
            status = llCSV2List(str);
            ShowText();
            Highlight();
        }
        else if (num == EVT_DEBUG) {
            dbg_engine = str;
            if (debug) ShowText();
        }
        else if (num == EVT_DEBUG_LEVELS) {
            dbg_levels = str;
            if (debug) ShowText();
        }
        else if (num == EVT_SETTINGS) {
            Load();
            ShowText();
            if (!greeted) {
                // the first settings message after a reset: welcome a new owner once
                greeted = TRUE;
                if (llLinksetDataRead("st:welcomed") != (string)llGetOwner()) {
                    llLinksetDataWrite("st:welcomed", (string)llGetOwner());
                    Say("Welcome to Wind " + VERSION + "! Tap the HUD to rise into the air and explore. W to go, A / D to turn, E / C for up and down. Hold the HUD for the menu, or type /" + (string)chan + " help.");
                }
            }
        }
        else if (num == MSG_MEMORY) Memory("HUD");
    }

    timer() {
        if (reopen) {
            integer r = reopen;
            reopen = 0;
            if (r == 2) Options();
            else Menu();
            return;
        }
        if (menu_h) if (llGetTime() - menu_t > 120.0) {
            llListenRemove(menu_h);
            menu_h = 0;
        }
        if (!menu_h) llSetTimerEvent(0.0);
    }
}
