FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

/**
 * The printed canard bay, and the retainer bar that clamps each servo.
 *
 * Built as a custom feature rather than as feature JSON because every additive body here
 * is RADIAL -- collar bosses, servo trays, clamp bosses -- and a radial extrude in plain
 * feature JSON needs a sketch on a plane that has to be named by a query. FeatureScript
 * takes coordinates directly and needs no plane at all.
 *
 * FRAME: the module Part Studio's. Origin on the rocket axis, +Z aft, Z 0 at the canard
 * module tube's forward face. So this drops into Assembly 1 at IDENTITY -- no transform
 * to compute, and none to get wrong.
 *
 * Every dimension arrives as a parameter from design/bay.py. Nothing is typed here.
 *
 * THREE FEATURESCRIPT TRAPS THIS FILE IS WRITTEN AROUND, all of them previously paid for:
 *   - `box` is a reserved word. Using it as a variable produces a parse error whose ONLY
 *     symptom is an empty `featurespecs` response.
 *   - `qCreatedBy(id, BODY)` comes back EMPTY for a body made by an f-prefixed primitive,
 *     because the primitive builds under a sub-operation. Capture new bodies as a set
 *     difference against a snapshot instead.
 *   - `opBoolean` UNION takes every body in `tools` and NO `targets`, and the union takes
 *     the NAME AND MATERIAL OF ITS FIRST TOOL. Put the shell first or the merged part
 *     comes back unnamed at zero density.
 */

// Snapshot-and-difference, because qCreatedBy does not see primitive bodies.
//
// THE evaluateQuery IS NOT OPTIONAL. `qSubtraction(qAllSolidBodies(), ...)` is a LAZY
// query: it is re-run wherever it is finally used. Hold one across a few more
// primitives and it quietly grows to mean "every body made since the snapshot" -- so
// `shell` starts also meaning the trays, the collars and the webs, and the first
// boolean that consumes it swallows the lot and regenerates as ERROR with no message.
// Evaluating here freezes it to the bodies that existed at THIS moment.
function madeBy(context is Context, before is array) returns Query
{
    return qUnion(evaluateQuery(context, qSubtraction(qAllSolidBodies(), qUnion(before))));
}

function snapshot(context is Context) returns array
{
    return evaluateQuery(context, qAllSolidBodies());
}

// A cuboid at quadrant 0 (+X radial, +Y across, +Z aft), then rotated into place.
function quadrantCuboid(context is Context, id is Id, quadrant is number,
                        lo is Vector, hi is Vector) returns Query
{
    var before = snapshot(context);
    fCuboid(context, id, { "corner1" : lo, "corner2" : hi });
    var made = madeBy(context, before);
    if (quadrant != 0)
        opTransform(context, id + "spin", {
                "bodies" : made,
                "transform" : rotationAround(line(vector(0, 0, 0) * meter,
                                                  vector(0, 0, 1)), quadrant * 90 * degree)
        });
    return made;
}

// A cylinder on a RADIAL axis at the given quadrant, spanning two radii.
function radialCylinder(context is Context, id is Id, quadrant is number,
                        rInner is ValueWithUnits, rOuter is ValueWithUnits,
                        z is ValueWithUnits, dia is ValueWithUnits,
                        across is ValueWithUnits) returns Query
{
    var a = quadrant * 90 * degree;
    var u = vector(cos(a), sin(a), 0);
    var t = vector(-sin(a), cos(a), 0);      // +Y at quadrant 0, rotated
    var axis = vector(0, 0, 1);
    var base = t * across + axis * z;
    var before = snapshot(context);
    fCylinder(context, id, {
            "bottomCenter" : base + u * rInner,
            "topCenter" : base + u * rOuter,
            "radius" : dia / 2
    });
    return madeBy(context, before);
}

