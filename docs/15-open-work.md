# 15. Open work — CFD, roll bandwidth, L2/L3

Written 2026-09-26. This is a HANDOFF, not a result. It records what was built in one session,
what it found, and — the point of the file — **what is unfinished, wrong, or unverified**, so
the next person or session does not have to rediscover it.

Nothing in this session touched `design/configure.py`. The airframe is not moved.

---

## A. Findings that are established

**A1. SU2 confirms the repo's static stability, independently of Barrowman.** Inviscid Euler,
Mach 0.45, 1.85M cells, α = 3°, canards neutral (`out/cfd/alpha3_coarse/`):

| | SU2 | repo (`out/baseline.txt`) |
|---|---|---|
| CP from nose | 980 mm | 975 mm |
| CN at 3° | 2.08 | 2.22 |

0.06 cal on CP. Better than the OpenRocket cross-check (`docs/03`) and from a method that
shares no theory with it. R1 and the static margin survive a genuinely independent check.

**A2. The canard chordwise CP is NOT at 0.25 MAC, and two independent methods agree.**
`design/packaging.hinge_moment` assumes `cp_frac = 0.25`, giving a 2.98 mm moment arm about the
hinge at 0.20 MAC. Measured:

| method | canard CP | hinge arm | vs design |
|---|---|---|---|
| `cfd/vlm.py`, body images, resolution-converged | 0.357 MAC | 9.37 mm | 3.14× |
| SU2 Euler, α = 3°, no deflection | 0.327 MAC | 7.58 mm | 2.54× |
| design assumption | 0.250 MAC | 2.98 mm | — |

A 10:1-taper, 42°-swept delta carries its load much further aft than thin-airfoil 0.25c. The
0.25 was a constant in the code, never computed for this planform, and correction 63's pointed
delta made it worse while being priced as cosmetic.

**If this holds at deflection it moves the servo torque margin from 2.07× to roughly 0.7×**,
i.e. the servo cannot hold the canard at the 9.2° cap and horizontal max q. See B1 — the
deflected case is the one that decides it and it did not finish.

**A3. The roll axis is far faster and higher-gain than the loop-rate requirement assumed.**
From `scripts/roll_bandwidth.py` sections 1–3, which are sound:

- roll time constant 17–20 ms, corner **8–10 Hz** — the fastest mode on the vehicle. The
  existing "loop rate ≥ 72 Hz" in `out/baseline.txt` was sized from the 3.6 Hz **pitch** mode.
- roll gain **283 °/s per degree** of canard (vertical max q), **321** (horizontal).
- The servo **slew rate is not the binding constraint**: at the ±2° R13 roll cap, 667 °/s is
  good to 53 Hz.
- What binds is **phase lag, which the KST datasheet does not publish.** Routh limit on a
  proportional roll-angle loop, `Kp_max = (τ_roll + τ_servo)/(τ_roll·τ_servo·gain)`:
  Kp_max ≈ 0.50 at a 10 ms servo, ≈ 0.29 at 30 ms.
- **`sil_demo.ROLL_KP = 1.0` is above that limit for every plausible servo lag** — 2× at
  optimistic, 4× at realistic. docs/13's "settles to <0.1° roll error" comes from an actuator
  model that is a pure rate limiter with no phase in it (`sil_demo.slew()`), which is the only
  actuator model in the repo.
- **RESOLVED 2026-09-26** — see B2 and C2. Roll law is now PD, Kp 0.07 / Kd 0.0024
  (`design/control.py`), and both SIL scripts model servo lag. docs/13 carries the correction.

**A4. L2 attitude authority runs out at 8 m/s crosswind.** `scripts/sil_guidance.py`:

| crosswind | attitude error RMS | peak | fraction of time at the 9.2° stop |
|---|---|---|---|
| 2 m/s | 3.6° | 8.4° | 1–3% |
| 4 m/s | 4.8° | 9.4° | 1–3% |
| 8 m/s | 10.1° | 18.7° | **54%** |

L2 holds in light wind and saturates at 8 m/s. Separately, the **largest α in the whole flight
is the rail-exit transient — 21° at 8 m/s wind**, before the loop is allowed to run (q < Q_MIN)
and with no canard authority available. That is geometry (8 m/s against a 20.6 m/s rail-exit
speed), it is what R1's static margin is carrying, and it is an argument for a **wind limit on
the launch card**.

