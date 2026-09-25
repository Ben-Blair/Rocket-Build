"""Minimal driver for the ngspice that ships inside KiCad.

KiCad bundles ngspice as a shared library (libngspice) for its own simulator.  This talks to
that library directly through its C API (ngSpice_Init / ngSpice_Circ / ngSpice_Command /
ngGet_Vec_Info), so there is nothing to install: no Homebrew ngspice, no PySpice.

    from design.ngspice import run
    vecs = run(netlist_text, ".tran 1u 10m")    # dict: name -> list of floats

Vectors come back by lower-case name ("time", "v(vin)", "frequency", ...).  AC results are
returned as magnitudes.
"""

from __future__ import annotations

import ctypes
import math
import os

LIB = "/Applications/KiCad/KiCad.app/Contents/Frameworks/libngspice.0.dylib"

_OUT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)


class _VecInfo(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("type", ctypes.c_int), ("flags", ctypes.c_short),
                ("realdata", ctypes.POINTER(ctypes.c_double)),
                ("compdata", ctypes.POINTER(ctypes.c_double)), ("length", ctypes.c_int)]


_lib = None
_errors: list[str] = []


def _printf(s, _id, _u):
    t = s.decode(errors="replace")
    if "error" in t.lower():
        _errors.append(t)
    return 0


_cb = _OUT(_printf)


def _init():
    global _lib
    if _lib is None:
        if not os.path.exists(LIB):
            raise RuntimeError("KiCad's libngspice not found at " + LIB)
        _lib = ctypes.CDLL(LIB)
        _lib.ngSpice_Init(_cb, None, None, None, None, None, None)
        _lib.ngGet_Vec_Info.restype = ctypes.POINTER(_VecInfo)
        _lib.ngSpice_CurPlot.restype = ctypes.c_char_p
        _lib.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)
    return _lib


def run(netlist: str, analysis: str) -> dict[str, list[float]]:
    lib = _init()
    _errors.clear()
    lines = ["* generated"] + [l for l in netlist.strip().splitlines()] + [analysis, ".end"]
    arr = (ctypes.c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None)
    lib.ngSpice_Command(b"destroy all")
    lib.ngSpice_Circ(arr)
    lib.ngSpice_Command(b"run")
    if _errors:
        raise RuntimeError("ngspice: " + " | ".join(_errors[:5]))
    plot = lib.ngSpice_CurPlot()
    names = lib.ngSpice_AllVecs(plot)
    out: dict[str, list[float]] = {}
    i = 0
    while names[i]:
        name = names[i].decode()
        v = lib.ngGet_Vec_Info(name.encode()).contents
        if v.realdata:
            out[name.lower()] = [v.realdata[k] for k in range(v.length)]
        elif v.compdata:
            out[name.lower()] = [math.hypot(v.compdata[2 * k], v.compdata[2 * k + 1])
                                 for k in range(v.length)]
        i += 1
    # ngspice names node voltages bare ("vin"); accept "v(vin)" too
    for k in list(out):
        if "(" not in k and k not in ("time", "frequency"):
            out.setdefault("v(%s)" % k, out[k])
    return out
