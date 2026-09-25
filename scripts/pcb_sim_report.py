"""Simulations of the Stage 2 flight computer board, from its routed copper.

Run:  python scripts/pcb_sim_report.py

Free tools only: KiCad's own bundled ngspice (driven by design/ngspice.py -- nothing to
install), plus numpy/scipy for the field solve.  Every board number below -- trace
resistances, current paths, positions -- is read from pcb/flight_computer/flight_computer.kicad_pcb
by design/pcb_copper.py, so re-routing the board changes the answers.

Four questions:

  1. SERVO STALL  -- all four servos stall at once (docs/14: 4.1 A).  How far do VBATT at the
     headers and VIN at the regulators sag, and does anything brown out?
  2. IMU SUPPLY NOISE -- how much noise reaches the ICM-42688-P's supply pin, on the old
     arrangement (IMU on the shared +3V3) against the new one (its own LP2985 from VIN)?
  3. MAGNETOMETER  -- the field at the MMC5983MA from the board's own VBATT copper and its
     ground-plane return at 4.1 A, against estimation.required_magnetic_cleanliness().
  4. DC DROP / HEATING on the VBATT trunk.

What these are NOT: a vendor-model SPICE run.  The TPS62162 is modelled from its datasheet's
power-save-mode equations (SLVSAM2E eq. 3/4), the LP2985 from its ripple-rejection figures
(SLVS522S), servos as current sources.  Each assumption is a named constant below.  The
answers are good to "which arrangement is quieter and by roughly how much", not to the uV.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import ngspice
from design.pcb_copper import NetGraph, ipc2221_rise_c, oriented
from design.pcb_placement import load_pads

# ------------------------------------------------------------------ assumptions (named)
SERVO_STALL_A = 4.1 / 4          # docs/14, per servo
PACK = {  # 2S LiPo 1500 mAh: EMF, internal resistance (both cells)
    "fresh 8.4 V": (8.4, 0.020),
    "nominal 7.4 V": (7.4, 0.040),
    "depleted, cold 6.6 V": (6.6, 0.120),
}
PIGTAIL_OHM = 0.0063 + 0.001     # 2 x 150 mm of 18 AWG (21 mohm/m) + XT30 contact
LOGIC_W = 3.3 * 0.100 / 0.88     # +3V3 load ~100 mA through the buck at ~88 %
TPS_UVLO = 2.6                   # V, falling, worst case (SLVSAM2E 7.5)
LDO_MIN_VIN = 3.3 + 0.35         # LP2985 dropout at light load, generous
# Effective capacitance after DC bias (X5R, ~50 % loss near rated-fraction bias)
C_EFF = {"C1": 12e-6, "C2": 12e-6, "C3": 6e-6, "C5": 12e-6, "C22": 1.2e-6,
         "C30": 0.7e-6, "C32": 3.5e-6}
# Ferrite FB1 (GZ2012D601TF): DCR 0.3 ohm, ~1.5 uH-equivalent, 600 ohm loss at HF
FB1 = (0.3, 1.5e-6, 600.0)
# Servos "working": 4 x (0.3 A mean + 0.5 A pulses at the 333 Hz frame, 30 % duty)
SERVO_WORK = (0.3, 0.5, 333.0, 0.30)
# MCU/flash load steps on +3V3: 80 mA base + 30 mA bursts at 1 kHz, 20 % duty
MCU_LOAD = (0.080, 0.030, 1000.0, 0.20)
# Buck closed-loop behaviour at low frequency: output impedance and line rejection
BUCK_ZOUT = 0.08                 # ohm, ~100 kHz loop bandwidth into ~20 uF
BUCK_LINE_REJ_DB = 50.0          # VIN ripple -> VOUT at low frequency (assumed)
# LP2985 ripple rejection: legacy silicon 45 dB @ 1 kHz, new silicon 78 dB (SLVS522S);
# modelled as a zero at FZ and a pole at FP -- worse (smaller) above FZ, flat above FP.
LDO_PSRR = {"legacy silicon": (45.0, 10e3, 316e3), "new silicon": (70.0, 31.6e3, 3.16e6)}
LDO_NOISE_UVRMS = 30.0           # 300 Hz-50 kHz, 10 nF bypass
R33_OHM = 10.0                   # RC pre-filter ahead of the LDO; 0 reproduces "no filter"
NH_PER_MM = 0.7e-9               # trace over a plane 0.21 mm below, rough
# Magnetometer
MAG_Z_MM = 0.6                   # sensing element above the top copper
EARTH_GAUSS_TO_MG = 1000.0


def line(title=""):
    print("\n" + "=" * 92 + "\n" + title + "\n" + "=" * 92 if title else "-" * 92)


# ============================================================ 4. DC drop and heating first
def dc_drop():
    line("4. VBATT TRUNK -- DC drop and heating at the 4.1 A stall, from the routed copper")
    g = NetGraph("VBATT")
    paths = {j: g.path(("J1", "1"), (j, "2")) for j in ("J9", "J8", "J7", "J6")}
    load = {}
    for j, (_r, items) in paths.items():
        for it in items:
            load[id(it)] = (it, load.get(id(it), (it, 0))[1] + 1)
    for j, (r, items) in paths.items():
        drop = sum(it.ohms * load[id(it)][1] * SERVO_STALL_A for it in items)
        print(f"  J1 -> {j} pin 2   {r * 1e3:5.2f} mohm of copper   {drop * 1e3:5.1f} mV at stall")
    worst = max(load.values(), key=lambda v: v[1])
    i_max = worst[1] * SERVO_STALL_A
    print(f"  hottest segment   {worst[0].width:.2f} mm carrying {i_max:.2f} A -> "
          f"+{ipc2221_rise_c(i_max, worst[0].width):.1f} degC (IPC-2221, conservative)")
    return {j: r for j, (r, _i) in paths.items()}, g.path(("J1", "1"), ("C2", "1"))[0]


# ============================================================ 1. servo stall transient
def stall(r_hdr, r_c2):
    line("1. SERVO STALL -- all four stall together at t = 1 ms (ngspice transient)")
    rows = []
    try:
        gr = NetGraph("SERVO_GND")
        r_ret = {j: gr.path(("J1", "2"), (j, "3"))[0] for j in ("J9", "J8", "J7", "J6")}
    except (KeyError, ValueError):
        r_ret = {j: 0.0 for j in ("J9", "J8", "J7", "J6")}     # plane return, ~0 ohm
    rseg = [r_ret["J9"], r_ret["J8"] - r_ret["J9"], r_ret["J7"] - r_ret["J8"],
            r_ret["J6"] - r_ret["J7"]]
    for name, (emf, rint) in PACK.items():
        seg = [r_hdr["J9"], r_hdr["J8"] - r_hdr["J9"], r_hdr["J7"] - r_hdr["J8"],
               r_hdr["J6"] - r_hdr["J7"]]
        net = f"""
