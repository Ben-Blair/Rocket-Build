"""Mass and centre-of-gravity buildup.

Structural masses come from geometry and material density. Subsystem masses come from an
explicit, editable budget -- replace each line with a measured value as parts arrive. The
budget is the single most common source of error in a first rocket design, and an
optimistic budget shows up as an optimistic static margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import PointMass, Rocket
from .motors import Motor

# Editable subsystem budget, kg. These are estimates, not measurements.
DEFAULT_AVIONICS_BUDGET: dict[str, float] = {
    "flight_computer": 0.060,
    # ADDED Aug 2026, and it had been missing since this dict was written. docs/04 section 5
    # lists nine avionics lines totalling 620 g including a commercial dual-deploy altimeter;
    # this dict listed nine lines totalling 560 g and the altimeter was the one it did not
    # have. Every other line agreed to the gram, which is why nobody saw it -- a total is a
    # bad place to look for an error (correction 22).
    #
    # It is not an optional part. It is the independent commercial altimeter that fires the
    # ejection charges, it is what design/seal.py's feed-through is wired to, and flying
    # deployment off the custom PCB alone is a different safety argument than the one these
    # documents make. Found by asking where the boards physically go, not by any check.
    "deployment_altimeter": 0.060,
    "gnss_receiver_antenna": 0.030,
    "imu_daughterboard": 0.020,
    "battery_lipo_2s_1500mah": 0.090,
    "servo_power_bec": 0.025,
    "wiring_connectors": 0.080,
    "sled_and_hardware": 0.150,
    "telemetry_radio": 0.045,
    "gps_tracker_independent": 0.060,
}

# Which avionics lines physically live in the NOSE rather than in the nav bay. See
# design/avionics.py: the nav bay wanted 152 mm of sled and had 103, and moving these two
# was the only way out that touched no frozen geometry. Both are RF parts, neither needs a
# short wire to the flight computer, and a tracker whose job is to still be working when
# nothing else is belongs in its own compartment with its own battery anyway.
NOSE_AVIONICS = {"telemetry_radio", "gps_tracker_independent"}

DEFAULT_RECOVERY_BUDGET: dict[str, float] = {
    "drogue_chute": 0.070,
    "main_chute": 0.280,
    # 0.186 kg, and it is now a RESULT rather than a budget line. It was 0.220 kg, which
    # nothing had ever checked, and dividing it by an assumed bulk density is where a
    # quarter of the recovery bay's volume came from. `recovery.size_harness()` picks the
    # webbing from the opening shock it actually carries -- 3/4" tubular nylon at 4.3x after
    # a knot derating, against 1" at 6.8x -- and 2 x 3.40 m comes to 136 g of webbing plus
    # 50 g of links and swivels. `configure.evaluate()` re-derives it every run and warns if
    # this constant has drifted from the sized part, so the two cannot disagree in silence.
    "shock_cord_and_links": 0.186,
    "ejection_hardware_charges": 0.060,
    "nomex_protectors": 0.070,
}

DEFAULT_STRUCTURE_BUDGET: dict[str, float] = {
    "couplers_bulkheads": 0.300,
    "motor_mount_centering_rings": 0.250,
    "rail_buttons_fasteners": 0.060,
    "epoxy_and_fillets": 0.200,
}


def bay_centre(rocket: Rocket, name: str) -> float:
    """Station of the centre of the named body tube."""
    for i, tube in enumerate(rocket.tubes):
        if tube.name == name:
            return rocket.tube_station(i) + tube.length / 2.0
    raise KeyError(f"no bay named {name!r}; have {[t.name for t in rocket.tubes]}")


def bay_joints(rocket: Rocket) -> list[float]:
    """Stations of every tube-to-tube joint, where couplers live."""
    return [rocket.tube_station(i) for i in range(len(rocket.tubes))]


@dataclass
class MassResult:
    dry_mass: float
    wet_mass: float
    dry_cg: float
    wet_cg: float
    items: list[PointMass] = field(default_factory=list)

    def report(self) -> str:
        lines = [f"{'component':38s} {'mass (kg)':>10s} {'x (m)':>8s} {'moment':>9s}"]
        lines.append("-" * 68)
        for it in sorted(self.items, key=lambda p: -p.mass):
            lines.append(f"{it.name:38s} {it.mass:10.3f} {it.x:8.3f} {it.mass * it.x:9.4f}")
        lines.append("-" * 68)
        lines.append(f"{'DRY TOTAL':38s} {self.dry_mass:10.3f} {self.dry_cg:8.3f}")
        lines.append(f"{'WET TOTAL (incl. propellant)':38s} {self.wet_mass:10.3f} {self.wet_cg:8.3f}")
        return "\n".join(lines)


def _tube_mass(outer_d: float, thickness: float, length: float, density: float) -> float:
    mean_d = outer_d - thickness
    return density * math.pi * mean_d * thickness * length


def build_mass(
    rocket: Rocket,
    motor: Motor,
    avionics: dict[str, float] | None = None,
    recovery: dict[str, float] | None = None,
    structure: dict[str, float] | None = None,
    servo_mass_each: float = 0.055,
    n_servos: int = 4,
    contingency: float = 0.10,
    nose_ballast_kg: float = 0.0,
    nose_ballast_station: float = 0.191,
    nose_avionics_station: float = 0.300,
) -> MassResult:
    """Assemble the mass list and compute dry/wet CG.

    `contingency` is added as a uniformly distributed mass. Carry it until the vehicle is
    actually built; every real build comes out heavier than its model.

    `nose_ballast_kg` is the threaded-rod-and-washer stack in the nose shoulder, at
    `nose_ballast_station` metres from the nose tip. It is not a fudge factor: the design
    needs it to satisfy R1 once real 9 g servos replace the 55 g budget placeholder, and it
    is deliberately the last free parameter, set after weighing the built vehicle. See
    docs/00-requirements.md section 7.1.
    """
    items: list[PointMass] = []

    items.append(
        PointMass(
            "nose cone",
            rocket.nose.wetted_area * rocket.nose.wall_thickness * rocket.nose.material_density,
            0.6 * rocket.nose.length,
        )
    )

    for i, tube in enumerate(rocket.tubes):
        x0 = rocket.tube_station(i)
        items.append(
            PointMass(
                f"tube: {tube.name}",
                _tube_mass(tube.outer_diameter, tube.wall_thickness, tube.length, tube.material_density),
                x0 + tube.length / 2.0,
            )
        )

    for fins, label in ((rocket.aft_fins, "aft fins"), (rocket.canards, "canards")):
        if fins is None:
            continue
        fin_mass = fins.count * fins.planform_area_single * fins.thickness * fins.material_density
        # Tabs/mounting hardware roughly double an exposed panel's mass.
        items.append(PointMass(label, fin_mass * 2.0, fins.cp_station))

    if rocket.canards is not None:
        items.append(
            PointMass(
                f"canard servos x{n_servos}",
                n_servos * servo_mass_each,
                rocket.canards.x_root_le + rocket.canards.root_chord / 2.0,
            )
        )
        items.append(
            PointMass(
                "canard shafts/bearings/sled",
                n_servos * 0.030 + 0.120,
                rocket.canards.x_root_le + rocket.canards.root_chord / 2.0,
            )
        )

    if nose_ballast_kg > 0.0:
        items.append(PointMass("nose ballast", nose_ballast_kg, nose_ballast_station))

    avionics = DEFAULT_AVIONICS_BUDGET if avionics is None else avionics
    recovery = DEFAULT_RECOVERY_BUDGET if recovery is None else recovery
    structure = DEFAULT_STRUCTURE_BUDGET if structure is None else structure

    # Subsystems sit in the bay they are named after. An earlier version of this model
    # placed them at fixed fractions of overall length, which happened to put the avionics
    # budget inside the recovery bay and the recovery budget inside the nav bay -- the two
    # heaviest budget lines, swapped. That is worth about a quarter caliber of static
    # margin, so the stations are now derived from the actual layout.
    x_motor = rocket.length - motor.length / 2.0
    # THE AVIONICS BUDGET IS IN TWO PLACES NOW. The telemetry radio and the independent
    # tracker moved into the nose in Aug 2026 because the nav bay could not hold everything
    # (docs/01 correction 27), and a point mass in the wrong bay is worth about a quarter
    # caliber of static margin -- this function's own comment below says so, from the time
    # the avionics and recovery budgets were accidentally swapped. So the split is modelled
    # rather than averaged.
    nose_items = {k: v for k, v in avionics.items() if k in NOSE_AVIONICS}
    bay_items = {k: v for k, v in avionics.items() if k not in NOSE_AVIONICS}
    items.append(PointMass("avionics bay (budget)", sum(bay_items.values()),
                           bay_centre(rocket, "nav bay")))
    if nose_items:
        items.append(PointMass("avionics in nose (budget)", sum(nose_items.values()),
                               nose_avionics_station))
    items.append(PointMass("recovery (budget)", sum(recovery.values()), bay_centre(rocket, "recovery bay")))

    joints = bay_joints(rocket)
    x_booster = bay_centre(rocket, "booster")
    structure_stations = {
        "couplers_bulkheads": sum(joints) / len(joints),
        "motor_mount_centering_rings": x_motor,
        "rail_buttons_fasteners": x_booster,
        # Fillets are concentrated at the two fin roots; the rest is spread over joints.
        "epoxy_and_fillets": 0.5 * (rocket.aft_fins.cp_station + sum(joints) / len(joints)),
    }
    for key, value in structure.items():
        items.append(
            PointMass(f"structure: {key}", value, structure_stations.get(key, 0.55 * rocket.length))
        )

    items.append(PointMass("motor case (dry)", motor.dry_mass, x_motor))

    subtotal = sum(i.mass for i in items)
    items.append(PointMass("contingency", subtotal * contingency, 0.5 * rocket.length))

    dry_mass = sum(i.mass for i in items)
    dry_cg = sum(i.mass * i.x for i in items) / dry_mass

    prop = PointMass("propellant", motor.propellant_mass, x_motor)
    wet_mass = dry_mass + prop.mass
    wet_cg = (dry_cg * dry_mass + prop.x * prop.mass) / wet_mass

    return MassResult(dry_mass, wet_mass, dry_cg, wet_cg, items + [prop])


def cg_at_time(result: MassResult, motor: Motor, t: float, rocket: Rocket) -> float:
    """CG station at time `t`, interpolating propellant burn-off."""
    x_motor = rocket.length - motor.length / 2.0
    prop_mass = max(motor.mass_at(t) - motor.dry_mass, 0.0)
    total = result.dry_mass + prop_mass
    return (result.dry_cg * result.dry_mass + x_motor * prop_mass) / total
