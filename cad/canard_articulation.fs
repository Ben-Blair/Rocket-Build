FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

/**
 * Classify the bodies of this Part Studio: the tube, the four canard panels, the four
 * canard shafts, and the obsolete servo envelope blocks.
 *
 * ONE COPY, because there were two and they had to agree. Both `canardDeflection` and
 * `canardHingeConnectors` carried their own identical thresholds, which is the same
 * duplication that once let six scripts drift apart from one baseline (design/configure.py).
 *
 * CLASSIFIED BY Z EXTENT, not by radius, and that change has a specific cause. The
 * thresholds used to be `radius > 45 mm` for a panel; adding the root tang extends a shaft
 * from R 40.2 to R 65.2 and takes its centre radius from 36.84 to 49.34 mm, so every shaft
 * would have been classified as a panel and the deflection feature would have rotated the
 * wrong eight bodies. Z extent separates them and does not move when the tang goes on:
 *
 *      tube 142.90   panel 74.90   block 23.50   shaft 6.00, or 11.50 with its tang
 *
 * so a panel is anything over 50 and a shaft is anything under 18, with better than 6 mm
 * of clear air on both sides of both thresholds.
 */
function classifyCanardBodies(context is Context) returns map
{
    const AXIAL_BODY_RADIUS = 5 * millimeter;
    const PANEL_MIN_Z_EXTENT = 50 * millimeter;
    const SHAFT_MAX_Z_EXTENT = 18 * millimeter;

    var tube = undefined;
    var panels = {};
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

        var quadrant = round(atan2(centre[1], centre[0]) / (90 * degree));
        if (quadrant < 0)
            quadrant += 4;

        if (zExtent > PANEL_MIN_Z_EXTENT)
            panels[quadrant] = body;
        else if (zExtent < SHAFT_MAX_Z_EXTENT)
            shafts[quadrant] = body;
        // else: obsolete servo envelope block, which nothing here touches.
    }

    if (tube == undefined || size(keys(panels)) != 4 || size(keys(shafts)) != 4)
        throw regenError("Expected one tube, four canard panels and four shafts; found "
            ~ (tube == undefined ? "no tube" : "a tube") ~ ", "
            ~ toString(size(keys(panels))) ~ " panels and "
            ~ toString(size(keys(shafts))) ~ " shafts. The Part Studio has changed shape "
            ~ "-- fix the classification before trusting anything downstream.");

    return { "tube" : tube, "panels" : panels, "shafts" : shafts };
}


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
        const found = classifyCanardBodies(context);

        var groups = {};
        for (var quadrant in keys(found.panels))
            groups[quadrant] = [found.panels[quadrant], found.shafts[quadrant]];

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
        const found = classifyCanardBodies(context);
        const tube = found.tube;
        const shafts = found.shafts;

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

/**
 * Canard root tang -- the joint between each canard shaft and its panel.
 *
 * WHAT THIS BUILDS. The outboard end of each shaft becomes a flat blade that lands in a
 * slot in the panel root and is bonded there. Two operations per canard: the slot is cut
 * from the panel, then the tang is added to the shaft. Nominal tang inside an oversize
 * slot, so what is left between them is the bond line.
 *
 * WHY A TANG AT ALL. The sleeve ends flush at the panel root, R 40.200, and the panel is
 * 3.0 mm thick, so a dia 6 shaft cannot simply enter it. This is the HARD end of the load
 * path, not the easy one: the bearing takes the couple out going inboard, so going
 * outboard the moment is at its maximum -- 0.721 N m into 3.0 mm of G10. A root boss needs
 * 9 mm of panel thickness and t/c drives the flutter margin; a clevis stands proud of the
 * panel in the fastest flow it sees; a one-piece aluminium panel puts 154 g aft of a CG
 * that already needs 100 g of nose ballast. The tang spends none of those, because it
 * moves the problem into the PLANE of the panel rather than its thickness.
 *
 * THE DIMENSIONS ARE NOT FREE PARAMETERS. They come from design/hinge.py, which balances
 * the tang against the skin left over it and against the swept leading edge, and
 * scripts/hinge_report.py prints the margins. Do not tune them here -- change them there
 * and re-apply, or the CAD and the analysis stop agreeing, which is the failure mode this
 * whole project is organised against.
 *
 * THE CONSTRAINT THAT ACTUALLY BINDS is the leading edge. The panel is swept 35.4 deg, so
 * its LE runs aft 0.71 mm per mm of span while the tang stays in a fixed axial band about
 * the hinge -- it must, being the end of a shaft that turns about that axis. Depth is
 * therefore paid for in leading-edge material at better than half a millimetre per
 * millimetre, which is the opposite of how it first reads.
 *
 * NOTE ON THE PANEL, because the solid modelled here does not show it. The real panel is a
 * 0.6 / 2.0 / 0.6 mm bonded G10 LAMINATE, 3.2 mm total, with the middle sheet cut away over
 * 12.1 x 25.5 mm at the root. It is built that way so the slot never has to be cut: a
 * 1.8 mm slot 25 mm deep into the edge of a solid plate is a 13:1 blind cut needing a
 * slitting saw on a mill, whereas a gap in the middle sheet is a flat shape cut before
 * bonding. Every one of those three thicknesses is a stocked G10 sheet -- 1.8 mm, which an
 * earlier version of this specified, is not sold anywhere.
 *
 * The slot cut here is therefore the MIDDLE SHEET's thickness, tang + bond line on each
 * face, and the skins that survive are the outer sheets. That distinction is not cosmetic:
 * sizing the skin against the tang instead of against the slot overstated it by 1.44x and
 * turned a 1.69x margin into an apparent 2.5x.
 */