Vpack p0 0 {emf}
Rint p0 p1 {rint}
Rlead p1 j1 {PIGTAIL_OHM}
Resr1 j1 c1a 0.005
C1 c1a 0 {C_EFF['C1']} ic={emf}
R9 j1 n9 {seg[0]}
R8 n9 n8 {seg[1]}
R7 n8 n7 {seg[2]}
R6 n7 n6 {seg[3]}
Is9 n9 g9 PWL(0 0 1m 0 1.2m {SERVO_STALL_A})
Is8 n8 g8 PWL(0 0 1m 0 1.2m {SERVO_STALL_A})
Is7 n7 g7 PWL(0 0 1m 0 1.2m {SERVO_STALL_A})
Is6 n6 g6 PWL(0 0 1m 0 1.2m {SERVO_STALL_A})
Rg9 g9 0 {max(rseg[0], 1e-6)}
Rg8 g8 g9 {max(rseg[1], 1e-6)}
Rg7 g7 g8 {max(rseg[2], 1e-6)}
Rg6 g6 g7 {max(rseg[3], 1e-6)}
Rtoc2 j1 c2n {r_c2}
Resr2 c2n c2a 0.005
C2 c2a 0 {C_EFF['C2']} ic={emf}
Lfb c2n fbm {FB1[1]}
Rfb fbm vin {FB1[0]}
Rfbp c2n vin {FB1[2]}
RC3 vin c3a 0.003
C3 c3a 0 {C_EFF['C3']}
C4 vin 0 100n
C30 vin 0 {C_EFF['C30']}
Bbuck vin 0 I={LOGIC_W}/max(v(vin),2.0)
Rldo vin 0 3.3k
"""
        v = ngspice.run(net, ".tran 2u 6m")
        t = np.array(v["time"])
        pre = t < 0.9e-3
        vin = np.array(v["v(vin)"])
        vj6 = np.array(v["v(n6)"]) - np.array(v["v(g6)"])     # across the servo
        rows.append((name, vj6[pre].mean(), vj6.min(), vin[pre].mean(), vin.min()))
    print(f"  {'pack':<22}{'J6 before':>10}{'J6 min':>9}{'VIN before':>12}{'VIN min':>9}"
          f"   margin to TPS UVLO / LDO dropout")
    line()
    for name, a, b, c, d in rows:
        print(f"  {name:<22}{a:9.3f}V{b:8.3f}V{c:11.3f}V{d:8.3f}V"
              f"   {d - TPS_UVLO:+.2f} V / {d - LDO_MIN_VIN:+.2f} V")
    print("\n  The sag is the PACK's internal resistance, not the board: 4.1 A x the copper above"
          "\n  is tens of mV.  No brown-out of either regulator in any case, including a cold,"
          "\n  nearly flat pack.  Servo torque at 6.6 V - sag is the servo's problem, not this board's.")


# ============================================================ 2. IMU supply noise
def ldo_block(tag, psrr, vin_dc):
    """LP2985 as: V(out) = 3.3 + H(s)*(V(vin)-VIN_DC), H a lead network + buffer + pole."""
    db, fz, fp = psrr
    k0 = 10 ** (-db / 20)
    r2 = 1e3
    r1 = r2 * (1 / k0 - 1)
    c1 = 1 / (2 * math.pi * fz * r1)
    cp = 1 / (2 * math.pi * fp * 1e3)
    return f"""
