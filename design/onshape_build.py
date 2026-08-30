"""Emit Onshape Part Studio features as JSON, so CAD geometry can be generated from
`design/` instead of drawn by hand.

Why bother. Every geometric error this project has found in its CAD -- a cut that landed
on a face and so cut nothing, a pattern that dropped its material assignment, a dimension
taken to a circle's tangent, a datum plane that drove nothing -- was a hand-clicking
error, invisible in the viewport and obvious in the JSON. Geometry built from these
helpers is written from the same numbers the analysis uses, so that whole class of error
cannot happen: there is no second place for a dimension to live.

Sketches here are placed at absolute coordinates rather than dimensioned with constraints.
That is deliberate. The source of truth is Python; a sketch is an output, and a regenerated
output does not need to be editable. Do not hand-edit the sketches these produce -- change
the numbers and rebuild.
"""

from __future__ import annotations

import math
from typing import Any

# Default-plane queries. The compressed query encodes the operation id as a pair of
# strings, ("Top", "planeOp"), with `S<len>.<len>$` giving their lengths -- which is why
# the plane name's character count appears in the literal.
def plane_query(name: str) -> dict[str, Any]:
    """Query for one of the three default planes: 'Top', 'Front' or 'Right'."""
    if name not in ("Top", "Front", "Right"):
        raise ValueError(f"not a default plane: {name}")
    q = (
        'query=qCompressed(1.0,"%B5$QueryM4Sa$entityTypeBa$EntityTypeS4$FACESb$'
        f'historyTypeS8$CREATIONSb$operationIdB2$IdA1S{len(name)}.7${name}planeOp'
        'S9$queryTypeS5$DUMMY",id);'
    )
    return {"btType": "BTMIndividualQuery-138", "queryString": q, "deterministicIds": []}


def _quantity(pid: str, expr: str) -> dict[str, Any]:
    return {"btType": "BTMParameterQuantity-147", "parameterId": pid, "expression": expr}


def _enum(pid: str, enum_name: str, value: str) -> dict[str, Any]:
    return {"btType": "BTMParameterEnum-145", "parameterId": pid,
            "enumName": enum_name, "value": value}


def _bool(pid: str, value: bool) -> dict[str, Any]:
    return {"btType": "BTMParameterBoolean-144", "parameterId": pid, "value": value}


def _queries(pid: str, queries: list[dict]) -> dict[str, Any]:
    return {"btType": "BTMParameterQueryList-148", "parameterId": pid, "queries": queries}


# --- sketch entities. All coordinates in METRES, in the sketch plane's own frame. -----

def line(x0: float, y0: float, x1: float, y1: float, eid: str) -> dict[str, Any]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0.0:
        raise ValueError(f"zero-length line {eid}")
    return {
        "btType": "BTMSketchCurveSegment-155",
        "startParam": 0.0, "endParam": length,
        "startPointId": f"{eid}.start", "endPointId": f"{eid}.end",
        "geometry": {"btType": "BTCurveGeometryLine-117",
                     "pntX": x0, "pntY": y0, "dirX": dx / length, "dirY": dy / length},
        "entityId": eid,
    }


def rect(x0: float, y0: float, x1: float, y1: float, prefix: str) -> list[dict[str, Any]]:
    """Closed rectangle. Corners given as opposite corners; order does not matter."""
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    return [
        line(xa, ya, xb, ya, f"{prefix}_b"),
        line(xb, ya, xb, yb, f"{prefix}_r"),
        line(xb, yb, xa, yb, f"{prefix}_t"),
        line(xa, yb, xa, ya, f"{prefix}_l"),
    ]


def circle(cx: float, cy: float, radius: float, eid: str) -> dict[str, Any]:
    return {
        "btType": "BTMSketchCurve-4",
        "geometry": {"btType": "BTCurveGeometryCircle-115", "radius": radius,
                     "clockwise": False, "xCenter": cx, "yCenter": cy,
                     "xDir": 1.0, "yDir": 0.0},
        "centerId": f"{eid}.center",
        "entityId": eid,
    }


def sketch(name: str, plane: str | dict, entities: list[dict]) -> dict[str, Any]:
    """A new sketch on a default plane (by name) or on an explicit query."""
    q = plane_query(plane) if isinstance(plane, str) else plane
    return {
        "btType": "BTMSketch-151",
        "featureType": "newSketch",
        "name": name,
        "parameters": [_queries("sketchPlane", [q])],
        "entities": entities,
        "constraints": [],
    }


def sketch_regions(sketch_feature_id: str) -> dict[str, Any]:
    """Every closed region of a sketch -- the simple way to feed a sketch to an extrude
    without naming individual edges."""
    return {"btType": "BTMIndividualSketchRegionQuery-140",
            "featureId": sketch_feature_id, "queryStatement": None,
            "deterministicIds": []}


def extrude(
    name: str,
    regions: list[dict],
    depth_mm: float,
    operation: str = "NEW",
    opposite: bool = False,
    symmetric: bool = False,
    start_offset_mm: float | None = None,
    start_offset_opposite: bool = False,
    boolean_scope: list[dict] | None = None,
) -> dict[str, Any]:
    """A blind extrude.

    `operation` is NEW / ADD / REMOVE / INTERSECT. For ADD and REMOVE, pass
    `boolean_scope` (a list of body queries) or the feature defaults to every body.

    On `depth_mm`: never let a REMOVE land exactly on the face it is meant to cut
    through. A boolean whose result is coincident with an existing surface is degenerate
    and Onshape fails it with "would result in non-manifold body" -- or, worse, succeeds
    and removes nothing. Overshoot deliberately.
    """
    params: list[dict[str, Any]] = [
        _enum("domain", "OperationDomain", "MODEL"),
        _enum("bodyType", "ExtendedToolBodyType", "SOLID"),
        _enum("operationType", "NewBodyOperationType", operation),
        _queries("entities", regions),
        _enum("endBound", "BoundingType", "BLIND"),
        _quantity("depth", f"{depth_mm} mm"),
        _bool("oppositeDirection", opposite),
        _bool("symmetric", symmetric),
    ]
    if start_offset_mm is not None:
        params += [
            _bool("startOffset", True),
            _enum("startOffsetBound", "StartOffsetType", "BLIND"),
            _quantity("startOffsetDistance", f"{start_offset_mm} mm"),
            _bool("startOffsetOppositeDirection", start_offset_opposite),
        ]
    if boolean_scope is not None:
        params += [_bool("defaultScope", False), _queries("booleanScope", boolean_scope)]
    return {"btType": "BTMFeature-134", "featureType": "extrude",
            "name": name, "parameters": params}


def body_query(deterministic_id: str) -> dict[str, Any]:
    return {"btType": "BTMIndividualQuery-138",
            "deterministicIds": [deterministic_id], "queryStatement": None}
