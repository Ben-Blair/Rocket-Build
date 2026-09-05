// Reads OpenRocket's own ROLL DAMPING coefficient for the baseline vehicle.
//
// Why this exists. sim/probe.py found that RocketPy's cld_omega carries a spurious
// Af/reference_area factor, and that removing it still leaves ~1.7x between RocketPy and
// design/control.roll_damping_cl_p(). Nothing in this repository, and nothing in RocketPy,
// can settle which of those two is right -- they are two standard methods disagreeing about
// the per-fin lift slope that roll damping needs. This is the third implementation.
//
// READ THE RESULT WITH ONE CAVEAT. RocketPy's own fin_num_correction() cites
// "Niskanen, S. (2013), OpenRocket technical documentation" in its source, so RocketPy and
// OpenRocket share lineage on exactly the fin-count question at issue here. If those two
// agree against design/, that is weaker evidence than two genuinely independent codes
// agreeing -- it may only show that one borrowed from the other. If they DISAGREE, that is
// strong, because it means the borrowing did not extend to this term.
//
// Driven by scripts/openrocket_roll_check.py.

import java.io.File;

import info.openrocket.core.aerodynamics.AerodynamicForces;
import info.openrocket.core.aerodynamics.BarrowmanCalculator;
import info.openrocket.core.aerodynamics.FlightConditions;
import info.openrocket.core.document.OpenRocketDocument;
import info.openrocket.core.file.GeneralRocketLoader;
import info.openrocket.core.logging.WarningSet;
import info.openrocket.core.rocketcomponent.FlightConfiguration;
import info.openrocket.core.startup.OpenRocketCore;

public class OrkRollDamp {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: OrkRollDamp <file.ork> [mach] [velocity_m_s] [rollrate_rad_s]");
            System.exit(2);
        }
        double mach = args.length > 1 ? Double.parseDouble(args[1]) : 0.393;
        double velocity = args.length > 2 ? Double.parseDouble(args[2]) : 133.0;
        double rollRate = args.length > 3 ? Double.parseDouble(args[3]) : 1.0;

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
        conditions.setVelocity(velocity);
        conditions.setRollRate(rollRate);

        AerodynamicForces forces = aero.getAerodynamicForces(config, conditions, warnings);

        System.out.printf("ORK_REF_LENGTH_M %.6f%n", conditions.getRefLength());
        System.out.printf("ORK_REF_AREA_M2 %.8f%n", conditions.getRefArea());
        System.out.printf("ORK_MACH %.4f%n", conditions.getMach());
        System.out.printf("ORK_VELOCITY %.4f%n", conditions.getVelocity());
        System.out.printf("ORK_ROLL_RATE %.6f%n", conditions.getRollRate());
        System.out.printf("ORK_CROLL_DAMP %.8f%n", forces.getCrollDamp());
        System.out.printf("ORK_CROLL_FORCE %.8f%n", forces.getCrollForce());
        System.out.printf("ORK_CROLL %.8f%n", forces.getCroll());
        for (var w : warnings) {
            System.out.printf("ORK_WARNING %s%n", w.toString());
        }
    }
}