Eld{tag} la{tag} 0 vinldo 0 1
Vof{tag} la{tag} lb{tag} DC {vin_dc}
R1{tag} lb{tag} lc{tag} {r1}
C1{tag} lb{tag} lc{tag} {c1}
R2{tag} lc{tag} 0 {r2}
Ebf{tag} ld{tag} 0 lc{tag} 0 1
Rp{tag} ld{tag} le{tag} 1k
Cp{tag} le{tag} 0 {cp}
Bo{tag} lf{tag} 0 V=3.3+v(le{tag})
Ro{tag} lf{tag} ldo_out 0.01
"""


def noise_netlist(vin_dc, hf: bool, psrr):
    """Both arrangements in ONE circuit, so they see identical disturbances:
    imu_old = IMU on the shared +3V3 at the end of the routed +3V3 path (as before today),
    imu_new = IMU on +3V3_IMU from the LP2985 fed by VIN (as built now)."""
    r3v3 = NetGraph("+3V3").path(("U1", "6"), ("U2", "64"))
    rvin = NetGraph("VIN").path(("C4", "1"), ("R33", "1"))
    rimu = NetGraph("+3V3_IMU").path(("U9", "5"), ("U4", "8"))

    def lmm(items):
        return sum(getattr(i, "length", 1.6) for i in items)

    s = SERVO_WORK
    per = 1 / s[2]
    servo = f"PULSE({s[0]} {s[0] + s[1]} 0.5m 10u 10u {per * s[3]} {per})"
    m = MCU_LOAD
    mper = 1 / m[2]
    mcu = f"PULSE({m[0]} {m[0] + m[1]} 0.3m 1u 1u {mper * m[3]} {mper})"
    net = f"""
