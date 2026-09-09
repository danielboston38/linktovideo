#!/usr/bin/env python3
"""Distributed electrothermal model of a PCB trace, solved in ngspice.

The trace is discretised along its length into slices. Each slice carries:

  electrical  - a behavioural resistor R(T) = rho*dx/(w*t) * (1 + alpha*(T-20))
  thermal     - copper node --[spreading]--> near-FR4 node --[bulk]--> ambient
  lateral     - copper-to-copper thermal conduction to its neighbours

The lateral term is what makes a short neck flanked by wide copper survivable,
so it is essential: a lumped single-node model cannot distinguish the pre-fix
trace (one long uniform narrow run) from the post-fix trace (short necks beside
wide copper), and would wrongly condemn both.

Thermal node voltages are temperature RISE above ambient, in kelvin.

Vertical thermal resistance is calibrated so that a long uniform trace
reproduces IPC-2221 external-layer ampacity. That calibration deliberately
takes NO credit for an adjacent copper plane, so results are pessimistic for a
2-layer board with a ground pour. See run_all.py's sensitivity sweep.
"""
import math

RHO20   = 1.72e-8       # ohm.m      copper resistivity at 20 C
ALPHA   = 0.00393       # 1/K        copper temperature coefficient
T_CU    = 35e-6         # m          1 oz finished copper
K_CU    = 400.0         # W/m/K      copper thermal conductivity
CV_CU   = 8960 * 385    # J/m3/K     copper volumetric heat capacity
K_FR4   = 0.30          # W/m/K      FR4 thermal conductivity
CV_FR4  = 1850 * 1200   # J/m3/K     FR4 volumetric heat capacity
D_SUB   = 1.6e-3        # m          substrate thickness
IPC_K   = 0.048         # IPC-2221 external-layer constant


def ipc_current(w_mm, dT):
    """IPC-2221 external-layer allowable current (A) for width w at rise dT."""
    a = (w_mm / 0.0254) * (0.035 / 0.0254)          # cross-section in sq mils
    return IPC_K * dT ** 0.44 * a ** 0.725


def ipc_rise(w_mm, current):
    """Invert IPC-2221: temperature rise (K) for a given current."""
    a = (w_mm / 0.0254) * (0.035 / 0.0254)
    return (current / (IPC_K * a ** 0.725)) ** (1 / 0.44)


def rth_per_m(w_mm, scale=1.0):
    """Total steady vertical thermal resistance for 1 m of trace (K/W).

    Calibrated at dT=20 K against IPC-2221. `scale` < 1 credits an adjacent
    plane as a heat spreader (used by the sensitivity sweep)."""
    dT = 20.0
    a = (w_mm / 0.0254) * (0.035 / 0.0254)
    k = dT ** 0.12 / (IPC_K ** 2 * a ** 1.45 * (1 + ALPHA * dT))   # ohm.K/W
    r20_per_m = RHO20 / (w_mm * 1e-3 * T_CU)
    return k / r20_per_m * scale


def spread_per_m(w_mm):
    """Constriction resistance of a strip on a slab, per metre (K.m/W)."""
    return math.log(4 * D_SUB / (w_mm * 1e-3)) / (math.pi * K_FR4)


def slice_chain(chain, dx=0.25e-3):
    """Expand [(width_mm, length_mm), ...] into uniform dx slices."""
    out = []
    for w, ln in chain:
        n = max(1, int(round(ln * 1e-3 / dx)))
        out.extend([(w, ln * 1e-3 / n)] * n)
    return out


def build_deck(chain, tap_mm=None, dx=0.25e-3, rth_scale=1.0):
    """Return (spice_lines, n_slices, tap_index).

    tap_mm: distance along the chain where an external node attaches (used to
    model the USB-C A9 pad partway along the route). None = no tap.
    """
    L = slice_chain(chain, dx)
    tap, acc = len(L), 0.0
    if tap_mm is not None:
        for i, (w, dl) in enumerate(L):
            acc += dl
            if acc >= tap_mm * 1e-3 - 1e-9:
                tap = i + 1
                break
    d = [".option temp=25", f".param alpha={ALPHA}"]
    for i, (w, dl) in enumerate(L):
        r20   = RHO20 * dl / (w * 1e-3 * T_CU)
        ccu   = w * 1e-3 * T_CU * dl * CV_CU
        rsp   = spread_per_m(w) / dl
        rtot  = rth_per_m(w, rth_scale) / dl
        rbulk = max(rtot - rsp, 0.05 * rtot)
        cfr4  = ((w * 1e-3 + 0.8e-3) * 0.4e-3
                 + (w * 1e-3 + 4e-3) * D_SUB) * dl * CV_FR4
        d += [
            f"R{i} n{i} n{i}x R='{r20:.6e}*(1+alpha*V(tc{i}))'",
            f"Vm{i} n{i}x n{i+1} DC 0",
            f"B{i} 0 tc{i} I='(I(Vm{i})*I(Vm{i}))*{r20:.6e}*(1+alpha*V(tc{i}))'",
            f"Ccu{i} tc{i} 0 {ccu:.6e}",
            f"Rsp{i} tc{i} tf{i} {rsp:.6e}",
            f"Cf{i} tf{i} 0 {cfr4:.6e}",
            f"Rbk{i} tf{i} 0 {rbulk:.6e}",
        ]
    for i in range(len(L) - 1):
        w1, d1 = L[i]
        w2, d2 = L[i + 1]
        r = (d1 / 2) / (K_CU * w1 * 1e-3 * T_CU) + (d2 / 2) / (K_CU * w2 * 1e-3 * T_CU)
        d.append(f"Rlat{i} tc{i} tc{i+1} {r:.6e}")
    return d, len(L), tap


def onderdonk_current(w_mm, seconds, t_melt=1083.0, t_amb=25.0):
    """Adiabatic fusing current (A) - independent cross-check of the SPICE model."""
    a_cmil = (w_mm / 0.0254) * (0.035 / 0.0254) / 0.7854
    return a_cmil * math.sqrt(
        math.log10((t_melt - t_amb) / (234 + t_amb) + 1) / (33 * seconds))