annotation { "Feature Type Name" : "Canard bay" }
export const canardBay = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Shell OD" } isLength(definition.shellOd, LENGTH_BOUNDS);
        annotation { "Name" : "Shell ID" } isLength(definition.shellId, LENGTH_BOUNDS);
        annotation { "Name" : "Forward face Z" } isLength(definition.zFwd, LENGTH_BOUNDS);
        annotation { "Name" : "Aft face Z" } isLength(definition.zAft, LENGTH_BOUNDS);
        annotation { "Name" : "Hinge Z" } isLength(definition.zHinge, LENGTH_BOUNDS);

        annotation { "Name" : "Collar OD" } isLength(definition.collarOd, LENGTH_BOUNDS);
        annotation { "Name" : "Collar bore" } isLength(definition.collarBore, LENGTH_BOUNDS);
        annotation { "Name" : "Collar inner R" } isLength(definition.collarInnerR, LENGTH_BOUNDS);

        annotation { "Name" : "Tray flange R" } isLength(definition.trayFlangeR, LENGTH_BOUNDS);
        annotation { "Name" : "Tray back R" } isLength(definition.trayBackR, LENGTH_BOUNDS);
        annotation { "Name" : "Tray width" } isLength(definition.trayWidth, LENGTH_BOUNDS);
        annotation { "Name" : "Tray fwd Z" } isLength(definition.trayFwdZ, LENGTH_BOUNDS);
        annotation { "Name" : "Tray aft Z" } isLength(definition.trayAftZ, LENGTH_BOUNDS);

        annotation { "Name" : "Window length" } isLength(definition.windowLen, LENGTH_BOUNDS);
        annotation { "Name" : "Window width" } isLength(definition.windowWid, LENGTH_BOUNDS);
        annotation { "Name" : "Window fwd Z" } isLength(definition.windowFwdZ, LENGTH_BOUNDS);

        annotation { "Name" : "Web thickness" } isLength(definition.webThk, LENGTH_BOUNDS);
        annotation { "Name" : "Boss face R" } isLength(definition.bossFaceR, LENGTH_BOUNDS);
        annotation { "Name" : "Insert dia" } isLength(definition.insertDia, LENGTH_BOUNDS);
        annotation { "Name" : "Insert depth" } isLength(definition.insertDepth, LENGTH_BOUNDS);
        annotation { "Name" : "Clamp screw Y" } isLength(definition.clampY, LENGTH_BOUNDS);
        annotation { "Name" : "Screw row 1 Z" } isLength(definition.screwZ1, LENGTH_BOUNDS);
        annotation { "Name" : "Screw row 2 Z" } isLength(definition.screwZ2, LENGTH_BOUNDS);

        annotation { "Name" : "Retainer thickness" } isLength(definition.retThk, LENGTH_BOUNDS);
        annotation { "Name" : "Build retainer" } definition.buildRetainer is boolean;
    }
    {
        const OVER = 1 * millimeter;   // overshoot on every cut; a REMOVE that lands exactly
                                       // on a face is degenerate and silently cuts nothing.

        // ---- 1. the shell ------------------------------------------------------------
        var before = snapshot(context);
        fCylinder(context, id + "shellOuter", {
                "bottomCenter" : vector(0 * meter, 0 * meter, definition.zFwd),
                "topCenter" : vector(0 * meter, 0 * meter, definition.zAft),
                "radius" : definition.shellOd / 2
        });
        var shell = madeBy(context, before);

        before = snapshot(context);
        fCylinder(context, id + "shellInner", {
                "bottomCenter" : vector(0 * meter, 0 * meter, definition.zFwd - OVER),
                "topCenter" : vector(0 * meter, 0 * meter, definition.zAft + OVER),
                "radius" : definition.shellId / 2
        });
        opBoolean(context, id + "hollow", {
                "tools" : madeBy(context, before),
                "targets" : shell,
                "operationType" : BooleanOperationType.SUBTRACTION
        });

        // ---- 2. additive bodies, four quadrants --------------------------------------
        var adds = [];
        for (var q = 0; q < 4; q += 1)
        {
            // collar boss
            adds = append(adds, radialCylinder(context, id + ("collar" ~ q), q,
                    definition.collarInnerR, definition.shellOd / 2, definition.zHinge,
                    definition.collarOd, 0 * meter));

            // servo tray
            adds = append(adds, quadrantCuboid(context, id + ("tray" ~ q), q,
                    vector(definition.trayFlangeR, -definition.trayWidth / 2, definition.trayFwdZ),
                    vector(definition.trayBackR, definition.trayWidth / 2, definition.trayAftZ)));

            // two webs, tray back out into the shell wall
            for (var sgn in [-1, 1])
            {
                var yOuter = sgn * definition.trayWidth / 2;
                var yInner = yOuter - sgn * definition.webThk;
                adds = append(adds, quadrantCuboid(context, id + ("web" ~ q ~ (sgn > 0 ? "p" : "m")), q,
                        vector(definition.trayBackR, min(yInner, yOuter), definition.trayFwdZ),
                        vector(definition.shellId / 2 + OVER, max(yInner, yOuter), definition.trayAftZ)));
            }

            // clamp bosses: tray extended inboard to the flange's own inboard face, at
            // each screw row, so the retainer bar lands on boss and flange together.
            // Index the id by ROW NUMBER, not by the Z value: an id component built by
            // concatenating a ValueWithUnits is not a valid identifier.
            var rows = [definition.screwZ1, definition.screwZ2];
            for (var k = 0; k < size(rows); k += 1)
            {
                var zRow = rows[k];
                // Clamp the boss to the tray's own extent. Unclamped it runs 1.7 mm past
                // each end of the tray as a 1 mm-thick unsupported tab -- which prints,
                // and then snaps off in a bag of parts.
                var zLo = max(zRow - definition.insertDia, definition.trayFwdZ);
                var zHi = min(zRow + definition.insertDia, definition.trayAftZ);
                adds = append(adds, quadrantCuboid(context, id + ("boss" ~ q ~ "r" ~ k), q,
                        vector(definition.bossFaceR, -definition.trayWidth / 2, zLo),
                        vector(definition.trayFlangeR, definition.trayWidth / 2, zHi)));
            }
        }
        // Shell FIRST: a union takes the identity of its first tool.
        opBoolean(context, id + "join", {
                "tools" : qUnion(concatenateArrays([[shell], adds])),
                "operationType" : BooleanOperationType.UNION
        });

        // ---- 3. subtractive bodies ---------------------------------------------------
        var cuts = [];
        for (var q = 0; q < 4; q += 1)
        {
            // collar bore, printed undersize and reamed after bonding
            cuts = append(cuts, radialCylinder(context, id + ("bore" ~ q), q,
                    definition.collarInnerR - OVER, definition.shellOd / 2 + OVER,
                    definition.zHinge, definition.collarBore, 0 * meter));

            // Servo window: clears the CASE, so it runs the case's length and cuts the
            // full thickness of the tray.
            cuts = append(cuts, quadrantCuboid(context, id + ("win" ~ q), q,
                    vector(definition.bossFaceR - OVER, -definition.windowWid / 2, definition.windowFwdZ),
                    vector(definition.trayBackR + OVER, definition.windowWid / 2,
                           definition.windowFwdZ + definition.windowLen)));

            // Flange relief: clears the FLANGE, which is 6 mm longer than the case and
            // sits in exactly the band the clamp bosses occupy. Without this the bosses
            // and the servo's own flange want the same 1 mm of radius and the servo will
            // not seat -- a clash an end-on view does not show, because it is hidden
            // behind the tray. Longer in Z than the window, shallower in R.
            cuts = append(cuts, quadrantCuboid(context, id + ("flange" ~ q), q,
                    vector(definition.bossFaceR - OVER, -definition.windowWid / 2, definition.trayFwdZ - OVER),
                    vector(definition.trayFlangeR, definition.windowWid / 2, definition.trayAftZ + OVER)));

            // heat-set insert holes, blind from the boss face outward
            var rows = [definition.screwZ1, definition.screwZ2];
            for (var k = 0; k < size(rows); k += 1)
            {
                for (var sgn in [-1, 1])
                {
                    cuts = append(cuts, radialCylinder(context,
                            id + ("ins" ~ q ~ "r" ~ k ~ (sgn > 0 ? "p" : "m")), q,
                            definition.bossFaceR - OVER,
                            definition.bossFaceR + definition.insertDepth,
                            rows[k], definition.insertDia, sgn * definition.clampY));
                }
            }
        }
        opBoolean(context, id + "carve", {
                "tools" : qUnion(cuts),
                "targets" : qUnion([shell]),
                "operationType" : BooleanOperationType.SUBTRACTION
        });

        // ---- 4. the retainer bar, as a SECOND part -----------------------------------
        // One bar, modelled once at quadrant 0 forward row. Eight are needed; they are
        // identical, so the Part Studio carries one and the print is set to eight.
        if (definition.buildRetainer)
        {
            before = snapshot(context);
            fCuboid(context, id + "retainer", {
                    "corner1" : vector(definition.bossFaceR - definition.retThk,
                                       -definition.trayWidth / 2,
                                       definition.screwZ1 - definition.insertDia),
                    "corner2" : vector(definition.bossFaceR,
                                       definition.trayWidth / 2,
                                       definition.screwZ1 + definition.insertDia)
            });
            var bar = madeBy(context, before);
            var holes = [];
            for (var sgn in [-1, 1])
            {
                holes = append(holes, radialCylinder(context,
                        id + ("rethole" ~ (sgn > 0 ? "p" : "m")), 0,
                        definition.bossFaceR - definition.retThk - OVER,
                        definition.bossFaceR + OVER,
                        definition.screwZ1, definition.insertDia * 0.7,
                        sgn * definition.clampY));
            }
            opBoolean(context, id + "retholes", {
                    "tools" : qUnion(holes),
                    "targets" : bar,
                    "operationType" : BooleanOperationType.SUBTRACTION
            });
        }
    });
