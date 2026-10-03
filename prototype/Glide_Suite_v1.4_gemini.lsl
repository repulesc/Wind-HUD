// =========================================================================
// ARCHIVED PROTOTYPE - for reference only, do not put this in the HUD.
// This is the Gemini-made "Glide Suite" v1.4 that Wind replaces, kept so
// we can compare. See docs/Prototype_Review.md for what it did and why it
// was hard to steer. Only the stray markdown fences from the paste were
// removed; the code is unchanged.
// =========================================================================

// =========================================================================
// GLIDE SUITE - CORE ENGINE v1.4 (Permission-Safe Camera & Stable Flight)
// =========================================================================
integer is_active = FALSE;
integer altitude_mode = 0; // 0 = Low (12m), 1 = High (50m)
// Fizikai magasság és lebegési határok
float TARGET_ALT_LOW = 12.0;
float TARGET_ALT_HIGH = 50.0;
float KP = 2.4;
float KD = 1.2;
// Sebesség és dinamika (m/s)
float SPEED_CRUISE_BASE = 18.0;
float SPEED_MAX_TURBO = 34.0;
float SPEED_BRAKE = 2.5;
float current_cruise_speed = 18.0;
integer is_turbo_active = FALSE;
// Tapadási és fékezési együtthatók (Fizikai válaszidő)
float GRIP_ACTIVE_DRIVE = 3.4; // Feszes kanyarív sodródás nélkül
float GRIP_COAST_STOP = 2.8; // Organikus, gyors megállás elengedett gomboknál
float GRIP_HARD_BRAKE = 4.5; // Határozott légfék (C billentyű)
// Bemenetkezelés és időzítés
float current_target_z = 0.0;
vector current_input_move = <0.0, 0.0, 0.0>;
integer is_braking = FALSE;
// Dupla W (Turbó) detektor
float last_fwd_tap_time = 0.0;
// HUD kattintáskezelő számlálók
integer pending_clicks = 0;
integer click_timeout_ticks = 0;

safe_clear_camera()
{
    if (llGetPermissions() & PERMISSION_CONTROL_CAMERA)
    {
        llClearCameraParams();
    }
}

start_engine(integer start_mode)
{
    altitude_mode = start_mode;
    current_cruise_speed = SPEED_CRUISE_BASE;
    is_turbo_active = FALSE;
    // Kizárólag a mozgásvezérlést és a forgásérzékelést kérjük le
    llRequestPermissions(llGetOwner(), PERMISSION_TAKE_CONTROLS | PERMISSION_TRACK_CAMERA);
}

stop_engine()
{
    is_active = FALSE;
    pending_clicks = 0;
    click_timeout_ticks = 0;
    is_turbo_active = FALSE;
    current_cruise_speed = SPEED_CRUISE_BASE;

    llSetTimerEvent(0.0);
    llSetBuoyancy(0.0);
    safe_clear_camera();
    llReleaseControls();

    llMessageLinked(LINK_SET, 1000, "SET_STATE", "INACTIVE");
    llOwnerSay("[Glide]: Kikapcsolva. Hajtómű leállítva.");
}

toggle_altitude()
{
    altitude_mode = !altitude_mode;
    if (altitude_mode == 1)
    {
        llOwnerSay("[Glide]: Madártávlat mód (~50m).");
        llMessageLinked(LINK_SET, 1000, "SET_ALT_MODE", "HIGH");
    }
    else
    {
        llOwnerSay("[Glide]: Felszínközeli siklás (~12m).");
        llMessageLinked(LINK_SET, 1000, "SET_ALT_MODE", "LOW");
    }
}