/**
 * Build one axis-aligned box, spin it about the rocket axis, and hand back a query that
 * resolves to exactly that body.
 *
 * WHY NOT JUST `qCreatedBy(boxId, EntityType.BODY)`, which is the obvious way and is what
 * this file did first: it came back EMPTY. `fCuboid` creates its body under a sub-operation
 * of the id it is given, and the query did not match it. Nothing said so -- the empty query
 * made `opTransform` a silent no-op, and the failure only surfaced one step later as
 * "Need at least two parts or surfaces for a Boolean operation", which points at the
 * boolean and not at the query that actually failed.
 *
 * Capturing the body as a DIFFERENCE instead -- everything that exists now, minus
 * everything that existed a moment ago -- does not care how the primitive names its
 * sub-ids. It also lets this assert that exactly one body appeared, so the next person
 * gets told which operation failed rather than which one noticed.
 */
function makeBox(context is Context, boxId is Id, spin is Transform,
                 corner1 is Vector, corner2 is Vector) returns Query
{
    // `newBody`, not `box`: **`box` is a reserved identifier in FeatureScript**, and using
    // it as a variable is a parse error that surfaces ONLY as an empty `featurespecs`
    // response -- no message, no line number, and the Part Studio's features all go to
    // error because the studio they depend on will not compile. This project had already
    // recorded that gotcha before walking into it again.
    const before = qUnion(evaluateQuery(context, qAllSolidBodies()));
    fCuboid(context, boxId, { "corner1" : corner1, "corner2" : corner2 });
    const newBody = qSubtraction(qAllSolidBodies(), before);

    const made = evaluateQuery(context, newBody);
    if (size(made) != 1)
        throw regenError("makeBox(" ~ toString(boxId) ~ ") produced " ~ toString(size(made))
            ~ " bodies, expected exactly 1. The box primitive did not build.");

    opTransform(context, boxId + "spin", { "bodies" : newBody, "transform" : spin });
    return newBody;
}

annotation { "Feature Type Name" : "Canard root tang" }
export const canardRootTang = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Hinge station, from module forward face" }
        isLength(definition.hingeStation, LENGTH_BOUNDS);

        annotation { "Name" : "Panel root radius" }
        isLength(definition.panelRootRadius, LENGTH_BOUNDS);

        annotation { "Name" : "Tang thickness" }
        isLength(definition.tangThickness, LENGTH_BOUNDS);

        annotation { "Name" : "Tang width" }
        isLength(definition.tangWidth, LENGTH_BOUNDS);

        annotation { "Name" : "Tang engagement into the panel" }
        isLength(definition.tangEngagement, LENGTH_BOUNDS);

        annotation { "Name" : "Bond line (each face)" }
        isLength(definition.bondLine, LENGTH_BOUNDS);
    }
    {
        const found = classifyCanardBodies(context);

        const rootR = definition.panelRootRadius;
        const hingeZ = definition.hingeStation;
        const halfT = definition.tangThickness / 2;
        const halfW = definition.tangWidth / 2;
        const bond = definition.bondLine;

        // Both boxes START INBOARD of the panel root face, in the 0.5 mm standoff gap
        // between the tube and the panel, and the slot ENDS past the tang. Never let a
        // boolean land exactly on the face it is meant to meet: a coincident result is
        // degenerate, and Onshape either fails it as non-manifold or -- worse -- succeeds
        // and removes nothing. This Part Studio has already carried one cut that cut
        // nothing for exactly that reason (docs/05, Extrude 4).
        const OVERSHOOT = 1 * millimeter;

        for (var quadrant in keys(found.shafts))
        {
            const theta = quadrant * 90 * degree;
            const spin = rotationAround(line(vector(0, 0, 0) * meter, vector(0, 0, 1)), theta);
            const q = toString(quadrant);

            // --- the slot in the panel, cut oversize by the bond line -------------------
            const slot = makeBox(context, id + ("slotBox" ~ q), spin,
                    vector(rootR - OVERSHOOT, -halfT - bond, hingeZ - halfW - bond),
                    vector(rootR + definition.tangEngagement + bond,
                           halfT + bond, hingeZ + halfW + bond));
            opBoolean(context, id + ("slotCut" ~ q), {
                    "tools" : slot,
                    "targets" : found.panels[quadrant],
                    "operationType" : BooleanOperationType.SUBTRACTION
            });

            // --- the tang itself, unioned into the shaft --------------------------------
            const tang = makeBox(context, id + ("tangBox" ~ q), spin,
                    vector(rootR - OVERSHOOT, -halfT, hingeZ - halfW),
                    vector(rootR + definition.tangEngagement, halfT, hingeZ + halfW));
            // UNION takes EVERY body in `tools` and NO `targets`. `targets` exists only
            // for SUBTRACTION and INTERSECTION, where the operation is directional --
            // targets minus tools. Passing a target to a union is BOOLEAN_BAD_INPUT, and
            // the message says nothing about which argument was wrong.
            //
            // Worth knowing how this presented, because it cost a full debugging cycle:
            // the slot cut above is a SUBTRACTION and worked first time, so four of the
            // eight operations succeeded and four failed, and the feature reported only
            // "Need at least two parts or surfaces for a Boolean operation" -- which points
            // at a body count, not at an argument name. Every body involved resolved
            // correctly; the geometry was never the problem.
            // ORDER MATTERS HERE, and it is the whole fix. `opBoolean` UNION takes every
            // body in `tools` and NO `targets` -- targets exists only for SUBTRACTION and
            // INTERSECTION, where the operation is directional. Passing a target to a union
            // is BOOLEAN_BAD_INPUT.
            //
            // And the SHAFT goes first. The union keeps the identity of the first body, so
            // listing the shaft first means the merged part keeps the shaft's name and its
            // material. With the tang first it came back as "Part 10" at 0.0000 g, and the
            // module mass FELL by 10.5 g where it should have risen by 12 -- geometry
            // perfect, mass meaningless. That is the same silent loss as the circular
            // pattern dropping material from its copies, which once made this studio read
            // 0.175 kg instead of 0.260. Check the mass after every boolean.
            opBoolean(context, id + ("tangJoin" ~ q), {
                    "tools" : qUnion([found.shafts[quadrant], tang]),
                    "operationType" : BooleanOperationType.UNION
            });
        }
    });


