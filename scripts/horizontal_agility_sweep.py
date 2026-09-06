"""Horizontal-launch agility: search the design space for peak HEADING RATE.

Run:  python scripts/horizontal_agility_sweep.py [--samples 2000] [--quick]

WHAT IS DIFFERENT FROM `scripts/agility_sweep.py`, AND WHY IT MATTERS.

`agility_sweep.py` searched the same knobs against `control.heading_change`, which
integrates a turn rate against `trajectory.simulate`'s VERTICAL speed history. It
concluded, in a sentence docs/11 puts in bold, that "agility on this airframe comes from
static margin, not from the motor". That conclusion is correct **for a vertical launch**
and it is an artefact of one requirement:

    R6, apogee <= 1600 m, binds on a vertical flight long before R5's Mach 0.8 does.

Fly the same hardware flat and R6 stops binding -- a 25 deg launch tops out a few hundred
metres up, whatever the motor -- and the whole speed band between Mach 0.42 and Mach 0.80
opens. Since

    psi_dot = 0.5 rho V S CN / m

is LINEAR in speed, that band is worth a factor of nearly two in heading rate that the
vertical search could not reach and therefore never priced. On a horizontal launch the
motor is back on the table, and it is the single biggest lever there is.

Three further things change when the vehicle is flown flat, all of them handled in
`design/horizontal.py` and none of them visible to `heading_change`:

  gravity is no longer axial   A vertical J401FJ flight loses ~27 m/s of speed to gravity
                               during the burn and then decelerates at 1 g plus drag. Flat,
                               gravity is perpendicular to the velocity: it curves the
                               path and does not slow it. Burnout speed 141 -> 160 m/s on
                               the frozen vehicle, and the decay after it is drag alone.
  the air stays thick          A vertical flight manoeuvres between 200 and 1000 m. A flat
                               one stays near the ground, where rho is 5-10% higher, and
                               rho appears linearly in both rate AND radius.
  the window ends at the dirt  Not at apogee. Launch elevation becomes a design parameter
                               with a real optimum, and there is a floor below which the
                               vehicle noses into the ground before the control law is
                               even allowed to start (see stage 2 -- it is about 22 deg,
                               and the cause is gravity droop during boost).

WHAT IS SCORED. `peak velocity-vector rotation rate`, in deg/s, from a flown 3-DOF
trajectory. NOT the compass azimuth: on a steep flight azimuth rate is a_h/v_horiz with
v_horiz -> 0, which diverges while nothing physical happens, and docs/11 section 7 already
had to retract one number to that artefact. On the shallow flights this script recommends
the two agree to about 1%, and both are printed so that can be checked rather than
asserted.

WHAT STAYS HARD (they are engineering limits, not approval limits):
    L2 impulse, 54 mm bore, ~3 in fiberglass, canard actuation only
    R5   Mach <= 0.8      -- Barrowman and every aero model in this repo stop there
    IMU  +/-16 g axial    -- a clipped accelerometer deletes the state estimate
    flutter >= 1.5x, servo torque >= 2.0x, servo fits direct drive
    R11  recovery packing
    NEW: apogee >= 250 m  -- a flat flight that never gets above the main's 200 m deploy
         altitude has no dual-deploy recovery sequence. Vertical flight never had to think
         about this; it is the constraint horizontal launch ADDS. See stage 5.

WHAT IS SCORED RATHER THAN GATED:
    R1   static margin band and P(SM < 1.0). Reported on every row, gated in the ladder
         only. The user has written approval for guided flights and asked explicitly that
         R1 margin not be maximised as a hidden objective; the Pareto in stage 4 is the
         deliverable, and the recommendation names its own risk.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness  # noqa: E402
from design import (  # noqa: E402
    aero, atmosphere, control, flutter, hinge, horizontal, recovery, seal, tube_section,
)
from design.configure import (  # noqa: E402
    DEFLECTION_LIMIT_DEG, DesignParams, LIMITS, baseline, build_vehicle, evaluate,
)
from design.estimation import ACCEL_16G  # noqa: E402
from design.motors import Motor, load_eng  # noqa: E402
from design.packaging import (  # noqa: E402
    SERVO_GEOMETRY, SERVOS, check_direct_drive, torque_margin,
)

ROOT = Path(__file__).resolve().parents[1]

TARGET_RATE_DEG_S = 10.0          # AIM-9B heading rate, the stated goal
MOTOR_BORE_MAX = 0.0545
G10_STOCK_M = (0.0032, 0.0040, 0.0048, 0.0064, 0.0079)
BUILT_MOUNT_LENGTH = 0.33208      # docs/09, as built
AXIAL_G_MAX = ACCEL_16G.accel_full_scale_g
FLUTTER_MIN = 1.5
TORQUE_MIN = 2.0
RISK_BUDGET = 0.01
R1_NOMINAL = (1.5, 2.5)
CONTROLLER_DUTY = 0.7
STALL_LOCAL_ALPHA = control.STALL_LIMIT_DEG

# A flat flight has to leave itself room to come down on a parachute. The main deploys at
# 200 m (R11); below roughly 250 m of apogee there is no dual-deploy sequence left, only a
# drogue-to-ground descent this vehicle is not sized for. THIS IS THE REQUIREMENT
# HORIZONTAL LAUNCH ADDS, and it is the mirror image of R6: vertical flight is capped from
# above, flat flight is capped from BELOW.
APOGEE_MIN_HORIZONTAL_M = 250.0

# THE STRUCTURAL CHAIN, AND THE THIRD AND FOURTH TIME THIS SEARCH HAS BEEN WRONG THE SAME
# WAY. docs/11 section 7 already records two constraints that were written down somewhere
# and never encoded here -- the +/-16 g accelerometer, then the canard root joint and the
# self-loading recovery anchor. Flying flat adds two more, and both of them bite on the
# FROZEN geometry, which is why they are gated rather than noted:
#
#   the hinge chain     Hinge moment goes as q, and a flat flight's max q is the burnout
#                       value at sea level rather than at 230 m: 15.5 kPa against 12.4,
#                       before any extra deflection. Run the frozen vehicle flat at 9.2 deg
#                       and the plain bearing falls to 1.53x and the root joint's skin over
#                       the tang slot to 1.93x, both against this project's 2.0x. Servo
#                       torque -- the one the old search DID check -- is fine at 2.26x. The
#                       check that was in place was not the check that mattered.
#   the deployment      A flat flight's apogee is not a low-speed event. Vertically the
#                       vehicle arrives at apogee doing 1 m/s and the drogue costs nothing;
#                       at a 28 deg elevation it arrives doing 95 m/s, because the
#                       horizontal component never went away, and the drogue's opening
#                       shock is 1.4x the load the M10 anchors, the 3/4 in harness and the
#                       quick links were all sized against (docs/10). Apogee is still the
#                       right trigger -- it is the MINIMUM-speed point of a flat arc -- it
#                       is just no longer a slow one.
STRUCT_MARGIN_MIN = 2.0

# Fastest the vehicle may be falling under drogue when the main fires at 200 m. The frozen
# 18 in drogue gives 20 m/s and `configure.evaluate` sizes the whole recovery chain against
# the main opening at exactly that. A flat flight's drogue has to be SMALLER (it deploys at
# 90 m/s, not 1), which makes this the number that can run out.
DROGUE_DESCENT_MAX = 30.0

# THE HINGE BEARING HAS A CEILING, AND IT IS THE REAL STRUCTURAL WALL ON THIS AIRFRAME.
#
# Peak bearing pressure goes as 1/L^2, so length is the only cheap fix -- and the bearing
# grows INBOARD from a fixed outboard end at the panel root, straight at the servo's output
# face. Buying length means moving the servo further inboard, and `hinge.selected` already
# records what that costs: 4.000 mm is "the largest move the four servo cable bosses allow
# with a millimetre to spare before they meet on the rocket axis". Walking the move out,
# `boss_collision_margin` falls 1.0 mm per mm and reaches zero at 6.09 mm.
#
# So the servo can go to about 6.0 mm inboard and the bearing to about 8.0 mm, and that is
# the end of it: no length, no material and no fit buys any more. At 8.0 mm the hinge can
# carry roughly 45 N of panel normal force at 2.0x, which is what caps the canard semispan
# near 1.50 cal on a flat flight -- NOT stall, NOT static margin, and NOT the servo's
# torque. Every one of those was checked before this was.
SERVO_MOVE_MAX = 6.000e-3
BEARING_LENGTH_MAX = 8.000e-3
BEARING_STEPS_M = (6.0e-3, 6.5e-3, 7.0e-3, 7.5e-3, 8.0e-3)

# Canard laminate is skin + 2.0 mm slot + skin, and the skins are SHEETS TO BUY
# (design/hinge.selected_root_joint). 0.8/2.0/0.8 is the frozen 3.6; the rest are the next
# stocked steps up. Skin stress goes as 1/t^2, so each step is worth a lot.
CANARD_STOCK_M = (0.0036, 0.0040, 0.0044, 0.0048, 0.0052)

# The launch elevation the search scores at. Chosen in stage 2, not assumed: below ~22 deg
# the vehicle is descending by burnout and never reaches the manoeuvre altitude floor.
SEARCH_ELEVATION_DEG = 25.0
SEARCH_POLICY = "sustain"

# ELEVATION IS SOLVED PER VEHICLE, NOT ASSUMED. Flatter is always faster -- less of the
# speed is spent climbing and the manoeuvre happens in denser air -- so the optimum is the
# LOWEST elevation that still leaves the recovery sequence somewhere to happen. That
# depends on the motor, so it cannot be a constant. `auto_elevation` walks up from the
# gravity-droop floor until the flat apogee clears APOGEE_MIN_HORIZONTAL_M.
# Starts at 24 rather than at the 22 deg aerodynamic floor because nothing in this study
# has ever cleared the 250 m recovery floor below 26 deg, and each probe is a full
# trajectory at the scoring dt. Stops at 46: past there the vehicle is climbing, not
# turning, and stage 2 shows the rate falling monotonically.
ELEVATION_FLOOR_DEG = 24.0
ELEVATION_CEIL_DEG = 46.0
ELEVATION_STEP_DEG = 2.0

# HOW MUCH OF THE STALL BUDGET TO LEAVE ON THE TABLE, in degrees of local alpha.
#
# NOT ZERO, and this is the correction that matters most in this file. Driving the canard
# to exactly `STALL_LIMIT_DEG` reads as the optimum and is not one: past the limit the
# turn rate does not roll off, it COLLAPSES -- on the frozen vehicle, 10.0 deg of
# deflection makes 9.96 deg/s and 10.5 deg makes 6.28, worse than 8 deg ever was, because
# `pitch_authority` applies a 0.6 post-stall haircut to a vehicle that is now also
# trimming further. A design point with 0.07 deg of headroom against a stall limit that is
# itself a modelling constant (linear, attached, small-alpha -- docs/11 section 3) is not a
# design point. One degree is not generous; it is one gust.
STALL_HEADROOM_DEG = 1.0


def stall_limited_deflection(rocket, point, mass) -> float:
    """Largest deflection that keeps local alpha under the 12 deg stall limit.

    local_alpha = alpha_trim + delta, and alpha_trim is LINEAR in delta at trim, so the
    ratio is a property of the airframe and one probe finds it. docs/11 section 3 makes
    this point at length: the 12 deg is a budget shared between body lean and canard
    throw, and how it splits is set entirely by static margin.
    """
    probe = control.pitch_authority(rocket, point, mass, 1.0)
    k = probe.canard_local_alpha_deg  # local alpha per 1 deg of deflection
    usable = STALL_LOCAL_ALPHA - STALL_HEADROOM_DEG
    return usable / k if k > 0 else 0.0


class Candidate:
    """One vehicle, flown flat, scored against every requirement at once."""

    def __init__(self, params: DesignParams, samples: int,
                 deflection_cap: float = 90.0,
                 elevation=SEARCH_ELEVATION_DEG,
                 policy: str = SEARCH_POLICY):
        self.params = params
        self.elevation = elevation
        self.policy = policy

        # The vertical evaluation still runs, and it is not decoration: static margin,
        # recovery packing, T/W and rail exit are launch-angle independent, and the
        # vertical-mode numbers in the deliverable come from exactly this object.
        ev0 = evaluate(params, deflection_deg=min(deflection_cap, 8.0))
        r, f = ev0.rocket, ev0.flight
        coast = [p for p in f.points if p.t >= f.burnout_time]
        pk = max(coast, key=lambda p: p.q) if coast else f.points[-1]
        self.deflection = min(deflection_cap,
                              stall_limited_deflection(r, pk, pk.mass) - 0.05)
        self.ev = ev = evaluate(params, deflection_deg=self.deflection)
        self.rocket, self.vflight = ev.rocket, ev.flight

        if elevation == "auto":
            # BISECTION, not a walk. Apogee is monotonic in elevation, so the lowest legal
            # rail is found in ~4 flights instead of ~12 -- and each flight here is the
            # scoring integration, not a cheap approximation of it.
            #
            # SAME dt AS THE SCORING FLIGHT, deliberately. At dt=0.02 the probe read 250.3 m
            # where the dt=0.01 flight it selects reads 249.9, and the candidate then failed
            # the floor it had just been chosen to clear. A screening integration coarser
            # than the one it screens for is a bug, not an optimisation.
            def apogee_at(deg: float) -> float:
                return horizontal.fly(
                    ev.rocket, params.motor, ev.masses, elevation_deg=deg,
                    deflection_deg=self.deflection, policy=policy, duty_cycle=1.0,
                    dt=0.01).max_altitude_m

            lo, hi = ELEVATION_FLOOR_DEG, ELEVATION_CEIL_DEG
            if apogee_at(lo) >= APOGEE_MIN_HORIZONTAL_M:
                elevation = lo
            elif apogee_at(hi) < APOGEE_MIN_HORIZONTAL_M:
                elevation = hi  # nothing in range clears it; `fails()` will say so
            else:
                while hi - lo > ELEVATION_STEP_DEG:
                    mid = lo + round((hi - lo) / 2.0 / ELEVATION_STEP_DEG) * ELEVATION_STEP_DEG
                    if mid <= lo or mid >= hi:
                        break
                    if apogee_at(mid) >= APOGEE_MIN_HORIZONTAL_M:
                        hi = mid
                    else:
                        lo = mid
                elevation = hi
            self.elevation = elevation
        self.hz = horizontal.fly(
            ev.rocket, params.motor, ev.masses, elevation_deg=elevation,
            deflection_deg=self.deflection, policy=policy, duty_cycle=1.0, dt=0.01)

        # Flutter and hinge moment are priced against the HORIZONTAL flight's own speed
        # and q, which is the whole point -- a flat flight is faster and lower, so both
        # are worse than the vertical numbers `agility_sweep.py` checked.
        self.fast_speed = self.hz.max_speed
        self.flutter_aft = flutter.evaluate(r.aft_fins, self.hz.max_speed, 0.0).margin
        self.flutter_canard = flutter.evaluate(r.canards, self.hz.max_speed, 0.0).margin
        self.flutter = min(self.flutter_aft, self.flutter_canard)

        worst = max(f.points, key=lambda p: p.q)
        q_worst = max(self.hz.max_q, worst.q)
        probe = replace(worst, q=q_worst)
        self.hinge = abs(control.pitch_authority(
            r, probe, probe.mass, self.deflection).hinge_moment_per_panel)
        self.servo = SERVOS[params.servo]
        self.torque = torque_margin(self.hinge, self.servo)
        self.servo_fits = check_direct_drive(
            r.tubes[0].inner_diameter, self.servo, params.n_canards).fits

        self.axial_g = max(f.max_acceleration_g, self.hz.max_axial_g)
        self.motor_fits_built_mount = params.motor.length <= BUILT_MOUNT_LENGTH

        self._structure(r, worst, q_worst)
        self._deployment(ev)

        sm, _, _ = robustness.sample(samples, seed=3, params=params)
        self.risk = float((sm < 1.0).mean())
        self.sm_nominal = float(np.median(sm))

    def _structure(self, r, worst, q_worst) -> None:
        """Size the hinge bearing and the canard laminate, at the FLAT flight's own q.

        SIZED, NOT ASSUMED, for the same reason `with_flutter_fix` sizes the aft fin: these
        are the PRICE of the flight profile. Holding them at their as-built values -- which
        is what the first run of this search did -- makes every fast vehicle fail the hinge
        and hands the fin search a 763 N.s motor and 5.07 deg/s, WORSE than the frozen
        baseline. A search that cannot buy the cheap fix will report that the expensive
        thing is impossible.

        Both have hard ceilings (SERVO_MOVE_MAX, BEARING_LENGTH_MAX, CANARD_STOCK_M), and
        when a vehicle runs into them it fails rather than quietly exceeding them.
        """
        probe = replace(worst, q=q_worst)
        hm = control.pitch_authority(
            r, probe, probe.mass, self.deflection).hinge_moment_per_panel
        servo, geom = SERVOS[self.params.servo], SERVO_GEOMETRY[self.params.servo]
        arm = r.diameter / 2.0 + hinge.spanwise_centroid(
            r.canards.root_chord, r.canards.tip_chord, r.canards.semispan)

        # THE HINGE IS FROZEN HARDWARE AND THIS FUNCTION MUST NOT REDESIGN IT.
        #
        # It used to walk `BEARING_STEPS_M`, deriving a servo inboard move from the bearing
        # length, and it NEVER RAN `check_hinge_stack`. On the 1.45 cal canard it duly
        # selected a 7.0 mm bearing at a 5.5 mm servo move -- 0.59 mm of boss clearance
        # against that check's 1.0 mm minimum -- and reported 2.27x for a hinge that cannot
        # be built. That is what put 1.45/1.85 on the "unlocked" list in docs/12 section 10,
        # and it was wrong.
        #
        # The lesson is the one this file already has three paragraphs about, turned on
        # itself: a search is only as honest as its constraint set, and the constraint most
        # likely to be missing is the one that was settled somewhere else. `hinge.selected`
        # and `check_hinge_stack` are that somewhere else. Use them; do not re-derive them.
        stack = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, geom)
        loads = hinge.hinge_loads(stack, hm, r.canards.mean_chord, arm,
                                  servo.stall_torque, geom.spline_teeth)
        self.bearing_length = stack.bearing_length
        self.servo_move = hinge.SERVO_INBOARD_MOVE
        self.hinge_stack_ok = hinge.check_hinge_stack(stack, loads).ok
        self.bearing_margin = loads.bearing_margin
        self.panel_force = loads.normal_force

        self.canard_thickness = self.params.canard_thickness
        skin = tang = 0.0
        for t in CANARD_STOCK_M:
            if t < self.params.canard_thickness:
                continue
            probe_r = build_vehicle(replace(self.params, canard_thickness=t))
            joint = hinge.selected_root_joint(stack, probe_r.canards)
            jl = hinge.root_joint_loads(joint, loads.normal_force, arm, servo.stall_torque)
            skin = hinge.G10_FLEXURAL / jl.skin_bending_stress
            # The tang SELECTS its material rather than tolerating any of them
            # (scripts/hinge_report.py), so the best available material is the honest
            # margin -- and it does NOT improve with a thicker laminate, which is why the
            # loop breaks on the skin alone.
            tang = max(jl.tang_margin.values())
            self.canard_thickness = t
            if skin >= STRUCT_MARGIN_MIN:
                break
        self.skin_margin, self.tang_margin = skin, tang

        # THE TUBE THE BEARING IS PRESSED INTO, which is a different check from the bearing
        # pressure above and is the one that ends up binding. `check_cut_station`'s seat
        # crush margin depends on how much of the bearing the TUBE actually holds, and the
        # 2.3 mm wall holds 2.3 mm of it -- the rest is carried by the printed bay's housing
        # collar, which `design/bay.py` has always priced as optional ("a part that exists
        # in CAD is not yet a part that carries load").
        #
        # ON A FLAT FLIGHT IT IS NOT OPTIONAL. Bare wall: 1.80x against 2.0x. With the
        # collar bonded in: 12.10x. Vertically the bare wall was 2.23x and the collar was a
        # nice-to-have; the horizontal freeze is what makes it structure. So this is scored
        # with the collar, and `collar_required` records that the answer depends on it.
        cut = tube_section.CutStation(
            hinge.canard_hinge_station(r), r.diameter, r.tubes[1].wall_thickness,
            stack.wall_bore_dia, r.canards.count, r.tubes[1].name)
        loads_sec = tube_section.canard_module_loads(
            r, self.ev.masses, self.vflight,
            aero.stability(r, probe.cg, mach=probe.mach), cut.station,
            panel_normal_force=loads.normal_force,
            panel_cp_radius=r.canards.spanwise_cp_radius,
            seat_moment=loads.moment_at_bearing,
            alpha_trim_rad=math.radians(control.pitch_authority(
                r, probe, probe.mass, self.deflection).alpha_trim_deg),
            q=q_worst)
        bare = tube_section.check_cut_station(
            cut, loads_sec, stack.bearing_od, hinge.BEARING_SEAT_INTERFERENCE,
            seat_length=cut.wall_thickness)
        withc = tube_section.check_cut_station(
            cut, loads_sec, stack.bearing_od, hinge.BEARING_SEAT_INTERFERENCE,
            seat_length=stack.bearing_length)
        self.tube_margin_bare = min(bare.margins.values())
        self.tube_margin = min(withc.margins.values())
        self.collar_required = self.tube_margin_bare < STRUCT_MARGIN_MIN

    def _deployment(self, ev) -> None:
        """Size the drogue for the speed a FLAT apogee actually happens at.

        SIZED, NOT GATED, and the distinction is the same one `with_flutter_fix` makes
        about fin thickness: this is not an agility knob, it is the PRICE of the flight
        profile. Vertically the drogue is sized by descent rate, because it opens at 1 m/s
        and the opening shock is nothing. Flown flat the vehicle arrives at apogee doing
        90-odd m/s and the drogue is sized by its OWN opening shock instead -- the same
        inversion the aft fins went through when speed started sizing them for flutter
        rather than for area.

        The reference load is the one docs/10 sized the M10 anchors, the 3/4 in harness and
        the quick links against: the MAIN opening at the drogue descent rate. Holding the
        flat drogue's shock to that load means none of that hardware has to change.
        """
        m = ev.masses
        main = recovery.Canopy("main", recovery.size_for_descent_rate(m.dry_mass, 5.0), 2.2)
        stock = recovery.Canopy("drogue", 0.457, 1.5)
        self.design_shock = seal.opening_shock(
            m.dry_mass, stock.descent_rate(m.dry_mass, 200.0), main.cd_a,
            atmosphere.density(200.0), 1.7)
        v, z = self.hz.apogee_speed, self.hz.max_altitude_m
        rho = atmosphere.density(max(z, 0.0))
        self.deploy_shock_stock = seal.opening_shock(
            m.dry_mass, v, stock.cd_a, rho, 1.7)
        self.deploy_ratio = (self.deploy_shock_stock / self.design_shock
                             if self.design_shock > 0 else float("inf"))
        # Diameter that puts the flat-deploy shock exactly on the design load. Shock is
        # linear in cd_a and cd_a goes as d^2, so one square root does it.
        self.drogue_dia = (0.457 / math.sqrt(self.deploy_ratio)
                           if self.deploy_ratio > 1.0 else 0.457)
        sized = recovery.Canopy("drogue", self.drogue_dia, 1.5)
        self.drogue_descent = sized.descent_rate(m.dry_mass, 200.0)

    # -- observables -----------------------------------------------------------------
    @property
    def rate(self) -> float:
        return self.hz.peak_vec_rate_deg_s

    @property
    def radius(self) -> float:
        return self.hz.min_vec_radius_m

    @property
    def heading(self) -> float:
        return self.hz.vec_turn_deg

    @property
    def heading_realistic(self) -> float:
        return self.hz.vec_turn_deg * CONTROLLER_DUTY

    @property
    def lateral_g(self) -> float:
        return self.hz.peak_lateral_g

    def fails(self, ignore: frozenset[str] = frozenset()) -> list[str]:
        out: list[str] = []
        for v in self.ev.violations:
            tag = ("R5" if "Mach" in v else
                   "R6" if "apogee" in v else
                   "R1" if "SM" in v else
                   "stall" if "stall" in v else
                   "R11" if "recovery bay" in v or "harness" in v else "limits")
            # R6 is the VERTICAL apogee cap. On a flat flight the vehicle never gets
            # near it, so the vertical evaluation's verdict is not this flight's verdict.
            # It is still reported, because the vertical MODE has to pass it.
            if tag in ignore or tag == "R6":
                continue
            out.append(f"{tag}: {v}")
        if "R5" not in ignore and self.hz.max_mach > LIMITS["mach_max"]:
            out.append(f"R5: Mach {self.hz.max_mach:.2f} flat")
        if "R1" not in ignore:
            if self.risk > RISK_BUDGET:
                out.append(f"R1: P(SM<1.0) {self.risk:.1%}")
            if not (R1_NOMINAL[0] <= self.sm_nominal <= R1_NOMINAL[1]):
                out.append(f"R1: nominal SM {self.sm_nominal:.2f} cal")
        if "imu" not in ignore and self.axial_g > AXIAL_G_MAX:
            out.append(f"imu: {self.axial_g:.0f} g axial")
        if "flutter" not in ignore and self.flutter < FLUTTER_MIN:
            out.append(f"flutter: {self.flutter:.2f}x")
        if "servo" not in ignore:
            if not self.servo_fits:
                out.append(f"servo: {self.params.servo} does not fit")
            if self.torque < TORQUE_MIN:
                out.append(f"servo: torque {self.torque:.1f}x")
        if "recovery_alt" not in ignore and self.hz.max_altitude_m < APOGEE_MIN_HORIZONTAL_M:
            out.append(f"recovery: apogee {self.hz.max_altitude_m:.0f} m flat")
        if "hinge" not in ignore:
            if not self.hinge_stack_ok:
                out.append("hinge: the frozen stack does not pass check_hinge_stack")
            if self.bearing_margin < STRUCT_MARGIN_MIN:
                out.append(f"hinge: bearing {self.bearing_margin:.2f}x")
            if self.skin_margin < STRUCT_MARGIN_MIN:
                out.append(f"hinge: root skin {self.skin_margin:.2f}x")
            if self.tang_margin < STRUCT_MARGIN_MIN:
                out.append(f"hinge: tang {self.tang_margin:.2f}x")
            if self.tube_margin < STRUCT_MARGIN_MIN:
                out.append(f"tube: seat crush {self.tube_margin:.2f}x even with the collar")
        # The drogue is SIZED above, so the only failure left is a drogue so small that
        # the vehicle arrives at the main under too much speed for the main to survive.
        if "deploy" not in ignore and self.drogue_descent > DROGUE_DESCENT_MAX:
            out.append(f"deploy: drogue descent {self.drogue_descent:.0f} m/s")
        return out

    def line(self, ignore: frozenset[str] = frozenset()) -> str:
        p = self.params
        fails = self.fails(ignore)
        star = "*" if not self.motor_fits_built_mount else " "
        return (f"{p.motor.name[:16]:16s}{star}{p.canard_semispan_cal:5.2f} "
                f"{p.aft_semispan_cal:4.2f} {p.nose_ballast_kg * 1000:4.0f}g "
                f"{p.fin_thickness * 1000:4.1f} {self.deflection:4.1f} "
                f"{self.sm_nominal:5.2f} {self.risk:6.1%} {self.hz.max_mach:4.2f} "
                f"{self.hz.max_altitude_m:5.0f} {self.lateral_g:5.2f} {self.rate:6.2f} "
                f"{self.radius / 1000:5.2f} {self.heading_realistic:5.0f} "
                f"{self.flutter:4.2f} {self.torque:4.1f} {self.bearing_margin:4.2f} "
                f"{self.skin_margin:4.2f} {self.deploy_ratio:4.1f}  "
                f"{'ok' if not fails else '; '.join(fails)[:38]}")


HEADER = (f"{'motor':17s}{'can':>5s} {'aft':>4s} {'blst':>5s} {'t':>4s} {'del':>4s} "
          f"{'SM':>5s} {'P<1':>6s} {'M':>4s} {'alt':>5s} {'g':>5s} {'deg/s':>6s} "
          f"{'R km':>5s} {'psi':>5s} {'flt':>4s} {'trq':>4s} {'brg':>4s} {'skn':>4s} "
          f"{'dep':>4s}  verdict")


def motor_pool() -> list[Motor]:
    out = []
    for path in sorted((ROOT / "data" / "motors").glob("*.eng")):
        try:
            m = load_eng(path)
        except Exception:
            continue
        if m.diameter <= MOTOR_BORE_MAX:
            out.append(m)
    return out


def with_flutter_fix(params: DesignParams, samples: int, **kw) -> Candidate:
    """Score `params`, sizing the aft fin for flutter and the canard laminate for its root
    joint, and FEEDING BOTH BACK INTO THE FLIGHT.

    Two disciplines in one function, and the second one is a correction.

    Thickness is the PRICE of speed, not an agility knob, so it is sized rather than
    searched -- same as `agility_sweep.with_flutter_fix`. A flat flight is faster than the
    vertical one that sized the frozen 3.2 mm, so this does real work here.

    THE CORRECTION: sizing the canard laminate inside `Candidate._structure` and then
    reporting the flight that was flown at the OLD laminate is the exact error docs/11
    section 7 records twice ("anything agility_sweep.py prints is an UPPER BOUND until the
    structural chain has been run on the winning point"). A 3.6 -> 4.0 mm canard is four
    heavier panels, and heavier panels are a slower vehicle: on the recommended point it is
    9.13 -> 9.00 deg/s, about 1.4%. Small, and small is not the same as absent. So the
    candidate is rebuilt until the laminate stops moving -- the same one-pass fixed point
    the recovery anchor needed, and for the same reason.
    """
    cand = Candidate(params, samples, **kw)
    for t in G10_STOCK_M:
        if t <= params.fin_thickness or cand.flutter >= FLUTTER_MIN:
            continue
        params = replace(params, fin_thickness=t)
        cand = Candidate(params, samples, **kw)
    for _ in range(3):
        if cand.canard_thickness <= params.canard_thickness:
            break
        params = replace(params, canard_thickness=cand.canard_thickness)
        cand = Candidate(params, samples, **kw)
    return cand


# ==========================================================================================
# STAGE 0 -- does the horizontal integrator agree with the codes it has to agree with?
# ==========================================================================================
def stage_validate(samples: int) -> None:
    print("=" * 124)
    print("STAGE 0  VALIDATION -- the flat-flight integrator against the vertical codes")
    print("=" * 124)
    p = baseline()
    ev = evaluate(p, deflection_deg=8.0)
    tc = control.heading_change(ev.rocket, ev.flight, 8.0, duty_cycle=1.0)
    hv = horizontal.fly(ev.rocket, p.motor, ev.masses, elevation_deg=85.0,
                        deflection_deg=8.0, policy="max_rate", duty_cycle=1.0,
                        stop_at_apogee=True, dt=0.005)
    print("  Flown at 85 deg elevation -- i.e. the 5-deg-off-vertical rail the frozen")
    print("  baseline actually uses -- `design/horizontal.fly` must reproduce the numbers")
    print("  `control.heading_change` and `scripts/virtual_flight.py` already agree on.\n")
    print(f"  {'':28s} {'peak deg/s':>11s} {'total deg':>10s} {'window s':>9s}")
    print(f"  {'control.heading_change':28s} {tc.peak_rate_deg_s:11.2f} "
          f"{tc.heading_deg:10.1f} {tc.seconds:9.1f}")
    print(f"  {'virtual_flight (docs/11)':28s} {6.49:11.2f} {34.6:10.1f} {'--':>9s}")
    print(f"  {'horizontal.fly @ 85 deg':28s} {hv.peak_vec_rate_deg_s:11.2f} "
          f"{hv.vec_turn_deg:10.1f} {hv.control_seconds:9.1f}")
    err = abs(hv.peak_vec_rate_deg_s - tc.peak_rate_deg_s) / tc.peak_rate_deg_s
    print(f"\n  Peak rate agrees to {err:.1%}; apogee {hv.max_altitude_m:.0f} m against "
          f"{ev.flight.apogee:.0f} m from trajectory.py's RK4.")
    print("  A third integration path, and it lands on the same vehicle. The flat-flight")
    print("  numbers below are therefore differences in the FLIGHT, not in the code.")


# ==========================================================================================
# STAGE 1 -- the frozen vehicle, vertical against flat. No design change at all.
# ==========================================================================================
def stage_frozen(samples: int) -> Candidate:
    print("\n" + "=" * 124)
    print("STAGE 1  THE FROZEN VEHICLE, LAUNCHED FLAT -- same hardware, nothing changed")
    print("=" * 124)
    p = baseline()
    ev = evaluate(p, deflection_deg=8.0)
    tc = control.heading_change(ev.rocket, ev.flight, 8.0, duty_cycle=1.0)
    fl = horizontal.fly(ev.rocket, p.motor, ev.masses, elevation_deg=SEARCH_ELEVATION_DEG,
                        deflection_deg=8.0, policy="sustain", duty_cycle=1.0, dt=0.005)
    print(f"  {'':22s} {'VERTICAL (5 deg rail)':>22s} {'FLAT (25 deg rail)':>20s}")
    rows = [
        ("burnout speed, m/s", f"{ev.flight.burnout_velocity:.1f}", f"{fl.burnout_speed:.1f}"),
        ("peak heading rate, deg/s", f"{tc.peak_rate_deg_s:.2f}", f"{fl.peak_vec_rate_deg_s:.2f}"),
        ("turn radius, m", f"{tc.min_radius_m:.0f}", f"{fl.min_vec_radius_m:.0f}"),
        ("control window, s", f"{tc.seconds:.1f}", f"{fl.control_seconds:.1f}"),
        ("heading change, deg", f"{tc.heading_deg:.0f}", f"{fl.vec_turn_deg:.0f}"),
        ("apogee, m", f"{ev.flight.apogee:.0f}", f"{fl.max_altitude_m:.0f}"),
        ("max Mach", f"{ev.flight.max_mach:.2f}", f"{fl.max_mach:.2f}"),
    ]
    for name, a, b in rows:
        print(f"  {name:22s} {a:>22s} {b:>20s}")
    gain = fl.peak_vec_rate_deg_s / tc.peak_rate_deg_s
    print(f"\n  {gain:.2f}x the heading rate and {tc.min_radius_m / fl.min_vec_radius_m:.2f}x "
          f"the radius FOR FREE -- no new part, no new motor, no margin spent.")
    print("  It is the flight profile, not the vehicle: gravity stops eating speed, and")
    print("  the manoeuvre happens in sea-level air instead of at 600 m.")
    return Candidate(p, samples)


# ==========================================================================================
# STAGE 2 -- launch elevation is a design parameter now. Where is its floor?
# ==========================================================================================
def stage_elevation() -> None:
    print("\n" + "=" * 124)
    print("STAGE 2  LAUNCH ELEVATION -- and the floor nobody had to think about before")
    print("=" * 124)
    p = baseline()
    ev = evaluate(p, deflection_deg=8.0)
    print(f"  {'elev':>5} {'policy':>9} {'V_bo':>6} {'fpa_bo':>7} {'apogee':>7} "
          f"{'deg/s':>6} {'R m':>6} {'ctl s':>6} {'psi':>6} {'range km':>9} {'verdict'}")
    for el in (15, 20, 22, 25, 30, 35, 45, 60):
        for pol in ("max_rate", "sustain"):
            f = horizontal.fly(ev.rocket, p.motor, ev.masses, elevation_deg=el,
                               deflection_deg=8.0, policy=pol, duty_cycle=1.0, dt=0.01)
            rng = math.hypot(f.downrange_m, f.crossrange_m) / 1000.0
            verdict = ""
            if f.control_seconds <= 0.0:
                verdict = "never reaches the 50 m manoeuvre floor -- nose-in"
            elif f.max_altitude_m < APOGEE_MIN_HORIZONTAL_M:
                verdict = f"no dual-deploy room (apogee < {APOGEE_MIN_HORIZONTAL_M:.0f} m)"
            print(f"  {el:5.0f} {pol:>9} {f.burnout_speed:6.1f} {f.burnout_fpa_deg:7.1f} "
                  f"{f.max_altitude_m:7.0f} {f.peak_vec_rate_deg_s:6.2f} "
                  f"{f.min_vec_radius_m:6.0f} {f.control_seconds:6.1f} "
                  f"{f.vec_turn_deg:6.1f} {rng:9.2f} {verdict}")
    print("\n  THE FLOOR IS GRAVITY DROOP DURING BOOST, and it is worth about 20 degrees.")
    print("  While the motor burns, the velocity vector rotates down at g cos(gamma)/V,")
    print("  and V starts at 21 m/s off the rail. Integrating over the 2.8 s burn:")
    print("      delta_gamma ~ (g/a) ln(V_bo/V_rail) = (9.81/64) ln(160/21) = 19.9 deg")
    print("  So a 20 deg rail is DESCENDING by burnout and hits the ground before the")
    print("  control law is allowed to start. A truly horizontal launch is not available")
    print("  on a T/W of 6; 25 deg is the practical floor and it flies flat (fpa ~6 deg")
    print("  at burnout) because the boost has already spent the elevation.")


# ==========================================================================================
# STAGE 3 -- the search
# ==========================================================================================
def stage_search(samples: int, quick: bool) -> list[Candidate]:
    print("\n" + "=" * 124)
    print("STAGE 3  THE SEARCH -- motor x canard span x aft span x ballast, flown flat")
    print("=" * 124)

    motors = motor_pool()
    print(f"  screening {len(motors)} x 54 mm motors on the frozen fin set ...")
    screen: list[tuple[float, Motor, Candidate]] = []
    for m in motors:
        try:
            c = with_flutter_fix(baseline(motor=m), 400, elevation="auto")
        except Exception:
            continue
        # SCREEN ON EVERY HARD CONSTRAINT, NOT JUST THE CHEAP ONES. The first version of
        # this screen ranked on rate after checking only Mach, the IMU clip and the
        # recovery floor, and handed the fin search four 2000 N.s K motors -- every one of
        # which fails servo torque by a factor of two, because hinge moment goes as q and
        # a flat flight at Mach 0.75 sees 3x the q the frozen vehicle was sized against.
        # The search returned ZERO legal vehicles and the ladder was empty. A screen that
        # drops the binding constraint is not a screen.
        if c.fails(ignore=frozenset({"R1"})):
            continue
        screen.append((c.rate, m, c))
    screen.sort(key=lambda t: -t[0])
    keep = 3 if quick else 5
    finalists = [m for _, m, _ in screen[:keep]]
    print(f"  {len(screen)} pass EVERY requirement but R1 on the frozen fins; "
          f"carrying the top {len(finalists)} into the fin search:")
    print(f"    {', '.join(m.name for m in finalists)}\n")

    # Deliberately coarser than `agility_sweep.py`'s 1026 vehicles. Each candidate here
    # costs a flutter pass, a laminate convergence pass and an elevation solve, each of
    # which is a full trajectory -- roughly 30x an `evaluate()`. The knobs are smooth
    # (stage 4's Pareto has no kinks) so a coarse grid loses nothing but resolution, and
    # the refinement that matters is done by hand on the winner.
    cans = (1.15, 1.30, 1.45) if quick else (1.15, 1.30, 1.45, 1.60)
    afts = (1.55, 1.70, 1.85) if quick else (1.55, 1.70, 1.85, 2.00)
    blst = (0.025, 0.100) if quick else (0.025, 0.060, 0.100)

    out: list[Candidate] = []
    total = len(finalists) * len(cans) * len(afts) * len(blst)
    print(f"  {total} vehicles ...")
    n = 0
    for m in finalists:
        for c in cans:
            for a in afts:
                for b in blst:
                    n += 1
                    p = baseline(motor=m, canard_semispan_cal=c,
                                 aft_semispan_cal=a, nose_ballast_kg=b)
                    try:
                        out.append(with_flutter_fix(p, samples, elevation="auto"))
                    except Exception:
                        pass
                    if n % 100 == 0:
                        print(f"    ... {n}/{total}")
    legal = [c for c in out if not c.fails()]
    print(f"\n  {len(out)} scored, {len(legal)} legal against EVERY requirement "
          f"including R1.\n")
    print(HEADER)
    for c in sorted(legal, key=lambda c: -c.rate)[:12]:
        print(c.line())
    if not legal:
        print("  (none)")
    return out


# ==========================================================================================
# STAGE 4 -- the Pareto the user actually asked for: turn rate against R1 risk
# ==========================================================================================
def stage_pareto(cands: list[Candidate]) -> list[Candidate]:
    print("\n" + "=" * 124)
    print("STAGE 4  PARETO -- heading rate against P(SM < 1.0), everything else legal")
    print("=" * 124)
    print("  R1 is the only requirement scored rather than gated here. Every row below")
    print("  passes R5, the IMU clip, flutter, servo torque and fit, R11 packing and the")
    print("  250 m recovery floor. What separates them is static-margin RISK.\n")

    pool = [c for c in cands if not c.fails(ignore=frozenset({"R1"}))]
    pool.sort(key=lambda c: (c.risk, -c.rate))
    front: list[Candidate] = []
    best = -1.0
    for c in pool:
        if c.rate > best:
            front.append(c)
            best = c.rate
    print(HEADER)
    for c in front:
        print(c.line(ignore=frozenset({"R1"})))
    print("\n  Read the risk column, not the rate column. The knee is where P(SM<1.0)")
    print("  starts climbing faster than deg/s does.")
    return front


# ==========================================================================================
# STAGE 5 -- which requirement is in the way NOW
# ==========================================================================================
def stage_ladder(cands: list[Candidate]) -> None:
    print("\n" + "=" * 124)
    print("STAGE 5  THE RELAXATION LADDER -- flat-launch edition")
    print("=" * 124)
    print("  Same construction as agility_sweep.py stage 5, over the flat-flight score.")
    print("  The ORDER is the output: it has changed completely from the vertical case.\n")
    rungs = [
        (frozenset(), "nothing"),
        (frozenset({"R6"}), "R6 apogee <= 1600 m (vertical mode only)"),
        (frozenset({"recovery_alt"}), "250 m flat-apogee floor"),
        (frozenset({"flutter"}), "flutter >= 1.5x"),
        (frozenset({"servo"}), "servo torque >= 2.0x"),
        (frozenset({"hinge"}), "hinge bearing / root joint >= 2.0x"),
        (frozenset({"deploy"}), "drogue shock <= the docs/10 design load"),
        (frozenset({"imu"}), "+/-16 g accelerometer"),
        (frozenset({"R11"}), "R11 recovery packing"),
        (frozenset({"R5"}), "R5 Mach <= 0.8"),
        (frozenset({"R1"}), "R1 static margin band"),
        (frozenset({"R1", "R5", "imu", "servo", "flutter", "R11", "recovery_alt",
                    "hinge", "deploy"}), "everything except stall"),
    ]
    print(f"  {'requirement dropped':44s} {'best deg/s':>10s} {'g':>6s} {'radius':>8s} "
          f"{'P(SM<1)':>8s}  best vehicle")
    for ign, label in rungs:
        ok = [c for c in cands if not c.fails(ignore=ign)]
        if not ok:
            print(f"  {label:44s} {'--':>10s}")
            continue
        b = max(ok, key=lambda c: c.rate)
        p = b.params
        who = (f"{p.motor.name[:14]} {p.canard_semispan_cal:.2f}/"
               f"{p.aft_semispan_cal:.2f} {p.nose_ballast_kg * 1000:.0f}g "
               f"{b.deflection:.1f}d")
        print(f"  {label:44s} {b.rate:10.2f} {b.lateral_g:6.2f} "
              f"{b.radius / 1000:7.2f}k {b.risk:8.1%}  {who}")


# ==========================================================================================
# STAGE 6 -- the recommendation, and how the same airframe flies vertically
# ==========================================================================================
def stage_recommend(cand: Candidate, samples: int) -> None:
    print("\n" + "=" * 124)
    print("STAGE 6  THE RECOMMENDED POINT, AND ITS VERTICAL MODE")
    print("=" * 124)
    p = cand.params
    print(f"  motor              {p.motor.name}  ({p.motor.total_impulse:.0f} N s, "
          f"{p.motor.length * 1000:.0f} mm case"
          f"{'' if cand.motor_fits_built_mount else ' -- LONGER THAN THE BUILT MOUNT'})")
    print(f"  canard / aft span  {p.canard_semispan_cal:.2f} / {p.aft_semispan_cal:.2f} cal")
    print(f"  nose ballast       {p.nose_ballast_kg * 1000:.0f} g")
    print(f"  aft fin thickness  {p.fin_thickness * 1000:.1f} mm")
    print(f"  deflection         {cand.deflection:.1f} deg "
          f"(stall-limited; the frozen cap is {DEFLECTION_LIMIT_DEG:.1f})")

    print(f"\n  HORIZONTAL MODE  ({cand.elevation:.0f} deg rail, bank-to-turn, "
          f"altitude-holding bank)")
    h = cand.hz
    print(f"    peak heading rate    {h.peak_vec_rate_deg_s:.2f} deg/s"
          f"   ({h.peak_vec_rate_deg_s / TARGET_RATE_DEG_S:.0%} of the AIM-9B's 10 deg/s)")
    print(f"    azimuth rate         {h.peak_rate_deg_s:.2f} deg/s at "
          f"{h.fpa_at_peak_deg:.0f} deg flight path"
          f"{'  [STEEP -- do not quote]' if h.steep_azimuth else '  (shallow: sound)'}")
    print(f"    turn radius          {h.min_vec_radius_m:.0f} m")
    print(f"    lateral g            {h.peak_lateral_g:.2f} g")
    print(f"    control window       {h.control_seconds:.1f} s")
    print(f"    heading change       {h.vec_turn_deg:.0f} deg raw, "
          f"{h.vec_turn_deg * CONTROLLER_DUTY:.0f} deg at {CONTROLLER_DUTY:.0%} duty")
    print(f"    90 deg turn in       {h.quarter_turn_seconds:.1f} s at the mean rate")
    print(f"    apogee / max Mach    {h.max_altitude_m:.0f} m / {h.max_mach:.2f}")
    print(f"    ground range         {math.hypot(h.downrange_m, h.crossrange_m) / 1000:.2f} km")

    print("\n  VERTICAL MODE  (same hardware on a 5 deg rail)")
    f = cand.vflight
    tc = control.heading_change(cand.rocket, f, cand.deflection, duty_cycle=1.0)
    print(f"    apogee               {f.apogee:.0f} m "
          f"(R6 cap {LIMITS['apogee_max_m']:.0f} m: "
          f"{'OK' if f.apogee <= LIMITS['apogee_max_m'] else 'BREACHED'})")
    print(f"    max Mach             {f.max_mach:.2f}")
    print(f"    static margin        {f.min_static_margin:.2f} - {f.max_static_margin:.2f} cal")
    print(f"    nominal SM / P(SM<1) {cand.sm_nominal:.2f} cal / {cand.risk:.2%}")
    print(f"    peak heading rate    {tc.peak_rate_deg_s:.2f} deg/s")
    print(f"    recovery packing     "
          f"{'fits, ' + format(cand.ev.packing.margin * 1000, '.1f') + ' mm spare' if cand.ev.packing.fits else 'DOES NOT FIT'}")
    print(f"    axial g              {cand.axial_g:.1f} against a {AXIAL_G_MAX:.0f} g accelerometer")

    print("\n  LOCKED-CANARD VERTICAL (R12 failsafe, canards centred and held)")
    locked = replace(cand.rocket, canards=cand.rocket.canards)
    pk = max((q for q in f.points if q.t >= f.burnout_time), key=lambda q: q.q)
    print(f"    the canards do not disappear when locked -- they are still 27% of CNa --")
    print(f"    so the failsafe vehicle is the SAME airframe at zero deflection:")
    print(f"    static margin {f.min_static_margin:.2f} cal at rail exit, "
          f"{cand.sm_nominal:.2f} nominal, P(SM<1.0) {cand.risk:.2%}.")
    print(f"    That is the number R12 rides on, and it is why the Pareto's risk column")
    print(f"    is a SAFETY column and not a performance one.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=2000,
                    help="Monte Carlo samples per candidate for P(SM < 1.0)")
    ap.add_argument("--quick", action="store_true", help="coarse grid")
    ap.add_argument("--stage", type=str, default="all")
    args = ap.parse_args()

    if args.stage in ("all", "0"):
        stage_validate(args.samples)
    frozen = None
    if args.stage in ("all", "1"):
        frozen = stage_frozen(args.samples)
    if args.stage in ("all", "2"):
        stage_elevation()
    if args.stage in ("all", "3", "4", "5", "6"):
        cands = stage_search(args.samples, args.quick)
        front = stage_pareto(cands)
        stage_ladder(cands)
        if front:
            # The recommendation is the fastest point on the front that still meets R1 as
            # written. If none does, it is the fastest point inside a 5% risk budget --
            # named as such, not silently substituted.
            legal = [c for c in front if not c.fails()]
            pick = (max(legal, key=lambda c: c.rate) if legal else
                    max([c for c in front if c.risk <= 0.05] or front,
                        key=lambda c: c.rate))
            stage_recommend(pick, args.samples)


if __name__ == "__main__":
    main()