default
{
    state_entry()
    {
        is_active = FALSE;
        pending_clicks = 0;
        click_timeout_ticks = 0;
        llSetBuoyancy(0.0);
        safe_clear_camera();
        llOwnerSay("[Glide Core v1.4]: Kész. Kamera engedélyvédve, natív nézőke aktív.");
    }

    on_rez(integer param) { llResetScript(); }
    changed(integer change) { if (change & (CHANGED_OWNER | CHANGED_REGION)) llResetScript(); }

    touch_start(integer total_number)
    {
        if (llDetectedKey(0) != llGetOwner()) return;

        pending_clicks++;
        if (pending_clicks == 1)
        {
            click_timeout_ticks = 3;
            llSetTimerEvent(0.1);
        }
        else if (pending_clicks >= 2)
        {
            pending_clicks = 0;
            click_timeout_ticks = 0;

            if (!is_active) start_engine(1);
            else toggle_altitude();
        }
    }

    run_time_permissions(integer perm)
    {
        if (perm & PERMISSION_TAKE_CONTROLS)
        {
            is_active = TRUE;
            // A forgásgombok (CONTROL_ROT_LEFT/RIGHT) nincsenek elfogva, a nézőke szabadon fordítja a testet
            llTakeControls(CONTROL_FWD | CONTROL_BACK | CONTROL_LEFT | CONTROL_RIGHT |
                           CONTROL_UP | CONTROL_DOWN, TRUE, FALSE);

            llSetBuoyancy(1.0); // Zéró gravitáció lebegéshez

            vector my_pos = llGetPos();
            float g_z = llGround(ZERO_VECTOR);
            float w_z = llWater(ZERO_VECTOR);
            float s_z = g_z; if (w_z > s_z) s_z = w_z;

            if (altitude_mode == 1)
                current_target_z = s_z + TARGET_ALT_HIGH;
            else
                current_target_z = s_z + TARGET_ALT_LOW;

            llMessageLinked(LINK_SET, 1000, "SET_STATE", "ACTIVE");
            llSetTimerEvent(0.1);

            if (altitude_mode == 1)
                llOwnerSay("[Glide]: Bekapcsolva. Madártávlat (~50m).");
            else
                llOwnerSay("[Glide]: Bekapcsolva. Felszínközeli siklás (~12m).");
        }
    }

    control(key id, integer level, integer edge)
    {
        if (!is_active) return;

        float now = llGetTime();
        integer pressed = level & edge;

        // Dupla W = Azonnali Turbó fokozat
        if (pressed & CONTROL_FWD)
        {
            if ((now - last_fwd_tap_time) < 0.35)
            {
                is_turbo_active = TRUE;
                current_cruise_speed = SPEED_MAX_TURBO;
            }
            last_fwd_tap_time = now;
        }

        // Előre gomb felengedésekor turbó leállítása
        if (!(level & CONTROL_FWD))
        {
            is_turbo_active = FALSE;
        }

        current_input_move = ZERO_VECTOR;
        is_braking = FALSE;

        // Légfék: C vagy Lefelé nyíl
        if (level & CONTROL_DOWN) is_braking = TRUE;

        // Horizontális mozgásbemenetek
        if (level & CONTROL_FWD)  current_input_move.x += 1.0;
        if (level & CONTROL_BACK) current_input_move.x -= 1.0;
        if (level & CONTROL_LEFT)  current_input_move.y += 1.0;
        if (level & CONTROL_RIGHT) current_input_move.y -= 1.0;
    }

    timer()
    {
        // 1. HUD kattintási szűrő (Szimpla be/ki kapcsolás)
        if (pending_clicks == 1)
        {
            click_timeout_ticks--;
            if (click_timeout_ticks <= 0)
            {
                pending_clicks = 0;
                if (!is_active)
                {
                    start_engine(0);
                    return;
                }
                else
                {
                    stop_engine();
                    return;
                }
            }
        }

        if (!is_active)
        {
            if (pending_clicks == 0) llSetTimerEvent(0.0);
            return;
        }

        // 2. Környezeti és forgási adatok lekérdezése
        vector pos = llGetPos();
        vector vel = llGetVel();
        float mass = llGetMass();
        float sim_time = llGetTime();
        key owner = llGetOwner();

        // Irányvektor kinyerése a nézőke által elforgatott testből
        rotation av_rot = llList2Rot(llGetObjectDetails(owner, [OBJECT_ROT]), 0);
        vector fwd_dir = <1.0, 0.0, 0.0> * av_rot;
        fwd_dir.z = 0.0;
        fwd_dir = llVecNorm(fwd_dir);

        vector side_dir = <-fwd_dir.y, fwd_dir.x, 0.0>;

        // Terep és vízszint referencia
        float ground_z = llGround(ZERO_VECTOR);
        float water_z = llWater(ZERO_VECTOR);
        float surface_z = ground_z;
        if (water_z > surface_z) surface_z = water_z;

        float target_h = TARGET_ALT_LOW;
        if (altitude_mode == 1) target_h = TARGET_ALT_HIGH;

        // 3. Sebességarányos Raycast akadályfelismerés
        float speed_xy = llVecMag(<vel.x, vel.y, 0.0>);
        float lookahead_dist = 4.5 + (speed_xy * 0.55);

        vector ray_start = pos + <0.0, 0.0, 0.5>;
        vector ray_end = ray_start + (fwd_dir * lookahead_dist);

        float obstacle_z = surface_z;
        list ray_results = llCastRay(ray_start, ray_end, [RC_REJECT_TYPES, RC_REJECT_AGENTS, RC_DATA_FLAGS, RC_GET_NORMAL]);
        if (llList2Integer(ray_results, -1) > 0)
        {
            vector hit_pos = llList2Vector(ray_results, 1);
            obstacle_z = hit_pos.z + 1.6; // Akadály feletti biztonsági magasság
        }

        if (obstacle_z > surface_z) surface_z = obstacle_z;
        float desired_raw_z = surface_z + target_h;

        // Aszimmetrikus szűrő
        if (desired_raw_z > current_target_z)
            current_target_z = desired_raw_z;
        else
            current_target_z = current_target_z + (desired_raw_z - current_target_z) * 0.12;

        // Lebegési hullámzás és vertikális erő
        float hover_osc = 0.04 * llSin(sim_time * 1.4);
        float active_z = current_target_z + hover_osc;

        float z_error = active_z - pos.z;
        float force_z = mass * ((z_error * KP) - (vel.z * KD));

        // 4. Horizontális tolóerő és tapadás
        vector target_vel_xy = ZERO_VECTOR;
        float effective_grip = GRIP_COAST_STOP;

        if (current_input_move != ZERO_VECTOR)
        {
            effective_grip = GRIP_ACTIVE_DRIVE;

            if (current_input_move.x > 0.0 && !is_turbo_active)
            {
                current_cruise_speed += 0.45;
                if (current_cruise_speed > SPEED_MAX_TURBO) current_cruise_speed = SPEED_MAX_TURBO;
            }

            float active_speed = current_cruise_speed;
            if (is_braking)
            {
                active_speed = SPEED_BRAKE;
                effective_grip = GRIP_HARD_BRAKE;
            }

            vector move_dir = (fwd_dir * current_input_move.x) + (side_dir * current_input_move.y);
            move_dir = llVecNorm(move_dir);
            target_vel_xy = move_dir * active_speed;
        }
        else
        {
            current_cruise_speed = SPEED_CRUISE_BASE;
            if (is_braking) effective_grip = GRIP_HARD_BRAKE;
        }

        vector vel_diff = target_vel_xy - <vel.x, vel.y, 0.0>;
        vector force_xy = mass * vel_diff * effective_grip;

        // 5. Egyesített fizikai impulzus leadása (10 Hz)
        vector total_impulse = <force_xy.x, force_xy.y, force_z> * 0.1;
        llApplyImpulse(total_impulse, FALSE);
    }
}
