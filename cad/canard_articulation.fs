FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

/**
 * Canard deflection -- rotate all four canard panels and their shafts about their hinge
 * axes by a single commanded angle.
 *
 * WHY THIS EXISTS. Everything in this Part Studio was static, so nothing about the
 * design's motion could be checked: the interference question docs/05 asks -- does a
 * panel, its shaft, the bay or a neighbouring servo foul anything through the full
 * deflection -- has no answer in a model that cannot move. Setting `deflection` here
 * moves the geometry for real, in the Part Studio and therefore in every assembly that
 * references it, so the check becomes a matter of looking.
 *
 * WHY IT PICKS ITS OWN BODIES rather than taking a selection. This Part Studio is
 * generated, and its bodies come from a circular pattern whose copies have no stable
 * hand-picked identity. Classifying by geometry is the one description that survives a
 * rebuild. It is also self-checking: if the classification ever stops finding exactly
 * four panels and four shafts, the feature fails loudly instead of silently rotating the
 * wrong thing -- which, in a model that has already hidden a cut that cut nothing and a
 * datum that drove nothing, is the behaviour worth having.
 *
 * SIGN. Positive deflection is a right-handed rotation about the OUTWARD radial axis at
 * each canard's own station. Whether that is nose-up or nose-down for the vehicle is a
 * question for design/control.py, not for this file; the hinge sign convention lives in
 * packaging.hinge_moment() and must not be duplicated here.
 */
annotation { "Feature Type Name" : "Canard deflection" }
export const canardDeflection = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Deflection" }
        isAngle(definition.deflection, ANGLE_360_ZERO_DEFAULT_BOUNDS);

        annotation { "Name" : "Hinge station, from module forward face" }
        isLength(definition.hingeStation, LENGTH_BOUNDS);
    }
    {
        const hingeZ = definition.hingeStation;

        // Classification thresholds. These separate four kinds of body in this studio:
        // the tube (centred on the axis), the canard panels (well outboard), the canard
        // shafts (mid-radius, short in Z) and the obsolete servo envelope blocks
        // (mid-radius, long in Z). Panels and shafts turn; the tube and the blocks do not.
        const AXIAL_BODY_RADIUS = 5 * millimeter;
        const PANEL_MIN_RADIUS = 45 * millimeter;
        const SHAFT_MAX_Z_EXTENT = 10 * millimeter;

        var groups = {};
        var panelCount = 0;
        var shaftCount = 0;

        for (var body in evaluateQuery(context, qAllSolidBodies()))
        {
            const bbox = evBox3d(context, { "topology" : body });
            const centre = (bbox.minCorner + bbox.maxCorner) / 2;
            const radius = sqrt(centre[0] * centre[0] + centre[1] * centre[1]);
            const zExtent = bbox.maxCorner[2] - bbox.minCorner[2];

            if (radius < AXIAL_BODY_RADIUS)
                continue;                                  // the tube

            const isPanel = radius > PANEL_MIN_RADIUS;
            const isShaft = !isPanel && zExtent < SHAFT_MAX_Z_EXTENT;
            if (!isPanel && !isShaft)
                continue;                                  // servo envelope block

            // Which of the four stations this body belongs to, from where it sits.
            var quadrant = round(atan2(centre[1], centre[0]) / (90 * degree));
            if (quadrant < 0)
                quadrant += 4;

            if (groups[quadrant] == undefined)
                groups[quadrant] = [];
            groups[quadrant] = append(groups[quadrant], body);

            if (isPanel)
                panelCount += 1;
            else
                shaftCount += 1;
        }

        if (panelCount != 4 || shaftCount != 4)
            throw regenError("Expected 4 canard panels and 4 shafts; classified "
                ~ toString(panelCount) ~ " panels and " ~ toString(shaftCount)
                ~ " shafts. The Part Studio has changed shape -- fix the classification "
                ~ "before trusting any sweep.");

        for (var quadrant in keys(groups))
        {
            const bodies = groups[quadrant];
            const theta = quadrant * 90 * degree;
            const outward = vector(cos(theta), sin(theta), 0);
            const hingeAxis = line(vector(0 * meter, 0 * meter, hingeZ), outward);

            opTransform(context, id + ("canard" ~ toString(quadrant)), {
                    "bodies" : qUnion(bodies),
                    "transform" : rotationAround(hingeAxis, definition.deflection)
            });
        }
    });

/**
 * Canard hinge mate connectors -- one pair per canard, both on the hinge axis and exactly
 * coincident, one owned by the tube and one owned by that canard's shaft.
 *
 * WHY A PAIR AT THE SAME PLACE. A revolute mate aligns its two mate connectors, so if they
 * start apart, mating MOVES a part. Building both from the same coordinate system and
 * differing only in `owner` means the mate has nothing to correct: the assembly stays
 * exactly where this Part Studio put it, and the only freedom left is the one rotation
 * that is wanted.
 *
 * The Z axis of each connector is the outward radial, so a revolute mate turns the canard
 * about its own hinge and its mate limits are the deflection limit directly.
 */
annotation { "Feature Type Name" : "Canard hinge mate connectors" }
export const canardHingeConnectors = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Hinge station, from module forward face" }
        isLength(definition.hingeStation, LENGTH_BOUNDS);

        annotation { "Name" : "Connector radius from the rocket axis" }
        isLength(definition.connectorRadius, LENGTH_BOUNDS);
    }
    {
        const AXIAL_BODY_RADIUS = 5 * millimeter;
        const PANEL_MIN_RADIUS = 45 * millimeter;
        const SHAFT_MAX_Z_EXTENT = 10 * millimeter;

        var tube = undefined;
        var shafts = {};

        for (var body in evaluateQuery(context, qAllSolidBodies()))
        {
            const bbox = evBox3d(context, { "topology" : body });
            const centre = (bbox.minCorner + bbox.maxCorner) / 2;
            const radius = sqrt(centre[0] * centre[0] + centre[1] * centre[1]);
            const zExtent = bbox.maxCorner[2] - bbox.minCorner[2];

            if (radius < AXIAL_BODY_RADIUS)
            {
                tube = body;
                continue;
            }
            if (radius > PANEL_MIN_RADIUS || zExtent >= SHAFT_MAX_Z_EXTENT)
                continue;                              // panel, or servo envelope block

            var quadrant = round(atan2(centre[1], centre[0]) / (90 * degree));
            if (quadrant < 0)
                quadrant += 4;
            shafts[quadrant] = body;
        }

        if (tube == undefined || size(keys(shafts)) != 4)
            throw regenError("Expected one tube and four canard shafts; found "
                ~ (tube == undefined ? "no tube" : "a tube") ~ " and "
                ~ toString(size(keys(shafts))) ~ " shafts.");

        for (var quadrant in keys(shafts))
        {
            const theta = quadrant * 90 * degree;
            const outward = vector(cos(theta), sin(theta), 0);
            const origin = vector(definition.connectorRadius * cos(theta),
                                  definition.connectorRadius * sin(theta),
                                  definition.hingeStation);
            // X along the rocket axis, Z outward radial -- so the mate's rotation axis is
            // the hinge and its limits read directly as canard deflection.
            const cs = coordSystem(origin, vector(0, 0, 1), outward);

            opMateConnector(context, id + ("tube" ~ toString(quadrant)), {
                    "coordSystem" : cs,
                    "owner" : tube
            });
            opMateConnector(context, id + ("shaft" ~ toString(quadrant)), {
                    "coordSystem" : cs,
                    "owner" : shafts[quadrant]
            });
        }
    });
