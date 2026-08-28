# OpenRocket correlation

Reproduce with `python scripts/openrocket_check.py`. Raw output in `out/openrocket_check.txt`.

## Why this check exists

The margin Monte Carlo (`scripts/robustness.py`, and §7 of `00-requirements.md`) found
that **CP prediction error dominates every other uncertainty in the design** — it outweighs
every mass line put together. Nothing in this repository can find an error in this
repository, so the only way to attack that uncertainty is a second, independently written
Barrowman implementation. OpenRocket is that second opinion.

The comparison is automated rather than done by hand in the GUI. A one-off manual check
goes stale the moment the design changes, and this design changed twice while the check
was being built.

## Method

`out/RocketSenior.ork` is regenerated on every run of `scripts/openrocket_check.py`, so it
is always current — and so hand edits made in the OpenRocket GUI and saved back to that
path are overwritten. Treat it as build output: open it to simulate and inspect, but make
changes in `design/configure.py` or `scripts/make_ork.py`.

`scripts/make_ork.py` writes an `.ork` (a zip containing one XML document) directly from
the same `DesignParams` the Python tool uses, so the two models cannot drift apart.
`tools/OrkCheck.java` then loads that file with OpenRocket 24.12's own engine headlessly
and reports CP, CG and mass.

Two deliberate choices about what is transferred and what is recomputed:

- **Subsystem masses are transferred** as mass components at identical stations. If
  OpenRocket used its own mass assumptions, a static margin disagreement would blend CP
  error with mass error and neither could be isolated. With mass pinned, a CP disagreement
  is purely aerodynamic.
- **Structural mass is recomputed** by OpenRocket from geometry and material density. That
  gives one genuinely independent number without polluting the CP comparison. Every budget
  line is either modelled geometrically or transferred, never both.

## Results, Mach 0.1, motor loaded

| Quantity | This tool | OpenRocket | Delta |
|---|---|---|---|
| Total length | 1361.1 mm | 1365.5 mm | +0.3% |
| Dry mass | 5.48 kg | 5.54 kg | +1.2% |
| Loaded mass | 6.10 kg | 6.17 kg | +1.1% |
| CG dry | 800.4 mm | 805.1 mm | +0.6% |
| CG loaded | 841.3 mm | 845.1 mm | +0.5% |
| **CNa, no body lift** | **26.57 /rad** | **26.48 /rad** | **−0.3%** |
| CNa, with body lift | 28.05 /rad | 26.48 /rad | −5.6% |
| CP, no body lift | 1009.2 mm | 1022.7 mm | +1.3% (+0.17 cal) |
| CP, with body lift | 995.8 mm | 1022.7 mm | +2.7% (+0.34 cal) |
| Static margin, loaded | 1.95 cal | 2.24 cal | +0.29 cal |

Masses and CG reflect the real KST X08 Plus servos (9 g each) rather than the earlier 55 g
budget placeholder, and include the 100 g of nose ballast the design now carries. The
aerodynamic rows are unchanged by both, as they should be.

The ballast is transferred into the `.ork` as a mass component **inside the nose cone**.
That needed a fix: `make_ork.py`'s station-to-component mapping only searched body tubes,
so a station forward of the first tube fell through to a last-tube fallback and put the
ballast 750 mm aft of where it belongs. The symptom was a CG disagreement that grew to
+2.3% while masses still matched — worth remembering as the shape this class of bug takes.

OpenRocket resolved the motor exactly: `J449 | 1261J449-15A | 321.0 mm | 54.0 mm |
2.76 s | 1260 N·s | 1.122 kg launch | 0.498 kg empty`, matching the `.eng` file. No load
or geometry warnings.

The length figure differs only because OpenRocket measures to the aft fin tip trailing
edge, which sweeps 4.4 mm past the tail. The airframe itself matches to the micron.

## Reading the numbers

**The headline is CNa agreeing to 0.3%.** Two independently written Barrowman
implementations landing within a third of a percent on total normal force slope means
neither contains a coding error in the nose, canard or aft fin terms. That was the thing
most worth ruling out.

**The CP gap is explained, not mysterious.** OpenRocket's Barrowman runs at zero angle of
attack and therefore carries no body lift term at all. This tool includes a Galejs
body-lift correction linearised about 4°, which adds normal force at the body centroid,
well forward of the fins, and so pulls CP forward. Switch it off and the gap falls from
0.34 to 0.17 caliber — and the residual 0.17 cal is the ordinary difference between two
implementations of the fin-body interference factor and the fin CP formula.

**The disagreement is in the safe direction.** OpenRocket thinks the rocket is *more*
stable than this tool does. The airframe was sized against the pessimistic of the two, so
the real vehicle should have more margin than the design assumed, not less.

**Structural mass agrees to 1.2%**, which is a better result than expected given this tool
estimates tube mass from a mean-diameter thin-wall approximation and nose mass from a
wetted-area approximation.

## What this does not prove

Two implementations agreeing tells you neither has a coding error. It does **not** tell
you Barrowman is right about this airframe. Both tools share the same theory, and that
theory has two limitations that matter here:

1. **It does not model canard-to-fin interference at all.** The roll coupling analysis in
   `design/control.py` — the entire reason this project has canards — is invisible to both
   tools. OpenRocket cannot validate it because OpenRocket does not model it.
2. **Barrowman is a slender-body, small-angle, subsonic theory.** It is being applied to a
   vehicle with a large forward lifting surface deliberately operated at deflection, which
   is outside what it was derived for.

Only flight data settles either point. That is what the GV-1 open-loop deflection sweep is
for: command a known canard deflection, log the resulting roll rate and angle of attack,
and fit the actual interference factors before closing any control loop.

## Effect on the design

The Monte Carlo assumed a CP uncertainty of 0.35 caliber, 1σ. The like-for-like
disagreement between two implementations came in at 0.17 cal, comfortably inside that. The
assumption is kept as is — one cross-check constrains implementation error, not theory
error, and theory error is the larger worry for this configuration — but there is now
evidence behind it rather than judgement alone.

No design change follows from this check. That is the good outcome.
