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
    "gnss_receiver_antenna": 0.030,
    "imu_daughterboard": 0.020,
    "battery_lipo_2s_1500mah": 0.090,
    "servo_power_bec": 0.025,
    "wiring_connectors": 0.080,
    "sled_and_hardware": 0.150,
    "telemetry_radio": 0.045,
    "gps_tracker_independent": 0.060,
}

DEFAULT_RECOVERY_BUDGET: dict[str, float] = {
    "drogue_chute": 0.070,
    "main_chute": 0.280,
    "shock_cord_and_links": 0.220,
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
) -> MassResult:
    """Assemble the mass list and compute dry/wet CG.

    `contingency` is added as a uniformly distributed mass. Carry it until the vehicle is
    actually built; every real build comes out heavier than its model.
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

    avionics = DEFAULT_AVIONICS_BUDGET if avionics is None else avionics
    recovery = DEFAULT_RECOVERY_BUDGET if recovery is None else recovery
    structure = DEFAULT_STRUCTURE_BUDGET if structure is None else structure

    # Subsystems sit in the bay they are named after. An earlier version of this model
    # placed them at fixed fractions of overall length, which happened to put the avionics
    # budget inside the recovery bay and the recovery budget inside the nav bay -- the two
    # heaviest budget lines, swapped. That is worth about a quarter caliber of static
    # margin, so the stations are now derived from the actual layout.
    x_motor = rocket.length - motor.length / 2.0
    items.append(PointMass("avionics bay (budget)", sum(avionics.values()), bay_centre(rocket, "nav bay")))
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
