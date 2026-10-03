// ---------------------------------------------------------------------
// WIND - CONFIG
// Reads the "Wind Settings" notecard into the HUD's own memory
// (LinksetData, keys "cfg:<name>"), where the other scripts read it with
// Cfg(). Also answers /8 set, get, settings, reload and defaults.
// Only this script writes settings.
//
// The notecard is read when the HUD first starts for a new owner, when
// the notecard is saved (edited), and on /8 reload. Values from
// "/8 set" last until the notecard is read again.
// ---------------------------------------------------------------------
// @include common

key     query;
integer counting;          // the question was "how many lines" (it loads the notecard)
integer line;
integer good;
integer bad;
integer tell;              // say when done (a reload you asked for)

// The notecard as it is now, to notice edits ("none" if there is none).
string CardId() {
    if (llGetInventoryType(SETTINGS_NOTECARD) != INVENTORY_NOTECARD) return "none";
    return (string)llGetInventoryKey(SETTINGS_NOTECARD);
}

Load(integer say) {
    llLinksetDataDeleteFound("^cfg:", "");
    llLinksetDataDelete("st:card");      // until the whole notecard has been read
    tell = say;
    good = 0;
    bad = 0;
    line = 0;
    if (llGetInventoryType(SETTINGS_NOTECARD) != INVENTORY_NOTECARD) {
        Done();
        return;
    }
    // asking how many lines it has brings the notecard into the region's
    // memory; then Next() can read it all at once
    counting = TRUE;
    query = llGetNumberOfNotecardLines(SETTINGS_NOTECARD);
}

// Reads on for as long as the region has the notecard ready, then asks
// for the next line the slow way (one dataserver event per line).
Next() {
    while (TRUE) {
        string s = llGetNotecardLineSync(SETTINGS_NOTECARD, line);
        if (s == EOF) {
            Done();
            return;
        }
        if (s == NAK) {
            query = llGetNotecardLine(SETTINGS_NOTECARD, line);
            return;
        }
        Line(s);
        ++line;
    }
}

Done() {
    query = NULL_KEY;
    llLinksetDataWrite("st:card", CardId());
    Send(EVT_SETTINGS, "");
    if (tell || bad) {
        string m = "Settings: " + (string)good + " read from the notecard";
        if (bad) m += ", " + (string)bad + " line(s) skipped";
        Say(m + ".");
    }
}

integer Number(string s) {
    string c = llGetSubString(s, 0, 0);
    if (c == "-" || c == "+") {
        s = llDeleteSubString(s, 0, 0);
        c = llGetSubString(s, 0, 0);
    }
    if (c == ".") c = llGetSubString(s, 1, 1);
    if (c == "") return FALSE;
    return llSubStringIndex("0123456789", c) != -1;
}

// Checks and stores one setting. Returns "" or what is wrong.
string Store(string name, string value) {
    name = llToLower(name);
    integer i = llListFindList(CFG, [name]);
    if (i == -1) return "there is no setting called \"" + name + "\"";
    string v = llToLower(value);
    float f;
    if (v == "on" || v == "yes" || v == "true") f = 1.0;
    else if (v == "off" || v == "no" || v == "false") f = 0.0;
    else if (Number(v)) f = (float)v;
    else return name + ": \"" + value + "\" is not a number";
    float lo = llList2Float(CFG, i + 2);
    float hi = llList2Float(CFG, i + 3);
    if (f < lo || f > hi) return name + " must be from " + Fmt(lo) + " to " + Fmt(hi);
    llLinksetDataWrite("cfg:" + name, (string)f);
    return "";
}

// One notecard line: "name = value", with # starting a comment.
Line(string s) {
    integer c = llSubStringIndex(s, "#");
    if (c == 0) return;
    if (c > 0) s = llGetSubString(s, 0, c - 1);
    s = llStringTrim(s, STRING_TRIM);
    if (s == "") return;
    integer eq = llSubStringIndex(s, "=");
    string err = "it should look like: name = value";
    if (eq > 0) {
        string value = "";
        if (eq < llStringLength(s) - 1) value = llStringTrim(llGetSubString(s, eq + 1, -1), STRING_TRIM);
        err = Store(llStringTrim(llGetSubString(s, 0, eq - 1), STRING_TRIM), value);
    }
    if (err == "") ++good;
    else {
        ++bad;
        Say(SETTINGS_NOTECARD + " line " + (string)(line + 1) + ": " + err + " (skipped)");
    }
}

ListAll() {
    string out = "settings:";
    integer i;
    for (i = 0; i < llGetListLength(CFG); i += 4) {
        string name = llList2String(CFG, i);
        string one = "  " + name + " " + Fmt(Cfg(name));
        if (llLinksetDataRead("cfg:" + name) == "") one += "*";
        if (llStringLength(out + one) > 900) {
            Say(out);
            out = "";
        }
        out += one;
    }
    Say(out + "\n(* = default)");
}

Command(string m) {
    string c8 = "/" + (string)((integer)Cfg("channel")) + " ";
    list w = llParseString2List(m, [" "], []);
    string c = llList2String(w, 0);
    string name = llToLower(llList2String(w, 1));
    if (c == "set") {
        if (llGetListLength(w) < 3) {
            Say("Use: " + c8 + "set name value.  For example: " + c8 + "set speed_cruise 7");
            return;
        }
        string err = Store(name, llList2String(w, 2));
        if (err != "") {
            Say(err);
            return;
        }
        Say(name + " = " + Fmt(Cfg(name)) + "  (until the settings notecard is read again)");
        Send(EVT_SETTINGS, "");
    }
    else if (c == "get") {
        if (llListFindList(CFG, [name]) == -1) Say("there is no setting called \"" + name + "\"");
        else Say(name + " = " + Fmt(Cfg(name)));
    }
    else if (c == "settings") ListAll();
    else if (c == "reload") Load(TRUE);
    else if (c == "defaults") {
        llLinksetDataDeleteFound("^cfg:", "");
        Send(EVT_SETTINGS, "");
        Say("All settings are back to their defaults. " + c8 + "reload reads the notecard again.");
    }
}

default {
    state_entry() {
        string me = (string)llGetOwner();
        if (llLinksetDataRead("st:owner") != me) {
            // a new owner, or the very first start: nothing from before is kept
            llLinksetDataReset();
            llLinksetDataWrite("st:owner", me);
            Load(FALSE);
        }
        else if (llLinksetDataRead("st:card") != CardId()) Load(FALSE);
        else Done();
    }

    on_rez(integer p) {
        llResetScript();
    }

    changed(integer c) {
        if (c & CHANGED_OWNER) llResetScript();
        if (c & CHANGED_INVENTORY) {
            // read the notecard again if it was edited, added or removed
            string id = CardId();
            if (id != llLinksetDataRead("st:card") || id == (string)NULL_KEY) Load(TRUE);
        }
    }

    dataserver(key id, string data) {
        if (id != query) return;
        if (counting) counting = FALSE;
        else if (data == EOF) {
            Done();
            return;
        }
        else {
            Line(data);
            ++line;
        }
        Next();
    }

    link_message(integer from, integer num, string str, key id) {
        if (num == SET_COMMAND) Command(str);
        else if (num == MSG_MEMORY) Memory("Config");
    }
}