**A5. `control.InterferenceModel` has no angle-of-attack term at all.** `strength()` is a
function of one variable, canard-to-fin spacing in calibers. Every roll number in the repo is
computed at the same interference strength whether the vehicle is at 0° or at the ~11° local
incidence bank-to-turn actually flies. The canard vortex pair is convected by crossflow, so at
incidence the 45° interdigitation stops being symmetric between windward and leeward fins — the
mechanism for an angle-dependent and possibly **asymmetric** induced roll is in the geometry.
Magnitude unknown. This is GV-2's job and cannot be closed on a bench.

**A6. `cfd/vlm.py` puts the roll interference far higher than the model.** Aft fins take back
**78%** of canard roll authority (body images, 0° incidence) against the model's **10.5%**. Sign
does not reverse (net +3.6 /rad), but the margin against reversal is much thinner than
`out/baseline.txt` claims. A VLM wake is a rigid flat sheet that never rolls up, which is
exactly the physics at issue, so SU2 gets the deciding vote — see B1.

---

## B. Unfinished — started, not done

**B1. The deflected SU2 case never finished.** `out/cfd/pitch6_coarse/` (±6° pitch pair) was
still running at ~575 iterations when the session ended, converging well (residual −3.9, CL
settled at 0.568, CD −0.210). **This is the single most valuable outstanding item**: it decides
A2's effect on the servo margin and gives SU2's verdict on A6.

To finish: `.venv-cfd/bin/python cfd/run.py --case pitch6 --level coarse --reduce-only`
once it stops, then compare `hinge_coeff` against `packaging.hinge_moment` at the same q.
Also worth running `--case trim9` (9.2° at 2° α, the actual design point) and `--case roll5`
(all four canards at +5°, which is the A6 case).

Note `run.py` reduces `CMy(MARKER)` etc. — SU2 8.5 writes per-marker columns with parentheses,
not `@`. That is already fixed; do not "fix" it again.

**B2. DONE 2026-09-26 — section 4 rewritten.** Fixed `simulate()` (dead line gone, the delay
queue now actually delays), added frequency-domain margins with 1.5 periods of loop delay, a
grid search that derives the gains from a stated PM/GM rule, and a nonlinear check that
shows Kp 1.0 limit-cycling and the new gains settling in 0.26–0.54 s. Original note kept:

~~`scripts/roll_bandwidth.py` section 4 is unreliable and its conclusion is unsupported.~~
Sections 1–3 (plant, rate limit, analytic Routh limit) are sound and are A3. Section 4's
time-domain simulation has a **dead line in the servo model** (a `... if False else 0.0`
statement left in from an edit) so the servo dynamics are not what the docstring says. Worse,
the section's written conclusion — "with Kd on the gyro the original Kp = 1.0 becomes usable
again" — is **contradicted by its own output table**, which still reports NO for every Kd row.
Either the Kd values swept are too small or the servo model is wrong. **Rewrite section 4 from
scratch; do not trust the printed table.** The analytic result in section 3 stands on its own.

**B3. `scripts/sil_guidance.py` contains one false claim.** Its report prints "run with --kd 0
and L2 oscillates instead of holding." It does not — results are bit-identical, because at 8 m/s
the loop is saturated 54% of the time (A4) and the rate term has nothing to act on. **Remove or
correct that sentence.** The four PASS checks are real, but "L2 attitude hold PASS" oversells a
10° RMS saturated result; report A4's wind table instead of a single verdict.

**B4. `design/control.pitch_damping_cm_q` is new and unverified.** Added this session for L2.
Gives Cm_q = −2530 /rad, hence **ζ = 0.079** — the 3.6 Hz pitch mode is nearly undamped and
rings ~2.2 s, longer than the control window. Derivation follows `roll_damping_cl_p`'s strip
argument exactly and reads its contributions from `aero.stability`, but **nothing has checked
it**. `sim/probe.py`'s T2 found three implementations of *roll* damping disagreeing by 2×;
assume the same risk here. Probe it against RocketPy the way `sim/probe.py` does.

**B5. No `docs/` write-up of A1–A6 beyond this file.** In particular `docs/00` §6.1's servo and
hinge rows, and `docs/13`'s roll-hold claim, both now have findings against them and neither has
been annotated. Nothing has been committed — `git status` shows `design/control.py` modified and
`cfd/`, `scripts/sil_guidance.py`, `scripts/roll_bandwidth.py`, `out/cfd/` untracked.

