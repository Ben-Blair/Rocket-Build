# 13. Software-in-the-loop demo: closing the roll loop before any hardware

`scripts/sil_demo.py` closes L1 (roll hold), bank-to-turn, and the R12 failsafe entirely in
software, against this repo's own aero/mass/motor model. It is Step 4's items 3-5 done in
the order docs/01 prescribes them ("write [safety logic] before the controller, not after"),
run before there is any hardware to put it in the loop with. It does not touch the frozen
airframe in `design/configure.py`, does not open CFD, and does not reshape a canard.

## How to run it

```bash
python scripts/sil_demo.py            # magnetometer-aided roll estimate (default)
python scripts/sil_demo.py --no-mag   # gyro-only dead reckoning, to see it drift
```

Writes `out/sil_demo.png` (roll, canard commands, path turn, altitude — two columns, one
per launch case) and `out/sil_demo.txt` (the same numbers as text, plus PASS/FAIL checks).
Takes a few seconds; nothing is committed by running it.

## What it proves

Two cases, same airframe, same control law: `elevation_deg=28` (R15's horizontal mode) and
`elevation_deg=85` (R15's vertical mode, 5° off vertical). In both:

1. **L1 — roll hold.** An assumed 30°/s rail-exit roll-rate disturbance (not measured — see
   the script's docstring) is nulled and roll held at the commanded angle using a GYRO
   ESTIMATE, not the true state — optionally magnetometer-aided, same as the airframe's real
   sensor set (`design/estimation.py`). Checked at the *end* of the hold phase, not the peak
   over it: canards have no authority below `Q_MIN`, so the vehicle free-drifts through the
   first fraction of a second no controller can do anything about. Both cases settle to
   0.02° of roll error with the magnetometer aiding on; gyro-only settles to ~0.2° over the
   same window — small on this timescale, but the direction of the effect is the same one
   docs/07 found: gyro-only roll drifts, and the dominant term is the gyro's SCALE FACTOR
   error during the fast bank-to-turn snap, not its bias or noise.
2. **Bank-to-turn.** Once the estimate is within 3° of the 90° bank target, the canards pull
   `DEFLECTION_LIMIT_DEG` (9.2°) in the banked plane. Peak turn rate driven by the canard
   force alone comes out to 9.40°/s (horizontal) and 7.49°/s (vertical) — within a few
   percent of docs/12's frozen 9.76°/s and docs/11's 7.31°/s, which is the cross-check that
   matters: this script's closed loop is flying the same airframe/aero everything else in
   the repo flies, not a different one.
3. **R12 failsafe.** A fault is injected mid-pull. Both canard channels' COMMANDS ramp to
   centred over 0.35 s (not 0.5 s — see the correction below), and the lagged surfaces
   PASS the check that they are within 0.15° of zero by the 0.5 s latency R12 requires,
   regardless of what the guidance law wanted next. On the horizontal case the canards are
   additionally forced to centre, unconditionally, once the vehicle is *descending* below
   50 m AGL — this catches the fault-independent half of R12, the "reaches the ground with
   the canards fully effective" case docs/00 describes.

**Correction, 2026-09-26 — the roll loop was unstable and this demo could not see it.** The
original roll law was proportional-only, `ROLL_KP = 1.0`, against an actuator modelled as a
pure 667°/s slew limit with no lag. That model has no phase, so the loop looked perfect.
With any plausible servo lag it is not: the roll plant is ~300°/s per degree of canard with
a 17–20 ms time constant, and the Routh limit on Kp is 0.29 at a 30 ms servo lag
(`scripts/roll_bandwidth.py` section 3). Now:

- The law is PD on the gyro: `delta = 0.07·(phi_cmd − phi) − 0.0024·p`, gains in
  `design/control.py` (`ROLL_KP`, `ROLL_KD`), derived in `scripts/roll_bandwidth.py`
  section 4: ≥ 45° phase margin at the planned 71 Hz loop with 10–30 ms servo lag, ≥ 38° at
  60 ms, ~3 Hz crossover at max q (slower, with more margin, at lower speed).
- The servo is `control.servo_step`: slew limit plus a first-order lag, **SERVO_LAG_S = 30 ms,
  assumed** — the KST datasheet gives no lag. The controller output takes effect one loop
  period later, and the servo and roll axis are stepped at 1 kHz inside the 100 Hz loop.
- Under this model the old Kp = 1.0 limit-cycles at ~32° peak-to-peak and fails the roll-hold
  check; the new gains hold to 0.05–0.13° at 0–60 ms servo lag.
- The same lag broke R12: ramping the command to zero over the full 0.5 s left the surface
  ~0.7° off at 0.5 s, because the surface trails the command. The ramp is now 0.35 s
  (`R12_RAMP_S`), which leaves ~150 ms for latency and lag. **Firmware must do the same**:
  R12's 0.5 s is a surface position requirement, not a command one.
- `scripts/sil_guidance.py` uses the same roll gains and roll servo model. Its pitch/yaw
  channels are still slew-only and their gains (Kp 1.2, Kd 0.35) are unchecked against lag.

The servo bench test (docs/15 C1) turns the assumed 30 ms into a number; re-run
`scripts/roll_bandwidth.py` with it and it will say whether the gains still hold.

**A bug the first draft of this script had, worth recording because it is exactly the kind
of thing a SIL demo exists to catch on the bench rather than in the air:** gating the L1
roll-hold loop on `z >= 50 m` for the horizontal case (reusing R12's altitude number in the
wrong place) held the canards off for the first ~2 s of flight, because a 28° rail does not
climb through 50 m quickly — reproducing, in software, exactly the failure R12 exists to
prevent, just earlier. The fix was gating R12's floor on *descending* below it, not merely
being below it, since the requirement's own rationale (docs/00) is about proximity to ground
impact, not altitude in general.

## What it does not prove

- **Nothing about wake interference.** `roll_authority` and `InterferenceModel` here are the
  same ones every other script in the repo uses — docs/00 section 5's weakest link. Closing
  this loop in software cannot validate the aerodynamics it runs on; GV-2's open-loop
  deflection sweep is still the only thing that turns it into a measurement.
- **Nothing about timing or embedded execution.** The loop runs at 100 Hz using an EXACT
  analytic update for the roll axis (a closed-form exponential, not a fixed-step
  integrator), which sidesteps the ~20 ms roll time constant's stability demands entirely.
  Real firmware still needs the ≥1 kHz quaternion propagation docs/07 calls for; this script
  says nothing about whether the board can hit that rate with margin.
- **The magnetometer is a virtual roll-angle sensor here**, with an angular noise sigma
  derived the same way `design/estimation.py`'s error budget derives one — not a 3-axis
  field model with body attitude in it.
- **No wind, no thrust misalignment, no measured tip-off rate**, and no descent-under-drogue
  dynamics past the vertical case's apogee cutoff.
- **This is not hardware-in-the-loop.** Nothing here has touched a servo, a real IMU, or a
  flight computer's scheduler. That is Step 4 item 3, still ahead of this script.

See `scripts/sil_demo.py`'s module docstring for the full version of all of the above.