/**
 * The spline socket in the four canard shafts.
 *
 * A plain round blind hole in the inboard end of each sleeve, a few hundredths over the
 * servo spline's crest diameter. It is NOT a broached spline and it is not meant to be:
 * the socket is filled with anaerobic retaining compound and pushed onto the spline, and
 * the compound cures in the tooth valleys and becomes the female spline. Fifteen keys,
 * cast by the part they mate with. See design/hinge.py, "THE COUPLING".
 *
 * docs/05 carried this as "the socket could be cut the same way now; it has not been,
 * because nothing depends on it". Something does now -- it is the whole coupling.
 *
 * WHY THIS NEEDS A CUSTOM FEATURE: the cut has to reach the four shafts and NOT the four
 * obsolete servo envelope blocks that share this Part Studio. That is a boolean scope, a
 * scope has to name bodies, and bodies cannot be named by bare deterministic id.
 */
annotation { "Feature Type Name" : "Canard spline socket" }
export const canardSplineSocket = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Hinge station, from module forward face" }
        isLength(definition.hingeStation, LENGTH_BOUNDS);

        annotation { "Name" : "Sleeve inboard radius" }
        isLength(definition.sleeveInboard, LENGTH_BOUNDS);

        annotation { "Name" : "Socket diameter" }
        isLength(definition.socketDia, LENGTH_BOUNDS);

        annotation { "Name" : "Socket depth" }
        isLength(definition.socketDepth, LENGTH_BOUNDS);
    }
    {
        const found = classifyCanardBodies(context);
        // Overshoot INBOARD only. The socket is blind by design -- the surplus adhesive
        // has to have somewhere to go -- so the far end must land exactly on depth and
        // only the open end is allowed to overshoot.
        const OVER = 1 * millimeter;

        for (var quadrant in [0, 1, 2, 3])
        {
            const a = quadrant * 90 * degree;
            const u = vector(cos(a), sin(a), 0);
            const base = vector(0, 0, 1) * definition.hingeStation;

            var before = evaluateQuery(context, qAllSolidBodies());
            fCylinder(context, id + ("socket" ~ quadrant), {
                    "bottomCenter" : base + u * (definition.sleeveInboard - OVER),
                    "topCenter" : base + u * (definition.sleeveInboard + definition.socketDepth),
                    "radius" : definition.socketDia / 2
            });
            // Freeze the capture. qSubtraction(qAllSolidBodies(), ...) is lazy and would
            // grow to mean every body made since the snapshot by the time the next
            // quadrant's boolean consumed it.
            const cutter = qUnion(evaluateQuery(context,
                    qSubtraction(qAllSolidBodies(), qUnion(before))));

            opBoolean(context, id + ("socketCut" ~ quadrant), {
                    "tools" : cutter,
                    "targets" : found.shafts[quadrant],
                    "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
    });