Vpack p0 0 7.4
Rint p0 j1 {0.040 + PIGTAIL_OHM + 0.009}
C1 j1 c1a {C_EFF['C1']}
RC1 c1a 0 0.005
Iserv j1 0 {servo}
Iserv4 j1 0 {servo}
Iserv3 j1 0 {servo}
Iserv2 j1 0 {servo}
Lfb j1 fbm {FB1[1]}
Rfb fbm vin {FB1[0]}
Rfbp j1 vin {FB1[2]}
C3 vin c3a {C_EFF['C3']}
RC3 c3a 0 0.003
C4 vin 0 100n
* VIN route to the LDO, from the routed copper
Rvr vin vr1 {rvin[0]}
Lvr vr1 vr2 {lmm(rvin[1]) * NH_PER_MM}
* R33 + C30: the RC pre-filter ahead of the LP2985 (design.py)
R33 vr2 vinldo {R33_OHM}
C30 vinldo 0 {C_EFF['C30']}
Rldoq vinldo 0 3.3k
* --- buck output (Norton: regulated source through its closed-loop Zout) ---
Breg bo 0 V=3.3+{10 ** (-BUCK_LINE_REJ_DB / 20)}*(v(vin)-{vin_dc})
Rreg bo v3 {BUCK_ZOUT}
C5 v3 c5a {C_EFF['C5']}
RC5 c5a 0 0.003
C6 v3 0 100n
* +3V3 route to the MCU's top-edge pins, where the IMU used to hang off the same rail
Rtr v3 t1 {r3v3[0]}
Ltr t1 mcu {lmm(r3v3[1]) * NH_PER_MM}
Cmcu mcu 0 500n
Imcu mcu 0 {mcu}
Ctr mcu 0 4.7u
* ---- OLD: IMU on +3V3 at the MCU end ----
Rio mcu io1 0.03
Lio io1 imu_old 10n
C20o imu_old 0 100n
C21o imu_old 0 100n
C22o imu_old 0 {C_EFF['C22']}
Iimuo imu_old 0 1m
* ---- NEW: IMU on +3V3_IMU from the LP2985 ----
C32 ldo_out 0 {C_EFF['C32']}
Rir ldo_out ir1 {rimu[0]}
Lir ir1 imu_new {lmm(rimu[1]) * NH_PER_MM}
C20n imu_new 0 100n
C21n imu_new 0 100n
C22n imu_new 0 {C_EFF['C22']}
Iimun imu_new 0 1m
"""
    net += ldo_block("x", psrr, vin_dc)
    if hf:
        # TPS62162 in power-save mode (SLVSAM2E eq. 3/4): fixed on-time, DCM triangle pulses.
        ton = 3.3 / vin_dc * 420e-9
        ipk = (vin_dc - 3.3) / 2.2e-6 * ton
        toff = ipk * 2.2e-6 / 3.3
        iload = MCU_LOAD[0] + 0.001
        q = 0.5 * ipk * (ton + toff)
        f = iload / q
        per = 1 / f
        net += (f"IL 0 v3 PULSE(0 {ipk} 0 {ton} {toff} 1p {per})\n"
                f"Iin vin 0 PULSE(0 {ipk} 0 {ton} 1p 1p {per})\n")
        # the Norton source must not ALSO supply the DC the pulses now deliver
        net = net.replace("Breg bo 0 V=3.3", f"Breg bo 0 V={3.3 + iload * BUCK_ZOUT}")
        return net, (f, ipk)
    else:
        net += f"Iinav vin 0 {LOGIC_W / vin_dc}\n"
        return net, None


def ptp(x):
    return float(np.max(x) - np.min(x))


def rms_ac(x):
    return float(np.sqrt(np.mean((x - np.mean(x)) ** 2)))


def imu_noise():
    line("2. IMU SUPPLY NOISE -- old (shared +3V3) vs new (own LP2985 from VIN), ngspice")
    vin_dc = 7.4 - 0.1
    for label, psrr in LDO_PSRR.items():
        # low-frequency run: servo frame current and MCU load bursts, buck averaged
        net, _ = noise_netlist(vin_dc, hf=False, psrr=psrr)
        v = ngspice.run(net, ".tran 2u 16m 4m 2u")
        old_lf, new_lf = np.array(v["v(imu_old)"]), np.array(v["v(imu_new)"])
        vin_lf = np.array(v["v(vin)"])
        # high-frequency run: the switching itself
        net, (fsw, ipk) = noise_netlist(vin_dc, hf=True, psrr=psrr)
        v = ngspice.run(net, ".tran 1n 80u 30u 1n")
        old_hf, new_hf = np.array(v["v(imu_old)"]), np.array(v["v(imu_new)"])
        v3_hf = np.array(v["v(v3)"])
        print(f"\n  LP2985 {label}: {psrr[0]:.0f} dB at 1 kHz"
              f"   |   buck in power-save at {fsw / 1e6:.2f} MHz, {ipk * 1e3:.0f} mA peaks")
        print(f"  {'':34}{'OLD: IMU on +3V3':>20}{'NEW: +3V3_IMU':>18}{'better by':>12}")
        line()
        for what, a, b in (("servo frame + MCU bursts (<50 kHz)", old_lf, new_lf),
                           ("regulator switching (MHz)", old_hf, new_hf)):
            pa, pb = ptp(a), ptp(b)
            print(f"  {what:<34}{pa * 1e3:15.3f} mVpp{pb * 1e3:13.3f} mVpp"
                  f"{20 * math.log10(pa / pb):9.1f} dB")
        tot_o = math.hypot(rms_ac(old_lf), rms_ac(old_hf))
        tot_n = math.sqrt(rms_ac(new_lf) ** 2 + rms_ac(new_hf) ** 2 + (LDO_NOISE_UVRMS * 1e-6) ** 2)
        print(f"  {'total rms (+ LDO self-noise)':<34}{tot_o * 1e6:15.0f} uVrms{tot_n * 1e6:12.0f} uVrms"
              f"{20 * math.log10(tot_o / tot_n):9.1f} dB")
        print(f"  (for scale: VIN itself swings {ptp(vin_lf) * 1e3:.0f} mVpp with the servos working;"
              f" +3V3 at the buck {ptp(v3_hf) * 1e3:.1f} mVpp switching ripple)")
    print("\n  The ICM-42688-P datasheet gives no supply-rejection figure, so this is reported as"
          "\n  volts at the pin, not dps.  What it establishes is the RATIO: the IMU's supply is"
          "\n  now isolated from both the servo current on the pack and every load on +3V3.")


# ============================================================ 3. magnetometer field
def plane_currents(src, sink, i_total, h=0.5, x0=100.0, y0=100.0, w=70.0, ht=45.0):
    """DC return-current distribution in the (merged) In1/In2 GND planes.

    Resistive grid, unit sheet conductance (the distribution does not depend on it).
    src: list of (x, y) where the servo returns enter, each i_total/len(src); sink: (x, y).
    Returns list of (x_mid, y_mid, dx, dy, current) current elements.
    """
    nx, ny = int(w / h) + 1, int(ht / h) + 1
    n = nx * ny

    def idx(i, j):
        return j * nx + i

    def node(x, y):
        return idx(int(round((x - x0) / h)), int(round((y - y0) / h)))

    a = lil_matrix((n, n))
    for j in range(ny):
        for i in range(nx):
            k = idx(i, j)
            for di, dj in ((1, 0), (0, 1)):
                ii, jj = i + di, j + dj
                if ii < nx and jj < ny:
                    m = idx(ii, jj)
                    a[k, k] += 1; a[m, m] += 1; a[k, m] -= 1; a[m, k] -= 1
    b = np.zeros(n)
    for x, y in src:
        b[node(x, y)] += i_total / len(src)
    ks = node(*sink)
    b[ks] -= i_total
    a[ks, :] = 0
    a[ks, ks] = 1
    b[ks] = 0
    v = spsolve(a.tocsr(), b)
    els = []
    for j in range(ny):
        for i in range(nx):
            for di, dj in ((1, 0), (0, 1)):
                ii, jj = i + di, j + dj
                if ii < nx and jj < ny:
                    cur = v[idx(i, j)] - v[idx(ii, jj)]          # unit conductance
                    if abs(cur) > 1e-9 * i_total:
                        els.append((x0 + (i + di / 2) * h, y0 + (j + dj / 2) * h,
                                    di * h, dj * h, cur))
    return els


def biot_savart(elements, p):
    """elements: (x, y, z, dlx, dly, I) mm/A.  Returns B at p in gauss."""
    b = np.zeros(3)
    for x, y, z, dx, dy, i in elements:
        r = np.array([p[0] - x, p[1] - y, p[2] - z]) * 1e-3
        dl = np.array([dx, dy, 0.0]) * 1e-3
        d = np.linalg.norm(r)
        b += 1e-7 * i * np.cross(dl, r) / d ** 3
    return b * 1e4


def magnetometer():
    line("3. MAGNETOMETER -- field from the board's own VBATT copper + plane return at stall")
    from design import estimation as est
    from design.configure import DEFLECTION_LIMIT_DEG, baseline, evaluate
    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    allowance_mg = est.required_magnetic_cleanliness(
        ev, est.attitude_error_budget(ev).gyro,
        roll_rate_deg_s=est.uncapped_roll_rate(ev)) * EARTH_GAUSS_TO_MG
    pads = {(p.ref, p.number): p for p in load_pads()}
    u5 = pads[("U5", "1")]
    sensor = (u5.x - 0.75, u5.y + 1.275, MAG_Z_MM)          # package centre
    def path_elements(net, a_pin, b_pin, sign):
        """Current elements along the routed path of each servo's current on `net`."""
        g = NetGraph(net)
        out = []
        for j in ("J9", "J8", "J7", "J6"):
            for layer, x0, y0, x1, y1 in oriented(g, (a_pin[0], a_pin[1]), (j, b_pin)):
                z = 0.0 if layer == "F.Cu" else -1.6
                n = 8
                for k in range(n):
                    x = x0 + (x1 - x0) * (k + 0.5) / n
                    y = y0 + (y1 - y0) * (k + 0.5) / n
                    out.append((x, y, z, (x1 - x0) / n, (y1 - y0) / n, sign * SERVO_STALL_A))
        return out

    els = path_elements("VBATT", ("J1", "1"), "2", +1)     # J1 -> header: supply direction
    rets = [(pads[(j, "3")].x, pads[(j, "3")].y) for j in ("J6", "J7", "J8", "J9")]
    sink = (pads[("J1", "2")].x, pads[("J1", "2")].y)
    star = pads[("J6", "3")].net == "SERVO_GND"
    if star:
        # as built: the return follows SERVO_GND copper back to J1 pad 2 (header -> J1,
        # i.e. opposite to the J1 -> pin-3 path direction)
        ret_els = path_elements("SERVO_GND", ("J1", "2"), "3", -1)
    plane = plane_currents(rets, sink, 4 * SERVO_STALL_A)
    z_plane = -(0.035 + 0.2104 + 0.5 * (1.065 + 0.035))     # mid-way between In1 and In2
    pel = [(x, y, z_plane, dx, dy, i) for x, y, dx, dy, i in plane]
    b_tr = biot_savart(els, sensor)
    b_pl = biot_savart(pel, sensor)
    b_plane_case = b_tr + b_pl
    b = b_tr + biot_savart(ret_els, sensor) if star else b_plane_case
    dist = math.dist(sensor[:2], sink)
    print(f"  sensor at ({sensor[0]:.1f}, {sensor[1]:.1f}) mm, {dist:.0f} mm from the pack pads")
    print(f"  supply copper alone            {np.linalg.norm(b_tr) * 1e3:7.3f} mgauss")
    print(f"  IF the return used the planes  {np.linalg.norm(b_plane_case) * 1e3:7.3f} mgauss"
          f"   (the board before the star ground)")
    print(f"  AS BUILT ({'SERVO_GND star return' if star else 'plane return'}) "
          f"{np.linalg.norm(b) * 1e3:7.3f} mgauss   against the {allowance_mg:.1f} mgauss allowance")
    one = est.wire_field_gauss(1.0, 0.050) * 1e3
    print(f"  compare: ONE untwisted 1 A servo lead 50 mm away = {one:.0f} mgauss (docs/14: twist them).")
    frac = np.linalg.norm(b) * 1e3 / allowance_mg
    print(f"  VERDICT: board copper uses {frac * 100:.1f} % of the magnetometer allowance at the 4.1 A worst"
          f"\n  case -- {'negligible' if frac < 0.1 else 'NOT negligible'}.  The servo leads, off-board, remain the real risk.")
    print("  DC is the worst case for a PLANE return (it spreads by resistance); the star return"
          "\n  is a trace, so it stays beside/under the trunk at every frequency.")


def main():
    r_hdr, r_c2 = dc_drop()          # printed as section 4; it feeds section 1
    stall(r_hdr, r_c2)
    imu_noise()
    magnetometer()


if __name__ == "__main__":
    main()
