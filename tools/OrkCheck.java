// Loads a .ork with OpenRocket's own engine and prints the numbers worth comparing.
//
// This exists so the OpenRocket cross-check is a command you run rather than a manual
// transcription exercise. The margin Monte Carlo in scripts/robustness.py found that CP
// prediction error dominates every other uncertainty in the design, and the only way to
// attack that is a second, independently written Barrowman implementation. Reading the
// number out of the GUI by hand works once; this works every time the design changes.
//
// Driven by scripts/openrocket_check.py -- see there for the compile and run invocation.

import info.openrocket.core.aerodynamics.BarrowmanCalculator;
import info.openrocket.core.aerodynamics.FlightConditions;
import info.openrocket.core.document.OpenRocketDocument;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.logging.WarningSet;
import info.openrocket.core.masscalc.MassCalculator;
import info.openrocket.core.masscalc.RigidBody;
import info.openrocket.core.rocketcomponent.FlightConfiguration;
import info.openrocket.core.startup.OpenRocketCore;
import info.openrocket.core.util.Coordinate;

import java.io.File;

public class OrkCheck {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: OrkCheck <file.ork> [mach]");
            System.exit(2);
        }
        double mach = args.length > 1 ? Double.parseDouble(args[1]) : 0.1;

        OpenRocketCore.initialize();

        GeneralRocketLoader loader = new GeneralRocketLoader(new File(args[0]));
        OpenRocketDocument doc = loader.load();
        FlightConfiguration config = doc.getRocket().getSelectedConfiguration();
        config.setAllStages();

        WarningSet warnings = new WarningSet();
        BarrowmanCalculator aero = new BarrowmanCalculator();
        FlightConditions conditions = new FlightConditions(config);
        conditions.setMach(mach);
        conditions.setAOA(0.0);

        Coordinate cp = aero.getCP(config, conditions, warnings);
        RigidBody launch = MassCalculator.calculateLaunch(config);
        RigidBody burnout = MassCalculator.calculateBurnout(config);
        RigidBody structure = MassCalculator.calculateStructure(config);

        double refLength = conditions.getRefLength();
        double smLoaded = (cp.x - launch.getCM().x) / refLength;
        double smBurnout = (cp.x - burnout.getCM().x) / refLength;

        System.out.printf("ORK_LENGTH_MM %.2f%n", doc.getRocket().getLength() * 1000.0);
        var bb = config.getBoundingBoxAerodynamic();
        System.out.printf("ORK_BBOX_X_MM %.2f .. %.2f%n", bb.min.x * 1000.0, bb.max.x * 1000.0);
        var bbAll = config.getBoundingBox();
        System.out.printf("ORK_BBOX_ALL_MM %.2f .. %.2f%n",
                bbAll.min.x * 1000.0, bbAll.max.x * 1000.0);
        System.out.printf("ORK_REF_LENGTH_MM %.3f%n", refLength * 1000.0);
        System.out.printf("ORK_STRUCTURE_MASS_KG %.4f%n", structure.getMass());
        System.out.printf("ORK_DRY_MASS_KG %.4f%n", burnout.getMass());
        System.out.printf("ORK_WET_MASS_KG %.4f%n", launch.getMass());
        System.out.printf("ORK_DRY_CG_MM %.2f%n", burnout.getCM().x * 1000.0);
        System.out.printf("ORK_WET_CG_MM %.2f%n", launch.getCM().x * 1000.0);
        System.out.printf("ORK_CP_MM %.2f%n", cp.x * 1000.0);
        System.out.printf("ORK_CNA %.4f%n", cp.weight);
        System.out.printf("ORK_SM_LOADED_CAL %.3f%n", smLoaded);
        System.out.printf("ORK_SM_BURNOUT_CAL %.3f%n", smBurnout);
        System.out.printf("ORK_MOTOR_COUNT %d%n", config.getActiveMotors().size());
        for (var mc : config.getActiveMotors()) {
            var m = mc.getMotor();
            System.out.printf("ORK_MOTOR %s | %s | len %.1f mm | dia %.1f mm | "
                            + "burn %.2f s | impulse %.0f Ns | launch %.3f kg | empty %.3f kg%n",
                    m.getCommonName(), m.getDesignation(),
                    m.getLength() * 1000.0, m.getDiameter() * 1000.0,
                    m.getBurnTimeEstimate(), m.getTotalImpulseEstimate(),
                    m.getLaunchMass(), m.getBurnoutMass());
        }

        for (info.openrocket.core.rocketcomponent.RocketComponent c
                : doc.getRocket().getAllChildren()) {
            double x = c.getComponentLocations().length > 0
                    ? c.getComponentLocations()[0].x : Double.NaN;
            System.out.printf("ORK_COMPONENT %-34s x=%8.2f len=%7.2f aft=%8.2f  %s%n",
                    c.getName(), x * 1000.0, c.getLength() * 1000.0,
                    (x + c.getLength()) * 1000.0, c.getClass().getSimpleName());
        }

        for (var w : warnings) {
            System.out.println("ORK_WARNING " + w.toString());
        }
        for (var w : loader.getWarnings()) {
            System.out.println("ORK_LOAD_WARNING " + w.toString());
        }
    }
}
