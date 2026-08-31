"""Vehicle geometry definitions.

Convention: all station coordinates `x` are measured in metres from the nose tip,
positive aft. All lengths in metres, angles in radians unless the name says otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

NoseShape = Literal["cone", "ogive", "vonkarman"]


@dataclass
class NoseCone:
    length: float
    base_diameter: float
    shape: NoseShape = "ogive"
    wall_thickness: float = 0.0025
    material_density: float = 1850.0  # fiberglass

    @property
    def fineness(self) -> float:
        return self.length / self.base_diameter

    @property
    def cp_station(self) -> float:
        """Barrowman centre of pressure, from nose tip."""
        factors = {"cone": 2.0 / 3.0, "ogive": 0.466, "vonkarman": 0.5}
        return factors[self.shape] * self.length

    def radius_at(self, x: float) -> float:
        """Outer radius at `x` metres from the tip.

        Added Aug 2026 because moving the tracker and the telemetry radio into the nose
        needs an answer to "is there room there", and a nose cone is the one part of this
        vehicle whose available width is a function of station rather than a constant. A
        bay is a cylinder and you can check it with one number; a cone cannot be.

        Tangent ogive of radius rho = (R^2 + L^2) / 2R, which is the standard construction:
        the profile is the arc that meets the base radius tangentially to the body tube, so
        there is no slope discontinuity at the shoulder.
        """
        x = max(0.0, min(x, self.length))
        r = self.base_diameter / 2.0
        if self.shape == "cone":
            return r * x / self.length
        rho = (r**2 + self.length**2) / (2.0 * r)
        return math.sqrt(rho**2 - (self.length - x) ** 2) + r - rho

    def inner_radius_at(self, x: float) -> float:
        """Usable radius at `x`, inside the wall."""
        return max(self.radius_at(x) - self.wall_thickness, 0.0)

    @property
    def wetted_area(self) -> float:
        """Approximate lateral surface area."""
        r = self.base_diameter / 2.0
        slant = math.hypot(self.length, r)
        if self.shape == "cone":
            return math.pi * r * slant
        # Ogive/Von Karman are fuller than a cone; empirical correction.
        return math.pi * r * slant * 1.06


@dataclass
class BodyTube:
    length: float
    outer_diameter: float
    wall_thickness: float = 0.0025
    material_density: float = 1850.0
    name: str = "body"

    @property
    def inner_diameter(self) -> float:
        return self.outer_diameter - 2.0 * self.wall_thickness

    @property
    def wetted_area(self) -> float:
        return math.pi * self.outer_diameter * self.length


@dataclass
class FinSet:
    """Trapezoidal fin set. `x_root_le` is the root leading-edge station from nose tip."""

    count: int
    root_chord: float
    tip_chord: float
    semispan: float
    sweep_length: float  # axial distance from root LE to tip LE
    x_root_le: float
    thickness: float = 0.003
    body_diameter: float = 0.075
    material_density: float = 1850.0
    cant_deg: float = 0.0
    name: str = "fins"

    @property
    def mid_chord_sweep_length(self) -> float:
        """Axial length of the mid-chord line ('Lm' in Barrowman)."""
        return self.sweep_length + 0.5 * (self.tip_chord - self.root_chord)

    @property
    def mid_chord_line(self) -> float:
        return math.hypot(self.mid_chord_sweep_length, self.semispan)

    @property
    def planform_area_single(self) -> float:
        return 0.5 * (self.root_chord + self.tip_chord) * self.semispan

    @property
    def mean_chord(self) -> float:
        return 0.5 * (self.root_chord + self.tip_chord)

    @property
    def aspect_ratio_single(self) -> float:
        """Aspect ratio of one exposed panel treated as half of a full wing."""
        return 2.0 * self.semispan / self.mean_chord

    @property
    def wetted_area(self) -> float:
        return 2.0 * self.count * self.planform_area_single

    @property
    def spanwise_cp_radius(self) -> float:
        """Radial station of the panel's spanwise centre of pressure, from the axis."""
        r_body = self.body_diameter / 2.0
        cr, ct = self.root_chord, self.tip_chord
        y_bar = (self.semispan / 3.0) * (cr + 2.0 * ct) / (cr + ct)
        return r_body + y_bar

    @property
    def cp_station(self) -> float:
        """Barrowman axial centre of pressure, from nose tip."""
        cr, ct = self.root_chord, self.tip_chord
        term1 = self.mid_chord_sweep_length * (cr + 2.0 * ct) / (3.0 * (cr + ct))
        term2 = (1.0 / 6.0) * (cr + ct - cr * ct / (cr + ct))
        return self.x_root_le + term1 + term2


@dataclass
class PointMass:
    name: str
    mass: float
    x: float  # station of its centre of mass, from nose tip


@dataclass
class Rocket:
    nose: NoseCone
    tubes: list[BodyTube]
    aft_fins: FinSet
    canards: FinSet | None = None
    point_masses: list[PointMass] = field(default_factory=list)

    @property
    def diameter(self) -> float:
        return self.nose.base_diameter

    @property
    def reference_area(self) -> float:
        return math.pi * self.diameter**2 / 4.0

    @property
    def body_length(self) -> float:
        return sum(t.length for t in self.tubes)

    @property
    def length(self) -> float:
        return self.nose.length + self.body_length

    @property
    def fineness(self) -> float:
        return self.length / self.diameter

    def tube_station(self, index: int) -> float:
        """Forward station of tube `index`."""
        return self.nose.length + sum(t.length for t in self.tubes[:index])