**B6. `cfd/` has no README.** `cfd/run.py`'s docstring points at one for SU2 install
instructions and it was never written. What it needs to say: SU2 8.5.0 is free (LGPL), no student
licence; a native arm64 build is at `~/opt/su2native/bin` (built from a git clone of the v8.5.0
tag with a conda `su2build` env supplying clang/OpenMPI/meson/ninja, because Homebrew is blocked
until `sudo xcodebuild -license accept` is run); `mpirun` comes from that same conda env; the
official x86_64 macOS binary is at `~/opt/su2/bin` as a fallback. Python deps are in `.venv-cfd`
(gmsh, numpy, scipy, matplotlib) — and `.venv-cfd/` should probably be gitignored.

---

## C. Never started

**C1. Servo bench test — now wanted for three separate reasons.** docs/14 already asks for a
current probe for the 1.15× continuous-duty margin. Add: (a) a **position** trace to get the
servo lag `τ_servo` that A3's whole answer turns on, and (b) hinge moment under representative
load, to close A2 experimentally. One test, three answers.

**C2. DONE 2026-09-26.** Rate term added (`control.ROLL_KD` on the gyro), in `sil_demo.py`
and `sil_guidance.py`. Found on the way: the lagged servo made the R12 failsafe miss its
0.5 s (surface trails command), so the command ramp is now 0.35 s — firmware must do the
same. Original note:

~~A rate term on the roll loop in `sil_demo.py`.~~ It has `ROLL_KP` only. A3 says
proportional-only is unstable at that gain, and the gyro rate signal is already in the sensor
model — it is free phase lead.

**C3. Re-derive the hinge line from the measured CP.** If A2 holds, moving the hinge aft toward
the real 0.33–0.36 MAC shrinks the moment arm back down. But `hinge.canard_hinge_station` is
0.20c of the MAC by construction and the shaft, four collars, four servos and four wall bores
are all dimensioned from it (docs/12 §13) — so this is a bay rebuild, not a constant change.
Price it before choosing between it, a gear ratio, and a lower deflection cap.

**C4. Mesh convergence study.** Only `coarse` has ever been meshed and run. `cfd/mesh.py` has
`medium` and `fine` levels that are untested, and coarse already gives 1.85M cells, so fine may
not fit in 17 GB. No grid-convergence check exists, so every SU2 number above is single-grid.

**C5. Viscous / stall answer.** Euler cannot see separation, so **nothing here validates the 12°
stall limit** in `control.STALL_LIMIT_DEG` or the 1.0° of headroom at the 9.2° cap. That needs
RANS with a turbulence model and a boundary-layer-resolved mesh — a much larger job, and
arguably a wind-tunnel question instead.

**C6. GV-2 at several angles of attack.** A5 and A6 both end here. The existing GV-2 plan is an
open-loop deflection sweep; it needs to be flown **at more than one α** to get the angle
dependence, and that changes the flight-card design.

**C7. Pitch/yaw attitude gains against servo lag.** `sil_guidance.py`'s `ATT_KP 1.2 /
ATT_KD 0.35` were only ever run against a slew-only actuator — the same blind spot that hid
the roll instability. The pitch plant is slower (3.6 Hz, ζ 0.079), so it is likely less
severe, but no one has checked. Do the roll_bandwidth.py analysis for pitch.

---

## D. Notes for whoever picks this up

- `cfd/vlm.py` validates itself first (Helmbold lift slope at three aspect ratios; chordwise CP
  against lifting-line at AR 8 and slender-wing theory for deltas) and passes. Trust its
  *method*; its *wake* is the known weakness.
- `cfd/mesh.py` builds the nose as a **loft through circular sections**, not a revolve. A
  surface of revolution is degenerate at the tip and gmsh falls back to MeshAdapt, which took
  14+ minutes without finishing; the loft meshes in 1.1 s. It costs a 0.4 mm blunted tip —
  1e-4 of reference area, and the one place the mesh is not the frozen geometry. Do not
  "simplify" it back to a revolve.
- Body tube is built as separate cylindrical bands rotated 22.5° so seams miss every panel root,
  for the same meshing reason.
- Everything in `cfd/` reads geometry from `design/configure.py` and
  `hinge.canard_hinge_station`. Keep it that way.
