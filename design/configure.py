"""Turn a compact parameter set into a full vehicle, and score it against requirements.

Layout, nose to tail:

    [nose cone] [nav bay] [canard module] [recovery bay] [booster + aft fins]

The nav bay is forward on purpose: GNSS antennas need sky view and want to be as far as
possible from the servo power wiring, and a fiberglass airframe is an RF shield, so the
antenna wants to sit under the (thin, non-conductive) nose shoulder region.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from . import aero, control, mass as mass_mod, recovery, trajectory
from .geometry import BodyTube, FinSet, NoseCone, Rocket
from .motors import GENERIC, Motor, load_eng
from .packaging import SERVOS


@dataclass
class DesignParams:
    outer_diameter: float
    wall_thickness: float
    motor: Motor
    nose_fineness: float = 4.0
    nose_shape: str = "ogive"
    nav_bay_cal: float = 1.6  # bay lengths in calibers
    canard_module_cal: float = 1.8
    # 4.5 cal, and it is now CHECKED rather than assumed. It was a number someone typed,
    # and recovery.check_packing() exists because nothing had ever verified it. The first
    # run said it was 11 mm short -- but that verdict came from estimating packed volume as
    # budgeted mass / an assumed bulk density, and the budget carries a 280 g main against
    # a real Fruity Chutes Iris Ultra 60" Compact at 193 g. With the vendor's published
    # pack volumes standing in for the estimate, the hardware needs 4.33 cal and this bay
    # fits it with 13 mm to spare. The airframe was right; only the confidence in it was
    # missing. See design/recovery.py for the sourced numbers.
    recovery_bay_cal: float = 4.5
    booster_margin_cal: float = 1.2  # booster length beyond the motor
    canard_semispan_cal: float = 0.85
    # Root chord and taper are set TOGETHER and hold panel area constant at 3188 mm^2.
    # 0.85/0.40 replaced 0.70/0.70 in Aug 2026: at the 35.4 deg sweep below, a more
    # sharply tapered panel recovers most of the authority the sweep costs (1.82 -> 1.93 g,
    # 394 -> 418 m of crossrange) because CNa rises as the tip unloads. It also reads more
    # like a real missile canard, which is why it was chosen -- the aerodynamics came out
    # ahead as well, which is rare enough to note.
    #
    # The cost is flutter: the root chord grows 55.6 -> 67.5 mm at a fixed 3.0 mm thickness,
    # so t/c falls 0.054 -> 0.044 and the canard flutter margin drops 5.42x -> 4.46x. Still
    # ~3x the 1.5x requirement, but this is now the parameter to watch if the panel ever
    # gets thinner. See docs/00-requirements.md section 8.
    canard_root_cal: float = 0.85
    canard_taper: float = 0.40
    # Canard leading-edge sweep, calibers of axial offset from root LE to tip LE.
    # None means "match the aft fin sweep ANGLE", which is the design intent: the two sets
    # should read as one vehicle, and hardcoding a number here would silently drift the
    # moment `aft_sweep_cal` moved. Set a float to probe a different planform.
    #
    # This was 0.0 (a symmetric-taper trapezoid) until Aug 2026, not because anything chose
    # it but because the canards never had a sweep parameter while the aft fins did. That
    # default was the maximum-authority shape -- symmetric taper puts the mid-chord line at
    # zero sweep, which maximises CNa per unit area in aero.fin_cn_alpha -- so sweeping
    # costs authority. It is a deliberate trade, priced in docs/00-requirements.md section 5.
    #
    # Sweep does NOT change planform area, and it does NOT flip the hinge sign: both the
    # hinge (0.20c) and the panel CP (0.25c) are referenced to the same MAC, so the net
    # hinge moment stays restoring at any sweep. See correction 2 before assuming otherwise.
    canard_sweep_cal: float | None = None
    aft_semispan_cal: float = 1.55
    aft_root_cal: float = 1.90
    aft_taper: float = 0.45
    aft_sweep_cal: float = 1.10
    n_canards: int = 4
    n_aft_fins: int = 4
    fin_thickness: float = 0.0032
    # Key into packaging.SERVOS. Drives BOTH the actuator packaging check and the
    # servo line of the mass budget, so the two cannot disagree.
    servo: str = "kst_x08_plus"
    # Threaded rod + washer stack in the nose shoulder, metres from the nose tip.
    # REQUIRED, not optional: without it P(SM < 1.0) is 1.8% against R1's 1% limit,
    # because the real 9 g servos removed ~180 g from ahead of the CG. 75 g is the
    # minimum that satisfies R1; 100 g is the design point. See docs 7.1.
    nose_ballast_kg: float = 0.100
    nose_ballast_station: float = 0.191
    canard_thickness: float = 0.0030
    material_density: float = 1850.0

    @property
    def label(self) -> str:
        return f"D{self.outer_diameter * 1000:.0f}/{self.motor.name}"


# ----------------------------------------------------------------------------------------
# THE FROZEN BASELINE -- single source of truth
# ----------------------------------------------------------------------------------------
# Every script builds its vehicle from baseline() below. Do not copy these numbers into a
# script; import them. Six scripts each used to carry their own copy, they drifted apart
# from the documentation, and reconciling that cost a full day.
#
# Fin semispans are the dataclass defaults above (canard 0.85 cal, aft 1.55 cal), set
# jointly by the constrained search in scripts/robustness.py -- see docs/00-requirements.md
# section 7. Sizing the two sets independently was the original mistake: canard area buys
# control authority but costs static margin, aft area buys margin but costs authority.

ROOT = Path(__file__).resolve().parents[1]

BASELINE_OD = 0.0794  # 3.0 in fiberglass, 79.4 mm OD
BASELINE_WALL = 0.0023

# Selected by scripts/motor_trade.py against the real ThrustCurve.org catalogue.
# Cesaroni Pro54 J449 Blue Streak: ~3.0x the crossrange of the J430 at Mach 0.523 and 8.2 g.
BASELINE_MOTOR_FILE = ROOT / "data" / "motors" / "Cesaroni_1261J449-15A.eng"


@lru_cache(maxsize=1)
def baseline_motor() -> Motor:
    """The frozen motor, falling back to a placeholder if the catalogue is not downloaded."""
    if BASELINE_MOTOR_FILE.exists():
        return load_eng(BASELINE_MOTOR_FILE)
    return GENERIC["J-54"]


def baseline(motor: Motor | None = None, **overrides) -> DesignParams:
    """The frozen baseline vehicle.

    Pass a motor to swap it (motor trade studies); pass keyword overrides to probe a
    variation without disturbing the frozen values.
    """
    params = DesignParams(
        outer_diameter=BASELINE_OD,
        wall_thickness=BASELINE_WALL,
        motor=motor if motor is not None else baseline_motor(),
    )
    return replace(params, **overrides) if overrides else params


def build_vehicle(p: DesignParams) -> Rocket:
    d = p.outer_diameter
    nose = NoseCone(
        length=p.nose_fineness * d,
        base_diameter=d,
        shape=p.nose_shape,  # type: ignore[arg-type]
        wall_thickness=p.wall_thickness,
        material_density=p.material_density,
    )

    booster_len = p.motor.length + p.booster_margin_cal * d
    tubes = [
        BodyTube(p.nav_bay_cal * d, d, p.wall_thickness, p.material_density, "nav bay"),
        BodyTube(p.canard_module_cal * d, d, p.wall_thickness, p.material_density, "canard module"),
        BodyTube(p.recovery_bay_cal * d, d, p.wall_thickness, p.material_density, "recovery bay"),
        BodyTube(booster_len, d, p.wall_thickness, p.material_density, "booster"),
    ]

    x_canard_module = nose.length + tubes[0].length
    canard_root = p.canard_root_cal * d

    # Sweep angle is what the eye reads, so match the ANGLE rather than the caliber offset --
    # the two sets have different semispans, so equal offsets would not look equal.
    if p.canard_sweep_cal is None:
        aft_sweep_angle = math.atan2(p.aft_sweep_cal, p.aft_semispan_cal)
        canard_sweep = p.canard_semispan_cal * math.tan(aft_sweep_angle) * d
    else:
        canard_sweep = p.canard_sweep_cal * d
    canards = FinSet(
        count=p.n_canards,
        root_chord=canard_root,
        tip_chord=canard_root * p.canard_taper,
        semispan=p.canard_semispan_cal * d,
        sweep_length=canard_sweep,
        x_root_le=x_canard_module + 0.5 * (tubes[1].length - canard_root),
        thickness=p.canard_thickness,
        body_diameter=d,
        material_density=p.material_density,
        name="canards",
    )

    total_length = nose.length + sum(t.length for t in tubes)
    aft_root = p.aft_root_cal * d
    aft_fins = FinSet(
        count=p.n_aft_fins,
        root_chord=aft_root,
        tip_chord=aft_root * p.aft_taper,
        semispan=p.aft_semispan_cal * d,
        sweep_length=p.aft_sweep_cal * d,
        x_root_le=total_length - aft_root,
        thickness=p.fin_thickness,
        body_diameter=d,
        material_density=p.material_density,
        name="aft fins",
    )

    return Rocket(nose=nose, tubes=tubes, aft_fins=aft_fins, canards=canards)


@dataclass
class Evaluation:
    params: DesignParams
    rocket: Rocket
    masses: mass_mod.MassResult
    flight: trajectory.Flight
    pitch: control.AuthorityResult | None
    roll_aligned: control.RollResult | None
    roll_interdig: control.RollResult | None
    crossrange: float
    control_seconds: float
    sm_without_canards: float
    packing: recovery.PackingResult
    violations: list[str]

    @property
    def feasible(self) -> bool:
        return not self.violations


LIMITS = dict(
    sm_min=1.4,  # minimum over the flight, which occurs at rail exit (motor loaded)
    sm_max=3.0,  # above this the vehicle weathercocks hard and fights the controller
    rail_exit_min=15.0,
    twr_min=5.0,
    mach_max=0.80,
    apogee_min_m=450.0,
    # The field has no altitude waiver ceiling, so this cap is no longer regulatory. It is
    # set by recovery footprint instead: see scripts/recovery_study.py. At 1600 m the walk
    # to the landing point is about 1 km in a 15 mph wind, which is recoverable on foot
    # within a launch window. Past that, recovery risk per flight starts to dominate, and
    # this project needs five or six flights with the data intact.
    apogee_max_m=1600.0,
    lateral_g_min=0.5,
)


def evaluate(
    p: DesignParams,
    deflection_deg: float = 6.0,
    rail_length: float = 3.66,
    rail_angle_deg: float = 5.0,
) -> Evaluation:
    rocket = build_vehicle(p)
    masses = mass_mod.build_mass(
        rocket, p.motor,
        servo_mass_each=SERVOS[p.servo].mass, n_servos=p.n_canards,
        nose_ballast_kg=p.nose_ballast_kg, nose_ballast_station=p.nose_ballast_station,
    )
    flight = trajectory.simulate(
        rocket, p.motor, masses, rail_length=rail_length, rail_angle_deg=rail_angle_deg
    )

    violations: list[str] = []
    if flight.thrust_to_weight < LIMITS["twr_min"]:
        violations.append(f"T/W {flight.thrust_to_weight:.1f} < {LIMITS['twr_min']}")
    if flight.rail_exit_velocity < LIMITS["rail_exit_min"]:
        violations.append(f"rail exit {flight.rail_exit_velocity:.0f} m/s low")
    if flight.max_mach > LIMITS["mach_max"]:
        violations.append(f"Mach {flight.max_mach:.2f} > {LIMITS['mach_max']}")
    if flight.min_static_margin < LIMITS["sm_min"]:
        violations.append(f"SM {flight.min_static_margin:.2f} < {LIMITS['sm_min']} cal")
    if flight.max_static_margin > LIMITS["sm_max"]:
        violations.append(f"SM {flight.max_static_margin:.2f} > {LIMITS['sm_max']} cal")
    if not (LIMITS["apogee_min_m"] <= flight.apogee <= LIMITS["apogee_max_m"]):
        violations.append(f"apogee {flight.apogee:.0f} m outside window")

    # Will the recovery hardware physically go in the tube? `recovery_bay_cal` was an
    # assumed constant for a long time and nothing checked it. A canopy that does not fit
    # is not a soft failure: it is a rocket that cannot be assembled on the pad, found on
    # launch day.
    rec_tube = next(t for t in rocket.tubes if t.name == "recovery bay")
    packing = recovery.check_packing(rec_tube.inner_diameter, rec_tube.length)
    if not packing.fits:
        violations.append(
            f"recovery bay {rec_tube.length * 1000:.0f} mm, needs "
            f"{packing.required_length * 1000:.0f} mm for the chutes "
            f"({packing.required_length / p.outer_diameter:.2f} cal)"
        )

    # Control assessment at the highest-q point after burnout, where authority is best.
    coast = [pt for pt in flight.points if pt.t >= flight.burnout_time]
    pitch = roll_a = roll_i = None
    sm_bare = float("nan")
    if coast:
        pt = max(coast, key=lambda q: q.q)
        pitch = control.pitch_authority(rocket, pt, pt.mass, deflection_deg)
        roll_a = control.roll_authority(
            rocket, pt, pt.mass, deflection_deg, control.InterferenceModel.aligned()
        )
        roll_i = control.roll_authority(
            rocket, pt, pt.mass, deflection_deg, control.InterferenceModel.interdigitated()
        )
        # Static margin is a derivative, so it does not change with deflection. What the
        # canards do is add a forward normal-force contribution that reduces the margin
        # relative to the same airframe without them. Quantify that penalty explicitly:
        # it is the cost you pay for control authority.
        bare = replace(rocket, canards=None)
        sm_bare = aero.stability(bare, pt.cg, pt.mach).static_margin_cal
        if pitch.lateral_accel_g < LIMITS["lateral_g_min"]:
            violations.append(f"lateral {pitch.lateral_accel_g:.2f} g < {LIMITS['lateral_g_min']}")
        if pitch.stalled:
            violations.append(f"canard stall at {deflection_deg:.0f} deg")

    crossrange, seconds = control.achievable_crossrange(rocket, flight, masses, deflection_deg)

    return Evaluation(
        params=p,
        rocket=rocket,
        masses=masses,
        flight=flight,
        pitch=pitch,
        roll_aligned=roll_a,
        roll_interdig=roll_i,
        crossrange=crossrange,
        control_seconds=seconds,
        sm_without_canards=sm_bare,
        packing=packing,
        violations=violations,
    )
